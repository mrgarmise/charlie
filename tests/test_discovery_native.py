import hashlib
from types import SimpleNamespace

import pytest

from learning.discovery.native import NativeInquiry, public_settings


def test_discovery_policy_is_opt_in_and_carries_exact_pins(tmp_path):
    assert public_settings({}) is None
    assert public_settings({"discovery": {"enabled": False}}) is None
    settings = dict(enabled=True, archive_dir=str(tmp_path / "archive"),
                    journal_path=str(tmp_path / "journal"), archive_version="a" * 64,
                    archive_manifest_sha256="b" * 64, model_enabled=False)
    public = public_settings(dict(discovery=settings, code_revision="c" * 40))
    assert public["prompts"] == {}
    assert public["archive_manifest_sha256"] == "b" * 64
    settings["archive_manifest_sha256"] = "missing"
    with pytest.raises(ValueError):
        public_settings(dict(discovery=settings, code_revision="c" * 40))


def test_native_refuses_unpinned_archive_without_creating_notebook(tmp_path):
    archive = tmp_path / "archive"
    archive.mkdir()
    original = b"{}"
    (archive / "manifest.json").write_bytes(original)
    journal = tmp_path / "research.sqlite"
    settings = dict(archive_dir=str(archive), journal_path=str(journal),
                    archive_version="a" * 64,
                    archive_manifest_sha256=hashlib.sha256(original + b" ").hexdigest())
    with pytest.raises(ValueError, match="manifest checksum"):
        NativeInquiry(settings, SimpleNamespace(), [], tmp_path / "operational.sqlite")
    assert not journal.exists()
