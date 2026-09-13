import hashlib
import io
import json
import zipfile
from datetime import UTC, date, datetime, timedelta

import pytest
from test_hazard_boundaries import package

from helvetic_lens.hazard_boundaries import BoundaryError
from helvetic_lens.hazard_boundary_store import BoundaryStore, install_catalogue
from helvetic_lens.hazard_contracts import MunicipalityLocation

NOW = datetime(2026, 9, 13, 12, tzinfo=UTC)
EXPIRY = date(2026, 10, 1)
PLACE = MunicipalityLocation(kind="municipality", canton="BE", municipality_code="1")


def archive(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("synthetic.gpkg", package())
    path = tmp_path / "synthetic.zip"
    path.write_bytes(stream.getvalue())
    return path, hashlib.sha256(stream.getvalue()).hexdigest()


def install(tmp_path, **kwargs):
    path, checksum = archive(tmp_path)
    return install_catalogue(tmp_path, path, archive_sha256=checksum, version="2026-01",
        expires_on=kwargs.pop("expires_on", EXPIRY), now=NOW, **kwargs)


def test_source_scope_covers_entire_radius_not_just_its_verified_center(tmp_path):
    from test_hazard_boundaries import point_from_lv95

    install(tmp_path)
    store = BoundaryStore(tmp_path)
    point = point_from_lv95(2600500, 1200500)
    assert store.verify_location(point, now=NOW)["state"] == "verified"
    assert store.verify_source_scope(point, ("BE",), now=NOW)["state"] == "unavailable"
    small = point.model_copy(update={"radius_km": 0.1})
    proof = store.verify_source_scope(small, ("BE",), now=NOW)
    assert proof["state"] == "verified" and proof["reason"] == "whole_location_in_source_scope"
    assert store.verify_source_scope(PLACE, ("BE",), now=NOW)["state"] == "verified"
    assert store.verify_source_scope(PLACE, ("BS",), now=NOW)["state"] == "unavailable"
    assert store.verify_source_scope(small, ("BE",), now=NOW + timedelta(days=30))["state"] == "unavailable"


def test_install_renewal_and_revocation_never_use_a_stale_cached_catalogue(tmp_path):
    store = BoundaryStore(tmp_path)
    assert store.verify_location(PLACE, now=NOW)["reason"] == "boundary_catalogue_not_installed"
    first = install(tmp_path)
    proof = store.verify_location(PLACE, now=NOW)
    assert proof["state"] == "verified" and proof["municipality_code"] == "1"
    assert proof["sha256"] == first["sha256"]
    assert not proof["radius_coverage_verified"]
    assert store.verify_location(PLACE, now=datetime(2026, 10, 1, tzinfo=UTC))["state"] == "unavailable"
    renewed = install(tmp_path, expires_on=date(2026, 11, 1), expected_selection_sha256=first["selection_sha256"])
    assert renewed["selection_sha256"] != first["selection_sha256"]
    assert store.verify_location(PLACE, now=datetime(2026, 10, 1, tzinfo=UTC))["state"] == "verified"
    (store.root / "current.json").unlink()
    assert store.verify_location(PLACE, now=NOW)["state"] == "unavailable"
    assert store._catalogue is None


def test_concurrent_installer_and_wrong_selection_cannot_replace_current_edition(tmp_path):
    first = install(tmp_path)
    current = tmp_path / "hazard-boundaries/current.json"
    before = current.read_bytes()
    with pytest.raises(BoundaryError, match="selection_conflict"):
        install(tmp_path)
    assert current.read_bytes() == before
    lock = current.parent / ".install.lock"
    lock.write_text("another installer")
    with pytest.raises(FileExistsError):
        install(tmp_path, expected_selection_sha256=first["selection_sha256"])
    assert lock.read_text() == "another installer" and current.read_bytes() == before


def test_missing_corrupt_or_changed_asset_invalidates_cache(tmp_path):
    installed = install(tmp_path)
    store = BoundaryStore(tmp_path)
    assert store.verify_location(PLACE, now=NOW)["state"] == "verified"
    path = store.root / "objects" / (installed["sha256"] + ".gpkg")
    original = path.read_bytes()
    path.write_bytes(original + b"changed")
    assert store.verify_location(PLACE, now=NOW)["state"] == "unavailable"
    assert store._catalogue is None
    path.write_bytes(original)
    assert store.verify_location(PLACE, now=NOW)["state"] == "verified"
    path.unlink()
    assert store.verify_location(PLACE, now=NOW)["state"] == "unavailable"


@pytest.mark.parametrize("change", [
    {"reviewed_at": "2027-01-01T00:00:00Z"}, {"reviewed_at": "2026-01-01T00:00:00"},
    {"version": "2027-01"}, {"schema_version": True}, {"sha256": "../private"}, {"owner": "forged"},
])
def test_invalid_or_future_selection_cannot_confirm_private_location(tmp_path, change):
    install(tmp_path)
    store = BoundaryStore(tmp_path)
    current = store.root / "current.json"
    selection = json.loads(current.read_bytes())
    current.write_text(json.dumps({**selection, **change}), encoding="utf-8")
    assert store.verify_location(PLACE, now=NOW)["state"] == "unavailable"


def test_oversize_duplicate_and_invalid_json_are_unavailable(tmp_path):
    install(tmp_path)
    store = BoundaryStore(tmp_path)
    for content in ('{"version":"2026-01","version":"2025-01"}', " " * 16385, "not json"):
        (store.root / "current.json").write_text(content)
        assert store.verify_location(PLACE, now=NOW)["state"] == "unavailable"


def test_selection_replaced_during_decode_is_not_returned(monkeypatch, tmp_path):
    import helvetic_lens.hazard_boundary_store as module

    install(tmp_path)
    original = module.load_geopackage

    def replace_selection(*args, **kwargs):
        catalogue = original(*args, **kwargs)
        (tmp_path / "hazard-boundaries/current.json").write_text("{}")
        return catalogue

    monkeypatch.setattr(module, "load_geopackage", replace_selection)
    assert BoundaryStore(tmp_path).verify_location(PLACE, now=NOW)["reason"] == "boundary_selection_changed"


def test_invalid_archive_or_expiry_does_not_publish(tmp_path):
    path, checksum = archive(tmp_path)
    for digest, expiry in (("0" * 64, EXPIRY), (checksum, NOW.date() - timedelta(days=1))):
        with pytest.raises(BoundaryError):
            install_catalogue(tmp_path, path, archive_sha256=digest, version="2026-01", expires_on=expiry, now=NOW)
    assert not (tmp_path / "hazard-boundaries/current.json").exists()


def test_worker_matching_observes_catalogue_binding_and_revocation(tmp_path):
    from helvetic_lens.hazard_cap import CAPArea
    from helvetic_lens.hazard_matching import COMMUNE

    install(tmp_path)
    store = BoundaryStore(tmp_path)
    area = CAPArea("Synthetic municipality filter", (), (), ((COMMUNE, "1"),), None, None)
    result = store.match_warning((area,), PLACE, geocode_version="2026-01", now=NOW)
    assert result["state"] == "match" and result["basis"] == "administrative_filter"
    assert store.match_warning((area,), PLACE, now=NOW)["state"] == "unavailable"
    (store.root / "current.json").unlink()
    assert store.match_warning((area,), PLACE, geocode_version="2026-01", now=NOW)["state"] == "unavailable"
