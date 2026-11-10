"""Shared helpers: paths, config loading, logging."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
PRODUCTS = ROOT / "products"
CONTENT = ROOT / "content"
DATA = ROOT / "data"
OUTPUT = ROOT / "output"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def load_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def brand():
    return load_json(CONFIG / "brand.json")


def schedule():
    return load_json(CONFIG / "schedule.json")


def products():
    items = load_json(PRODUCTS / "products.json", [])
    return {p["id"]: p for p in items}


def queue():
    return load_json(CONTENT / "queue.json", [])


def posted():
    return load_json(DATA / "posted.json", {"items": {}, "slots": {}})


def save_posted(data):
    save_json(DATA / "posted.json", data)


def product_images(product_id):
    folder = PRODUCTS / product_id
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def log(msg):
    print(msg, flush=True)


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def env(name, default=""):
    return os.environ.get(name, default).strip()
