"""Install the pinned, official OpenCode CLI inside this project.

This utility downloads a standalone executable only. It never runs OpenCode,
changes PATH, installs packages, reads credentials, or starts a service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERSION = "2.2.7"
ASSET_NAME = "opencode-windows-x64-baseline.zip"
ASSET_SIZE = 124_794_066
ASSET_SHA256 = "93323d0d6f72f9d1ba9f847e8002de71ace79bb5ea64f18d6b70bbbc30cc719e"
RELEASE_URL = f"https://github.com/anomalyco/opencode/releases/tag/v{VERSION}"
DOWNLOAD_URL = (
    f"https://github.com/anomalyco/opencode/releases/download/v{VERSION}/{ASSET_NAME}"
)
SOCKET_TIMEOUT_SECONDS = 25
DOWNLOAD_TIMEOUT_SECONDS = 300
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
MAX_EXECUTABLE_BYTES = 512 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {
        "github.com",
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
        "github-releases.githubusercontent.com",
    }
)
INSTALL_DIRECTORY = PROJECT_ROOT / ".opencode" / "bin" / VERSION
EXECUTABLE_PATH = INSTALL_DIRECTORY / "opencode.exe"
MANIFEST_PATH = INSTALL_DIRECTORY / "install.json"
DOWNLOAD_DIRECTORY = PROJECT_ROOT / "Temporal" / "opencode" / "download"


class InstallationError(RuntimeError):
    """A validation failure that must stop installation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_local_directory(path: Path) -> None:
    """Refuse junctions/symlinks that would put writes outside the project."""
    root = PROJECT_ROOT.resolve()
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise InstallationError("La ruta de instalación sale del proyecto.") from exc
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.resolve(strict=True).relative_to(root)
    except ValueError as exc:
        raise InstallationError("La carpeta resuelta sale del proyecto.") from exc


def installation_is_verified() -> bool:
    """Check the local receipt and executable without making network requests."""
    if not MANIFEST_PATH.is_file() or not EXECUTABLE_PATH.is_file():
        return False
    try:
        MANIFEST_PATH.resolve(strict=True).relative_to(PROJECT_ROOT.resolve())
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            return False
        expected = {
            "version": VERSION,
            "asset": ASSET_NAME,
            "asset_sha256": ASSET_SHA256,
            "asset_size": ASSET_SIZE,
            "download_url": DOWNLOAD_URL,
            "license": "MIT",
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            return False
        executable_hash = manifest.get("executable_sha256", "")
        if (
            not isinstance(executable_hash, str)
            or len(executable_hash) != 64
            or any(character not in "0123456789abcdef" for character in executable_hash)
        ):
            return False
        resolved_executable = EXECUTABLE_PATH.resolve(strict=True)
        resolved_executable.relative_to(PROJECT_ROOT.resolve())
        if not 0 < resolved_executable.stat().st_size <= MAX_EXECUTABLE_BYTES:
            return False
        return sha256_file(resolved_executable) == executable_hash
    except (OSError, ValueError, TypeError):
        return False


def _validate_download_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_DOWNLOAD_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise InstallationError("La descarga intentó salir de los hosts HTTPS oficiales.")


class OfficialRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        _validate_download_url(new_url)
        return super().redirect_request(request, response, code, message, headers, new_url)


def download_verified_archive() -> Path:
    _ensure_local_directory(DOWNLOAD_DIRECTORY)
    archive_path = DOWNLOAD_DIRECTORY / ASSET_NAME
    partial_path = DOWNLOAD_DIRECTORY / f"{ASSET_NAME}.part"
    if partial_path.is_symlink() or archive_path.is_symlink():
        raise InstallationError("No se permiten enlaces en los archivos de descarga.")
    if archive_path.is_file():
        if (
            archive_path.stat().st_size == ASSET_SIZE
            and sha256_file(archive_path) == ASSET_SHA256
        ):
            return archive_path
        archive_path.unlink()
    request = urllib.request.Request(
        DOWNLOAD_URL,
        headers={"User-Agent": "SparkX-OpenCode-Installer/1.0", "Accept": "application/octet-stream"},
    )
    opener = urllib.request.build_opener(OfficialRedirectHandler())
    started = time.monotonic()
    last_progress = started
    downloaded = 0
    digest = hashlib.sha256()
    print(f"Descargando OpenCode {VERSION} oficial ({ASSET_SIZE / 1024**2:.1f} MiB)…", flush=True)
    try:
        with opener.open(request, timeout=SOCKET_TIMEOUT_SECONDS) as response:
            _validate_download_url(response.geturl())
            declared_length = response.headers.get("Content-Length")
            if declared_length and int(declared_length) != ASSET_SIZE:
                raise InstallationError("El tamaño anunciado no coincide con el asset fijado.")
            with partial_path.open("wb") as destination:
                while True:
                    if time.monotonic() - started > DOWNLOAD_TIMEOUT_SECONDS:
                        raise InstallationError("La descarga superó el tiempo máximo de 300 segundos.")
                    chunk = response.read(CHUNK_BYTES)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > min(ASSET_SIZE, MAX_DOWNLOAD_BYTES):
                        raise InstallationError("La descarga supera el tamaño autorizado.")
                    digest.update(chunk)
                    destination.write(chunk)
                    now = time.monotonic()
                    if now - last_progress >= 5:
                        print(f"Descarga: {downloaded * 100 / ASSET_SIZE:.0f}%", flush=True)
                        last_progress = now
        if downloaded != ASSET_SIZE or digest.hexdigest() != ASSET_SHA256:
            raise InstallationError("El ZIP no coincide con el tamaño y SHA-256 oficiales; no se instalará.")
        os.replace(partial_path, archive_path)
        print("ZIP oficial verificado con SHA-256.", flush=True)
        return archive_path
    finally:
        if partial_path.exists() and not partial_path.is_dir():
            partial_path.unlink()


def _validated_executable_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    members = archive.infolist()
    if len(members) > 32:
        raise InstallationError("El ZIP contiene una cantidad inesperada de entradas.")
    executable = None
    unexpected_files = []
    for member in members:
        normalized = member.filename.replace("\\", "/")
        name = PurePosixPath(normalized)
        unix_mode = member.external_attr >> 16
        if (
            normalized.startswith("/")
            or ".." in name.parts
            or any(":" in part for part in name.parts)
            or "\x00" in normalized
            or stat.S_ISLNK(unix_mode)
            or member.flag_bits & 1
        ):
            raise InstallationError("El ZIP contiene rutas, enlaces o entradas no permitidas.")
        if member.is_dir():
            continue
        if name.name.lower() != "opencode.exe" or executable is not None:
            unexpected_files.append(member.filename)
            continue
        if not 0 < member.file_size <= MAX_EXECUTABLE_BYTES:
            raise InstallationError("El ejecutable tiene un tamaño no permitido.")
        executable = member
    if unexpected_files:
        listing = ", ".join(repr(name) for name in unexpected_files[:8])
        raise InstallationError(
            "El paquete contiene archivos adicionales; revisar el listado antes de instalar: " + listing
        )
    if executable is None:
        raise InstallationError("El paquete no contiene exactamente un opencode.exe autónomo.")
    return executable


def install_archive(archive_path: Path) -> Path:
    """Verify again, inspect the complete ZIP, then copy only opencode.exe."""
    if archive_path.stat().st_size != ASSET_SIZE or sha256_file(archive_path) != ASSET_SHA256:
        raise InstallationError("La comprobación previa a la extracción del ZIP falló.")
    _ensure_local_directory(INSTALL_DIRECTORY)
    staged_executable = INSTALL_DIRECTORY / "opencode.exe.part"
    staged_manifest = INSTALL_DIRECTORY / "install.json.part"
    for destination in (EXECUTABLE_PATH, MANIFEST_PATH, staged_executable, staged_manifest):
        if destination.is_symlink():
            raise InstallationError("No se permiten enlaces en los destinos de instalación.")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            member = _validated_executable_member(archive)
            print(f"Contenido del ZIP revisado: {member.filename} ({member.file_size / 1024**2:.1f} MiB).", flush=True)
            extracted = 0
            digest = hashlib.sha256()
            with archive.open(member) as source, staged_executable.open("wb") as destination:
                while True:
                    chunk = source.read(CHUNK_BYTES)
                    if not chunk:
                        break
                    extracted += len(chunk)
                    if extracted > min(member.file_size, MAX_EXECUTABLE_BYTES):
                        raise InstallationError("La extracción supera el tamaño permitido.")
                    digest.update(chunk)
                    destination.write(chunk)
            if extracted != member.file_size:
                raise InstallationError("El tamaño extraído no coincide con el listado del ZIP.")
        with staged_executable.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise InstallationError("El archivo no tiene una cabecera ejecutable de Windows.")
        manifest = {
            "version": VERSION,
            "asset": ASSET_NAME,
            "asset_size": ASSET_SIZE,
            "asset_sha256": ASSET_SHA256,
            "executable_sha256": digest.hexdigest(),
            "executable_size": extracted,
            "download_url": DOWNLOAD_URL,
            "release_url": RELEASE_URL,
            "license": "MIT",
            "installed_at": datetime.now(timezone.utc).isoformat(),
        }
        staged_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(staged_executable, EXECUTABLE_PATH)
        os.replace(staged_manifest, MANIFEST_PATH)
        if not installation_is_verified():
            raise InstallationError("La verificación final de la instalación falló.")
        archive_path.unlink()
        return EXECUTABLE_PATH
    finally:
        for staged_file in (staged_executable, staged_manifest):
            if staged_file.exists() and not staged_file.is_dir():
                staged_file.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verificar la instalación local sin conexión.")
    parser.add_argument("--repair", action="store_true", help="Reemplazar una instalación local que no supera la verificación.")
    arguments = parser.parse_args(argv)
    if installation_is_verified():
        print(f"OpenCode {VERSION} verificado: {EXECUTABLE_PATH}")
        return 0
    if arguments.check:
        print("OpenCode no está instalado o su integridad no coincide.", file=sys.stderr)
        return 1
    if platform.system() != "Windows" or platform.machine().lower() not in {"amd64", "x86_64"}:
        print("Este instalador fijado admite únicamente Windows x64.", file=sys.stderr)
        return 1
    try:
        if (EXECUTABLE_PATH.exists() or MANIFEST_PATH.exists()) and not arguments.repair:
            raise InstallationError("La instalación existente no supera la verificación. Revisarla antes de usar --repair.")
        result = install_archive(download_verified_archive())
        print(f"Instalado y verificado: {result}\nNo se ejecutó el agente ni se realizaron llamadas de IA.")
        return 0
    except (InstallationError, OSError, ValueError, zipfile.BadZipFile, urllib.error.URLError) as exc:
        print(f"Instalación detenida: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
