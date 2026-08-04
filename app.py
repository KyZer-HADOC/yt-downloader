from flask import Flask, render_template, request, jsonify
import yt_dlp
import os

app = Flask(__name__)

# Render.com temp folder use karanna
DOWNLOAD_FOLDER = '/tmp/downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# meka add karanna - Render port handle karanna
import os
port = int(os.environ.get("PORT", 5000))

@app.route('/')
def index():
    return render_template('index.html')

# ... tawa code tika ...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)