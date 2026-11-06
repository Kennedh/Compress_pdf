"""Gera e testa o pacote nativo do sistema atual. Execute na raiz do projeto."""

import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_version import VERSION


def main():
    system = platform.system()
    architecture = platform.machine().lower()
    architecture = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(architecture, architecture)
    names = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}
    if system not in names or architecture not in ("x64", "arm64"):
        raise SystemExit(f"Plataforma não suportada: {system} {architecture}")

    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "CompressPDF.spec"],
        cwd=ROOT, check=True,
    )
    distribution = ROOT / "dist"
    if system == "Darwin":
        product = distribution / "CompressPDF.app"
        executable = product / "Contents" / "MacOS" / "CompressPDF"
    else:
        product = distribution / "CompressPDF"
        executable = product / ("CompressPDF.exe" if system == "Windows" else "CompressPDF")

    with tempfile.TemporaryDirectory(prefix="compress-release-") as directory:
        report_path = Path(directory) / "smoke.json"
        process = subprocess.run(
            [str(executable), "--smoke-test", str(report_path)],
            cwd=directory, timeout=120,
        )
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
        if process.returncode or not report.get("ok"):
            raise RuntimeError(f"O aplicativo empacotado falhou no teste: {report}")
        print(json.dumps(report, ensure_ascii=True))

    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    name = f"CompressPDF-v{VERSION}-{names[system]}-{architecture}"
    if system == "Darwin":
        archive = release / f"{name}.zip"
        # ditto mantém permissões e links simbólicos do bundle macOS.
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(product), str(archive)], check=True)
    elif system == "Windows":
        archive = Path(shutil.make_archive(str(release / name), "zip", distribution, product.name))
    else:
        archive = release / f"{name}.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(product, arcname=product.name)

    with archive.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    archive.with_name(archive.name + ".sha256").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    (release / f"{name}.build.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Package: {archive.name} ({archive.stat().st_size // 1024 // 1024} MB)")


if __name__ == "__main__":
    main()
