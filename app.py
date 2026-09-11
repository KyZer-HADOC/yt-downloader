from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
import os
import uuid
import glob
import re

app = Flask(__name__)

DOWNLOAD_FOLDER = "/tmp/downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


def clean_title(title):
    return re.sub(r'[\\/:*?"<>|]+', "_", title).strip()[:120] or "youtube_download"


def cleanup_old_files():
    for path in glob.glob(os.path.join(DOWNLOAD_FOLDER, "*")):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


def get_url(data):
    return (data.get("url") or "").strip()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/get-info", methods=["POST"])
def get_info():
    data = request.get_json(silent=True) or request.form
    url = get_url(data)
    if not url:
        return jsonify({"error": "Please enter a YouTube URL."}), 400

    try:
        options = {"quiet": True, "no_warnings": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []
        seen = set()
        for f in info.get("formats", []):
            format_id = f.get("format_id")
            height = f.get("height")
            ext = f.get("ext")
            if not format_id or not height or not ext:
                continue
            if f.get("vcodec") == "none":
                continue
            label = f"{height}p ({ext})"
            if label in seen:
                continue
            seen.add(label)
            formats.append({"format_id": format_id, "quality": label, "height": height})

        formats.sort(key=lambda x: x["height"], reverse=True)
        return jsonify({
            "title": info.get("title", "YouTube video"),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration") or 0,
            "formats": formats[:15],
        })
    except Exception as exc:
        return jsonify({"error": f"Could not get video info: {str(exc)}"}), 500


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or request.form
    url = get_url(data)
    quality = (data.get("quality") or "best").strip()

    if not url:
        return jsonify({"error": "Please enter a YouTube URL."}), 400

    cleanup_old_files()
    job_id = uuid.uuid4().hex
    output_template = os.path.join(DOWNLOAD_FOLDER, f"{job_id}.%(ext)s")

    if quality == "best":
        format_selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    elif quality == "worst":
        format_selector = "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst"
    elif quality.isdigit():
        format_selector = f"{quality}+bestaudio/best"
    else:
        return jsonify({"error": "Invalid quality selection."}), 400

    options = {
        "outtmpl": output_template,
        "format": format_selector,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            title = clean_title(info.get("title", "youtube_download"))

        files = [p for p in glob.glob(os.path.join(DOWNLOAD_FOLDER, f"{job_id}.*")) if os.path.isfile(p)]
        if not files:
            return jsonify({"error": "Download completed but output file was not found."}), 500

        file_path = files[0]
        extension = os.path.splitext(file_path)[1].lower() or ".mp4"
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"{title}{extension}",
            mimetype="video/mp4",
        )
    except Exception as exc:
        return jsonify({"error": f"Download failed: {str(exc)}"}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
