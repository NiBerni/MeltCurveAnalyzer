from typing import Any

import pytest

from app.ingestion.parser import CyclerDataParser


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
