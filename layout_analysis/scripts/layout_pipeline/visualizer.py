from PIL import Image, ImageDraw

COLORS = {
    "HEADER":        (255, 107, 107),
    "CLAUSE":        (78, 205, 196),
    "TABLE":         (69, 183, 209),
    "FOOTER":        (150, 206, 180),
    "SECTION_TITLE": (255, 217, 61),
}


def draw_regions_on_image(pil_img, regions_1000, out_path):
    """
    pil_img: rendered page (PIL, RGB).
    regions_1000: [{label, box[0-1000]}].
    Draws colored boxes + label text, saves to out_path.
    """
    img = pil_img.convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for r in regions_1000:
        b = r["box"]
        px = [b[0] / 1000 * w, b[1] / 1000 * h, b[2] / 1000 * w, b[3] / 1000 * h]
        color = COLORS.get(r["label"], (150, 150, 150))
        draw.rectangle(px, outline=color, width=3)
        label = r["label"]
        ty = max(0, px[1] - 16)
        draw.rectangle([px[0], ty, px[0] + len(label) * 8 + 6, ty + 16], fill=color)
        draw.text((px[0] + 3, ty + 2), label, fill=(0, 0, 0))
    img.save(out_path)