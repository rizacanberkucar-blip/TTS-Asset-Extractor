# TTS Asset Extractor

Pull the cards, miniatures, terrain, tokens and boards out of a **Tabletop Simulator** mod, and turn them into files you can **3D print** (STL) and **paper print** at real size (300 DPI).

It works on any TTS mod. It was built and tested on *Dark Souls: The Board Game* and *Gloomhaven*.

| What you get | From | Tool |
|---|---|---|
| Every card as its own PNG, named after the card | card sprite sheets | `tts_card_extractor.py` |
| OBJ models, textures, asset bundles, board and token images | the mod's 3D and image objects | `tts_model_extractor.py` |
| Printable STL figures and terrain, upright and in mm | OBJ models | `obj_to_stl.py` |
| Printable STL figures from Unity asset bundles | `.unity3d` bundles | `bundle_to_stl.py` |
| Printable tokens: multi-color (AMS), relief, or sticker blanks | token images | `token_to_stl.py` |
| Cards, tokens and tiles resized to real size at 300 DPI | everything above | `make_print_ready.py` |

> **Please respect the creators.** Game art, cards and sculpts belong to their publishers. Use what you extract for your **own personal copies** of games you play. Don't sell it or share it.

---

## Contents

1. [Install (one time)](#1-install-one-time)
2. [Find your mod](#2-find-your-mod)
3. [Extract everything](#3-extract-everything)
4. [Make 3D-printable figures and terrain](#4-make-3d-printable-figures-and-terrain)
5. [Make 3D-printable tokens](#5-make-3d-printable-tokens)
6. [Make print-ready cards and tokens](#6-make-print-ready-cards-and-tokens)
7. [Printing tips](#7-printing-tips)
8. [Troubleshooting](#8-troubleshooting)
9. [Tool reference](#9-tool-reference)

---

## 1. Install (one time)

### Python

1. Download Python from **[python.org/downloads](https://www.python.org/downloads/)** and run the installer.
2. On the first screen, **tick "Add python.exe to PATH"** before clicking *Install Now*. This is the step people usually miss.

### This toolkit

Click the green **Code** button at the top of this page, choose **Download ZIP**, and unzip it somewhere easy, for example `C:\TTS-Extractor`.

Or with git:

```
git clone https://github.com/<your-username>/tts-asset-extractor.git
```

### Libraries

Open a terminal in the toolkit folder. In File Explorer, open the folder, click the address bar, type `cmd`, and press Enter. Then run:

```
py -m pip install -r requirements.txt
```

On macOS or Linux, use `python3` instead of `py` everywhere in this guide.

---

## 2. Find your mod

### Load it in TTS once

Subscribe to the mod on the Steam Workshop, then **open it in Tabletop Simulator once**. TTS copies the mod into its `Mods` folder when you load it.

### Get its workshop ID

The ID is the number in the mod's Steam Workshop address:

```
https://steamcommunity.com/sharedfiles/filedetails/?id=1301493206
                                                       ^^^^^^^^^^
```

If you don't pass an ID, the scripts use **the mod you opened most recently**.

### Where TTS keeps mods

The scripts look in all of these places automatically:

| Setup | Folder |
|---|---|
| Windows (default) | `C:\Users\<you>\Documents\My Games\Tabletop Simulator\Mods` |
| Windows with OneDrive | `C:\Users\<you>\OneDrive\Documents\My Games\Tabletop Simulator\Mods` |
| TTS set to "Game Data" | `C:\Program Files (x86)\Steam\steamapps\common\Tabletop Simulator\Tabletop Simulator_Data\Mods` |
| macOS | `~/Library/Tabletop Simulator/Mods` |
| Linux | `~/.local/share/Tabletop Simulator/Mods` |

To check which one your TTS uses, open TTS and go to **Menu → Configuration → General → Mod Save Location**.

If your folder is somewhere else, find it by searching your PC for `WorkshopFileInfos.json`. That file sits inside `Mods\Workshop`. Then tell the scripts where the folder is:

```
set TTS_MODS=D:\Games\Tabletop Simulator\Mods
```

In PowerShell, use `$env:TTS_MODS="D:\Games\Tabletop Simulator\Mods"` instead.

---

## 3. Extract everything

Make a folder for the game's files, open a terminal in it, and run both extractors. Replace `1301493206` with your mod's ID, and `C:\TTS-Extractor` with wherever you unzipped the toolkit.

```
mkdir "C:\Exports\Gloomhaven"
cd "C:\Exports\Gloomhaven"

py C:\TTS-Extractor\tools\tts_card_extractor.py 1301493206
py C:\TTS-Extractor\tools\tts_model_extractor.py 1301493206
```

> **Paths with spaces need quotes.** If you type `cd Documents\My Games\...` in PowerShell, you'll get *"A positional parameter cannot be found"*. Use `cd "Documents\My Games\..."` instead.

When it finishes, you'll have:

```
cards_<mod name>/            every card as a PNG, plus card backs (_back_sheetNN.png)
assets_<mod name>/
  models/                    original .obj models and their textures
  stl/                       raw STL copies of the OBJ models (not yet oriented or scaled)
  bundles/                   .unity3d asset bundles (often the painted miniatures)
  boards_tiles_tokens/       boards, tiles and tokens as images
```

**About downloads:** the scripts use TTS's local cache first. Anything that isn't cached, such as items still packed in bags, is downloaded straight from the mod's links. Old Steam links (`cloud-3.steamusercontent.com`) no longer work, so the scripts rewrite them to Steam's current address automatically, the same way TTS does.

Big mods take a while. Gloomhaven has 143 card sheets, 733 models and about 1,900 images.

---

## 4. Make 3D-printable figures and terrain

Mods store their miniatures in one of two ways. Run whichever applies, or both.

### OBJ models (`assets_…/models`)

```
py C:\TTS-Extractor\tools\obj_to_stl.py "assets_<mod name>\models" "assets_<mod name>\printable" --scale 18
```

- This stands every model upright, scales it to millimetres and centres it on the bed.
- It sorts models into `figures\` and `terrain\`. Models whose name contains `(3D)` count as terrain; change that with `--terrain`.
- It skips flat or simple models automatically: map tiles, cardboard standees, mats and UI pieces.

### Asset bundles (`assets_…/bundles`)

```
py C:\TTS-Extractor\tools\bundle_to_stl.py "assets_<mod name>\bundles" "assets_<mod name>\figures" --scale 10
```

- This reads each Unity bundle, puts the figure, base and weapons in their correct positions, and exports `stl\` and `obj\` files.
- It's safe to stop and re-run: finished bundles are skipped.

### Scale

TTS has no fixed real-world unit, so the scale depends on the mod. These values were measured:

| Game | Tool | `--scale` | Result |
|---|---|---|---|
| Gloomhaven | `obj_to_stl.py` | `18` | hero base about 26 mm, one hex about 31 mm |
| Dark Souls: The Board Game | `bundle_to_stl.py` | `10` | hero base about 30 mm, boss base 75 mm |

For a new game, convert one figure, measure its base in your slicer, and adjust the scale. In the Dark Souls mod, figures from different mod authors came out at different sizes, so you may need to rescale some figures individually in your slicer.

---

## 5. Make 3D-printable tokens

`token_to_stl.py` turns token images into printable tokens. The token's outline comes from the image's transparency, so shaped tokens keep their shape.

| Mode | What it makes | Best for |
|---|---|---|
| `color` (default) | one base part plus one top-layer part per color | multi-color printers (Bambu AMS, Prusa MMU and others) |
| `relief` | one solid part, with the art as raised detail (light areas high) | single color, painted or dry-brushed |
| `sticker` | a blank with a shallow pocket, plus a 300 DPI sticker PNG sized to fit it | full art detail, using a printer and a cutting machine |

```
py C:\TTS-Extractor\tools\token_to_stl.py "assets_<mod name>\boards_tiles_tokens" --mode color --size 25
py C:\TTS-Extractor\tools\token_to_stl.py "Poison.png" "Stun.png" --mode relief --size 20
py C:\TTS-Extractor\tools\token_to_stl.py "assets_<mod name>\boards_tiles_tokens" --mode sticker --size 25 --circle
```

The results go to `tokens_3d\<token name>\`. Common options:

| Option | Meaning | Default |
|---|---|---|
| `--size` | longest side of the token in mm | 25 |
| `--circle` | clip to a circle (for square images of round tokens) | off |
| `--colors` | number of top colors in `color` mode | 4 |
| `--base` / `--top` | base and top-layer thickness in mm (`color` mode) | 2.4 / 0.6 |
| `--relief` / `--invert` | raised detail height in mm; `--invert` makes dark areas high instead | 1.0 |
| `--thick` / `--depth` / `--inset` | blank thickness, pocket depth and rim width in mm (`sticker` mode) | 3.0 / 0.3 / 0.6 |
| `--res` | mesh resolution in mm (smaller gives finer detail and bigger files) | 0.1 |

**Loading a color token in Bambu Studio:** select all the STL files from one token folder, drag them in together, and click **Yes** when asked to load them as a single object with multiple parts. Then assign a filament to each part. The color's hex code is in each filename.

**Choosing a mode:** simple icon-style tokens look great in `color` mode. Busy, painted art loses detail when reduced to a few colors, so use `sticker` mode for those.

---

## 6. Make print-ready cards and tokens

`make_print_ready.py` resizes every card, token and tile to its real size at 300 DPI. Run it in the same folder as the extractors:

```
py C:\TTS-Extractor\tools\make_print_ready.py 1301493206
```

The output goes to `print_ready_300dpi\`:

```
cards_standard_63.5x88mm/
cards_mini_44x68mm/
tokens/
tiles_boards/
sizes.csv                 every file with its width × height in mm
```

How the sizes are decided:

- **Cards** are sorted into standard and mini by their shape. The defaults fit Gloomhaven and most games: standard 63.5 × 88 mm and mini 44 × 68 mm. Change them with `--standard 63x88 --mini 41x63`.
- **Tokens and tiles** are sized from their scale on the TTS table. The default is calibrated so that one Gloomhaven hex is 38.1 mm (1.5"), which also makes condition tokens about 14–20 mm. For another game, measure one real component and adjust `--mm-per-scale`.
- Images over 200 mm are saved at 150 DPI, which keeps them sharp and the files manageable. Images over 600 mm (`--max-mm`) are skipped, because those are table backgrounds rather than game pieces.

Note that player mats and some boards are often enlarged in TTS for readability, so their computed size can be larger than the physical component. Print those scaled to fit A4 or A3.

---

## 7. Printing tips

### Paper (cards, tokens, stickers)
- The files have their DPI saved in them, so in the print dialog choose **"Actual size" or 100% scale**. Don't use "Fit to page", or everything will be resized.
- Stickers for sticker-mode tokens: print `sticker_300dpi.png` on sticker paper, then cut it with a Silhouette or Cricut using *trace* and *print & cut*.

### 3D (figures, terrain, tokens)
- Game meshes are made for the screen, so many aren't watertight. Let your slicer repair them when it asks; Bambu Studio and PrusaSlicer both do this automatically.
- Detailed figures print best on resin, or on FDM with a 0.2 mm nozzle and 0.08–0.12 mm layers, using tree supports.
- Models come out at the scale you chose. Check one against a real component before printing a whole set.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `'py' is not recognized` | Python isn't on PATH. Reinstall it and tick **"Add python.exe to PATH"**. |
| `A positional parameter cannot be found` (PowerShell) | Put paths with spaces in quotes: `cd "My Games\Tabletop Simulator"`. |
| `Couldn't find the Tabletop Simulator Mods folder` | Search your PC for `WorkshopFileInfos.json`, then `set TTS_MODS=<the Mods folder>`. See [step 2](#2-find-your-mod). |
| The wrong mod was extracted | Pass the workshop ID explicitly, or open the right mod in TTS last. |
| `HTTP Error 403` on `cloud-3.steamusercontent.com` | You're using an old copy of the scripts. Download the latest version; current versions rewrite these links. |
| Many sheets are `skipped`, or only cached items come out | Your network blocks the image hosts. Run on a normal home connection, or load the mod in TTS and spawn the items so they get cached. |
| `No module named …` | Run `py -m pip install -r requirements.txt` again. |
| A figure is tiny or huge | Change `--scale` (see [Scale](#scale)), or resize it in your slicer. |
| A figure is lying down or upside down | Rotate it in your slicer. This can happen when a mod author exported it oddly. |
| The STL has holes or errors in the slicer | Use the slicer's repair function, or Blender's *3D Print Toolbox*. |
| An asset bundle gives `no mesh` | That bundle holds only textures or effects, with nothing to print. |

---

## 9. Tool reference

Every tool prints its full help with `-h`, for example `py tools\token_to_stl.py -h`.

| Tool | Input | Output | Needs |
|---|---|---|---|
| `tts_card_extractor.py [id]` | mod JSON + card sheets | `cards_<mod>/` | Pillow |
| `tts_model_extractor.py [id]` | mod JSON + models, bundles, images | `assets_<mod>/` | (trimesh, optional) |
| `obj_to_stl.py <models> <out>` | `.obj` files | `<out>/figures`, `<out>/terrain` | trimesh, numpy |
| `bundle_to_stl.py <bundles> <out>` | `.unity3d` files | `<out>/stl`, `<out>/obj` | UnityPy, trimesh, numpy |
| `token_to_stl.py <images…>` | token PNG/JPG files | `tokens_3d/` | Pillow, numpy |
| `make_print_ready.py <id>` | `cards_*` + `assets_*` | `print_ready_300dpi/` | Pillow |

### How it works

- TTS stores a mod as one JSON file listing every object and the web address of each image, model and bundle. TTS caches downloaded files in `Mods\Images`, `Mods\Models` and `Mods\Assetbundles`, named after the address with the symbols removed. The extractors read the JSON, find each file in the cache or download it, and save it under a readable name.
- TTS cards are cut from sprite sheets: a grid of up to 10 × 7 cards per image. Each card stores its sheet and position, which is how the card extractor knows where to cut and what to call the file.
- Unity asset bundles are read with [UnityPy](https://github.com/K0lb3/UnityPy). Each part is placed using its transform, then the model is converted from Unity's left-handed, Y-up space to a slicer's Z-up space.

## License

The code is released under the [MIT License](LICENSE). This license covers the code only, not anything you extract with it.
