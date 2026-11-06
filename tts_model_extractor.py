"""
Tabletop Simulator model / asset extractor.

Pulls every 3D model and other asset out of a TTS mod:
  - Custom models (OBJ)      -> copied as .obj + texture, and converted to .stl for printing
  - Asset bundles (.unity3d) -> copied as-is (open them with AssetRipper to get the meshes)
  - Boards, tiles, tokens    -> copied as images

Usage:
    pip install trimesh            # optional, only needed for the OBJ -> STL conversion
    python tts_model_extractor.py                 # uses the most recently modified mod
    python tts_model_extractor.py 1234567890      # a specific workshop ID
    python tts_model_extractor.py path/to/mod.json
"""
import json
import re
import shutil
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

try:
    import trimesh
except ImportError:
    trimesh = None

CANDIDATES = [
    Path.home() / "Documents" / "My Games" / "Tabletop Simulator" / "Mods",  # Windows
    Path.home() / "OneDrive" / "Documents" / "My Games" / "Tabletop Simulator" / "Mods",  # Windows + OneDrive
    Path.home() / "OneDrive" / "Belgeler" / "My Games" / "Tabletop Simulator" / "Mods",   # Turkish OneDrive
    Path("C:/Program Files (x86)/Steam/steamapps/common/Tabletop Simulator/Tabletop Simulator_Data/Mods"),  # "Game Data" setting
    Path("C:/Program Files/Steam/steamapps/common/Tabletop Simulator/Tabletop Simulator_Data/Mods"),
    Path.home() / "Library" / "Tabletop Simulator" / "Mods",                 # macOS
    Path.home() / ".local" / "share" / "Tabletop Simulator" / "Mods",        # Linux
]
# You can also point the script at your Mods folder directly:  set TTS_MODS=D:\path\to\Mods
import os
if os.environ.get("TTS_MODS"):
    CANDIDATES.insert(0, Path(os.environ["TTS_MODS"]))
MODS = next((p for p in CANDIDATES if (p / "Workshop").exists()), None)
if MODS is None:
    sys.exit("Couldn't find the Tabletop Simulator Mods folder. Find it (search for WorkshopFileInfos.json), then run:  set TTS_MODS=<that Mods folder>")

FOLDERS = {
    "model": ("Models", "Models Raw"),
    "image": ("Images", "Images Raw"),
    "bundle": ("Assetbundles",),
}
DEFAULT_EXT = {"model": ".obj", "image": ".png", "bundle": ".unity3d"}


def pick_mod_json():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        p = Path(arg)
        if p.suffix == ".json" and p.exists():
            return p
        p = MODS / "Workshop" / f"{arg}.json"
        if p.exists():
            return p
        sys.exit(f"Couldn't find mod: {arg}")
    files = sorted((MODS / "Workshop").glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    files = [f for f in files if f.name != "WorkshopFileInfos.json"]
    if not files:
        sys.exit("No workshop mods found.")
    return files[0]


def safe(name):
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", str(name)).strip()
    return name[:120] or "unnamed"


OLD_STEAM = re.compile(r"^https?://(cloud-3\.steamusercontent\.com|steamusercontent-a\.akamaihd\.net|steamuserimages-a\.akamaihd\.net)/", re.I)


def url_variants(url):
    """Old Steam CDN links no longer work; TTS rewrites them to the new host. Try both."""
    new = OLD_STEAM.sub("https://steamusercontent-a.akamaihd.net/", url)
    return [new, url] if new != url else [url]


def fetch(url, kind, dest_base):
    """Copy from the TTS cache, or download if not cached. Returns the saved path or None."""
    if not url:
        return None
    for u in url_variants(url):
        key = re.sub(r"[^A-Za-z0-9]", "", u)
        for folder in FOLDERS[kind]:
            d = MODS / folder
            if not d.exists():
                continue
            for f in d.glob(key + "*"):
                if f.stem == key or f.name == key:
                    ext = f.suffix or DEFAULT_EXT[kind]
                    dest = dest_base.with_suffix(ext)
                    shutil.copyfile(f, dest)
                    return dest
    print(f"    downloading: {url_variants(url)[0]}")
    err = None
    for u in url_variants(url):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            dest = dest_base.with_suffix(DEFAULT_EXT[kind])
            dest.write_bytes(data)
            return dest
        except Exception as e:
            err = e
    print(f"    failed: {err}")
    return None


def walk(obj, found):
    if isinstance(obj, dict):
        name = obj.get("Nickname") or obj.get("Name") or "unnamed"
        if isinstance(obj.get("CustomMesh"), dict):
            found["model"].append((name, obj["CustomMesh"]))
        if isinstance(obj.get("CustomAssetbundle"), dict):
            found["bundle"].append((name, obj["CustomAssetbundle"]))
        if isinstance(obj.get("CustomImage"), dict):
            found["image"].append((name, obj["CustomImage"]))
        for v in obj.values():
            walk(v, found)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, found)


def unique(path_base, used):
    key = str(path_base)
    used[key] += 1
    return path_base if used[key] == 1 else path_base.with_name(f"{path_base.name}_{used[key]}")


def main():
    mod_path = pick_mod_json()
    data = json.loads(mod_path.read_text(encoding="utf-8"))
    title = data.get("SaveName") or mod_path.stem
    print(f"Mod: {title}")

    found = defaultdict(list)
    walk(data, found)

    root = Path.cwd() / f"assets_{safe(title)}"
    dirs = {k: root / k for k in ("models", "stl", "bundles", "boards_tiles_tokens")}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    used, seen = defaultdict(int), set()
    counts = defaultdict(int)

    # --- OBJ models -> copy + STL
    print(f"\nModels: {len(found['model'])} found")
    for name, m in found["model"]:
        url = m.get("MeshURL", "")
        if not url or url in seen:
            continue
        seen.add(url)
        base = unique(dirs["models"] / safe(name), used)
        obj_path = fetch(url, "model", base)
        if not obj_path:
            continue
        fetch(m.get("DiffuseURL", ""), "image", base.with_name(base.name + "_texture"))
        counts["models"] += 1
        if trimesh:
            try:
                mesh = trimesh.load(obj_path, force="mesh")
                mesh.export(dirs["stl"] / f"{base.name}.stl")
                counts["stl"] += 1
            except Exception as e:
                print(f"    STL conversion failed for {base.name}: {e}")

    # --- Asset bundles
    print(f"Asset bundles: {len(found['bundle'])} found")
    for name, b in found["bundle"]:
        url = b.get("AssetbundleURL", "")
        if not url or url in seen:
            continue
        seen.add(url)
        if fetch(url, "bundle", unique(dirs["bundles"] / safe(name), used)):
            counts["bundles"] += 1

    # --- Boards / tiles / tokens
    print(f"Boards/tiles/tokens: {len(found['image'])} found")
    for name, ci in found["image"]:
        for field, suffix in (("ImageURL", ""), ("ImageSecondaryURL", "_back")):
            url = ci.get(field, "")
            if not url or url in seen:
                continue
            seen.add(url)
            if fetch(url, "image", unique(dirs["boards_tiles_tokens"] / (safe(name) + suffix), used)):
                counts["images"] += 1

    print(f"\nDone -> {root}")
    print(f"  OBJ models: {counts['models']}   STL files: {counts['stl']}"
          f"{'' if trimesh else '  (pip install trimesh to get STLs)'}")
    print(f"  Asset bundles: {counts['bundles']}   Boards/tiles/tokens: {counts['images']}")
    if counts["bundles"]:
        print("  Open the .unity3d files with AssetRipper to export their meshes.")


if __name__ == "__main__":
    main()
