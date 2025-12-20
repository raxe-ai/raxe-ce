"""Security tests for model downloader tarball extraction.

Tests path traversal and symlink attack prevention (CVE-2007-4559).
This verifies the fix for S-002.
"""
import io
import tarfile
from pathlib import Path

import pytest

from raxe.infrastructure.ml.model_downloader import _extract_tarball, _get_safe_members


class TestTarballExtractionSecurity:
    """Security tests for _extract_tarball function."""

    def test_rejects_absolute_path_traversal(self, tmp_path: Path) -> None:
        """Tarball with absolute path should be rejected."""
        archive_path = tmp_path / "evil.tar.gz"
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with tarfile.open(archive_path, "w:gz") as tar:
            data = b"malicious content"
            info = tarfile.TarInfo(name="/etc/passwd")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        with pytest.raises(RuntimeError, match="absolute path"):
            _extract_tarball(archive_path, dest_dir)

        # Verify nothing was extracted
        assert not (tmp_path / "etc").exists()

    def test_rejects_relative_path_traversal(self, tmp_path: Path) -> None:
        """Tarball with ../../../ path should be rejected."""
        archive_path = tmp_path / "evil.tar.gz"
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with tarfile.open(archive_path, "w:gz") as tar:
            data = b"malicious content"
            info = tarfile.TarInfo(name="../../../etc/passwd")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        with pytest.raises(RuntimeError, match="path traversal"):
            _extract_tarball(archive_path, dest_dir)

    def test_rejects_dot_dot_in_middle_of_path(self, tmp_path: Path) -> None:
        """Tarball with nested ../ path should be rejected."""
        archive_path = tmp_path / "evil.tar.gz"
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with tarfile.open(archive_path, "w:gz") as tar:
            data = b"malicious content"
            info = tarfile.TarInfo(name="models/../../secrets/api_key")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        with pytest.raises(RuntimeError, match="path traversal"):
            _extract_tarball(archive_path, dest_dir)

    def test_skips_symlinks_silently(self, tmp_path: Path) -> None:
        """Symlinks in tarball should be skipped (not extracted)."""
        archive_path = tmp_path / "with_symlink.tar.gz"
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with tarfile.open(archive_path, "w:gz") as tar:
            # Add a regular file
            data = b"regular file content"
            info = tarfile.TarInfo(name="regular.txt")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

            # Add symlink pointing outside
            symlink = tarfile.TarInfo(name="evil_symlink")
            symlink.type = tarfile.SYMTYPE
            symlink.linkname = "/etc/passwd"
            tar.addfile(symlink)

        # Should not raise - symlinks are skipped
        _extract_tarball(archive_path, dest_dir)

        # Regular file should exist
        assert (dest_dir / "regular.txt").exists()
        # Symlink should NOT exist (skipped)
        assert not (dest_dir / "evil_symlink").exists()

    def test_allows_safe_extraction(self, tmp_path: Path) -> None:
        """Valid tarball should extract successfully."""
        archive_path = tmp_path / "safe.tar.gz"
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        with tarfile.open(archive_path, "w:gz") as tar:
            # Add valid nested file
            data = b"model weights here"
            info = tarfile.TarInfo(name="model/weights.bin")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

            # Add config file
            config = b'{"name": "test"}'
            info2 = tarfile.TarInfo(name="model/config.json")
            info2.size = len(config)
            tar.addfile(info2, io.BytesIO(config))

        _extract_tarball(archive_path, dest_dir)

        assert (dest_dir / "model" / "weights.bin").exists()
        assert (dest_dir / "model" / "config.json").exists()


class TestGetSafeMembers:
    """Unit tests for _get_safe_members helper function."""

    def test_filters_absolute_paths(self, tmp_path: Path) -> None:
        """Should reject absolute paths."""
        archive_path = tmp_path / "test.tar.gz"

        with tarfile.open(archive_path, "w:gz") as tar:
            info = tarfile.TarInfo(name="/etc/passwd")
            info.size = 0
            tar.addfile(info, io.BytesIO(b""))

        with tarfile.open(archive_path, "r:gz") as tar:
            with pytest.raises(RuntimeError, match="absolute path"):
                _get_safe_members(tar, tmp_path)

    def test_filters_path_traversal(self, tmp_path: Path) -> None:
        """Should reject path traversal attempts."""
        archive_path = tmp_path / "test.tar.gz"

        with tarfile.open(archive_path, "w:gz") as tar:
            info = tarfile.TarInfo(name="../escape.txt")
            info.size = 0
            tar.addfile(info, io.BytesIO(b""))

        with tarfile.open(archive_path, "r:gz") as tar:
            with pytest.raises(RuntimeError, match="path traversal"):
                _get_safe_members(tar, tmp_path)

    def test_skips_symlinks(self, tmp_path: Path) -> None:
        """Should skip symlinks without raising."""
        archive_path = tmp_path / "test.tar.gz"

        with tarfile.open(archive_path, "w:gz") as tar:
            # Regular file
            info = tarfile.TarInfo(name="regular.txt")
            info.size = 5
            tar.addfile(info, io.BytesIO(b"hello"))

            # Symlink
            symlink = tarfile.TarInfo(name="link")
            symlink.type = tarfile.SYMTYPE
            symlink.linkname = "regular.txt"
            tar.addfile(symlink)

        with tarfile.open(archive_path, "r:gz") as tar:
            safe = _get_safe_members(tar, tmp_path)

        # Only regular file should be included
        assert len(safe) == 1
        assert safe[0].name == "regular.txt"

    def test_allows_safe_nested_paths(self, tmp_path: Path) -> None:
        """Should allow safe nested directory structures."""
        archive_path = tmp_path / "test.tar.gz"

        with tarfile.open(archive_path, "w:gz") as tar:
            for name in ["dir/file1.txt", "dir/subdir/file2.txt"]:
                info = tarfile.TarInfo(name=name)
                info.size = 0
                tar.addfile(info, io.BytesIO(b""))

        with tarfile.open(archive_path, "r:gz") as tar:
            safe = _get_safe_members(tar, tmp_path)

        assert len(safe) == 2
        names = [m.name for m in safe]
        assert "dir/file1.txt" in names
        assert "dir/subdir/file2.txt" in names
