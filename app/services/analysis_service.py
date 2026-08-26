"""
Analysis Service Module
=======================
Provides the core orchestration layer connecting data ingestion,
mathematical signal processing, clustering, and persistence.
"""

import functools
import uuid
from typing import Any, Callable, ParamSpec, TypeVar

from loguru import logger

from app.db.models import MeltCurve, Sample

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

    @log_and_profile
    def process_run(
        self,
        file_content: str | bytes,
        filename: str,
        template_identifier: str,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Processes a raw PCR cycler file through the mathematical pipeline and persists results.

        :param file_content: Raw XML/CSV content from the cycler.
        :param filename: Original uploaded filename.
        :param template_identifier: Identifier to locate the specific assay template.
        :param user_id: UUID of the operator performing the run.
        :return: A JSON-ready summary dictionary.
        """
        # 1. Template Retrieval & Validation
        template = self.template_repo.get_by_identifier(template_identifier)
        if not template:
            raise ValueError(f"Assay template not found: {template_identifier}")

        multiplex_mapping = getattr(template, "multiplex_mapping", {})

        # 2. Data Parsing
        parsed_data = self.parser.parse_roche_xml_mvp(file_content)
        if not parsed_data:
            raise ValueError("Parsed data is empty or invalid.")

        # Extract run_identifier with fallback to filename
        run_identifier = parsed_data[0].get("run_identifier", filename)

        # 3. PcrRun Record Creation
        run_record = self.run_repo.create(
            run_identifier=f"{run_identifier}_{uuid.uuid4().hex[:6]}",
            device_id="UNKNOWN",  # Placeholder based on MVP requirements
            raw_operator="UNKNOWN",
            imported_by_id=user_id,
        )

        persisted_results: list[dict[str, Any]] = []

        # 4. Channel-Isolated Math & Classification Loop
        for well_data in parsed_data:
            well_pos = well_data.get("well_position", "").lower()
            sample = Sample(pcr_run_id=run_record.id, well_position=well_pos)
            self.run_repo.session.add(sample)
            self.run_repo.session.flush()
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

            # Run peak detection
            analysis_result = {}
            if hasattr(self.analyzer, "analyze"):
                analysis_result = self.analyzer.analyze(
                    temperatures=temperatures,
                    patient_rfu=raw_fluorescence,
                    ntc_rfu=None,
                )
                peaks = analysis_result.get("tm_peaks", [])
                escalated = analysis_result.get("requires_senior_validation", False)
            else:
                peaks = self.analyzer.analyze_curve(temperatures, raw_fluorescence)
                escalated = False

            # Extract multiplex mapping for the current channel
            mix_data = multiplex_mapping.get("Mix_1", {}).get(channel, {})
            target_names = mix_data.get("targets", [])
            expected_tms = mix_data.get("expected_tms", [])

            # Run ML classification
            classified_targets = {}
            if target_names and expected_tms:
                classified_targets = self.classifier.classify_channel_targets(
                    detected_peaks=peaks,
                    target_names=target_names,
                    expected_tms=expected_tms,
                )

            # 5. Quality Control (QC) Gates
            is_pc = "pc" in well_pos or "positive" in well_pos
            is_ntc = "ntc" in well_pos or "negative" in well_pos

            if is_pc:
                # Positive Control must detect at least one true target
                if not any(classified_targets.values()):
                    raise ValueError(
                        f"Positive Control failure in well {well_pos}: No targets detected."
                    )

            if is_ntc:
                # Negative Control must have no peaks and no escalations
                if len(peaks) > 0 or escalated:
                    raise ValueError(
                        f"Negative Control contamination in well {well_pos}."
                    )

            # 6. Persistence
            for target_name, is_positive in classified_targets.items():
                result_record = self.result_repo.create(
                    sample_id=sample.id,  # Assuming sample aligns with run for MVP tests
                    target_name=target_name,
                    algo_is_positive=is_positive,
                    algo_tm_peaks=peaks,
                    cluster_label="Unknown",
                )
                persisted_results.append(
                    {
                        "id": str(result_record.id),
                        "target": target_name,
                        "positive": is_positive,
                    }
                )

        # Return Summary
        return {
            "run_id": str(run_record.id),
            "run_identifier": run_identifier,
            "results": persisted_results,
        }
