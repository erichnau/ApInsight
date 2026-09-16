
import json
import os

from data.data_structure import (
    cleanup_json,
    find_matching_npy,
    find_matching_fld,
    read_project_info_from_json,
)


def test_cleanup_json_paths_and_duplicates():
    data = {
        "fld_file": r"C:\data\survey.fld",
        "DTM_file": [
            r"C:\data\terrain.tif",
            r"C:\data\terrain.tif",
            None,
        ],
        "npy_file": None,
    }

    result = cleanup_json(data)

    assert result["fld_file"] == "C:/data/survey.fld"
    assert result["DTM_file"] == ["C:/data/terrain.tif"]
    assert result["npy_file"] is None


def test_find_matching_npy(tmp_path):
    fld_file = tmp_path / "survey.fld"
    npy_file = tmp_path / "survey.npy"

    fld_file.touch()
    npy_file.touch()

    result = find_matching_npy(str(fld_file))

    assert result == str(npy_file)


def test_find_matching_npy_returns_none_when_missing(tmp_path):
    fld_file = tmp_path / "survey.fld"
    fld_file.touch()

    result = find_matching_npy(str(fld_file))

    assert result is None


def test_find_matching_fld(tmp_path):
    # ApRadar-style project filename
    apprj_file = tmp_path / "survey_processing_001.ap_prj"
    fld_file = tmp_path / "survey.fld"

    apprj_file.touch()
    fld_file.touch()

    result = find_matching_fld(str(apprj_file))

    assert result == str(fld_file)


def test_read_project_info_from_json(tmp_path):
    json_file = tmp_path / "project.json"

    expected = {
        "projects": {
            "survey": {
                "fld_file": "survey.fld"
            }
        },
        "sections": {}
    }

    with open(json_file, "w") as f:
        json.dump(expected, f)

    result = read_project_info_from_json(str(json_file))

    assert result == expected