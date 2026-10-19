"""Package only the files needed to run the published Docker Compose release."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--image-manifests", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", args.version):
        parser.error("Use a semantic release version, for example 2.0.0")
    root = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=True)
    files = [
        "docker/release/compose.yml",
        "docker/release/configure.py",
        "docker/release/.env.example.fastapi",
        "docker/release/models.json",
        "docker/release/README.md",
        "docker/nginx/default.conf",
    ]
    images = []
    if args.image_manifests:
        for path in sorted(args.image_manifests.rglob("image.json")):
            images.append(json.loads(path.read_text()))
    contents = {name: (root / name).read_text() for name in files}
    contents["docker/release/compose.yml"] = contents[
        "docker/release/compose.yml"
    ].replace("${RELEASE_VERSION:-2.0.0}", args.version)
    contents["docker/release/configure.py"] = contents[
        "docker/release/configure.py"
    ].replace('"RELEASE_VERSION": "2.0.0"', f'"RELEASE_VERSION": "{args.version}"')
    manifest = {
        "version": args.version,
        "models": json.loads((root / "docker/release/models.json").read_text()),
        "images": images,
        "files": {
            name: hashlib.sha256(content.encode()).hexdigest()
            for name, content in contents.items()
        },
    }
    target = args.output / f"rag-ishms-{args.version}-docker.zip"
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    (args.output / "SHA256SUMS").write_text(f"{checksum}  {target.name}\n")
    print(f"Created {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
