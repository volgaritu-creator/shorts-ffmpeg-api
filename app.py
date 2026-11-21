import os
import re
import glob
import uuid
import textwrap
import subprocess
import requests
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

def download_gdrive_file(url, dest_path):
    session = requests.Session()
    response = session.get(url, stream=True, timeout=30)
    
    # Handle Google Drive large-file virus scan confirmation page if returned
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type and "drive.google.com" in url:
        html_text = response.text
        match = re.search(r'id="download-form" action="([^"]+)"', html_text)
        file_id_match = re.search(r'[?&]id=([^&]+)', url)
        if file_id_match:
            file_id = file_id_match.group(1)
            confirm_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
            response = session.get(confirm_url, stream=True, timeout=30)

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=32768):
            if chunk:
                f.write(chunk)

    # Verify downloaded file is not an HTML error page
    with open(dest_path, "rb") as f:
        header = f.read(200)
    if b"<!DOCTYPE html" in header or b"<html" in header:
        raise ValueError(f"Google Drive returned an HTML page instead of media for URL: {url}. Check file permissions ('Anyone with the link').")

def get_devanagari_font():
    # Search system fonts for NotoSansDevanagari
    matches = glob.glob("/usr/share/fonts/**/NotoSansDevanagari*Bold*.ttf", recursive=True)
    if not matches:
        matches = glob.glob("/usr/share/fonts/**/NotoSansDevanagari*.ttf", recursive=True)
    if matches:
        return matches[0]
    # Fallback to any available TrueType font
    fallback = glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
    if fallback:
        return fallback[0]
    raise FileNotFoundError("No TrueType (.ttf) fonts found in /usr/share/fonts")

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
        # 1. Download background image and MP3 audio safely
        download_gdrive_file(image_url, img_path)
        download_gdrive_file(audio_url, aud_path)

        # 2. Wrap Hindi topic text neatly into 2 lines
        wrapped_topic = "\n".join(textwrap.wrap(topic, width=22))
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(wrapped_topic)

        # 3. Locate font and run FFmpeg
        font_file = get_devanagari_font()
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
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({"error": "FFmpeg failed", "details": result.stderr[-800:]}), 500

        return send_file(out_path, mimetype="video/mp4", as_attachment=True, download_name="short.mp4")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        for p in [img_path, aud_path, txt_path]:
            if os.path.exists(p):
                os.remove(p)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
