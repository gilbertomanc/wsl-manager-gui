# Genera assets/icon.ico (icono de la app/tray) con Pillow.
# Uso: .venv\Scripts\python scripts\make_icon.py
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "assets" / "icon.ico"
OUT.parent.mkdir(parents=True, exist_ok=True)

SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
images = []
for w, h in SIZES:
    size = w
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 10
    d.rounded_rectangle((r, r, size - r, size - r), radius=size // 6, fill="#1e6f3e")
    # letra W
    w = size // 2
    d.line([(size * 0.28, size * 0.62), (size * 0.36, size * 0.34), (size * 0.44, size * 0.52),
            (size * 0.52, size * 0.34), (size * 0.62, size * 0.62)], fill="white", width=max(2, size // 12), joint="curve")
    # punto de estado
    d.ellipse((size * 0.62, size * 0.68, size * 0.80, size * 0.86), fill="#2ecc71")
    images.append(img)

images[0].save(OUT, format="ICO", sizes=[(s, s) for s, _ in SIZES])
print(f"icono generado: {OUT}")
