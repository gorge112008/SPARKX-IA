"""Distribution boundaries; all test data is synthetic and isolated in Temporal/."""
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from tools.package_release import (
    FIXED_TIME, PACKAGE_ROOT, PROJECT_ROOT, ROOT_FILES, SOURCE_DIRS, ReleaseError,
    build_release, collect_sources, is_allowed, secret_findings, verify_release,
)


class PackageReleaseTests(unittest.TestCase):
    def setUp(self):
        directory = PROJECT_ROOT / "Temporal" / "qa-gica-jury"
        directory.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="release-contract-", dir=directory)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ROOT_FILES:
            (self.root / name).write_text("example\n", encoding="utf-8")
        (self.root / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
        for directory in SOURCE_DIRS:
            (self.root / directory).mkdir()
        (self.root / "apps" / "__init__.py").write_text("", encoding="utf-8")

    def test_allowlist_excludes_private_state_and_unknown_roots(self):
        denied = ["var/db.sqlite3", "Temporal/data.json", ".env", "apps/.env.local",
                  "apps/test.sqlite3", ".agents/SKILL.md", "entrega/report.docx",
                  "apps/a.pem", "docs/private.key", ".git/config", "outputs/test.html"]
        for name in denied:
            with self.subTest(name=name):
                self.assertFalse(is_allowed(name))
        for name in [".env.example", "apps/__init__.py", "static/vendor/htmx.LICENSE", "docs/guias/release.md"]:
            self.assertTrue(is_allowed(name))

    def test_traversal_absolute_and_windows_paths_fail(self):
        for name in ["../apps/x.py", "/apps/x.py", "apps/../../key.py", "apps\\x.py", "C:/apps/x.py", "apps//x.py", "apps/./x.py", "apps/NUL.py", "apps/file.py.", "apps/file.py "]:
            with self.subTest(name=name), self.assertRaises(ReleaseError):
                is_allowed(name)

    def test_private_files_do_not_enter_selection(self):
        (self.root / "var").mkdir()
        (self.root / "var" / "db.sqlite3").write_bytes(b"private-data")
        (self.root / "apps" / ".env").write_text("private-data", encoding="utf-8")
        (self.root / "docs" / "private.pem").write_text("private-data", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("private mentor references", encoding="utf-8")
        files = collect_sources(self.root)
        self.assertNotIn("private-data", repr(files))
        self.assertNotIn(b"private mentor references", files["AGENTS.md"])

    def test_unknown_credential_pattern_blocks_even_in_tests_without_disclosing_it(self):
        token = b"sk-" + b"different-test-credential-value-1234567890"
        findings = secret_findings("apps/test_new.py", token)
        self.assertEqual(findings[0]["kind"], "token_pattern")
        self.assertNotIn(token.decode(), repr(findings))
        (self.root / "apps" / "test_new.py").write_bytes(token)
        with self.assertRaises(ReleaseError) as caught:
            collect_sources(self.root)
        self.assertNotIn(token.decode(), str(caught.exception))

    def test_same_sources_make_byte_identical_verified_archives(self):
        first = self.root / "entrega" / "one.zip"
        second = self.root / "entrega" / "two.zip"
        result1 = build_release(self.root, first)
        result2 = build_release(self.root, second)
        self.assertEqual(result1["sha256"], result2["sha256"])
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertTrue(verify_release(first)["verified"])
        with zipfile.ZipFile(first) as archive:
            self.assertTrue(all(info.date_time == FIXED_TIME for info in archive.infolist()))

    def test_output_outside_delivery_folder_is_rejected(self):
        with self.assertRaises(ReleaseError):
            build_release(self.root, self.root / "archive.zip")
        self.assertFalse((self.root / "archive.zip").exists())

    def test_new_root_uses_product_name_and_legacy_archives_remain_readable(self):
        path = self.root / "entrega" / "current.zip"
        build_release(self.root, path)
        with zipfile.ZipFile(path) as archive:
            payload = [(info, archive.read(info)) for info in archive.infolist()]
        self.assertEqual(PACKAGE_ROOT, "ArquiGica")
        self.assertTrue(all(info.filename.startswith("ArquiGica/") for info, _ in payload))
        legacy = self.root / "entrega" / "legacy.zip"
        with zipfile.ZipFile(legacy, "w") as archive:
            for info, data in payload:
                info.filename = "SPARKX3.0/" + info.filename.split("/", 1)[1]
                archive.writestr(info, data)
        self.assertTrue(verify_release(legacy)["verified"])

    def test_mixed_current_and_legacy_roots_are_rejected(self):
        path = self.root / "entrega" / "mixed.zip"
        build_release(self.root, path)
        with zipfile.ZipFile(path) as archive:
            payload = [(info, archive.read(info)) for info in archive.infolist()]
        with zipfile.ZipFile(path, "w") as archive:
            for index, (info, data) in enumerate(payload):
                if index == 0:
                    info.filename = "SPARKX3.0/" + info.filename.split("/", 1)[1]
                archive.writestr(info, data)
        with self.assertRaises(ReleaseError):
            verify_release(path)

    def test_tampered_content_is_rejected(self):
        path = self.root / "entrega" / "one.zip"
        build_release(self.root, path)
        with zipfile.ZipFile(path) as original:
            payload = [(info, original.read(info)) for info in original.infolist()]
        with zipfile.ZipFile(path, "w") as changed:
            for info, data in payload:
                changed.writestr(info, b"tampered" if info.filename.endswith("README.md") else data)
        with self.assertRaises(ReleaseError):
            verify_release(path)

    def test_symlink_zip_entry_is_rejected_before_use(self):
        path = self.root / "entrega" / "bad.zip"
        path.parent.mkdir()
        info = zipfile.ZipInfo(f"{PACKAGE_ROOT}/apps/link.py")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(info, "../../outside")
        with self.assertRaises(ReleaseError):
            verify_release(path)


if __name__ == "__main__":
    unittest.main()
