"""Build a deterministic, source-only SparkX release. No database or network I/O.

This allowlist is independent from Git's current tracked/ignored state. A small
credential-pattern check complements exclusions; it is not a complete DLP audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import tomllib
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = {"apps", "config", "docs", "static", "templates", "tools"}
ROOT_FILES = {
    ".env.example", ".gitignore", "README.md", "manage.py", "pyproject.toml",
    "requirements.txt", "requirements-dev.txt", "Iniciar SparkX.cmd", "Ayudante OpenCode.cmd",
}
IGNORED_PARTS = {
    "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", ".git",
    ".venv", ".agents", ".codex", ".aws", ".opencode", "var", "Temporal", "entrega",
}
SOURCE_SUFFIXES = {".py", ".html", ".css", ".js", ".json", ".md", ".txt", ".svg", ".jpg", ".png", ".wav", ".license"}
DENIED_SUFFIXES = {".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx", ".log", ".pyc", ".zip"}
MANIFEST_NAME = "release-manifest.json"
PACKAGE_ROOT = "SPARKX3.0"
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
PORTABLE_AGENTS = """# SparkX 3.0

Proyecto Django modular de arquitectura inteligente de eventos. Trabajar en español.
Leer README.md, docs/architecture.md, docs/construction-plan.md y docs/release.md.
La IA propone; el servidor controla permisos, validación, estados y aprobaciones.
No incluir secretos ni datos privados en código, registros, documentos o commits.
Material auxiliar exclusivamente en Temporal/, ignorado por Git.
PostgreSQL es obligatorio para acreditar bloqueos y concurrencia de producción.
Este paquete no incluye cuentas, datos activos, claves ni el mentor privado local.
No publicar, enviar ni desplegar externamente sin instrucción explícita del usuario.
"""
TOKEN_PATTERN = re.compile(
    rb"\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,})\b"
)
PRIVATE_KEY_PATTERN = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\r\n]+[A-Za-z0-9+/=\r\n]{40,}")
DATABASE_PASSWORD_PATTERN = re.compile(rb"postgres(?:ql)?://[^\s:/]+:([^@\s/]+)@", re.I)
# Exact token SHA-256 + exact test path, reviewed as synthetic negative fixtures.
# Unknown token-shaped strings, including new test fixtures, stop packaging.
SYNTHETIC_FIXTURES: set[tuple[str, str]] = {
    ("apps/assistant/test_interaction_memory.py", "4ffa47895db33000f04517ba4e1dc6a3e47e8408d373268f2e07810a7238183f"),
    ("apps/assistant/test_interaction_memory.py", "ad40fb40a6e9a0a2dcc5d8928dddb22c8b98628e96c007714df2ab91ce4a0368"),
    ("apps/assistant/test_interaction_memory.py", "400d4428b6d2abf1577273bfad7840ed5450553a1b65eda4bcea13e46054a160"),
    ("apps/assistant/test_knowledge_memory.py", "977b7ec104fb56cc781bf9316d207e203520660807d7a5c10e4894455c43c0e1"),
    ("apps/assistant/test_knowledge_memory.py", "3a8ce4e2c53f248d7508023a849a3c5c2c8f2868d57cd5ee382738dea1a95fc5"),
    ("apps/assistant/test_knowledge_memory.py", "00adffc7f3b5f5d38f951061d28b8a5016f3ace06c5b818f599a449a5cc97bfc"),
    ("apps/assistant/test_knowledge_memory.py", "3193831645bd691450f50c575c8f3019bcd83b9be8448321f223ef36671e03c5"),
    ("apps/assistant/test_knowledge_service.py", "38750363110a3edaf7e547ab2954aab33106d7bf42feb277ba50514cebfd394d"),
}


class ReleaseError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or "\x00" in name
            or any(ord(char) < 32 or char in '*?"<>|' for char in name)
            or path.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/"))
            or any(part.endswith((".", " ")) for part in path.parts)
            or any(part.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))} for part in path.parts)):
        raise ReleaseError("Ruta de archivo no permitida.")
    return path


def is_allowed(name: str) -> bool:
    path = safe_relative(name)
    if any(part.casefold() in {item.casefold() for item in IGNORED_PARTS} for part in path.parts):
        return False
    if any(part.startswith(".env") and part != ".env.example" for part in path.parts):
        return False
    if path.suffix.casefold() in DENIED_SUFFIXES:
        return False
    if len(path.parts) == 1:
        return name in ROOT_FILES or name == "AGENTS.md"
    return path.parts[0] in SOURCE_DIRS and path.suffix.casefold() in SOURCE_SUFFIXES


def secret_findings(name: str, data: bytes) -> list[dict]:
    findings = []
    for match in TOKEN_PATTERN.finditer(data):
        digest = sha256(match.group())
        if (name, digest) not in SYNTHETIC_FIXTURES:
            findings.append({"path": name, "kind": "token_pattern", "line": data[:match.start()].count(b"\n") + 1, "fingerprint": digest})
    if PRIVATE_KEY_PATTERN.search(data):
        findings.append({"path": name, "kind": "private_key"})
    for match in DATABASE_PASSWORD_PATTERN.finditer(data):
        # Explicit example placeholders never contain a usable password.
        if not (match.group(1).startswith(b"<") and match.group(1).endswith(b">")):
            findings.append({"path": name, "kind": "database_password_url"})
    return findings


def collect_sources(root: Path) -> dict[str, bytes]:
    root = root.resolve(strict=True)
    files = {}
    for name in sorted(ROOT_FILES):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ReleaseError(f"Falta un archivo regular obligatorio: {name}")
        files[name] = path.read_bytes()
    for directory in sorted(SOURCE_DIRS):
        start = root / directory
        if start.is_symlink() or not start.is_dir():
            raise ReleaseError(f"Falta un directorio regular obligatorio: {directory}")
        for current, dirs, names in os.walk(start, followlinks=False):
            for child in dirs + names:
                path = Path(current) / child
                if path.is_symlink() or path.is_junction():
                    raise ReleaseError(f"No se permiten enlaces: {path.relative_to(root).as_posix()}")
            dirs[:] = [name for name in dirs if name not in IGNORED_PARTS]
            for name in names:
                path = Path(current) / name
                relative = path.relative_to(root).as_posix()
                if is_allowed(relative):
                    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                        raise ReleaseError(f"Tamaño o tipo no permitido: {relative}")
                    files[relative] = path.read_bytes()
    files["AGENTS.md"] = PORTABLE_AGENTS.encode("utf-8")
    if sum(map(len, files.values())) > MAX_TOTAL_BYTES:
        raise ReleaseError("El código fuente supera el tamaño máximo previsto.")
    findings = [item for name, data in sorted(files.items()) for item in secret_findings(name, data)]
    if findings:
        # Paths, types and hashes only: never print the matched credential.
        raise ReleaseError(json.dumps({"secret_scan": "blocked", "findings": findings}, ensure_ascii=False))
    return dict(sorted(files.items()))


def source_version(root: Path) -> str:
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[a-z0-9.-]+)?", version):
        raise ReleaseError("Versión de proyecto no válida.")
    return version


def manifest(files: dict[str, bytes], version: str) -> dict:
    return {"schema": 1, "project": "SparkX 3.0", "version": version,
            "type": "source-only", "data_included": False,
            "files": [{"path": name, "bytes": len(data), "sha256": sha256(data)} for name, data in sorted(files.items())]}


def build_release(root: Path, output: Path) -> dict:
    files = collect_sources(root)
    release_manifest = manifest(files, source_version(root))
    files[MANIFEST_NAME] = (json.dumps(release_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    output = output.resolve()
    root = root.resolve(strict=True)
    permitted = (root / "entrega").resolve()
    if (not permitted.is_relative_to(root) or not output.is_relative_to(permitted)
            or output.suffix != ".zip"):
        raise ReleaseError("El ZIP debe guardarse en entrega/ dentro del proyecto.")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".sparkx-", suffix=".part", dir=output.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(f"{PACKAGE_ROOT}/{name}", date_time=FIXED_TIME)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data, compresslevel=9)
        result = verify_release(temporary)
        temporary.replace(output)
        digest = sha256(output.read_bytes())
        output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n", encoding="ascii")
        return {**result, "zip": str(output.relative_to(root)), "sha256": digest, "bytes": output.stat().st_size}
    finally:
        temporary.unlink(missing_ok=True)


def verify_release(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) > 10000 or len(names) != len({name.casefold() for name in names}):
            raise ReleaseError("El ZIP tiene demasiados archivos o nombres repetidos.")
        payload = {}
        total_size = 0
        for info in archive.infolist():
            parts = safe_relative(info.filename).parts
            if len(parts) < 2 or parts[0] != PACKAGE_ROOT or info.is_dir():
                raise ReleaseError("Raíz del paquete no válida.")
            name = PurePosixPath(*parts[1:]).as_posix()
            if name != MANIFEST_NAME and not is_allowed(name):
                raise ReleaseError("El ZIP contiene material fuera de la lista permitida.")
            if (info.external_attr >> 16) & 0o170000 != stat.S_IFREG or info.file_size > MAX_FILE_BYTES:
                raise ReleaseError("El ZIP contiene enlaces o archivos demasiado grandes.")
            total_size += info.file_size
            if total_size > MAX_TOTAL_BYTES:
                raise ReleaseError("El ZIP supera el tamaño permitido.")
            payload[name] = archive.read(info)
        if sum(map(len, payload.values())) > MAX_TOTAL_BYTES:
            raise ReleaseError("El ZIP supera el tamaño permitido.")
        try:
            expected = json.loads(payload.pop(MANIFEST_NAME))
        except (KeyError, ValueError, UnicodeError) as error:
            raise ReleaseError("Falta el manifiesto JSON válido.") from error
        if not isinstance(expected, dict) or expected != manifest(payload, expected.get("version", "")):
            raise ReleaseError("El contenido no coincide con el manifiesto.")
        findings = [item for name, data in payload.items() for item in secret_findings(name, data)]
        if findings:
            raise ReleaseError(json.dumps({"secret_scan": "blocked", "findings": findings}, ensure_ascii=False))
        return {"verified": True, "version": expected["version"], "source_files": len(payload), "secret_scan": "no_unreviewed_patterns"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Revisar la selección sin escribir un ZIP.")
    parser.add_argument("--verify", type=Path, help="Comprobar un ZIP generado anteriormente.")
    parser.add_argument("--output", type=Path, help="Destino dentro de entrega/.")
    args = parser.parse_args()
    try:
        if args.verify:
            result = verify_release(args.verify)
        elif args.check_only:
            files = collect_sources(PROJECT_ROOT)
            result = {"checked": True, "source_files": len(files), "bytes": sum(map(len, files.values()))}
        else:
            output = args.output or PROJECT_ROOT / "entrega" / f"SparkX3.0-codigo-v{source_version(PROJECT_ROOT)}.zip"
            result = build_release(PROJECT_ROOT, output)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ReleaseError, OSError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
