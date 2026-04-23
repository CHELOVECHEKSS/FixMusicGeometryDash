from flask import Flask, send_file, jsonify, request
from flask_cors import CORS
import requests
import os
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

SOUND_PATH = os.path.join(os.path.dirname(__file__), "sound")
STATS_FILE = os.path.join(SOUND_PATH, "stats.json")

os.makedirs(SOUND_PATH, exist_ok=True)

cache_stats = {
    "total_downloads": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "cached_files": 0
}

def load_stats():
    global cache_stats
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                cache_stats = json.load(f)
        except:
            pass

def save_stats():
    with open(STATS_FILE, 'w') as f:
        json.dump(cache_stats, f, indent=2)

def find_cached_file(music_id):
    for file in os.listdir(SOUND_PATH):
        if file.startswith(f"{music_id}."):
            return os.path.join(SOUND_PATH, file)
    return None

def download_from_newgrounds(music_id):
    url = f"https://www.newgrounds.com/audio/download/{music_id}"
    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        return response.content, response.headers.get('content-type', '')
    except Exception as e:
        raise Exception(f"Ошибка скачивания: {str(e)}")

def get_extension(content_type):
    if 'audio/mpeg' in content_type or 'mp3' in content_type:
        return 'mp3'
    elif 'audio/wav' in content_type or 'wav' in content_type:
        return 'wav'
    elif 'audio/ogg' in content_type or 'ogg' in content_type:
        return 'ogg'
    return 'mp3'

@app.route('/download/<int:music_id>', methods=['GET'])
def download_music(music_id):
    cached_file = find_cached_file(music_id)
    if cached_file:
        cache_stats["cache_hits"] += 1
        save_stats()
        return send_file(cached_file, as_attachment=True)
    
    try:
        cache_stats["cache_misses"] += 1
        cache_stats["total_downloads"] += 1
        
        content, content_type = download_from_newgrounds(music_id)
        extension = get_extension(content_type)
        
        file_path = os.path.join(SOUND_PATH, f"{music_id}.{extension}")
        with open(file_path, 'wb') as f:
            f.write(content)
        
        cache_stats["cached_files"] = len([f for f in os.listdir(SOUND_PATH) if f != "stats.json"])
        save_stats()
        
        return send_file(file_path, as_attachment=True)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    load_stats()
    print("🚀 Сервер запущен на http://localhost:5000")
    print(f"📁 Папка sound: {SOUND_PATH}")
    app.run(debug=False, host='localhost', port=5000)
