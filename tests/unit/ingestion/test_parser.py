import io

import pandas as pd
import pytest

from app.ingestion.parser import CyclerDataParser


@pytest.fixture
def valid_csv_content() -> str:
    return """[Header]
	Run_ID,RUN_20260723_001
	Date,2026-07-23 11:30:00
	Device_ID,LightCycler_480_02
	Operator,Operator
	
	[MeltCurveData]
	Well,Channel,Sample_ID,Target,Temperature,Fluorescence,Derivative
	A01,FAM,Sample_001,Gene_A,60.0,1200.5,5.2
	A01,FAM,Sample_001,Gene_A,60.5,1195.1,8.4
	A02,HEX,Sample_002,,60.0,980.2,3.1
	"""


def test_parse_valid_block_csv_success(valid_csv_content: str) -> None:
    stream: io.StringIO = io.StringIO(valid_csv_content)
    parser: CyclerDataParser = CyclerDataParser(stream)

    assert isinstance(parser.metadata, dict)
    assert parser.metadata.get("Run_ID") == "RUN_20260723_001"
    assert parser.metadata.get("raw_operator") == "Operator"

    assert len(parser.data) == 3

    first_row: dict[str, str | float | int | None] = (
        parser.data[0]
        if isinstance(parser.data, list)
        else parser.data.iloc[0].to_dict()
    )
    assert first_row.get("Well") == "A01"
    assert first_row.get("Channel") == "FAM"
    assert float(first_row.get("Temperature") or 0.0) == 60.0


@pytest.mark.parametrize(
    "raw_operator",
    ["Operator", "Default_user", "", "System", "MOD", "admin"],
)
def test_parse_generic_raw_operator_handled_gracefully(raw_operator: str) -> None:
    csv_data: str = f"""[Header]
Run_ID,RUN_20260723_002
Date,2026-07-23 12:00:00
Device_ID,LightCycler_480_02
Operator,{raw_operator}

[MeltCurveData]
Well,Channel,Sample_ID,Target,Temperature,Fluorescence,Derivative
A01,FAM,Sample_001,Gene_A,60.0,1200.5,5.2
"""
    stream: io.StringIO = io.StringIO(csv_data)
    parser: CyclerDataParser = CyclerDataParser(stream)

    assert parser.metadata.get("raw_operator") == raw_operator


def test_parse_missing_optional_target_column_success() -> None:
    csv_data: str = """[Header]
    Run_ID,RUND_20260723_003
    Date,20226-07-23 12:30:00
    Device_ID,LC_480
    Operator,JaneDoe
    
    [MeltCurveData]
    Well,Channel,Sample_ID,Temperature,Fluorescence,Derivative
    A01,FAM,Sample_001,60.0,1200.5,5.2
    A02,HEX,Sample_002,60.0,980.2,3.1
    """
    stream: io.StringIO = io.StringIO(csv_data)
    parser: CyclerDataParser = CyclerDataParser(stream)

    assert len(parser.data) == 2

    first_row: dict[str, str | float | int | None] = (
        parser.data[0]
        if isinstance(parser.data, list)
        else parser.data.iloc[0].to_dict()
    )
    assert (
        "Target" not in first_row
        or pd.isna(first_row.get("Target"))
        or first_row.get("Target") is None
    )


def test_parse_missing_header_section_raises_error() -> None:
    csv_data: str = """[MeltCurveData
    Well,Channel,Sample_ID,Temperature,Fluorescence,Derivative
    A01,Sample_001,Gene_A,60.0,1200.5,5.2
	"""
    stream: io.StringIO = io.StringIO(csv_data)
    with pytest.raises(ValueError):
        CyclerDataParser(stream)


@pytest.mark.parametrize(
    "missing_column_data",
    [
        """[Header]
				Run_ID,RUN_01
				Operator,User
				
				[MeltCurveData]
				Well,Sample_ID,Target,Temperature,Fluorescence,Derivative
				A01,Sample_01,Gene_A,60.0,1200.5,5.2""",
        """[Header]
				Run_ID,RUN_01
				Operator,User
				
				[MeltCurveData]
				Well,Channel,Sample_ID,Target,Fluorescence,Derivative
				A01,FAM,Sample_01,Gene_A,1200.5,5.2""",
        """[Header]
				Run_ID,RUN_01
				Operator,User
				
				[MeltCurveData]
				Well,Channel,Sample_ID,Target,Temperature,Derivative
				A01,FAM,Sample_01,Gene_A,60.0,5.2""",
    ],
)
def test_parse_missing_mandatory_columns_raises_error(missing_column_data: str) -> None:
    stream: io.StringIO = io.StringIO(missing_column_data)

    with pytest.raises(ValueError):
        CyclerDataParser(stream)


def test_parse_corrupted_numeric_value_raises_error() -> None:
    csv_data: str = """[Header]
    Run_ID,RUND_20260723_005
    Date,2026-07-23 14:00:00
    Device_ID,LC_480
    Operator,JohnDoe
    
    [MeltCurveData]
    Well,Channel,Sample_ID,Target,Temperature,Fluorescence,Derivative
    A01,FAM,Sample_001,Gene_A,NOT_A_NUMBER,1200.5,5.2
    """
    stream: io.StringIO = io.StringIO(csv_data)

    with pytest.raises(ValueError):
        CyclerDataParser(stream)


def test_parse_empty_file_raises_error() -> None:
    stream: io.StringIO = io.StringIO("")

    with pytest.raises(ValueError):
        CyclerDataParser(stream)
