import os
import uuid
import textwrap
import subprocess
import requests
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "FFmpeg Shorts Renderer is Live"})

@app.route("/render", methods=["POST"])
def render_video():
    data = request.get_json(force=True)
    image_url = data.get("image_url")
    audio_url = data.get("audio_url")
    topic = data.get("topic", "").strip()

    if not image_url or not audio_url:
        return jsonify({"error": "image_url and audio_url are required"}), 400

    job_id = str(uuid.uuid4())
    img_path = f"/tmp/{job_id}.png"
    aud_path = f"/tmp/{job_id}.mp3"
    txt_path = f"/tmp/{job_id}.txt"
    out_path = f"/tmp/{job_id}.mp4"

    try:
        # 1. Download background image and MP3 audio from Google Drive
        with open(img_path, "wb") as f:
            f.write(requests.get(image_url, timeout=30).content)
        with open(aud_path, "wb") as f:
            f.write(requests.get(audio_url, timeout=30).content)

        # 2. Wrap Hindi topic text neatly into 2 lines so it fits inside the red ribbon
        wrapped_topic = "\n".join(textwrap.wrap(topic, width=22))
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(wrapped_topic)

        # 3. FFmpeg command: 1080x1920 image + centered white Hindi text at y=1030 + MP3 audio
        font_file = "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
        vf_filter = (
            f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"drawtext=fontfile={font_file}:textfile={txt_path}:"
            f"fontcolor=white:fontsize=68:line_spacing=16:"
            f"shadowcolor=black@0.7:shadowx=3:shadowy=4:"
            f"x=(w-text_w)/2:y=1030"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", "2", "-i", img_path,
            "-i", aud_path,
            "-vf", vf_filter,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            out_path
        ]
        subprocess.run(cmd, check=True)

        return send_file(out_path, mimetype="video/mp4", as_attachment=True, download_name="short.mp4")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # Clean up temporary input files
        for p in [img_path, aud_path, txt_path]:
            if os.path.exists(p):
                os.remove(p)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
