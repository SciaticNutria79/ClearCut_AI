from flask import Flask, request, send_file, jsonify, render_template_string
from rembg import remove
from PIL import Image
import io
import os

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB


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
    img {
      width: 100%;
      max-width: 460px;
      min-height: 280px;
      object-fit: contain;
      border: 1px solid #ddd;
      border-radius: 12px;
      padding: 10px;
      background: #f6f6f6;
    }
    button {
      padding: 10px 14px;
      cursor: pointer;
      border-radius: 10px;
      border: 1px solid #ccc;
      background: #fff;
    }
    select, input[type="color"] {
      padding: 8px;
      border-radius: 10px;
      border: 1px solid #ccc;
    }
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
  bgColor.style.display = bgMode.value === "color" ? "inline-block" : "none";
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

  statusText.textContent = "Removing background… first run may take a bit.";
  btn.disabled = true;
  downloadBtn.style.display = "none";

  const formData = new FormData();
  formData.append("image", file);
  formData.append("bg_mode", bgMode.value);
  formData.append("bg_color", bgColor.value);

  try {
    const response = await fetch("/remove-bg", { method: "POST", body: formData });
    if (!response.ok) throw new Error("Server error");

    const blob = await response.blob();
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


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


@app.route("/remove-bg", methods=["POST"])
def remove_bg():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    bg_mode = request.form.get("bg_mode", "transparent")
    bg_color = request.form.get("bg_color", "#ffffff")

    input_image = Image.open(file).convert("RGBA")
    cutout = remove(input_image)

    if bg_mode in ("white", "color"):
        rgb = (255, 255, 255) if bg_mode == "white" else hex_to_rgb(bg_color)
        background = Image.new("RGBA", cutout.size, rgb + (255,))
        output = Image.alpha_composite(background, cutout)
    else:
        output = cutout

    buf = io.BytesIO()
    output.save(buf, format="PNG")
    buf.seek(0)

    return send_file(buf, mimetype="image/png")


# 🔥 CRITICAL FOR RENDER 🔥
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
