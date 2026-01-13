from flask import Flask, request, send_file, jsonify, render_template_string
from rembg import remove
from PIL import Image
import io

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB


HOME_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Image Background Remover</title>
  <style>
    body { font-family: Arial; padding: 30px; max-width: 1000px; margin: auto; }
    h2 { text-align: center; margin-bottom: 20px; }
    .controls { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; align-items: center; }
    .row { display: flex; gap: 20px; margin-top: 25px; }
    .col { flex: 1; }
    img { width: 100%; max-width: 460px; min-height: 280px; object-fit: contain;
          border: 1px solid #ddd; border-radius: 12px; padding: 10px; background: #f6f6f6; }
    button { padding: 10px 14px; cursor: pointer; border-radius: 10px; border: 1px solid #ccc; }
    select, input[type="color"] { padding: 8px; border-radius: 10px; border: 1px solid #ccc; }
    #status { text-align: center; margin-top: 12px; }
    .center { text-align: center; }
  </style>
</head>
<body>
  <h2>Image Background Remover</h2>

  <div class="controls">
    <input type="file" id="fileInput" accept="image/*" />

    <label>Background:</label>
    <select id="bgMode">
      <option value="transparent" selected>Transparent</option>
      <option value="white">White</option>
      <option value="color">Custom Color</option>
    </select>

    <input type="color" id="bgColor" value="#ffffff" style="display:none;" />

    <button id="btn">Remove Background</button>
    <button id="downloadBtn" style="display:none;">Download PNG</button>
  </div>

  <p id="status"></p>

  <div class="row">
    <div class="col">
      <h3 class="center">Original</h3>
      <img id="preview" />
    </div>
    <div class="col">
      <h3 class="center">Result</h3>
      <img id="result" />
    </div>
  </div>

<script>
const fileInput = document.getElementById("fileInput");
const preview = document.getElementById("preview");
const result = document.getElementById("result");
const statusText = document.getElementById("status");
const btn = document.getElementById("btn");
const bgMode = document.getElementById("bgMode");
const bgColor = document.getElementById("bgColor");
const downloadBtn = document.getElementById("downloadBtn");

let latestBlobUrl = null;

bgMode.addEventListener("change", () => {
  if (bgMode.value === "color") bgColor.style.display = "inline-block";
  else bgColor.style.display = "none";
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return;
  preview.src = URL.createObjectURL(file);
  result.src = "";
  statusText.textContent = "";
  downloadBtn.style.display = "none";
});

btn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) return alert("Upload an image first!");

  statusText.textContent = "Removing background... (first run may take a bit)";
  btn.disabled = true;
  downloadBtn.style.display = "none";

  const formData = new FormData();
  formData.append("image", file);

  // send background options too
  formData.append("bg_mode", bgMode.value);
  formData.append("bg_color", bgColor.value);

  try {
    const response = await fetch("/remove-bg", { method: "POST", body: formData });
    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || "Server error");
    }

    const blob = await response.blob();

    // clean old url
    if (latestBlobUrl) URL.revokeObjectURL(latestBlobUrl);
    latestBlobUrl = URL.createObjectURL(blob);

    result.src = latestBlobUrl;

    downloadBtn.style.display = "inline-block";
    statusText.textContent = "Done ✅";

  } catch (e) {
    statusText.textContent = "Error: " + e.message;
  } finally {
    btn.disabled = false;
  }
});

downloadBtn.addEventListener("click", () => {
  if (!latestBlobUrl) return;
  const a = document.createElement("a");
  a.href = latestBlobUrl;
  a.download = "no-bg.png";
  document.body.appendChild(a);
  a.click();
  a.remove();
});
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HOME_HTML)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def hex_to_rgb(hex_color: str):
    # hex like "#ffffff"
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
        return jsonify({"error": "No image uploaded. Use form field name 'image'."}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename."}), 400

    bg_mode = request.form.get("bg_mode", "transparent")  # transparent | white | color
    bg_color = request.form.get("bg_color", "#ffffff")    # used if bg_mode=color

    try:
        input_image = Image.open(file).convert("RGBA")

        # Remove background -> RGBA with alpha
        cutout = remove(input_image)

        # If user wants a background color, composite it
        if bg_mode in ("white", "color"):
            if bg_mode == "white":
                rgb = (255, 255, 255)
            else:
                rgb = hex_to_rgb(bg_color)

            background = Image.new("RGBA", cutout.size, rgb + (255,))
            composed = Image.alpha_composite(background, cutout).convert("RGBA")
            output_image = composed
        else:
            output_image = cutout  # transparent

        buf = io.BytesIO()
        output_image.save(buf, format="PNG")
        buf.seek(0)

        return send_file(buf, mimetype="image/png")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
