"""Generate the app icon in all needed formats from one drawing.

Run once (or after tweaking the design):  python packaging/make_icon.py
Outputs to assets/: icon.png (1024), icon.ico (Windows), icon.icns.

Design: a centered stack of three books (a little "library") on a rounded
blue-gradient tile, with a soft shadow. Drawn at 4x supersampling for crisp
edges, then downscaled.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZE = 1024
SS = 4                      # supersampling factor
S = SIZE * SS               # working canvas size

# Palette
BG_TOP = (56, 120, 246)     # bright blue
BG_BOTTOM = (24, 58, 158)   # deep blue
SHADOW = (10, 30, 80)

BOOKS = [
    # (fill, edge)            bottom (widest) -> top (narrowest)
    ((239, 68, 68), (185, 40, 40)),     # red
    ((250, 204, 21), (200, 160, 12)),   # amber
    ((45, 212, 191), (24, 160, 145)),   # teal
]
PAGE = (248, 250, 252)      # cream page block on the spine side


def _rounded_gradient(size: int, radius: int) -> Image.Image:
    """Vertical-gradient rounded square as the app tile background."""
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        grad.putpixel(
            (0, y),
            tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)),
        )
    grad = grad.resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255
    )
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out


def _rrect(draw, box, radius, **kw):
    draw.rounded_rectangle(box, radius=radius, **kw)


def _draw_books(base: Image.Image) -> None:
    """A centered stack of three books, each a rounded bar with a page block."""
    # Draw the stack onto its own layer so we can add a shared soft shadow.
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    cx = S // 2
    book_h = int(S * 0.135)          # height of each book bar
    gap = int(S * 0.02)              # vertical gap between books
    widths = [int(S * 0.50), int(S * 0.44), int(S * 0.38)]
    stack_h = 3 * book_h + 2 * gap
    top0 = (S - stack_h) // 2        # vertically centered
    radius = int(book_h * 0.28)

    for i, (w, (fill, edge)) in enumerate(zip(widths, BOOKS)):
        # Slight alternating horizontal offset for a natural stacked look.
        offset = int(S * 0.015) * (1 if i % 2 == 0 else -1)
        left = cx - w // 2 + offset
        right = cx + w // 2 + offset
        top = top0 + i * (book_h + gap)
        bottom = top + book_h

        _rrect(d, [left, top, right, bottom], radius,
               fill=fill, outline=edge, width=max(1, SS * 2))

        # Page block on the left "fore-edge" of the book.
        pw = int(w * 0.16)
        pad = int(book_h * 0.18)
        _rrect(d, [left + pad, top + pad, left + pad + pw, bottom - pad],
               radius=int(radius * 0.5), fill=PAGE)

        # A thin highlight line along the top for a little depth.
        d.line([(left + radius, top + int(book_h * 0.22)),
                (right - radius, top + int(book_h * 0.22))],
               fill=tuple(min(255, c + 35) for c in fill),
               width=max(1, SS * 2))

    # Soft shadow beneath the whole stack.
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [cx - widths[0] // 2, top0 + int(S * 0.02),
         cx + widths[0] // 2, top0 + stack_h + int(S * 0.03)],
        radius=radius, fill=SHADOW + (110,),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(SS * 9))

    base.alpha_composite(shadow)
    base.alpha_composite(layer)


def build_base() -> Image.Image:
    img = _rounded_gradient(S, radius=int(S * 0.225))
    _draw_books(img)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def write_png(img: Image.Image) -> Path:
    p = ASSETS / "icon.png"
    img.save(p)
    return p


def write_ico(img: Image.Image) -> Path:
    p = ASSETS / "icon.ico"
    img.save(p, format="ICO",
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return p


def write_icns(img: Image.Image) -> Path | None:
    p = ASSETS / "icon.icns"
    try:
        img.resize((1024, 1024)).save(p, format="ICNS")
        return p
    except Exception as exc:  # noqa: BLE001
        print(f"  (skipped icon.icns: {exc}; run packaging/make_icns.sh on macOS)")
        return None


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    img = build_base()
    print("Wrote", write_png(img))
    print("Wrote", write_ico(img))
    icns = write_icns(img)
    if icns:
        print("Wrote", icns)


if __name__ == "__main__":
    main()
