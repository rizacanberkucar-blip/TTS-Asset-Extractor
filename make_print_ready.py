"""
Make print-ready images: resizes the extracted cards, tokens and tiles to their real
physical size at 300 DPI, so they print at the right size with "Actual size / 100%".

Cards are sorted into standard and mini by their shape. Tokens and tiles are sized from
their scale on the TTS table, calibrated so that a TTS scale of 0.668 = 38.1 mm (one
Gloomhaven hex). Use --mm-per-scale to calibrate for a different game.

Usage (run inside the folder where you ran the extractors):
    python make_print_ready.py <workshop-id-or-mod.json>
    python make_print_ready.py 1301493206 --standard 63.5x88 --mini 44x68

Output: print_ready_300dpi/ with one folder per type, plus sizes.csv (width x height in mm).
"""
import argparse, json, re, sys, csv
from pathlib import Path
from collections import defaultdict
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

import os

def _size(txt):
    a, b = txt.lower().split("x")
    return float(a), float(b)

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("mod", help="workshop ID or path to the mod .json")
ap.add_argument("--export", default=".", help="folder containing cards_* and assets_* (default: current folder)")
ap.add_argument("--standard", type=_size, default=(63.5, 88.0), help="standard card size in mm (default 63.5x88)")
ap.add_argument("--mini", type=_size, default=(44.0, 68.0), help="mini card size in mm (default 44x68)")
ap.add_argument("--split", type=float, default=0.695, help="card short/long ratio above which a card counts as standard")
ap.add_argument("--mm-per-scale", type=float, default=57.0, help="mm of a token/tile's longest side per 1.0 of TTS scale")
ap.add_argument("--max-mm", type=float, default=600, help="skip images bigger than this (table backgrounds)")
args = ap.parse_args()

DPI = 300
STANDARD, MINI, MM_PER_SCALE = args.standard, args.mini, args.mm_per_scale

CANDIDATES = [
    Path.home() / "Documents" / "My Games" / "Tabletop Simulator" / "Mods",
    Path.home() / "OneDrive" / "Documents" / "My Games" / "Tabletop Simulator" / "Mods",
    Path.home() / "OneDrive" / "Belgeler" / "My Games" / "Tabletop Simulator" / "Mods",
    Path.home() / "Library" / "Tabletop Simulator" / "Mods",
    Path.home() / ".local" / "share" / "Tabletop Simulator" / "Mods",
]
if os.environ.get("TTS_MODS"):
    CANDIDATES.insert(0, Path(os.environ["TTS_MODS"]))
mod_json = Path(args.mod)
if not (mod_json.suffix == ".json" and mod_json.exists()):
    mod_json = next((p / "Workshop" / f"{args.mod}.json" for p in CANDIDATES
                     if (p / "Workshop" / f"{args.mod}.json").exists()), None)
    if mod_json is None:
        sys.exit(f"Couldn't find mod {args.mod}. Pass the path to its .json, or set TTS_MODS.")
export = Path(args.export)
out = export / "print_ready_300dpi"
rows = []

def save(src, dst, w_mm, h_mm):
    rows_add = (round(w_mm, 1), round(h_mm, 1))
    if dst.exists():
        rows.append((dst.relative_to(out).as_posix(), *rows_add)); return
    im = Image.open(src).convert("RGBA")
    dpi = DPI if max(w_mm, h_mm) <= 200 else 150      # big boards: 150 DPI is plenty
    p = lambda mm: max(1, round(mm / 25.4 * dpi))
    im = im.resize((p(w_mm), p(h_mm)), Image.LANCZOS, reducing_gap=2.0)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if im.getextrema()[3][0] == 255:
        im = im.convert("RGB")
    im.save(dst, dpi=(dpi, dpi), compress_level=1)
    rows.append((dst.relative_to(out).as_posix(), round(w_mm, 1), round(h_mm, 1)))

# ---- cards
for f in sorted(next(export.glob("cards_*")).glob("*.png")):
    w, h = Image.open(f).size
    ratio = min(w, h) / max(w, h)
    short, long_ = STANDARD if ratio >= args.split else MINI
    kind = (f"cards_standard_{STANDARD[0]:g}x{STANDARD[1]:g}mm" if ratio >= args.split
            else f"cards_mini_{MINI[0]:g}x{MINI[1]:g}mm")
    w_mm, h_mm = (long_, short) if w > h else (short, long_)
    save(f, out / kind / f.with_suffix(".png").name, w_mm, h_mm)

# ---- tokens / tiles (same naming as tts_model_extractor.py)
def safe(name):
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", str(name)).strip()
    return name[:120] or "unnamed"

data = json.loads(mod_json.read_text(encoding="utf-8"))
items = []
def walk(o):
    if isinstance(o, dict):
        if isinstance(o.get("CustomImage"), dict):
            items.append(o)
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)
walk(data)

src_dir = next(export.glob("assets_*")) / "boards_tiles_tokens"
files = {p.stem: p for p in src_dir.iterdir()}
used, seen = defaultdict(int), set()
for o in items:
    name = o.get("Nickname") or o.get("Name") or "unnamed"
    ci = o["CustomImage"]
    scale = float(o.get("Transform", {}).get("scaleX", 1.0))
    kind = "tokens" if o.get("Name", "").startswith("Custom_Token") else "tiles_boards"
    for field, suffix in (("ImageURL", ""), ("ImageSecondaryURL", "_back")):
        url = ci.get(field, "")
        if not url or url in seen:
            continue
        seen.add(url)
        stem = safe(name) + suffix
        key = str(src_dir / stem); used[key] += 1
        if used[key] > 1:
            stem = f"{stem}_{used[key]}"
        src = files.get(stem)
        if not src:
            continue
        w, h = Image.open(src).size
        long_mm = scale * MM_PER_SCALE
        if long_mm > args.max_mm:          # table backgrounds / play-area surfaces, not game pieces
            continue
        w_mm, h_mm = (long_mm, long_mm * h / w) if w >= h else (long_mm * w / h, long_mm)
        save(src, out / kind / f"{stem}.png", w_mm, h_mm)

with open(out / "sizes.csv", "w", newline="", encoding="utf-8") as fh:
    wr = csv.writer(fh); wr.writerow(["file", "width_mm", "height_mm"]); wr.writerows(rows)
counts = defaultdict(int)
for r in rows: counts[r[0].split("/")[0]] += 1
print(dict(counts))
