"""
Convert extracted TTS OBJ models into printable STL files.

Stands each model upright (TTS/Unity is Y-up, slicers are Z-up), scales it to millimetres,
centres it on the bed and sorts it into figures/ or terrain/. Flat or very simple models
(map tiles, cardboard standees, mats, UI pieces) are skipped automatically.

Usage:
    pip install trimesh numpy
    python obj_to_stl.py <models-folder> <output-folder>
    python obj_to_stl.py "assets_My Mod/models" "assets_My Mod/printable" --scale 18

Options:
    --scale       mm per TTS unit (default 18: a Gloomhaven hero base comes out about 26 mm)
    --min-faces   skip models with fewer triangles than this (default 1000)
    --terrain     text that marks a model as terrain (default "(3D)")
    --skip        extra model names to skip
"""
import argparse
from pathlib import Path

import numpy as np
import trimesh


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("models", help="folder with .obj files")
    ap.add_argument("out", help="output folder")
    ap.add_argument("--scale", type=float, default=18.0)
    ap.add_argument("--min-faces", type=int, default=1000)
    ap.add_argument("--terrain", default="(3D)")
    ap.add_argument("--skip", nargs="*", default=[])
    a = ap.parse_args()

    src, out = Path(a.models), Path(a.out)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    (out / "terrain").mkdir(parents=True, exist_ok=True)
    counts = {"figures": 0, "terrain": 0, "skipped": 0}

    for f in sorted(src.glob("*.obj")):
        name = f.stem
        if name in a.skip:
            counts["skipped"] += 1
            continue
        try:
            m = trimesh.load(f, force="mesh", process=False)
        except Exception as e:
            print(f"{name}: failed ({e})")
            continue
        if len(m.faces) < a.min_faces:
            counts["skipped"] += 1
            continue
        m.merge_vertices()
        v = m.vertices.copy()
        m.vertices = np.c_[v[:, 0], -v[:, 2], v[:, 1]]          # Y-up -> Z-up
        m.apply_scale(a.scale)
        b = m.bounds
        m.apply_translation([-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]])
        kind = "terrain" if a.terrain and a.terrain in name else "figures"
        clean = name.replace(f" {a.terrain}", "").replace(a.terrain, "").strip() if a.terrain else name
        m.export(out / kind / f"{clean}.stl")
        counts[kind] += 1
        print(f"{kind:8s} {clean}: {np.round(m.extents).astype(int).tolist()} mm")

    print(f"\nDone -> {out.resolve()}")
    print(f"  figures: {counts['figures']}   terrain: {counts['terrain']}   skipped (flat/simple): {counts['skipped']}")


if __name__ == "__main__":
    main()
