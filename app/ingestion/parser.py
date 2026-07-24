"""
Cycler Data Parsing Module.

This module belongs to the Data Ingestion Layer of the PCR Analyzer architecture.
It handles the structural validation and transformation of raw CSV files generated
by the cycler, ensuring a downstream math process receives sanitized, strict data.
"""

import io
import time
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import pandas as pd
from loguru import logger

P = ParamSpec("P")
R = TypeVar("R")


def profile_parsing(func: Callable[P, R]) -> Callable[P, R]:
    """
    Decorator to profile the execution time of stream parsing.

    Logs the elapsed time via Loguru and ensures any unhandled,
    unexpected standard exceptions are caught, logged with full
    context, and re-raised securely as domain-specific ValueErrors.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "Stream parsing completed successfully in {elapsed_ms:.2f}ms",
                elapsed_ms=elapsed_ms,
            )
            return result
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error during stream parsing")
            raise ValueError(
                f"Parsing failed due to an unexpected error: {exc}"
            ) from exc

    return wrapper


class CyclerDataParser:
    """
    Parses and validates raw CSV output from the PCR Cycler.

    This class orchestrates the extraction of metadata headers and tabular melt curve data,
    yielding a robust pandas DataFrame that the AnalysisService can pass down to the MeltCurveAnalyzer.
    """

    def __init__(self, stream: io.TextIOBase) -> None:
        """
        Initialize the parser and process the file stream immediatly.

        :param stream: File-like text stream containing the raw CSV data.
        :raises ValueError: If the file is empty, malformed, or missing columns.
        """
        self.metadata: dict[str, str] = {}
        self.data: pd.DataFrame = pd.DataFrame()

        self._parse(stream)

    @profile_parsing
    def _parse(self, stream: io.TextIOBase) -> None:
        """
        Internal method to defensively read, validate, and extract the stream.

        :param stream: The raw text stream to parse.
        :raises ValueError: For missing sections, mandatory columns, or corrupted arrays.
        """
        content = stream.read().strip()
        if not content:
            raise ValueError("The provided file stream is empty.")
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if lines[0] != "[Header]":
            raise ValueError(
                "Missing or malformed [Header] section at the start of the file."
            )
        header_dict: dict[str, str] = {}
        data_start_idx: int = -1

        for i, line in enumerate(lines[1:], start=1):
            if line == "[MeltCurveData]":
                data_start_idx = i
                break
            if "," in line:
                key, val = line.split(",", 1)
                header_dict[key.strip()] = val.strip()
        if data_start_idx == -1:
            raise ValueError(
                "Missing [MeltCurveData] section. Invalid cycler export format."
            )
        self.metadata = {
            "Run_ID": header_dict.get("Run_ID", ""),
            "raw_operator": header_dict.get("Operator", ""),
            "Date": header_dict.get("Date", ""),
            "Device_ID": header_dict.get("Device_ID", ""),
        }
        data_csv_string = "\n".join(lines[data_start_idx + 1 :])
        if not data_csv_string.strip():
            raise ValueError("No data rows found after the [MeltCurveData] header.")

        df = pd.read_csv(io.StringIO(data_csv_string))

        mandatory_columns = {
            "Well",
            "Channel",
            "Sample_ID",
            "Temperature",
            "Fluorescence",
            "Derivative",
        }
        if not mandatory_columns.issubset(df.columns):
            raise ValueError(
                f"Missing mandatory columns. Required minimum: {mandatory_columns}!"
            )
        numeric_columns = ["Temperature", "Fluorescence", "Derivative"]
        for col in numeric_columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f'Corrupted numeric value identified in column "{col}": {exc}'
                ) from exc
        self.data = df
