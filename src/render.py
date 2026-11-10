"""Render a 30-second vertical product video plus thumbnails.

Usage (local test):
    python src/render.py --product bedtime-routine-pack --item test-1
"""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from common import OUTPUT, ROOT, brand, fail, log, product_images, products

W, H = 1080, 1920
FPS = 30
FADE = 0.5          # seconds of crossfade between slides
END_CARD = 3.5      # seconds the end card is on screen
MAX_SLIDES = 6
SAFE_BOTTOM = int(H * 0.80)  # keep text above the platform buttons


def hex_rgb(value, alpha=255):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def font(kind, size):
    b = brand()
    return ImageFont.truetype(str(ROOT / b["fonts"][kind]), size)


def wrap(draw, text, fnt, max_width, max_lines):
    """Greedy word wrap; shrinks nothing, just cuts extra lines with an ellipsis."""
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=fnt) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,!?") + "…"
    return lines


def fit_text(draw, text, kind, start_size, max_width, max_lines, min_size=34):
    size = start_size
    while size >= min_size:
        fnt = font(kind, size)
        words_ok = all(draw.textlength(w, font=fnt) <= max_width for w in text.split())
        lines = wrap(draw, text, fnt, max_width, max_lines + 1)
        if words_ok and len(lines) <= max_lines:
            return fnt, lines
        size -= 4
    fnt = font(kind, min_size)
    return fnt, wrap(draw, text, fnt, max_width, max_lines)


def cover(img, size):
    """Scale + centre-crop so the image fills `size`."""
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    left = (img.width - tw) // 2
    top = (img.height - th) // 2
    return img.crop((left, top, left + tw, top + th))


def contain(img, box):
    bw, bh = box
    scale = min(bw / img.width, bh / img.height)
    return img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width, img.height), radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def framed_product(src, box):
    """The product image with a white border, rounded corners and a soft shadow."""
    img = contain(src.convert("RGB"), (box[0] - 36, box[1] - 36))
    border = 18
    framed = Image.new("RGB", (img.width + border * 2, img.height + border * 2), "white")
    framed.paste(img, (border, border))
    framed = rounded(framed, 28)
    shadow = Image.new("RGBA", (framed.width + 80, framed.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((40, 50, framed.width + 40, framed.height + 50), 32, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    shadow.alpha_composite(framed, (40, 40))
    return shadow


def blurred_background(src, size, tint):
    bg = cover(src.convert("RGB"), size).filter(ImageFilter.GaussianBlur(45)).convert("RGBA")
    bg.alpha_composite(Image.new("RGBA", size, hex_rgb(tint, 140)))
    return bg


def slide_base(image_path, out_path):
    b = brand()
    src = Image.open(image_path)
    canvas = blurred_background(src, (W, H), b["colors"]["night"])
    product = framed_product(src, (960, 1100))
    x = (W - product.width) // 2
    y = 110 + max(0, (1100 - product.height) // 2) - 40
    canvas.alpha_composite(product, (x, y))
    canvas.convert("RGB").save(out_path)


def caption_overlay(text, out_path):
    b = brand()
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if not text:
        layer.save(out_path)
        return
    draw = ImageDraw.Draw(layer)
    fnt, lines = fit_text(draw, text, "bold", 66, 860, 2)
    line_h = int(fnt.size * 1.22)
    pad_x, pad_y = 44, 30
    text_w = max(draw.textlength(line, font=fnt) for line in lines)
    box_w = int(text_w + pad_x * 2)
    box_h = int(line_h * len(lines) + pad_y * 2)
    box_x = (W - box_w) // 2
    box_y = SAFE_BOTTOM - box_h - 40
    draw.rounded_rectangle((box_x, box_y, box_x + box_w, box_y + box_h), 36, fill=hex_rgb(b["colors"]["caption_bg"], 240))
    for i, line in enumerate(lines):
        lw = draw.textlength(line, font=fnt)
        draw.text(((W - lw) / 2, box_y + pad_y + i * line_h), line, font=fnt, fill=hex_rgb(b["colors"]["caption_text"]))
    layer.save(out_path)


def end_card(product_name, out_path):
    b = brand()
    c = b["colors"]
    img = Image.new("RGBA", (W, H), hex_rgb(c["night"]))
    draw = ImageDraw.Draw(img)
    # small stars + moon
    for (sx, sy, r) in [(180, 360, 5), (880, 300, 6), (760, 520, 4), (260, 620, 4), (930, 760, 5), (150, 1500, 4), (900, 1580, 5)]:
        draw.ellipse((sx - r, sy - r, sx + r, sy + r), fill=hex_rgb(c["cream"], 200))
    draw.ellipse((W / 2 - 110, 470, W / 2 + 110, 690), fill=hex_rgb(c["moon"]))
    draw.ellipse((W / 2 - 50, 440, W / 2 + 170, 660), fill=hex_rgb(c["night"]))
    name_font = font("bold", 96)
    nw = draw.textlength(b["shop_name"], font=name_font)
    draw.text(((W - nw) / 2, 820), b["shop_name"], font=name_font, fill=hex_rgb(c["cream"]))
    pfnt, plines = fit_text(draw, product_name, "regular", 50, 880, 2)
    for i, line in enumerate(plines):
        lw = draw.textlength(line, font=pfnt)
        draw.text(((W - lw) / 2, 980 + i * int(pfnt.size * 1.3)), line, font=pfnt, fill=hex_rgb(c["cream"], 220))
    cta_font = font("bold", 58)
    cta = b["end_card_cta"]
    cw = draw.textlength(cta, font=cta_font)
    bx, by = (W - cw) / 2 - 50, 1200
    draw.rounded_rectangle((bx, by, bx + cw + 100, by + 110), 55, fill=hex_rgb(c["moon"]))
    draw.text((bx + 50, by + 18), cta, font=cta_font, fill=hex_rgb(c["night"]))
    line_font = font("regular", 44)
    lw = draw.textlength(b["end_card_line"], font=line_font)
    draw.text(((W - lw) / 2, 1360), b["end_card_line"], font=line_font, fill=hex_rgb(c["cream"], 210))
    img.convert("RGB").save(out_path)


def youtube_thumbnail(image_path, hook, out_path):
    b = brand()
    c = b["colors"]
    tw, th = 1280, 720
    src = Image.open(image_path)
    canvas = blurred_background(src, (tw, th), c["night"])
    product = framed_product(src, (560, 660))
    canvas.alpha_composite(product, (40, (th - product.height) // 2))
    draw = ImageDraw.Draw(canvas)
    fnt, lines = fit_text(draw, hook, "bold", 84, 560, 4, min_size=48)
    line_h = int(fnt.size * 1.18)
    y = (th - line_h * len(lines)) // 2 - 30
    for i, line in enumerate(lines):
        draw.text((650, y + i * line_h), line, font=fnt, fill=hex_rgb(c["cream"]))
    small = font("bold", 34)
    draw.text((650, y + line_h * len(lines) + 24), b["shop_name"], font=small, fill=hex_rgb(c["moon"]))
    canvas.convert("RGB").save(out_path, quality=90)


def pinterest_cover(image_path, hook, out_path):
    b = brand()
    c = b["colors"]
    pw, ph = 1000, 1500
    src = Image.open(image_path)
    canvas = blurred_background(src, (pw, ph), c["night"])
    product = framed_product(src, (880, 1040))
    canvas.alpha_composite(product, ((pw - product.width) // 2, 20))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 1150, pw, ph), fill=hex_rgb(c["cream"]))
    fnt, lines = fit_text(draw, hook, "bold", 76, 880, 3, min_size=44)
    line_h = int(fnt.size * 1.2)
    y = 1150 + (300 - line_h * len(lines)) // 2 - 10
    for i, line in enumerate(lines):
        lw = draw.textlength(line, font=fnt)
        draw.text(((pw - lw) / 2, y + i * line_h), line, font=fnt, fill=hex_rgb(c["night"]))
    canvas.convert("RGB").save(out_path, quality=90)


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        fail("ffmpeg failed:\n" + result.stderr[-3000:])


def render_segment(base_png, overlay_png, seconds, out_mp4, zoom_in=True):
    frames = int(round(seconds * FPS))
    zoom = f"1+0.07*on/{frames}" if zoom_in else f"1.07-0.07*on/{frames}"
    filt = (
        f"[0:v]scale={W * 2}:{H * 2},"
        f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}[v];"
        f"[v][1:v]overlay=0:0,format=yuv420p[out]"
    )
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(base_png), "-i", str(overlay_png),
        "-filter_complex", filt, "-map", "[out]",
        "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        str(out_mp4),
    ])


def render_video(product, item, out_dir):
    """product: dict from products.json. item: dict from queue.json."""
    b = brand()
    total = float(b.get("video_seconds", 30))
    images = product_images(product["id"])[:MAX_SLIDES]
    if not images:
        fail(f"No images found in products/{product['id']}/ — add PNG or JPG files there.")
    captions = list(item.get("captions", []))
    n = len(images)
    slide_len = (total - END_CARD + n * FADE) / n
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        segments, lengths = [], []
        for i, img in enumerate(images):
            base, cap, seg = tmp / f"base{i}.png", tmp / f"cap{i}.png", tmp / f"seg{i}.mp4"
            slide_base(img, base)
            caption_overlay(captions[i] if i < len(captions) else "", cap)
            render_segment(base, cap, slide_len, seg, zoom_in=(i % 2 == 0))
            segments.append(seg)
            lengths.append(slide_len)
        end_png, blank, end_seg = tmp / "end.png", tmp / "blank.png", tmp / "end.mp4"
        end_card(product["name"], end_png)
        caption_overlay("", blank)
        render_segment(end_png, blank, END_CARD, end_seg)
        segments.append(end_seg)
        lengths.append(END_CARD)

        # crossfade chain
        inputs, parts = [], []
        for seg in segments:
            inputs += ["-i", str(seg)]
        prev, offset = "[0:v]", 0.0
        for i in range(1, len(segments)):
            offset += lengths[i - 1] - FADE
            label = f"[x{i}]"
            parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={FADE}:offset={offset:.3f}{label}")
            prev = label
        video_filter = ";".join(parts) if parts else "[0:v]null[x0]"
        if not parts:
            prev = "[x0]"

        music = ROOT / b.get("music", "assets/music.mp3")
        audio_index = len(segments)
        if music.exists():
            inputs += ["-stream_loop", "-1", "-i", str(music)]
            vol = b.get("music_volume", 0.6)
            audio_filter = (
                f"[{audio_index}:a]atrim=0:{total},asetpts=N/SR/TB,volume={vol},"
                f"afade=t=in:st=0:d=1,afade=t=out:st={total - 2}:d=2[a]"
            )
        else:
            log("No assets/music.mp3 found — video will have a silent audio track.")
            inputs += ["-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=44100:cl=stereo"]
            audio_filter = f"[{audio_index}:a]anull[a]"

        video_path = out_dir / "video.mp4"
        run([
            "ffmpeg", "-y", "-loglevel", "error", *inputs,
            "-filter_complex", f"{video_filter};{audio_filter}",
            "-map", prev, "-map", "[a]", "-t", str(total),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-movflags", "+faststart", str(video_path),
        ])

    hook = item.get("hook") or (captions[0] if captions else product["name"])
    youtube_thumbnail(images[0], hook, out_dir / "thumbnail.jpg")
    pinterest_cover(images[0], hook, out_dir / "pin_cover.jpg")
    log(f"Rendered {video_path}")
    return {
        "video": out_dir / "video.mp4",
        "thumbnail": out_dir / "thumbnail.jpg",
        "pin_cover": out_dir / "pin_cover.jpg",
    }


def main():
    from common import queue
    parser = argparse.ArgumentParser()
    parser.add_argument("--item", required=True, help="queue item id")
    args = parser.parse_args()
    item = next((q for q in queue() if q["id"] == args.item), None)
    if not item:
        fail(f"No queue item with id {args.item}")
    product = products().get(item["product"])
    if not product:
        fail(f"Product {item['product']} not in products/products.json")
    out = OUTPUT / item["id"]
    shutil.rmtree(out, ignore_errors=True)
    render_video(product, item, out)


if __name__ == "__main__":
    main()
