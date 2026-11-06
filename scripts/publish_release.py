"""Publica o release somente após validar todos os pacotes e seus checksums."""

import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_version import VERSION


def request(method, url, token, data=None, content_type="application/json"):
    body = json.dumps(data).encode() if content_type == "application/json" and data is not None else data
    call = urllib.request.Request(
        url, data=body, method=method,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "CompressPDF-release",
                 "Content-Type": content_type},
    )
    with urllib.request.urlopen(call, timeout=180) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def main():
    tag = f"v{VERSION}"
    if os.environ.get("GITHUB_REF_NAME") != tag:
        raise RuntimeError("O release deve ser executado na tag correspondente à versão.")
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    folder = ROOT / "release-assets"
    names = [
        f"CompressPDF-{tag}-windows-x64.zip",
        f"CompressPDF-{tag}-linux-x64.tar.gz",
        f"CompressPDF-{tag}-macos-x64.zip",
        f"CompressPDF-{tag}-macos-arm64.zip",
    ]
    checksums = []
    for name in names:
        archive = folder / name
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        expected = (folder / (name + ".sha256")).read_text(encoding="utf-8").split()[0]
        if digest != expected:
            raise RuntimeError(f"Checksum inválido: {name}")
        stem = name.removesuffix(".zip").removesuffix(".tar.gz")
        report = json.loads((folder / (stem + ".build.json")).read_text(encoding="utf-8"))
        if not report.get("ok") or report.get("version") != VERSION:
            raise RuntimeError(f"O pacote não passou nos testes: {name}")
        checksums.append(f"{digest}  {name}\n")
    (folder / "SHA256SUMS.txt").write_text("".join(checksums), encoding="utf-8")

    base = f"https://api.github.com/repos/{repository}"
    try:
        release = request("GET", f"{base}/releases/tags/{tag}", token)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        release = request("POST", f"{base}/releases", token, {
            "tag_name": tag, "target_commitish": os.environ["GITHUB_SHA"],
            "name": f"Compress PDF {tag}", "draft": True, "prerelease": False,
            "body": (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8"),
        })
    if not release["draft"]:
        raise RuntimeError("A versão já foi publicada; use uma nova tag para outro release.")

    upload_url = release["upload_url"].split("{", 1)[0]
    assets = names + ["SHA256SUMS.txt"] + sorted(p.name for p in folder.glob("*.build.json"))
    for name in assets:
        for old in release.get("assets", []):
            if old["name"] == name:
                request("DELETE", f"{base}/releases/assets/{old['id']}", token)
        path = folder / name
        request("POST", upload_url + "?name=" + urllib.parse.quote(name),
                token, path.read_bytes(), "application/octet-stream")
        print(f"Uploaded: {name}")
    release = request("PATCH", f"{base}/releases/{release['id']}", token, {"draft": False})
    print(release["html_url"])


if __name__ == "__main__":
    main()
