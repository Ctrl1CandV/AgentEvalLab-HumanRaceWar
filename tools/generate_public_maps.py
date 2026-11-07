"""Build the public/scrimmage map assets offline; never generate hidden maps.

Existing byte-identical files are accepted; different files are never replaced.
Published map sets must remain immutable. No bot or compiler is launched here.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from arena.games.outpost.mapgen import GENERATOR_VERSION, TYPES, generate


def plan():
    for kind_index, kind in enumerate(TYPES):
        for index in range(10):
            yield f"public/{kind}-{index+1:02d}.map", kind, (24, 28, 32, 36, 40)[index % 5], kind_index*100+index
    for index, kind in enumerate(TYPES):
        yield f"scrimmage/{kind}-01.map", kind, 32, 10_000+index


def build(destination: Path) -> dict:
    entries = []
    generated_files = {}
    for name, kind, size, seed in plan():
        generated = generate(kind, size, seed)
        generated_files[name] = generated.text.encode()
        entries.append({"path": name, "size": size, **generated.metadata()})
    if len({e["sha256"] for e in entries}) != len(entries):
        raise ValueError("duplicate generated map content")
    catalog = {"schemaVersion": 1, "generatorVersion": GENERATOR_VERSION,
               "profile": "default-22800-ore-10-sites; approved I11 zones/basePath; D5 home-walk<=12 and near-site-walk<=6",
               "publicMaps": 40, "scrimmageMaps": 4, "balanceValidated": False,
               "maps": entries}
    generated_files["catalog.json"] = (json.dumps(catalog, indent=2)+"\n").encode()
    # Check all paths before writing any: never partly replace an existing set.
    for name, data in generated_files.items():
        path = destination / name
        if path.is_symlink() or (path.exists() and path.read_bytes() != data):
            raise ValueError(f"refusing to replace different existing map asset: {path}")
    for name, data in generated_files.items():
        path = destination / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
    return {"maps": len(entries), "catalogSha256": sha256(generated_files["catalog.json"]).hexdigest(),
            "rejectedCandidates": sum(len(e["rejectedCandidates"]) for e in entries)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "maps")
    args = parser.parse_args()
    print(json.dumps(build(args.out), indent=2))


if __name__ == "__main__":
    main()
