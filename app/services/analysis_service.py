"""
Analysis Service Module
=======================
Provides the core orchestration layer connecting data ingestion, mathematical
signal processing, DBSCAN batch clustering, and persistence.
"""

import functools
import re
import uuid
from typing import Any, Callable, ParamSpec, TypeVar

from loguru import logger

from app.core.analyzer import MeltCurveAnalyzer
from app.core.classifier import ClusterClassifier
from app.db.models import MeltCurve, Sample
from app.exceptions import (
    ControlValidationFailedError,
    DataParsingError,
    TemplateNotFoundError,
)

P = ParamSpec("P")
R = TypeVar("R")


def log_and_profile(func: Callable[P, R]) -> Callable[P, R]:
    """
    Custom decorator to provide structured logging and execution profiling
    for service methods without cluttering business logic.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        logger.info(f"Starting execution of '{func.__name__}'")
        try:
            result = func(*args, **kwargs)
            logger.info(f"Successfully completed '{func.__name__}'")
            return result
        except Exception as e:
            logger.error(f"Execution failed in '{func.__name__}': {e}")
            raise

    return wrapper


class AnalysisService:
    """
    Orchestration layer connecting Data Ingestion, Core Math, Unsupervised ML Classification,
    and Data Access Layers.
    """

    def __init__(
        self,
        parser: Any,
        analyzer: Any,
        classifier: Any,
        run_repo: Any,
        result_repo: Any,
        template_repo: Any,
    ) -> None:
        """
        Initializes the AnalysisService with required dependencies.
        """
        self.parser = parser
        self.analyzer = analyzer
        self.classifier = classifier
        self.run_repo = run_repo
        self.result_repo = result_repo
        self.template_repo = template_repo

    @staticmethod
    def _extract_channel_targets(
        multiplex_mapping: dict[str, Any], channel: str | None
    ) -> tuple[list[str], list[float]]:
        """
        Extracts target names and expected melting temperatures (Tm) for a given channel.
        Supports both nested ('Mix_1') and flat channel mappings as well as dict/list formats.
        """
        if not channel or not isinstance(multiplex_mapping, dict):
            return [], []

        channel_source = multiplex_mapping.get("Mix_1", multiplex_mapping)
        if not isinstance(channel_source, dict):
            return [], []

        # Case-insensitive channel lookup fallback
        mix_data = channel_source.get(channel)
        if mix_data is None:
            for key, val in channel_source.items():
                if str(key).upper() == str(channel).upper():
                    mix_data = val
                    break

        if isinstance(mix_data, dict):
            if "targets" in mix_data or "expected_tms" in mix_data:
                target_names = [str(t) for t in mix_data.get("targets", [])]
                expected_tms = [float(tm) for tm in mix_data.get("expected_tms", [])]
                return target_names, expected_tms
            # Support direct {target_name: expected_tm} dictionary mapping
            try:
                target_names = [str(k) for k in mix_data.keys()]
                expected_tms = [float(v) for v in mix_data.values()]
                return target_names, expected_tms
            except ValueError, TypeError:
                return [], []

        return [], []

    @staticmethod
    def _is_control_well(well_pos: str) -> tuple[bool, bool]:
        """
        Determines whether a well position string designates a Positive Control (PC)
        or Negative Control (NTC) using token boundary matching to avoid substring collisions
        (e.g., preventing 'pcr' from matching 'pc').
        """
        normalized = well_pos.lower()
        tokens = set(re.split(r"[^a-z0-9]+", normalized))
        is_pc = bool(tokens & {"pc", "pos", "positive"}) or normalized.startswith("pc_")
        is_ntc = bool(tokens & {"ntc", "neg", "negative"}) or normalized.startswith(
            "ntc_"
        )
        return is_pc, is_ntc

    @log_and_profile
    def process_run(
        self,
        file_content: str | bytes,
        filename: str,
        template_identifier: str,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Processes a raw PCR cycler file through the mathematical pipeline, executes
        plate-wide DBSCAN clustering for thermal drift compensation, and persists results.

        :param file_content: Raw XML/CSV content from the cycler.
        :param filename: Original uploaded filename.
        :param template_identifier: Identifier to locate the specific assay template.
        :param user_id: UUID of the operator performing the run.
        :return: A JSON-ready summary dictionary.
        """
        # 1. Template Retrieval & Active Status Validation
        template = self.template_repo.get_by_identifier(template_identifier)
        if not template or getattr(template, "is_active", True) is False:
            raise TemplateNotFoundError(
                f"Assay template not found or inactive: {template_identifier}"
            )

        multiplex_mapping = getattr(template, "multiplex_mapping", {}) or {}

        # Optional per-template analyzer parameter override
        if (
            isinstance(self.analyzer, MeltCurveAnalyzer)
            and isinstance(multiplex_mapping, dict)
            and isinstance(multiplex_mapping.get("analyzer_config"), dict)
        ):
            active_analyzer: Any = MeltCurveAnalyzer.from_assay_config(
                multiplex_mapping["analyzer_config"]
            )
        else:
            active_analyzer = self.analyzer

        # 2. Data Parsing (supports XML and CSV with proper domain error translation)
        try:
            content_str = (
                file_content.decode("utf-8")
                if isinstance(file_content, bytes)
                else file_content
            )
            is_csv = filename.lower().endswith(
                ".csv"
            ) and content_str.lstrip().startswith("[Header]")
            if is_csv and hasattr(self.parser, "parse_csv_mvp"):
                parsed_data = self.parser.parse_csv_mvp(content_str)
            else:
                parsed_data = self.parser.parse_roche_xml_mvp(file_content)
        except ValueError as exc:
            raise DataParsingError(f"Failed to parse cycler data: {exc}") from exc

        if not parsed_data:
            raise DataParsingError("Parsed data is empty or invalid.")

        # Extract run metadata with fallback to filename
        first_entry = parsed_data[0]
        raw_run_id = first_entry.get("run_identifier") or filename
        unique_run_identifier = f"{raw_run_id}_{uuid.uuid4().hex[:6]}"
        device_id = first_entry.get("device_id", "UNKNOWN")
        raw_operator = first_entry.get("raw_operator", "UNKNOWN")

        # 3. PcrRun Record Creation
        run_record = self.run_repo.create(
            run_identifier=unique_run_identifier,
            device_id=device_id,
            raw_operator=raw_operator,
            imported_by_id=user_id,
        )

        # Pre-extract NTC reference fluorescence per channel for blanking
        ntc_curves_by_channel: dict[str, list[float]] = {}
        for well_data in parsed_data:
            w_pos = well_data.get("well_position", "")
            _, w_is_ntc = self._is_control_well(w_pos)
            chan = well_data.get("target_channel")
            rfu = well_data.get("raw_fluorescence", [])
            if w_is_ntc and chan and rfu:
                ntc_curves_by_channel[chan] = rfu

        persisted_results: list[dict[str, Any]] = []
        samples_by_well: dict[str, Sample] = {}
        evaluated_wells: list[dict[str, Any]] = []
        channel_peaks_pool: dict[str, list[float]] = {}

        # 4a. Pass 1: Signal Processing & Peak Extraction across all wells
        for well_data in parsed_data:
            well_pos = well_data.get("well_position", "").lower()

            sample = samples_by_well.get(well_pos)
            if sample is None:
                sample = Sample(pcr_run_id=run_record.id, well_position=well_pos)
                self.run_repo.session.add(sample)
                self.run_repo.session.flush()
                samples_by_well[well_pos] = sample

            channel = well_data.get("target_channel")
            temperatures = well_data.get("temperatures", [])
            raw_fluorescence = well_data.get("raw_fluorescence", [])

            curve = MeltCurve(
                sample_id=sample.id,
                target_channel=channel,
                temperatures=temperatures,
                raw_fluorescence=raw_fluorescence,
            )
            self.run_repo.session.add(curve)
            self.run_repo.session.flush()

            is_pc, is_ntc = self._is_control_well(well_pos)
            channel_ntc_rfu = ntc_curves_by_channel.get(channel) if channel else None

            if hasattr(active_analyzer, "analyze"):
                analysis_result = active_analyzer.analyze(
                    temperatures=temperatures,
                    patient_rfu=raw_fluorescence,
                    ntc_rfu=channel_ntc_rfu,
                )
                peaks = analysis_result.get("tm_peaks", [])
                escalated = analysis_result.get("requires_senior_validation", False)
            else:
                peaks = active_analyzer.analyze_curve(temperatures, raw_fluorescence)
                escalated = False

            if channel and not is_ntc and peaks:
                channel_peaks_pool.setdefault(channel, []).extend(peaks)

            evaluated_wells.append(
                {
                    "well_pos": well_pos,
                    "sample": sample,
                    "channel": channel,
                    "peaks": peaks,
                    "escalated": escalated,
                    "is_pc": is_pc,
                    "is_ntc": is_ntc,
                }
            )

        # 4b. Pass 2: Plate-wide DBSCAN Drift Estimation per Channel
        channel_drift_stats: dict[str, dict[str, Any]] = {}
        if isinstance(self.classifier, ClusterClassifier):
            for chan, pooled_peaks in channel_peaks_pool.items():
                _, exp_tms = self._extract_channel_targets(multiplex_mapping, chan)
                if exp_tms:
                    channel_drift_stats[chan] = self.classifier.estimate_run_drift(
                        channel_peaks=pooled_peaks,
                        expected_tms=exp_tms,
                    )

        # 4c. Pass 3: Target Classification, QC Gates & Persistence
        for item in evaluated_wells:
            well_pos = item["well_pos"]
            sample = item["sample"]
            channel = item["channel"]
            peaks = item["peaks"]
            escalated = item["escalated"]
            is_pc = item["is_pc"]
            is_ntc = item["is_ntc"]

            target_names, expected_tms = self._extract_channel_targets(
                multiplex_mapping, channel
            )

            classified_targets: dict[str, bool] = {}
            clustering_details: dict[str, dict[str, Any]] = {}

            if target_names and expected_tms:
                drift_info = channel_drift_stats.get(channel, {})
                thermal_shift = float(drift_info.get("thermal_shift", 0.0))
                shifted_peaks = [float(p - thermal_shift) for p in peaks]

                # Always invoke classify_channel_targets for strict contract/mock compatibility
                classified_targets = self.classifier.classify_channel_targets(
                    detected_peaks=shifted_peaks,
                    target_names=target_names,
                    expected_tms=expected_tms,
                )

                if isinstance(self.classifier, ClusterClassifier):
                    clustering_details = (
                        self.classifier.classify_with_clustering_details(
                            detected_peaks=peaks,
                            target_names=target_names,
                            expected_tms=expected_tms,
                            tolerance=float(drift_info.get("adaptive_tolerance", 0.5)),
                            thermal_shift=thermal_shift,
                            outlier_peaks=drift_info.get("outlier_peaks", []),
                        )
                    )

            # 5. Quality Control (QC) Gates
            if is_pc:
                if not any(classified_targets.values()):
                    raise ControlValidationFailedError(
                        f"Positive Control failure in well {well_pos}: No targets detected."
                    )

            if is_ntc:
                if len(peaks) > 0 or escalated:
                    raise ControlValidationFailedError(
                        f"Negative Control contamination in well {well_pos}."
                    )

            # 6. Persistence
            for target_name, is_positive in classified_targets.items():
                detail = clustering_details.get(target_name, {})
                needs_escalation = escalated or bool(
                    detail.get("requires_senior_validation", False)
                )
                default_label = (
                    "Escalated"
                    if needs_escalation
                    else ("Wildtype" if is_positive else "Negative")
                )
                cluster_label = str(detail.get("cluster_label", default_label))

                result_record = self.result_repo.create(
                    sample_id=sample.id,
                    target_name=target_name,
                    algo_is_positive=is_positive,
                    algo_tm_peaks=peaks,
                    cluster_label=cluster_label,
                )
                persisted_results.append(
                    {
                        "id": str(result_record.id),
                        "target": target_name,
                        "positive": is_positive,
                        "cluster_label": cluster_label,
                        "requires_senior_validation": needs_escalation,
                    }
                )

        # Return Summary
        return {
            "run_id": str(run_record.id),
            "run_identifier": unique_run_identifier,
            "results": persisted_results,
        }
