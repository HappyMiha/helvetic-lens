"""Offline source-proof boundaries; synthetic failures are not live acceptance."""

import hashlib
import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest


def load_script(name):
    path = Path(__file__).resolve().parents[3] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load_script("pollen_source_probe")
decode = load_script("pollen_decode_proof")


def test_capture_request_content_type(monkeypatch):
    requests = []

    class Response:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, count):
            return b"{}"

    def open_request(request, **kwargs):
        requests.append(request)
        return Response()

    monkeypatch.setattr(probe, "urlopen", open_request)
    probe.fetch("https://rgw.cscs.ch/public.grib2")
    probe.fetch(probe.ROOT + "/search", {"collections": [probe.FORECASTS]})
    assert requests[0].get_header("Content-type") is None
    assert requests[1].get_header("Content-type") == "application/json"
    assert requests[1].get_method() == "POST"


@pytest.mark.parametrize("url", ["http://data.geo.admin.ch/a", "https://cscs.ch.example/a", "file:///a"])
def test_capture_rejects_unexpected_provider(url):
    with pytest.raises(ValueError, match="provider"):
        probe.fetch(url)


def test_retained_proof_rejects_tampering_and_traversal(tmp_path):
    body = b"public source bytes"
    (tmp_path / "proof.csv").write_bytes(body)
    manifest = {"status": "fetched_not_yet_decoded", "files": {
        "proof.csv": {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()},
    }}
    decode.verify_files(tmp_path, manifest)
    (tmp_path / "proof.csv").write_bytes(b"changed")
    with pytest.raises(ValueError, match="bytes"):
        decode.verify_files(tmp_path, manifest)
    manifest["files"] = {"../proof.csv": {}}
    with pytest.raises(ValueError, match="filename"):
        decode.verify_files(tmp_path, manifest)


def fields():
    metadata = {"uuidOfHGrid": "fixture-grid", "numberOfValues": 1, "bitmapPresent": 0,
                "numberOfMissing": 0, "level": 80, "typeOfLevel": "generalVerticalLayer",
                "dataDate": 20260911, "dataTime": 0, "validityDate": 20260911, "validityTime": 600}
    return {name: ({**metadata, "units": unit}, [value]) for name, unit, value in (
        ("AMBRsnc", "kg-1", 2), ("DEN", "kg m-3", 1.25), ("CLAT", "deg N", 47), ("CLON", "deg E", 7),
    )}


MANIFEST = {"variable": "AMBRsnc", "issue_time": "2026-09-11T00:00:00+00:00", "lead_hours": 6}


def test_density_conversion_keeps_time_and_zero_semantics():
    issue, valid = decode.validate_fields(fields(), MANIFEST)
    assert (valid - issue).total_seconds() == 21600
    assert decode.concentration("2", "1.25") == "2.50"
    assert decode.concentration("0", "1.25") == "0.00"


@pytest.mark.parametrize("key,value", [
    ("uuidOfHGrid", "other-grid"), ("numberOfValues", 2), ("bitmapPresent", 1),
    ("numberOfMissing", 1), ("units", "unknown"), ("level", 79),
    ("dataTime", 300), ("validityTime", 900),
])
def test_rejects_incompatible_density(key, value):
    data = deepcopy(fields())
    data["DEN"][0][key] = value
    with pytest.raises(ValueError):
        decode.validate_fields(data, MANIFEST)


@pytest.mark.parametrize("number,density", [("NaN", "1"), ("1", "Infinity"), ("-1", "1"), ("1", "0")])
def test_missing_or_invalid_values_do_not_become_zero(number, density):
    with pytest.raises(ValueError):
        decode.concentration(number, density)


@pytest.mark.parametrize("release,native", [
    ("v2.47.0.2", "2.47.3"), ("v2.47.0.2", "2.46.0"),
    ("development", "2.47.0"), ("v2.47.0", "2.47.0"),
])
def test_decoder_rejects_incompatible_or_unversioned_definitions(tmp_path, release, native):
    (tmp_path / "RELEASE").write_text(release, encoding="utf-8")
    with pytest.raises(ValueError, match="must match exactly"):
        decode.definition_runtime(tmp_path, native)


def test_decoder_requires_definitions_and_records_content_identity(tmp_path):
    (tmp_path / "RELEASE").write_text("v2.47.0.2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="absent"):
        decode.definition_runtime(tmp_path, "2.47.0")
    definitions = tmp_path / "definitions"
    definitions.mkdir()
    definition = definitions / "boot.def"
    definition.write_bytes(b"original definition\n")
    runtime = decode.definition_runtime(tmp_path, "2.47.0")
    assert runtime["eccodes_native"] == "2.47.0"
    assert runtime["cosmo_release"] == "v2.47.0.2"
    assert runtime["cosmo_definition_files"] == 1
    assert runtime == decode.definition_runtime(tmp_path, "2.47.0")
    definition.write_bytes(b"changed definition\n")
    assert runtime["cosmo_definitions_sha256"] != decode.definition_runtime(
        tmp_path, "2.47.0",
    )["cosmo_definitions_sha256"]
