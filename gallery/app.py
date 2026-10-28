"""Wile E. Coyote GIF gallery: a grid of everything in static/gifs/."""
from pathlib import Path

from flask import Flask, abort, render_template

GIF_DIR = Path(__file__).resolve().parent / "static" / "gifs"
EXTENSIONS = {".gif", ".webp", ".png", ".jpg", ".jpeg"}

app = Flask(__name__)


def gif_names():
    return sorted(p.name for p in GIF_DIR.glob("*") if p.suffix.lower() in EXTENSIONS)


@app.route("/")
def index():
    return render_template("index.html", gifs=gif_names())


@app.route("/gif/<name>")
def gif(name):
    # Only names that are actually in the gallery; nothing else on disk.
    if name not in gif_names():
        abort(404)
    return render_template("gif.html", gif=name)


if __name__ == "__main__":
    app.run(debug=True, port=8080)
