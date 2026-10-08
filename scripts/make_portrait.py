#!/usr/bin/env python3
"""
make_portrait.py
Converts photo.png -> ascii.svg with an infinite looping self-typing SMIL animation.
Supports both GitHub Light (#6e7681) and Dark (#c9d1d9) modes.
"""

import base64
import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from rembg import remove, new_session

ROOT = Path(__file__).resolve().parent.parent
PHOTO = ROOT / "photo.png"
OUT = ROOT / "ascii.svg"
FONT_PATH = ROOT / "scripts" / "fonts" / "ramp.woff2"

RAMP = " .`:-=+*cs#%@"     # bright/sparse -> dark/dense; leading space = blank
COLS = 90
CLAHE_CLIP = 3.0
CURVE = 1.7
ROW_RATIO = 0.48

CHAR_W = 7.74
FONT_SIZE = 12.9
LINE_H = 15
ROW_DELAY = 0.08
HOLD_DUR = 4.5
FADE_DUR = 0.6
PAUSE_DUR = 0.5


def process_image(path):
    src = Image.open(path).convert("RGBA")
    session = new_session("u2netp")
    cut = remove(src, session=session)
    alpha = np.array(cut.split()[-1])

    # Composite onto pure white so transparent background maps to index 0 (space)
    white = Image.new("RGBA", cut.size, (255, 255, 255, 255))
    gray = np.array(Image.alpha_composite(white, cut).convert("L"))

    # Bilateral filter for smooth skin while preserving edges
    gray = cv2.bilateralFilter(gray, 11, 50, 50)
    gray = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=(8, 8)).apply(gray)
    gray = (255.0 * (gray / 255.0) ** CURVE).astype("uint8")
    gray[alpha < 20] = 255

    w, h = cut.size
    rows = int(COLS * (h / w) * ROW_RATIO)
    resized = Image.fromarray(gray).resize((COLS, rows), Image.LANCZOS)
    px = list(resized.getdata())
    n = len(RAMP)

    lines = []
    for r in range(rows):
        line = "".join(
            RAMP[min(n - 1, int((1 - px[r * COLS + c] / 255.0) * n))]
            for c in range(COLS)
        ).rstrip()
        lines.append(line)

    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    return lines


def build_svg(lines):
    pad = 14
    N = len(lines)
    cols = COLS
    width = int(cols * CHAR_W + pad * 2)
    height = N * LINE_H + pad * 2

    typing_end = N * ROW_DELAY
    t_hold_end = typing_end + HOLD_DUR
    t_fade_end = t_hold_end + FADE_DUR
    cycle = round(t_fade_end + PAUSE_DUR, 2)

    k_hold = t_hold_end / cycle
    k_fade = t_fade_end / cycle

    b64_font = ""
    if FONT_PATH.exists():
        b64_font = base64.b64encode(FONT_PATH.read_bytes()).decode()

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="JBMono,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">'
    )
    svg.append('<style>')
    if b64_font:
        svg.append(
            f'@font-face{{font-family:JBMono;font-style:normal;font-weight:400;font-display:block;'
            f'src:url(data:font/woff2;base64,{b64_font}) format("woff2");}}'
        )
    svg.append('.a{fill:#6e7681;}')
    svg.append('@media(prefers-color-scheme:dark){.a{fill:#c9d1d9;}}')
    svg.append('</style>')

    # Master group fading out before restarting the cycle
    svg.append('<g id="portrait">')
    svg.append(
        f'<animate attributeName="opacity" dur="{cycle:.2f}s" repeatCount="indefinite" '
        f'keyTimes="0; {k_hold:.4f}; {k_fade:.4f}; 1" values="1; 1; 0; 0"/>'
    )

    for i, line in enumerate(lines):
        y = pad + i * LINE_H
        t_start = i * ROW_DELAY
        t_end = (i + 1) * ROW_DELAY
        w_line = max(len(line), 1) * CHAR_W
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        k_s = max(0.0, min(1.0, t_start / cycle))
        k_e = max(0.0, min(1.0, t_end / cycle))

        if i == 0:
            kt_w = f"0; {k_e:.4f}; {k_hold:.4f}; {k_fade:.4f}; 1"
            val_w = f"0; {w_line:.1f}; {w_line:.1f}; 0; 0"
        else:
            kt_w = f"0; {k_s:.4f}; {k_e:.4f}; {k_hold:.4f}; {k_fade:.4f}; 1"
            val_w = f"0; 0; {w_line:.1f}; {w_line:.1f}; 0; 0"

        svg.append(f'<clipPath id="c{i}"><rect x="{pad}" y="{y}" height="{LINE_H}" width="0">')
        svg.append(
            f'<animate attributeName="width" dur="{cycle:.2f}s" repeatCount="indefinite" '
            f'keyTimes="{kt_w}" values="{val_w}"/>'
        )
        svg.append('</rect></clipPath>')

        svg.append(
            f'<g clip-path="url(#c{i})"><text xml:space="preserve" x="{pad}" '
            f'y="{y + 11.2:.1f}" class="a" font-size="{FONT_SIZE}">{safe}</text></g>'
        )

        # Cursor block riding the typing edge
        kt_c_pos = f"0; {k_s:.4f}; {k_e:.4f}; 1"
        val_c_pos = f"{pad}; {pad}; {pad + w_line:.1f}; {pad + w_line:.1f}"
        kt_c_op = f"0; {k_s:.4f}; {k_e:.4f}"
        val_c_op = "0; 0.8; 0"

        svg.append(f'<rect y="{y + 1}" width="6" height="12" class="a" opacity="0">')
        svg.append(
            f'<animate attributeName="x" dur="{cycle:.2f}s" repeatCount="indefinite" '
            f'keyTimes="{kt_c_pos}" values="{val_c_pos}"/>'
        )
        svg.append(
            f'<animate attributeName="opacity" dur="{cycle:.2f}s" repeatCount="indefinite" '
            f'calcMode="discrete" keyTimes="{kt_c_op}" values="{val_c_op}"/>'
        )
        svg.append('</rect>')

    svg.append('</g>')
    svg.append('</svg>')
    return "\n".join(svg)


def main():
    if not PHOTO.exists():
        sys.exit(f"ERROR: {PHOTO} not found.")

    print(f"Processing {PHOTO} ...")
    lines = process_image(PHOTO)
    print(f"Generated {len(lines)} ASCII lines.")

    print("Generating animated looping SVG ...")
    svg_content = build_svg(lines)
    OUT.write_text(svg_content, encoding="utf-8")
    print(f"Saved -> {OUT} ({len(svg_content)} bytes)")


if __name__ == "__main__":
    main()
