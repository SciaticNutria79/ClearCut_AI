from flask import Flask, request, send_file, jsonify, render_template_string
from PIL import Image
import io, os
from functools import lru_cache

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

REMBG_MODEL = os.environ.get("REMBG_MODEL", "u2netp")
MAX_SIDE = int(os.environ.get("MAX_SIDE", "1024"))

def downscale_for_speed(img: Image.Image, max_side: int = 1024) -> Image.Image:
    w, h = img.size
    m = max(w, h)
    if m <= max_side:
        return img
    scale = max_side / float(m)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

def hex_to_rgb(hex_color: str):
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) != 6:
        return (255, 255, 255)
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))

@lru_cache(maxsize=1)
def get_rembg_session():
    # Lazy import + create session ONE TIME only (cached)
    from rembg import new_session
    return new_session(REMBG_MODEL)

@lru_cache(maxsize=1)
def get_remove_fn():
    # Lazy import remove ONE TIME
    from rembg import remove
    return remove

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/remove-bg", methods=["POST"])
def remove_bg():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    bg_mode = request.form.get("bg_mode", "transparent")
    bg_color = request.form.get("bg_color", "#ffffff")

    try:
        img = Image.open(file.stream).convert("RGBA")
        img = downscale_for_speed(img, MAX_SIDE)

        remove = get_remove_fn()
        session = get_rembg_session()

        cutout = remove(img, session=session)

        if bg_mode in ("white", "color"):
            rgb = (255, 255, 255) if bg_mode == "white" else hex_to_rgb(bg_color)
            background = Image.new("RGBA", cutout.size, rgb + (255,))
            out = Image.alpha_composite(background, cutout)
        else:
            out = cutout

        buf = io.BytesIO()
        out.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return send_file(buf, mimetype="image/png")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
