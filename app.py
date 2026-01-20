from flask import Flask, request, send_file, jsonify, render_template_string
from PIL import Image
import io
import os

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

# ----------------------------
# FAST FIX 1: Load rembg ONCE
# ----------------------------
from rembg import remove, new_session

# Faster/smaller model than default u2net
# Options you can try: "u2netp" (fast), "isnet-general-use" (often good), "u2net" (higher quality, slower)
REMBG_MODEL = os.environ.get("REMBG_MODEL", "u2netp")
SESSION = new_session(REMBG_MODEL)

# ----------------------------
# FAST FIX 2: Cap processing size
# ----------------------------
MAX_SIDE = int(os.environ.get("MAX_SIDE", "1024"))  # 1024–1600 is a good range

def downscale_for_speed(img: Image.Image, max_side: int = 1024) -> Image.Image:
    """Downscale large images to speed up background removal."""
    w, h = img.size
    m = max(w, h)
    if m <= max_side:
        return img
    scale = max_side / float(m)
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.LANCZOS)

def hex_to_rgb(hex_color: str):
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) != 6:
        return (255, 255, 255)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b)

@app.route("/remove-bg", methods=["POST"])
def remove_bg():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    bg_mode = request.form.get("bg_mode", "transparent")  # transparent | white | color
    bg_color = request.form.get("bg_color", "#ffffff")

    try:
        # Load + convert once
        input_image = Image.open(file.stream).convert("RGBA")

        # Downscale for speed (huge improvement on big uploads)
        proc_image = downscale_for_speed(input_image, MAX_SIDE)

        # Remove background using the cached session
        cutout = remove(proc_image, session=SESSION)

        # Add background if requested
        if bg_mode in ("white", "color"):
            rgb = (255, 255, 255) if bg_mode == "white" else hex_to_rgb(bg_color)
            background = Image.new("RGBA", cutout.size, rgb + (255,))
            output_image = Image.alpha_composite(background, cutout)
        else:
            output_image = cutout

        buf = io.BytesIO()
        output_image.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return send_file(buf, mimetype="image/png")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Render bind
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
