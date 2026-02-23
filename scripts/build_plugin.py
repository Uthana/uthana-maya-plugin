#!/usr/bin/env python3
"""Build a Maya plugin zip with vendored runtime dependencies."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
PYPROJECT_FILE = ROOT_DIR / "pyproject.toml"
BUILD_DIR = ROOT_DIR / "build" / "plugin_stage"
DIST_DIR = ROOT_DIR / "dist"
PLUGIN_ENTRY = "uthana_maya.py"
PACKAGE_NAME = "uthana"
VERSION_LABEL_PATTERN = r"^\d+\.\d+\.\d+(?:-rc\.\d+)?$"


def read_plugin_version(plugin_file: Path) -> str:
    """Read version from _PLUGIN_VERSION in uthana_maya.py."""
    content = plugin_file.read_text(encoding="utf-8")
    match = re.search(r'_PLUGIN_VERSION\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError("Could not find _PLUGIN_VERSION in src/uthana_maya.py")
    return match.group(1)


def read_runtime_packages(pyproject_file: Path) -> list[str]:
    """Load runtime dependencies from Poetry, excluding Python itself."""
    data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
    dependencies = data["tool"]["poetry"]["dependencies"]
    return [name for name in dependencies if name.lower() != "python"]


def stage_plugin_source(stage_root: Path) -> None:
    """Copy uthana_maya.py and uthana/ to stage root."""
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True, exist_ok=True)

    shutil.copy2(SRC_DIR / PLUGIN_ENTRY, stage_root / PLUGIN_ENTRY)
    shutil.copytree(SRC_DIR / PACKAGE_NAME, stage_root / PACKAGE_NAME)


def vendor_dependencies(target_dir: Path, package_names: list[str]) -> None:
    if not package_names:
        return
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(target_dir),
        *package_names,
    ]
    subprocess.run(cmd, check=True)


def create_zip(stage_root: Path, version: str) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = DIST_DIR / f"uthana-maya-plugin-{version}.zip"
    if archive_path.exists():
        archive_path.unlink()

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in stage_root.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(stage_root)
                archive.write(file_path, arcname)
    return archive_path


def resolve_version_label(base_version: str) -> str:
    version_label = os.getenv("UTHANA_BUILD_VERSION_LABEL", base_version).strip()
    if not version_label:
        raise ValueError("UTHANA_BUILD_VERSION_LABEL cannot be empty")
    if not re.fullmatch(VERSION_LABEL_PATTERN, version_label):
        raise ValueError(
            "Version label must match MAJOR.MINOR.PATCH or MAJOR.MINOR.PATCH-rc.N "
            f"(received: {version_label!r})"
        )
    version_base = version_label.split("-", maxsplit=1)[0]
    if version_base != base_version:
        raise ValueError(
            "Version label base must match _PLUGIN_VERSION "
            f"(_PLUGIN_VERSION={base_version}, label={version_label})"
        )
    return version_label


def main() -> None:
    plugin_file = SRC_DIR / PLUGIN_ENTRY
    if not plugin_file.exists():
        raise FileNotFoundError(f"Missing plugin file: {plugin_file}")
    if not (SRC_DIR / PACKAGE_NAME).exists():
        raise FileNotFoundError(f"Missing package directory: {SRC_DIR / PACKAGE_NAME}")

    version = read_plugin_version(plugin_file)
    version_label = resolve_version_label(version)
    runtime_packages = read_runtime_packages(PYPROJECT_FILE)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    stage_plugin_source(BUILD_DIR)
    vendor_dependencies(BUILD_DIR, runtime_packages)
    archive_path = create_zip(BUILD_DIR, version_label)

    print(f"Built plugin zip: {archive_path}")
    print(f"Vendored dependencies: {', '.join(runtime_packages) if runtime_packages else '(none)'}")


if __name__ == "__main__":
    main()
