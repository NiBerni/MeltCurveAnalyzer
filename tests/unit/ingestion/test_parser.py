import io
from typing import Any, cast

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


@pytest.fixture
def valid_roche_xml_snippet() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<Experiment>
    <prop name="name">310726_Derma</prop>
    <Acquisitions>
        <Sample Number="1">
            <Acq Number="44">
                <Chan Number="0">
                    <prop name="Fluor">3.908</prop>
                    <prop name="Temp">54.98</prop>
                </Chan>
            </Acq>
            <Acq Number="45">
                <Chan Number="0">
                    <prop name="Fluor">3.903</prop>
                    <prop name="Temp">54.95</prop>
                </Chan>
            </Acq>
            <Acq Number="46">
                <Chan Number="0">
                    <prop name="Fluor">3.474</prop>
                    <prop name="Temp">44.95</prop>
                </Chan>
            </Acq>
            <Acq Number="47">
                <Chan Number="0">
                    <prop name="Fluor">3.492</prop>
                    <prop name="Temp">45.8</prop>
                </Chan>
            </Acq>
            <Acq Number="48">
                <Chan Number="0">
                    <prop name="Fluor">3.517</prop>
                    <prop name="Temp">46.86</prop>
                </Chan>
            </Acq>
        </Sample>
    </Acquisitions>
</Experiment>
"""


def test_parse_valid_block_csv_success(valid_csv_content: str) -> None:
    stream: io.StringIO = io.StringIO(valid_csv_content)
    parser: CyclerDataParser = CyclerDataParser(stream)

    assert isinstance(parser.metadata, dict)
    assert parser.metadata.get("Run_ID") == "RUN_20260723_001"
    assert parser.metadata.get("raw_operator") == "Operator"

    assert len(parser.data) == 3

    first_row = cast(dict[str, Any], parser.data.iloc[0].to_dict())
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

    first_row = cast(dict[str, Any], parser.data.iloc[0].to_dict())
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


def test_parse_roche_xml_success(valid_roche_xml_snippet: str) -> None:
    parser = CyclerDataParser()
    result: list[dict[str, Any]] = parser.parse_roche_xml_mvp(valid_roche_xml_snippet)

    assert isinstance(result, list)
    assert len(result) == 1

    sample_data = result[0]
    assert sample_data["run_identifier"] == "310726_Derma"
    assert sample_data["well_position"] == "Sample_1"
    assert sample_data["target_channel"] == "FAM"

    # Asserting that ONLY Acq >= 46 are included in the results
    assert sample_data["temperatures"] == [44.95, 45.8, 46.86]
    assert sample_data["raw_fluorescence"] == [3.474, 3.492, 3.517]


def test_parse_roche_xml_missing_acquisitions() -> None:
    invalid_xml = """<?xml version="1.0" encoding="utf-8"?>
<Experiment>
    <prop name="name">310726_Derma</prop>
</Experiment>
"""
    parser = CyclerDataParser()

    with pytest.raises(ValueError):
        parser.parse_roche_xml_mvp(invalid_xml)


def test_parse_roche_xml_no_melt_data() -> None:
    no_melt_xml = """<?xml version="1.0" encoding="utf-8"?>
<Experiment>
    <prop name="name">310726_Derma</prop>
    <Acquisitions>
        <Sample Number="1">
            <Acq Number="44">
                <Chan Number="0">
                    <prop name="Fluor">3.908</prop>
                    <prop name="Temp">54.98</prop>
                </Chan>
            </Acq>
            <Acq Number="45">
                <Chan Number="0">
                    <prop name="Fluor">3.903</prop>
                    <prop name="Temp">54.95</prop>
                </Chan>
            </Acq>
        </Sample>
    </Acquisitions>
</Experiment>
"""
    parser = CyclerDataParser()
    result: list[dict[str, Any]] = parser.parse_roche_xml_mvp(no_melt_xml)

    assert isinstance(result, list)
    assert len(result) == 0
