"""
Tabletop Simulator card extractor.

Reads a TTS mod's JSON, finds every card, slices it out of its sprite sheet
(using the local cache, or downloading the sheet if it isn't cached),
and saves each card as its own PNG, named after the card's in-game name.

Usage:
    pip install pillow
    python tts_card_extractor.py                 # uses the most recently modified mod
    python tts_card_extractor.py 1234567890      # a specific workshop ID
    python tts_card_extractor.py path/to/mod.json
"""
import io
import json
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

from PIL import Image

# --- locate the TTS Mods folder ---------------------------------------------
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


OLD_STEAM = re.compile(r"^https?://(cloud-3\.steamusercontent\.com|steamusercontent-a\.akamaihd\.net|steamuserimages-a\.akamaihd\.net)/", re.I)


def url_variants(url):
    """Old Steam CDN links no longer work; TTS rewrites them to the new host. Try both."""
    new = OLD_STEAM.sub("https://steamusercontent-a.akamaihd.net/", url)
    return [new, url] if new != url else [url]


def find_cached(url):
    """TTS names cached files after the URL with all non-alphanumerics removed."""
    for u in url_variants(url):
        key = re.sub(r"[^A-Za-z0-9]", "", u)
        for folder in ("Images", "Images Raw"):
            d = MODS / folder
            if not d.exists():
                continue
            for f in d.glob(key + "*"):
                if f.stem == key or f.name == key:
                    return f
    return None


def load_sheet(url):
    cached = find_cached(url)
    if cached:
        return Image.open(cached).convert("RGBA")
    print(f"  not cached, downloading: {url_variants(url)[0]}")
    err = None
    for u in url_variants(url):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return Image.open(io.BytesIO(r.read())).convert("RGBA")
        except Exception as e:
            err = e
    raise err


def walk(obj, out):
    """Collect (deck_info, index_on_sheet, nickname) for every card object."""
    if isinstance(obj, dict):
        if str(obj.get("Name", "")).startswith("Card") and "CardID" in obj and "CustomDeck" in obj:
            cid = int(obj["CardID"])
            info = obj["CustomDeck"].get(str(cid // 100))
            if info:
                out.append((info, cid % 100, obj.get("Nickname", "") or ""))
        for v in obj.values():
            walk(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, out)


def safe(name):
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", name).strip()
    return name[:120] or "card"


def main():
    mod_path = pick_mod_json()
    data = json.loads(mod_path.read_text(encoding="utf-8"))
    title = data.get("SaveName") or mod_path.stem
    print(f"Mod: {title}")

    cards = []
    walk(data, cards)
    if not cards:
        sys.exit("No custom cards found in this mod.")

    # group by sheet, dedupe identical copies
    sheets = defaultdict(dict)  # face_url -> {index: (nickname, info)}
    for info, idx, nick in cards:
        url = info.get("FaceURL", "")
        if url and idx not in sheets[url]:
            sheets[url][idx] = (nick, info)

    out_dir = Path.cwd() / f"cards_{safe(title)}"
    out_dir.mkdir(exist_ok=True)
    used = defaultdict(int)
    backs_saved = set()
    total = 0

    for n, (url, entries) in enumerate(sheets.items(), 1):
        print(f"Sheet {n}/{len(sheets)}: {len(entries)} cards")
        try:
            sheet = load_sheet(url)
        except Exception as e:
            print(f"  skipped ({e})")
            continue
        any_info = next(iter(entries.values()))[1]
        cols = int(any_info.get("NumWidth", 10))
        rows = int(any_info.get("NumHeight", 7))
        cw, ch = sheet.width / cols, sheet.height / rows

        for idx, (nick, info) in sorted(entries.items()):
            c, r = idx % cols, idx // cols
            box = (round(c * cw), round(r * ch), round((c + 1) * cw), round((r + 1) * ch))
            base = safe(nick) if nick else f"sheet{n:02d}_{idx:02d}"
            used[base] += 1
            name = base if used[base] == 1 else f"{base}_{used[base]}"
            sheet.crop(box).save(out_dir / f"{name}.png")
            total += 1

        # save the card back once per sheet (if it's a single shared back)
        back = any_info.get("BackURL")
        if back and back not in backs_saved and not any_info.get("UniqueBack", False):
            try:
                load_sheet(back).save(out_dir / f"_back_sheet{n:02d}.png")
                backs_saved.add(back)
            except Exception:
                pass

    print(f"\nDone: {total} cards saved to {out_dir}")


if __name__ == "__main__":
    main()
