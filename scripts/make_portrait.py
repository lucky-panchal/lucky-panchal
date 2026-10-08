"""
make_portrait.py
Converts photo.png -> ascii.svg with a self-typing SMIL animation.
Run: python scripts/make_portrait.py
"""

import sys, base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHOTO = ROOT / "photo.png"
OUT   = ROOT / "ascii.svg"

RAMP      = " .`:-=+*cs#%@"
COLS      = 90
W_PX      = 460
FONT_SIZE = 12.9
CHAR_W    = 7.74
CHAR_H    = FONT_SIZE * 1.2

def load_and_process(path):
    import numpy as np
    import cv2
    from PIL import Image
    from rembg import remove, new_session

    raw     = Image.open(path).convert("RGBA")
    session = new_session("u2netp")   # 4.7 MB model — fast download, great for portraits
    fg      = remove(raw, session=session)
    bg  = Image.new("RGBA", fg.size, (255,255,255,255))
    bg.alpha_composite(fg)
    img = bg.convert("RGB")

    rows = int(COLS * (img.height / img.width) * 0.48)
    img  = img.resize((COLS, rows))
    arr8 = np.array(img, dtype=np.uint8)

    arr8 = cv2.bilateralFilter(arr8, d=5, sigmaColor=50, sigmaSpace=50)
    gray = cv2.cvtColor(arr8, cv2.COLOR_RGB2GRAY).astype(np.float32)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    gray  = clahe.apply(gray.astype(np.uint8)).astype(np.float32)
    gray  = 255.0 * (gray/255.0) ** 1.7

    indices = (gray/255.0 * (len(RAMP)-1)).astype(int)
    chars   = [[ RAMP[i] for i in row] for row in indices]
    return chars, rows

def embed_font(p):
    data = p.read_bytes()
    b64  = base64.b64encode(data).decode()
    return ("@font-face{font-family:'JBM';"
            "src:url('data:font/woff2;base64," + b64 + "') format('woff2');"
            "font-weight:400;font-style:normal;}")

def build_svg(chars, rows):
    svg_w = COLS * CHAR_W
    svg_h = rows * CHAR_H
    font_css = ""
    font_family = "JBM,'Courier New',monospace"
    ramp_font = ROOT / "scripts" / "fonts" / "ramp.woff2"
    if ramp_font.exists():
        font_css = embed_font(ramp_font)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W_PX}" height="{int(svg_h*W_PX/svg_w)}" viewBox="0 0 {svg_w:.2f} {svg_h:.2f}">')
    lines.append(f'<style>{font_css}text{{font-family:{font_family};font-size:{FONT_SIZE}px;fill:#111111;white-space:pre;}}</style>')
    lines.append('<defs>')
    for i in range(rows):
        y_top = i * CHAR_H
        lines.append(f'<clipPath id="r{i}"><rect x="0" y="{y_top:.2f}" width="{svg_w:.2f}" height="{CHAR_H:.2f}"/></clipPath>')
    lines.append('</defs>')

    STAGGER  = 0.09
    WIPE_DUR = 0.35
    for i, row in enumerate(chars):
        y     = (i+1) * CHAR_H
        text  = "".join(row)
        begin = f"{i*STAGGER:.3f}s"
        lines.append(f'<rect id="w{i}" x="0" y="{i*CHAR_H:.2f}" width="0" height="{CHAR_H:.2f}"><animate attributeName="width" from="0" to="{svg_w:.2f}" dur="{WIPE_DUR}s" begin="{begin}" fill="freeze"/></rect>')
        lines.append(f'<text x="0" y="{y:.2f}" clip-path="url(#r{i})">{text}</text>')

    lines.append('</svg>')
    return "\n".join(lines)

def main():
    if not PHOTO.exists():
        sys.exit(f"ERROR: {PHOTO} not found.")
    print("Processing image ...")
    chars, rows = load_and_process(PHOTO)
    print(f"Building SVG ({COLS}x{rows}) ...")
    svg = build_svg(chars, rows)
    OUT.write_text(svg, encoding="utf-8")
    print(f"Written -> {OUT}")

if __name__ == "__main__":
    main()
