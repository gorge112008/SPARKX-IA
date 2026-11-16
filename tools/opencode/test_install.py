"""Offline regression tests for the pinned OpenCode installer.

All files live in an automatically removed Temporal fixture. No test accesses
the installed OpenCode binary, starts a process, or makes network requests.
"""

from __future__ import annotations

import hashlib
import io
import json
import stat
import tempfile
import unittest
import urllib.request
import zipfile
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from tools.opencode import install


def archive_bytes(entries: list[tuple[str | zipfile.ZipInfo, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


class FakeDownload(io.BytesIO):
    def __init__(self, content: bytes, *, declared_length: int | None = None, url: str | None = None):
        super().__init__(content)
        self.headers = {}
        if declared_length is not None:
            self.headers["Content-Length"] = str(declared_length)
        self.url = url or install.DOWNLOAD_URL

    def geturl(self):
        return self.url


class InstallerFixture(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temporal = Path(__file__).resolve().parents[2] / "Temporal"
        temporal.mkdir(exist_ok=True)
        temporary = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="test-opencode-install-", dir=temporal))
        self.root = Path(temporary) / "project"
        self.root.mkdir()
        self.binary = b"MZ\x90\x00fixture executable; never run"
        self.good_zip = archive_bytes([("bundle/", b""), ("bundle/opencode.exe", self.binary)])
        self.directory = self.root / ".opencode" / "bin" / install.VERSION
        self.executable = self.directory / "opencode.exe"
        self.manifest = self.directory / "install.json"
        self.downloads = self.root / "Temporal" / "opencode" / "download"
        self.archive = self.downloads / install.ASSET_NAME
        self.partial = self.downloads / f"{install.ASSET_NAME}.part"
        values = {
            "PROJECT_ROOT": self.root,
            "INSTALL_DIRECTORY": self.directory,
            "EXECUTABLE_PATH": self.executable,
            "MANIFEST_PATH": self.manifest,
            "DOWNLOAD_DIRECTORY": self.downloads,
            "ASSET_SIZE": len(self.good_zip),
            "ASSET_SHA256": hashlib.sha256(self.good_zip).hexdigest(),
        }
        self.stack.enter_context(patch.multiple(install, **values))
        self.network = self.stack.enter_context(
            patch.object(install.urllib.request, "build_opener", side_effect=AssertionError("Real network forbidden"))
        )
        self.output = io.StringIO()
        self.stack.enter_context(redirect_stdout(self.output))
        self.stack.enter_context(redirect_stderr(self.output))

    def write_archive(self, content: bytes | None = None, *, repin: bool = False) -> Path:
        content = self.good_zip if content is None else content
        self.downloads.mkdir(parents=True, exist_ok=True)
        self.archive.write_bytes(content)
        if repin:
            self.stack.enter_context(
                patch.multiple(install, ASSET_SIZE=len(content), ASSET_SHA256=hashlib.sha256(content).hexdigest())
            )
        return self.archive

    def write_verified_installation(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.executable.write_bytes(self.binary)
        manifest = {
            "version": install.VERSION,
            "asset": install.ASSET_NAME,
            "asset_sha256": install.ASSET_SHA256,
            "asset_size": install.ASSET_SIZE,
            "download_url": install.DOWNLOAD_URL,
            "license": "MIT",
            "executable_sha256": hashlib.sha256(self.binary).hexdigest(),
        }
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def mock_download(self, content: bytes, **kwargs):
        opener = Mock()
        opener.open.return_value = FakeDownload(content, **kwargs)
        self.network.side_effect = None
        self.network.return_value = opener
        return opener


class ArchiveInstallationTests(InstallerFixture):
    def test_verified_archive_installs_only_executable_and_receipt(self):
        archive = self.write_archive()
        result = install.install_archive(archive)
        self.assertEqual(result, self.executable)
        self.assertEqual(self.executable.read_bytes(), self.binary)
        self.assertTrue(install.installation_is_verified())
        receipt = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(receipt["asset_sha256"], hashlib.sha256(self.good_zip).hexdigest())
        self.assertEqual(receipt["executable_sha256"], hashlib.sha256(self.binary).hexdigest())
        self.assertEqual(receipt["license"], "MIT")
        self.assertEqual(receipt["download_url"], install.DOWNLOAD_URL)
        self.assertFalse(archive.exists(), "Successful installation removes the downloaded ZIP")
        self.assertEqual({path.name for path in self.directory.iterdir()}, {"opencode.exe", "install.json"})
        self.assertFalse((self.directory / "bundle").exists())
        self.network.assert_not_called()

    def test_changed_archive_fails_before_creating_installation(self):
        archive = self.write_archive(self.good_zip[:-1] + bytes([self.good_zip[-1] ^ 1]))
        with self.assertRaises(install.InstallationError):
            install.install_archive(archive)
        self.assertFalse(self.directory.exists())
        self.assertTrue(archive.exists())

    def test_unexpected_bundle_files_require_review_and_do_not_replace_existing_executable(self):
        self.directory.mkdir(parents=True)
        self.executable.write_bytes(b"previous installation")
        content = archive_bytes([("opencode.exe", self.binary), ("unexpected.dll", b"extra")])
        with self.assertRaisesRegex(install.InstallationError, "unexpected.dll"):
            install.install_archive(self.write_archive(content, repin=True))
        self.assertEqual(self.executable.read_bytes(), b"previous installation")
        self.assertFalse(self.manifest.exists())
        self.assertFalse((self.directory / "opencode.exe.part").exists())

    def test_non_windows_payload_is_rejected_and_staging_removed(self):
        content = archive_bytes([("opencode.exe", b"not a Windows executable")])
        with self.assertRaisesRegex(install.InstallationError, "cabecera"):
            install.install_archive(self.write_archive(content, repin=True))
        self.assertFalse(self.executable.exists())
        self.assertFalse(self.manifest.exists())
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_unsafe_paths_symlinks_duplicate_executables_and_missing_executable_are_blocked(self):
        symlink = zipfile.ZipInfo("opencode.exe")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        cases = {
            "parent traversal": [("../opencode.exe", self.binary)],
            "absolute path": [("/opencode.exe", self.binary)],
            "drive path": [("C:/opencode.exe", self.binary)],
            "alternate data stream": [("bundle:stream/opencode.exe", self.binary)],
            "windows traversal": [("..\\opencode.exe", self.binary)],
            "symlink": [(symlink, b"/outside/target")],
            "duplicate basename": [("a/opencode.exe", self.binary), ("b/opencode.exe", self.binary)],
            "missing executable": [("directory/", b"")],
        }
        for label, entries in cases.items():
            with self.subTest(case=label), zipfile.ZipFile(io.BytesIO(archive_bytes(entries))) as archive:
                with self.assertRaises(install.InstallationError):
                    install._validated_executable_member(archive)
        self.assertFalse(self.directory.exists())

    def test_archive_entry_count_encryption_and_declared_size_are_bounded(self):
        encrypted = zipfile.ZipInfo("opencode.exe")
        encrypted.flag_bits = 1
        encrypted.file_size = len(self.binary)
        oversized = zipfile.ZipInfo("opencode.exe")
        oversized.file_size = install.MAX_EXECUTABLE_BYTES + 1
        empty = zipfile.ZipInfo("opencode.exe")
        for label, members in {
            "encrypted": [encrypted],
            "oversized": [oversized],
            "empty": [empty],
            "too many entries": [zipfile.ZipInfo(f"folder-{index}/") for index in range(33)],
        }.items():
            with self.subTest(case=label):
                archive = Mock()
                archive.infolist.return_value = members
                with self.assertRaises(install.InstallationError):
                    install._validated_executable_member(archive)


class DownloadTests(InstallerFixture):
    def test_successful_mock_download_verifies_hash_and_uses_socket_timeout(self):
        opener = self.mock_download(self.good_zip, declared_length=len(self.good_zip))
        result = install.download_verified_archive()
        self.assertEqual(result.read_bytes(), self.good_zip)
        self.assertFalse(self.partial.exists())
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 25)
        self.assertEqual(opener.open.call_args.args[0].full_url, install.DOWNLOAD_URL)
        self.assertFalse(self.directory.exists(), "Downloading must not install or execute anything")

    def test_correct_cached_archive_never_opens_network(self):
        self.write_archive()
        self.assertEqual(install.download_verified_archive(), self.archive)
        self.network.assert_not_called()

    def test_corrupt_download_is_removed_and_never_promoted(self):
        changed = self.good_zip[:-1] + bytes([self.good_zip[-1] ^ 1])
        self.mock_download(changed, declared_length=len(self.good_zip))
        with self.assertRaisesRegex(install.InstallationError, "SHA-256"):
            install.download_verified_archive()
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.directory.exists())

    def test_length_truncation_and_byte_limit_fail_closed(self):
        for label, content, declared, maximum in [
            ("wrong response length", self.good_zip, len(self.good_zip) + 1, install.MAX_DOWNLOAD_BYTES),
            ("truncated body", self.good_zip[:-5], len(self.good_zip), install.MAX_DOWNLOAD_BYTES),
            ("oversized body", self.good_zip + b"extra", None, install.MAX_DOWNLOAD_BYTES),
            ("configured byte ceiling", self.good_zip, None, 16),
        ]:
            with self.subTest(case=label), patch.object(install, "MAX_DOWNLOAD_BYTES", maximum):
                self.mock_download(content, declared_length=declared)
                with self.assertRaises(install.InstallationError):
                    install.download_verified_archive()
                self.assertFalse(self.partial.exists())
                self.assertFalse(self.archive.exists())

    def test_elapsed_timeout_removes_partial_download(self):
        self.mock_download(self.good_zip)
        with patch.object(install.time, "monotonic", side_effect=[0, 301]):
            with self.assertRaisesRegex(install.InstallationError, "tiempo"):
                install.download_verified_archive()
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.archive.exists())

    def test_final_response_from_unapproved_host_is_rejected_before_writing(self):
        self.mock_download(self.good_zip, url="https://unapproved.example/asset.zip")
        with self.assertRaises(install.InstallationError):
            install.download_verified_archive()
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.archive.exists())


class LocalIntegrityTests(InstallerFixture):
    def test_verified_installation_is_idempotent_without_network(self):
        self.write_verified_installation()
        self.assertTrue(install.installation_is_verified())
        self.assertEqual(install.main([]), 0)
        self.assertEqual(install.main(["--check"]), 0)
        self.network.assert_not_called()

    def test_missing_and_modified_installation_fail_check_without_network(self):
        self.assertEqual(install.main(["--check"]), 1)
        self.write_verified_installation()
        self.executable.write_bytes(self.binary.replace(b"fixture", b"changed"))
        self.assertFalse(install.installation_is_verified())
        self.assertEqual(install.main(["--check"]), 1)
        self.network.assert_not_called()

    def test_receipt_pin_fields_and_executable_hash_are_required(self):
        original = self.write_verified_installation()
        for field in ("version", "asset", "asset_sha256", "asset_size", "download_url", "license", "executable_sha256"):
            with self.subTest(field=field):
                changed = {**original, field: "tampered"}
                self.manifest.write_text(json.dumps(changed), encoding="utf-8")
                self.assertFalse(install.installation_is_verified())
        self.network.assert_not_called()

    def test_malformed_and_non_object_receipts_are_unverified(self):
        self.write_verified_installation()
        for content in ("broken JSON", "null", "[]", '"string"', "42"):
            with self.subTest(receipt=content):
                self.manifest.write_text(content, encoding="utf-8")
                self.assertFalse(install.installation_is_verified())

    def test_invalid_existing_installation_needs_explicit_repair(self):
        self.directory.mkdir(parents=True)
        self.executable.write_bytes(b"unverified")
        with patch.object(install.platform, "system", return_value="Windows"), patch.object(
            install.platform, "machine", return_value="AMD64"
        ):
            self.assertEqual(install.main([]), 1)
        self.assertEqual(self.executable.read_bytes(), b"unverified")
        self.network.assert_not_called()

    def test_resolved_paths_must_stay_inside_fixture_project(self):
        outside = self.root.parent / "outside"
        with self.assertRaises(install.InstallationError):
            install._ensure_local_directory(outside)
        self.assertFalse(outside.exists())
        inside = self.root / "nested" / "install"
        install._ensure_local_directory(inside)
        self.assertTrue(inside.is_dir())
        self.write_verified_installation()
        external_receipt = self.root.parent / "receipt.json"
        external_receipt.write_text(self.manifest.read_text(encoding="utf-8"), encoding="utf-8")
        with patch.object(install, "MANIFEST_PATH", external_receipt):
            self.assertFalse(install.installation_is_verified())


class SourceAndUrlTests(unittest.TestCase):
    def test_production_paths_derive_from_project_root(self):
        source_root = Path(install.__file__).resolve().parents[2]
        self.assertEqual(install.PROJECT_ROOT, source_root)
        self.assertEqual(install.INSTALL_DIRECTORY, source_root / ".opencode" / "bin" / install.VERSION)
        self.assertEqual(install.DOWNLOAD_DIRECTORY, source_root / "Temporal" / "opencode" / "download")

    def test_only_official_https_urls_without_credentials_or_custom_ports_are_allowed(self):
        allowed = [
            "https://github.com/anomalyco/opencode/releases/download/v2.2.7/asset.zip",
            "https://release-assets.githubusercontent.com/asset?signature=fixture",
            "https://objects.githubusercontent.com/asset",
            "https://github-releases.githubusercontent.com:443/asset",
        ]
        denied = [
            "http://github.com/asset",
            "https://github.com.attacker.example/asset",
            "https://attacker.example/github.com/asset",
            "https://user:password@github.com/asset",
            "https://github.com:444/asset",
            "file:///tmp/asset.zip",
            "https://127.0.0.1/asset.zip",
        ]
        for url in allowed:
            with self.subTest(allowed=url):
                install._validate_download_url(url)
        for url in denied:
            with self.subTest(denied=url):
                with self.assertRaises(install.InstallationError):
                    install._validate_download_url(url)

    def test_redirects_to_unapproved_origin_are_blocked(self):
        request = urllib.request.Request(install.DOWNLOAD_URL)
        handler = install.OfficialRedirectHandler()
        with self.assertRaises(install.InstallationError):
            handler.redirect_request(request, None, 302, "Found", {}, "https://attacker.example/asset.zip")


if __name__ == "__main__":
    unittest.main()
