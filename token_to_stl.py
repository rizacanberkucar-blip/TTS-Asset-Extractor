"""
Token image -> 3D printable STL.

Turns flat token images (e.g. the ones in boards_tiles_tokens/ from the TTS extractor)
into printable tokens. The token's outline comes from the PNG's transparency, so a round
or shaped token becomes a round or shaped part.

Three modes:
  color    Multi-color for the AMS: one base part + one top-layer part per color.
           Load all STLs of a token together in Bambu Studio as ONE object with parts,
           then assign a filament to each part.
  relief   Single color: the image becomes raised detail (light = high) on a base.
  sticker  A blank with a shallow pocket on top, plus a 300 DPI PNG of the art sized
           to that pocket, for printing on sticker paper and cutting on a Cameo
           (use Silhouette Studio's trace + print & cut).

Usage:
    pip install numpy pillow
    python token_to_stl.py boards_tiles_tokens/ --mode color --size 25
    python token_to_stl.py "Souls Token.png" --mode relief --size 30 --invert
    python token_to_stl.py boards_tiles_tokens/ --mode sticker --size 25 --circle

Options:
    --size     longest side of the token in mm (default 25)
    --res      grid resolution in mm (default 0.1; smaller = finer detail, bigger files)
    --circle   clip to a circle (for square images without transparency)
    --base     base thickness in mm (color: 2.4, relief: 2.0)
    --top      color mode: thickness of the colored top layer (default 0.6)
    --colors   color mode: number of top colors (default 4)
    --relief   relief mode: height of the raised detail (default 1.0)
    --invert   relief mode: dark = high instead of light = high
    --thick    sticker mode: blank thickness (default 3.0)
    --depth    sticker mode: pocket depth (default 0.3)
    --inset    sticker mode: rim width around the pocket (default 0.6)
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


# ---------------------------------------------------------------- mesh building
def _clean_diagonals(mask):
    """Fill pixels that only touch diagonally, so the mesh stays manifold."""
    m = mask.copy()
    while True:
        a, b, c, d = m[:-1, :-1], m[:-1, 1:], m[1:, :-1], m[1:, 1:]
        bad1 = a & d & ~b & ~c
        bad2 = b & c & ~a & ~d
        if not (bad1.any() or bad2.any()):
            return m
        jj, ii = np.nonzero(bad1)
        m[jj, ii + 1] = True
        jj, ii = np.nonzero(bad2)
        m[jj, ii] = True


def column_mesh(hi, mask, lo, s):
    """Watertight solid: smooth heightfield top (z=hi over mask), flat bottom at z=lo."""
    mask = _clean_diagonals(mask)
    R, C = mask.shape
    jj, ii = np.nonzero(mask)
    if len(jj) == 0:
        return np.zeros((0, 3, 3))
    hi = np.broadcast_to(np.asarray(hi, dtype=np.float64), mask.shape)
    # vertex heights = mean of the masked pixels around each vertex
    hm = np.pad(np.where(mask, hi, 0.0), 1)
    cm = np.pad(mask.astype(np.float64), 1)
    tot = hm[:-1, :-1] + hm[:-1, 1:] + hm[1:, :-1] + hm[1:, 1:]
    cnt = cm[:-1, :-1] + cm[:-1, 1:] + cm[1:, :-1] + cm[1:, 1:]
    V = tot / np.maximum(cnt, 1)  # shape (R+1, C+1)

    def vx(r, c, top):
        z = V[r, c] if top else np.full(len(r), float(lo))
        return np.stack([c * s, (R - r) * s, z], axis=-1)

    TL = lambda t: vx(jj, ii, t)
    TR = lambda t: vx(jj, ii + 1, t)
    BR = lambda t: vx(jj + 1, ii + 1, t)
    BL = lambda t: vx(jj + 1, ii, t)

    tris = [
        np.stack([BL(1), BR(1), TR(1)], 1), np.stack([BL(1), TR(1), TL(1)], 1),  # top
        np.stack([BL(0), TR(0), BR(0)], 1), np.stack([BL(0), TL(0), TR(0)], 1),  # bottom
    ]
    mp = np.pad(mask, 1)
    walls = {
        "E": (~mp[jj + 1, ii + 2], BR, TR),
        "W": (~mp[jj + 1, ii], TL, BL),
        "N": (~mp[jj, ii + 1], TR, TL),
        "S": (~mp[jj + 2, ii + 1], BL, BR),
    }
    for sel, A, B in walls.values():
        if not sel.any():
            continue
        a0, b0, b1, a1 = A(0)[sel], B(0)[sel], B(1)[sel], A(1)[sel]
        tris.append(np.stack([a0, b0, b1], 1))
        tris.append(np.stack([a0, b1, a1], 1))
    return np.concatenate(tris)


def write_stl(path, tris):
    tris = tris.astype(np.float32)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, tris
    with open(path, "wb") as f:
        f.write(b"token_to_stl".ljust(80, b" "))
        f.write(np.uint32(len(tris)).tobytes())
        f.write(rec.tobytes())


# ---------------------------------------------------------------- image prep
def load_token(path, size_mm, res, circle):
    im = Image.open(path).convert("RGBA")
    alpha = np.array(im)[:, :, 3]
    has_alpha = alpha.min() < 250
    if has_alpha:
        ys, xs = np.nonzero(alpha > 128)
        if len(ys) == 0:
            return None
        im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))

    w, h = im.size
    scale = size_mm / max(w, h)
    W, H = max(1, round(w * scale / res)), max(1, round(h * scale / res))
    small = im.resize((W, H), Image.LANCZOS)
    arr = np.array(small)
    mask = arr[:, :, 3] > 128 if has_alpha else np.ones((H, W), bool)
    if circle:
        yy, xx = np.mgrid[0:H, 0:W]
        cy, cx, r = (H - 1) / 2, (W - 1) / 2, min(W, H) / 2
        mask &= (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r
    return im, arr[:, :, :3], mask


def erode(mask, px):
    if px <= 0:
        return mask
    img = Image.fromarray((mask * 255).astype(np.uint8))
    for _ in range(px):
        img = img.filter(ImageFilter.MinFilter(3))
    return np.array(img) > 128


# ---------------------------------------------------------------- modes
def do_relief(rgb, mask, a, out):
    g = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]) / 255.0
    g = np.array(Image.fromarray((g * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))) / 255.0
    if a.invert:
        g = 1 - g
    base = 2.0 if a.base is None else a.base
    write_stl(out / "token.stl", column_mesh(base + a.relief * g, mask, 0.0, a.res))
    return ["token.stl"]


def do_color(rgb, mask, a, out):
    base = 2.4 if a.base is None else a.base
    fill = np.median(rgb[mask], axis=0).astype(np.uint8)
    rgb = rgb.copy()
    rgb[~mask] = fill
    q = Image.fromarray(rgb).quantize(colors=a.colors, method=Image.Quantize.MEDIANCUT)
    pal = np.array(q.getpalette()[: 3 * 256]).reshape(-1, 3)
    raw = np.array(q)
    # merge near-identical palette entries (median cut can split one color in two)
    counts = np.bincount(raw[mask], minlength=256)
    lut = np.arange(256)
    kept = []
    for k in np.argsort(-counts):
        if counts[k] == 0:
            break
        near = [j for j in kept if np.abs(pal[k] - pal[j]).sum() < 45]
        if near:
            lut[k] = near[0]
        else:
            kept.append(k)
    idx = np.array(Image.fromarray(lut[raw].astype(np.uint8)).filter(ImageFilter.ModeFilter(5)))
    files = []
    write_stl(out / "0_base.stl", column_mesh(np.full(mask.shape, base), mask, 0.0, a.res))
    files.append("0_base.stl")
    for k in np.unique(idx[mask]):
        region = mask & (idx == k)
        if region.sum() < 4:
            continue
        hexc = "{:02x}{:02x}{:02x}".format(*pal[k])
        name = f"{len(files)}_color_{hexc}.stl"
        write_stl(out / name, column_mesh(np.full(mask.shape, base + a.top), region, base, a.res))
        files.append(name)
    return files


def do_sticker(full_im, mask, a, out):
    inset_px = max(1, round(a.inset / a.res))
    inner = erode(mask, inset_px)
    hi = np.where(inner, a.thick - a.depth, a.thick)
    write_stl(out / "token_blank.stl", column_mesh(hi, mask, 0.0, a.res))

    # sticker art at 300 DPI, exactly the size of the pocket
    H, W = mask.shape
    px_w, px_h = round(W * a.res / 25.4 * 300), round(H * a.res / 25.4 * 300)
    art = full_im.convert("RGBA").resize((px_w, px_h), Image.LANCZOS)
    m = Image.fromarray((inner * 255).astype(np.uint8)).resize((px_w, px_h), Image.BILINEAR)
    art.putalpha(m)
    art.save(out / "sticker_300dpi.png", dpi=(300, 300))
    return ["token_blank.stl", "sticker_300dpi.png"]


# ---------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("inputs", nargs="+")
    p.add_argument("--mode", choices=["color", "relief", "sticker"], default="color")
    p.add_argument("--size", type=float, default=25.0)
    p.add_argument("--res", type=float, default=0.1)
    p.add_argument("--circle", action="store_true")
    p.add_argument("--base", type=float, default=None)
    p.add_argument("--top", type=float, default=0.6)
    p.add_argument("--colors", type=int, default=4)
    p.add_argument("--relief", type=float, default=1.0)
    p.add_argument("--invert", action="store_true")
    p.add_argument("--thick", type=float, default=3.0)
    p.add_argument("--depth", type=float, default=0.3)
    p.add_argument("--inset", type=float, default=0.6)
    p.add_argument("--out", default="tokens_3d")
    a = p.parse_args()

    files = []
    for inp in a.inputs:
        ip = Path(inp)
        if ip.is_dir():
            files += sorted(f for f in ip.iterdir() if f.suffix.lower() in EXTS)
        elif ip.exists():
            files.append(ip)
    if not files:
        sys.exit("No images found.")

    root = Path(a.out)
    for f in files:
        loaded = load_token(f, a.size, a.res, a.circle)
        if loaded is None:
            print(f"skip (empty): {f.name}")
            continue
        full_im, rgb, mask = loaded
        out = root / f.stem
        out.mkdir(parents=True, exist_ok=True)
        if a.mode == "relief":
            made = do_relief(rgb, mask, a, out)
        elif a.mode == "color":
            made = do_color(rgb, mask, a, out)
        else:
            made = do_sticker(full_im, mask, a, out)
        print(f"{f.name}: {', '.join(made)}")
    print(f"\nDone -> {root.resolve()}")


if __name__ == "__main__":
    main()
