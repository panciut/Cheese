"""Converte figure PDF -> PNG (alta DPI) e seleziona alcune foto reali BMP -> JPG."""
import os, fitz
from PIL import Image

ROOT = r"C:\Users\nicol\Desktop\Cheese"
OUT = os.path.join(ROOT, "presentation", "assets")
os.makedirs(OUT, exist_ok=True)

# 1) PDF figure -> PNG
fig_dirs = [
    os.path.join(ROOT, "report_latex", "figures"),
    os.path.join(ROOT, "report_latex", "figures", "metrics"),
]
DPI = 200
zoom = DPI / 72.0
mat = fitz.Matrix(zoom, zoom)
converted = []
for d in fig_dirs:
    for f in os.listdir(d):
        if f.lower().endswith(".pdf"):
            src = os.path.join(d, f)
            doc = fitz.open(src)
            page = doc[0]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            name = os.path.splitext(f)[0] + ".png"
            dst = os.path.join(OUT, name)
            pix.save(dst)
            converted.append((name, pix.width, pix.height))
            doc.close()

# 2) Foto reali fetta/grana -> JPG ritagliate quadrate
photos = [
    ("2018-2019_Trentingrana__2018-09-12__P1a_304_fetta.bmp", "cheese_fetta_1.jpg"),
    ("2018-2019_Trentingrana__2018-09-12__P3a_310_grana.bmp", "cheese_grana_1.jpg"),
    ("2018-2019_Trentingrana__2018-09-12__P5a_316_fetta.bmp", "cheese_fetta_2.jpg"),
    ("2018-2019_Trentingrana__2018-09-12__P2a_306_grana.bmp", "cheese_grana_2.jpg"),
]
src_dir = os.path.join(ROOT, "data", "data", "images_flat")
for src_name, dst_name in photos:
    src = os.path.join(src_dir, src_name)
    if os.path.exists(src):
        im = Image.open(src).convert("RGB")
        im.save(os.path.join(OUT, dst_name), quality=90)
        # versione quadrata centrata
        w, h = im.size
        s = min(w, h)
        sq = im.crop(((w-s)//2, (h-s)//2, (w-s)//2+s, (h-s)//2+s))
        sq.save(os.path.join(OUT, dst_name.replace(".jpg", "_sq.jpg")), quality=90)

print("PNG convertiti:", len(converted))
for n, w, h in converted:
    print(f"  {n}  {w}x{h}")
print("Foto:", [p[1] for p in photos])
