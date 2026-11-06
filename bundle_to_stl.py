"""
Convert TTS asset bundles (.unity3d) into printable STL + OBJ files.

Many TTS mods ship their miniatures as Unity asset bundles instead of OBJ files.
This reads each bundle, puts all its parts (figure, base, weapons) in their correct
positions, stands it upright and scales it to millimetres.

Usage:
    pip install UnityPy trimesh numpy
    python bundle_to_stl.py <bundles-folder> <output-folder>
    python bundle_to_stl.py "assets_My Mod/bundles" "assets_My Mod/figures" --scale 10
    python bundle_to_stl.py <bundles-folder> <output-folder> --only Artorias Knight

Output: <output-folder>/stl and <output-folder>/obj. It's safe to stop and re-run:
finished bundles are listed in _done.txt and skipped.
"""
import argparse, sys, re
from pathlib import Path
import numpy as np
import UnityPy, trimesh

def quat_mat(q):
    x, y, z, w = q.x, q.y, q.z, q.w
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])

def world(tr):
    M = np.eye(4)
    while tr is not None:
        L = np.eye(4)
        s = tr.m_LocalScale; p = tr.m_LocalPosition
        L[:3, :3] = quat_mat(tr.m_LocalRotation) @ np.diag([s.x, s.y, s.z])
        L[:3, 3] = [p.x, p.y, p.z]
        M = L @ M
        try:
            tr = tr.m_Father.read() if tr.m_Father and tr.m_Father.path_id else None
        except Exception:
            tr = None
    return M

def mesh_from(m):
    txt = m.export()
    v, f = [], []
    for line in txt.splitlines():
        if line.startswith("v "):
            v.append([float(a) for a in line.split()[1:4]])
        elif line.startswith("f "):
            f.append([int(a.split("/")[0]) - 1 for a in line.split()[1:4]])
    if not v or not f:
        return None
    v = np.array(v); v[:, 0] *= -1          # back to Unity space (export flips X)
    return v, np.array(f)

def convert(bundle, out_stl, out_obj):
    env = UnityPy.load(str(bundle))
    parts, used = [], set()
    for o in env.objects:
        if o.type.name not in ("MeshFilter", "SkinnedMeshRenderer"):
            continue
        d = o.read()
        try:
            mp = d.m_Mesh
            if not mp or not mp.path_id:
                continue
            mesh = mp.read()
            go = d.m_GameObject.read()
            tr = None
            for c in go.m_Component:
                cc = (c.component if hasattr(c, "component") else c[1] if isinstance(c, tuple) else c)
                if cc.type.name == "Transform":
                    tr = cc.read(); break
        except Exception:
            continue
        r = mesh_from(mesh)
        if r is None:
            continue
        v, f = r
        M = world(tr) if tr is not None else np.eye(4)
        v = (np.c_[v, np.ones(len(v))] @ M.T)[:, :3]
        used.add(mp.path_id)
        parts.append(trimesh.Trimesh(v, f, process=False))
    if not parts:   # fall back to raw meshes
        for o in env.objects:
            if o.type.name == "Mesh":
                r = mesh_from(o.read())
                if r: parts.append(trimesh.Trimesh(*r, process=False))
    if not parts:
        return None
    m = trimesh.util.concatenate(parts)
    m.vertices[:, 0] *= -1                    # Unity left-handed -> right-handed
    m.invert()
    m.vertices = m.vertices[:, [0, 2, 1]] * [1, 1, 1]   # Y-up -> Z-up
    m.vertices[:, 1] *= -1
    m.invert()
    m.apply_translation(-m.bounds[0] * [0, 0, 1] - [m.centroid[0], m.centroid[1], 0])
    m.apply_scale(SCALE)                      # TTS units -> mm
    m.export(out_stl); m.export(out_obj)
    return m

SCALE = 10.0

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundles", help="folder with .unity3d files")
    ap.add_argument("out", help="output folder")
    ap.add_argument("--scale", type=float, default=10.0, help="mm per TTS unit (default 10)")
    ap.add_argument("--only", nargs="*", help="convert only these bundle names")
    a = ap.parse_args()
    SCALE = a.scale
    src, dst, only = Path(a.bundles), Path(a.out), a.only or None
    (dst / "stl").mkdir(parents=True, exist_ok=True); (dst / "obj").mkdir(exist_ok=True)
    for b in sorted(src.glob("*.unity3d")):
        if only and b.stem not in only: continue
        done = dst / "_done.txt"
        if not only and done.exists() and b.stem in done.read_text(encoding="utf-8").splitlines(): continue
        try:
            m = convert(b, dst / "stl" / f"{b.stem}.stl", dst / "obj" / f"{b.stem}.obj")
            if not only:
                with open(dst / "_done.txt", "a", encoding="utf-8") as fh: fh.write(b.stem + "\n")
            print(f"{b.stem}: " + ("no mesh" if m is None else f"{len(m.faces)} tris, size {np.round(m.extents,2).tolist()}, watertight={m.is_watertight}"), flush=True)
        except Exception as e:
            print(f"{b.stem}: FAILED {e}", flush=True)
