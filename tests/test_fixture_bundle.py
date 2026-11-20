import hashlib
from io import BytesIO
from pathlib import Path
import zipfile

import pytest

from scripts.fixture_bundle import FILES
from scripts.package_fixtures import package
from scripts.prepare_vercel_data import install_archive, prepare


def fake_fixtures(source):
    for name in FILES:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'test-only fixture')


def test_minimal_bundle_is_reproducible_and_can_be_restored(tmp_path):
    source, output, restored = tmp_path/'source', tmp_path/'fixture.zip', tmp_path/'restored'
    fake_fixtures(source)
    (source/'cdl_2025_fresno_06019.tif').write_bytes(b'excluded large county raster')
    checksum = package(source, output)
    assert package(source, tmp_path/'second.zip') == checksum
    install_archive(output.read_bytes(), restored, checksum)
    assert prepare(restored, environ={}) == 11
    assert not (restored/'cdl_2025_fresno_06019.tif').exists()


def test_checksum_and_zip_traversal_are_rejected(tmp_path):
    content = BytesIO()
    with zipfile.ZipFile(content, 'w') as archive:
        archive.writestr('../outside.txt', 'bad')
    raw = content.getvalue()
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        install_archive(raw, tmp_path/'restored', '0'*64)
    with pytest.raises(ValueError, match='allowlisted'):
        install_archive(raw, tmp_path/'restored', hashlib.sha256(raw).hexdigest())
    assert not (tmp_path/'outside.txt').exists()


def test_missing_deployment_data_fails_with_setup_instructions(tmp_path):
    with pytest.raises(ValueError, match='AGRIFORGE_DATA_URL'):
        prepare(tmp_path/'missing', environ={})


def test_fixture_download_requires_https(tmp_path):
    with pytest.raises(ValueError, match='HTTPS'):
        prepare(tmp_path/'missing', environ={'AGRIFORGE_DATA_URL':'http://example.invalid/fixture.zip'})
