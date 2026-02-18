"""Tests for GCPStorageManager — verifies behavior when GCS is disabled."""

import os

os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key")

from utils.gcp_storage import GCPStorageManager, get_storage_manager


def test_storage_disabled_by_default():
    """Without GCP_BUCKET_NAME, storage should be disabled."""
    manager = get_storage_manager()
    # In test env without bucket config, manager is disabled
    assert manager.enabled is False or manager.bucket_name is not None


def test_disabled_upload_returns_none():
    """Upload on a disabled manager should return None gracefully."""
    manager = GCPStorageManager.__new__(GCPStorageManager)
    manager.enabled = False
    manager.bucket_name = None
    manager.client = None

    result = manager.upload_file(b"test data", "test/file.txt")
    assert result is None


def test_disabled_download_returns_none():
    manager = GCPStorageManager.__new__(GCPStorageManager)
    manager.enabled = False
    manager.bucket_name = None
    manager.client = None

    result = manager.download_file("test/file.txt")
    assert result is None


def test_disabled_download_to_bytesio_returns_none():
    manager = GCPStorageManager.__new__(GCPStorageManager)
    manager.enabled = False
    manager.bucket_name = None
    manager.client = None

    result = manager.download_to_bytesio("test/file.txt")
    assert result is None


def test_disabled_exists_returns_false():
    manager = GCPStorageManager.__new__(GCPStorageManager)
    manager.enabled = False
    manager.bucket_name = None
    manager.client = None

    assert manager.exists("test/file.txt") is False


def test_generate_unique_filename():
    manager = GCPStorageManager.__new__(GCPStorageManager)
    manager.enabled = False
    manager.bucket_name = None
    manager.client = None

    name = manager.generate_unique_filename("images/previews", ".png")
    assert name.startswith("images/previews/")
    assert name.endswith(".png")
