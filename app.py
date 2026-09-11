from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
import os
import uuid
import glob

app = Flask(__name__)

DOWNLOAD_FOLDER = "/tmp/downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


def cleanup_old_files():
    for path in glob.glob(os.path.join(DOWNLOAD_FOLDER, "*")):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or request.form
    url = (data.get("url") or "").strip()
    fmt = (data.get("format") or "mp4").lower()

    if not url:
        return jsonify({"error": "Please enter a YouTube URL."}), 400

    if fmt not in {"mp4", "mp3"}:
        return jsonify({"error": "Invalid format."}), 400

    cleanup_old_files()
    job_id = uuid.uuid4().hex
    output_template = os.path.join(DOWNLOAD_FOLDER, f"{job_id}.%(ext)s")

    options = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    if fmt == "mp3":
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        options.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        })

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "download")

        files = glob.glob(os.path.join(DOWNLOAD_FOLDER, f"{job_id}.*"))
        if not files:
            return jsonify({"error": "Download completed but output file was not found."}), 500

        file_path = files[0]
        extension = "mp3" if fmt == "mp3" else "mp4"
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"{title[:120]}.{extension}",
            mimetype="audio/mpeg" if fmt == "mp3" else "video/mp4",
        )
    except Exception as exc:
        return jsonify({"error": f"Download failed: {str(exc)}"}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
