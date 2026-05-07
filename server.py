from flask import Flask, send_file, jsonify, request
from flask_cors import CORS
import requests
import os
import sys
import json
from datetime import datetime
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Отключаем буферизацию вывода
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

app = Flask(__name__)
CORS(app)

SOUND_PATH = os.path.join(os.path.dirname(__file__), "sound")
STATS_FILE = os.path.join(SOUND_PATH, "stats.json")
LOG_FILE = os.path.join(SOUND_PATH, "download.log")

os.makedirs(SOUND_PATH, exist_ok=True)

DEBUG = True

def dlog(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

cache_stats = {
    "total_downloads": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "cached_files": 0
}
stats_lock = threading.Lock()
download_locks = {}
download_locks_lock = threading.Lock()

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

def log_download(music_id, source, status):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] ID: {music_id} | Источник: {source} | Статус: {status}\n"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry)
    print(f"[{timestamp}] ID: {music_id} | {source} | {status}")

def find_cached_file(music_id):
    for file in os.listdir(SOUND_PATH):
        if file.startswith(f"{music_id}."):
            return os.path.join(SOUND_PATH, file)
    return None

def get_extension(content_type):
    if 'audio/mpeg' in content_type or 'mp3' in content_type:
        return 'mp3'
    elif 'audio/wav' in content_type or 'wav' in content_type:
        return 'wav'
    elif 'audio/ogg' in content_type or 'ogg' in content_type:
        return 'ogg'
    return 'mp3'

def stream_to_file(response, file_path):
    with open(file_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)

def download_from_newgrounds(music_id):
    url = f"https://www.newgrounds.com/audio/download/{music_id}"
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'ru,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.newgrounds.com/',
        'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "YaBrowser";v="26.3", "Yowser";v="2.5"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1'
    })
    try:
        dlog(f"[{music_id}] Попытка прямой загрузки: {url}")
        response = session.get(url, timeout=30, stream=True)
        
        if response.status_code == 403:
            log_download(music_id, "newgrounds.com/audio/download", "FAILED - капча/блокировка")
            raise Exception("Доступ запрещён (капча или блокировка)")
        if response.status_code == 404:
            log_download(music_id, "newgrounds.com/audio/download", "FAILED - трек не найден")
            raise Exception("Трек не существует")
        
        response.raise_for_status()
        content_type = response.headers.get('content-type', '')
        ext = get_extension(content_type)
        file_path = os.path.join(SOUND_PATH, f"{music_id}.{ext}")
        dlog(f"[{music_id}] Стриминг в файл: {file_path}")
        stream_to_file(response, file_path)
        log_download(music_id, "newgrounds.com/audio/download", "OK")
        return file_path
    except requests.exceptions.Timeout:
        log_download(music_id, "newgrounds.com/audio/download", "FAILED - таймаут")
        raise Exception("Превышено время ожидания")
    except requests.exceptions.ConnectionError:
        log_download(music_id, "newgrounds.com/audio/download", "FAILED - ошибка соединения")
        raise Exception("Не удалось подключиться к серверу")
    except Exception as e:
        if "капча" in str(e) or "не существует" in str(e) or "Превышено" in str(e) or "подключиться" in str(e):
            raise
        try:
            listen_url = f"https://www.newgrounds.com/audio/listen/{music_id}"
            dlog(f"[{music_id}] Прямая загрузка не удалась, парсим страницу: {listen_url}")
            response = session.get(listen_url, timeout=30)
            
            if response.status_code == 403:
                log_download(music_id, "newgrounds.com/audio/listen", "FAILED - капча/блокировка")
                raise Exception("Доступ запрещён (капча или блокировка)")
            if response.status_code == 404:
                log_download(music_id, "newgrounds.com/audio/listen", "FAILED - трек не найден")
                raise Exception("Трек не существует")
            
            response.raise_for_status()

            audio_match = re.search(r'og:audio"\s+content="([^"]+)"', response.text)
            if audio_match:
                audio_url = audio_match.group(1)
                dlog(f"[{music_id}] Найден og:audio: {audio_url}")
                audio_response = session.get(audio_url, timeout=30, stream=True)
                audio_response.raise_for_status()
                content_type = audio_response.headers.get('content-type', '')
                ext = get_extension(content_type)
                file_path = os.path.join(SOUND_PATH, f"{music_id}.{ext}")
                stream_to_file(audio_response, file_path)
                log_download(music_id, "audio.ngfiles.com (parsed)", "OK")
                return file_path

            log_download(music_id, "unknown", "FAILED - не найден og:audio")
            raise Exception("Аудиофайл не найден на странице")
        except requests.exceptions.Timeout:
            log_download(music_id, "unknown", "FAILED - таймаут")
            raise Exception("Превышено время ожидания")
        except requests.exceptions.ConnectionError:
            log_download(music_id, "unknown", "FAILED - ошибка соединения")
            raise Exception("Не удалось подключиться к серверу")
        except Exception as e:
            log_download(music_id, "unknown", f"FAILED - {str(e)}")
            raise

def get_download_lock(music_id):
    with download_locks_lock:
        if music_id not in download_locks:
            download_locks[music_id] = threading.Lock()
        return download_locks[music_id]

@app.route('/download/<int:music_id>', methods=['GET'])
def download_music(music_id):
    dlog(f"[{music_id}] Запрос на скачивание")
    cached_file = find_cached_file(music_id)
    if cached_file:
        dlog(f"[{music_id}] Кэш-хит: {cached_file}")
        with stats_lock:
            cache_stats["cache_hits"] += 1
            save_stats()
        log_download(music_id, "cache", "OK")
        return send_file(cached_file, as_attachment=True)

    lock = get_download_lock(music_id)
    with lock:
        cached_file = find_cached_file(music_id)
        if cached_file:
            dlog(f"[{music_id}] Кэш-хит после блокировки: {cached_file}")
            with stats_lock:
                cache_stats["cache_hits"] += 1
                save_stats()
            return send_file(cached_file, as_attachment=True)

        try:
            dlog(f"[{music_id}] Начало загрузки...")
            with stats_lock:
                cache_stats["cache_misses"] += 1
                cache_stats["total_downloads"] += 1

            file_path = download_from_newgrounds(music_id)
            dlog(f"[{music_id}] Загрузка завершена: {file_path}")

            with stats_lock:
                cache_stats["cached_files"] = len([
                    f for f in os.listdir(SOUND_PATH)
                    if f not in ("stats.json", "download.log")
                ])
                save_stats()

            return send_file(file_path, as_attachment=True)

        except Exception as e:
            print(f"[ERROR] [{music_id}] {e}")
            return jsonify({"error": str(e)}), 400

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    load_stats()
    from waitress import serve
    import time

    server_thread = threading.Thread(
        target=lambda: serve(app, host='0.0.0.0', port=1700),
        daemon=True
    )
    server_thread.start()
    time.sleep(1)

    print("🚀 Сервер запущен на http://localhost:1700")
    print(f"📁 Папка sound: {SOUND_PATH}")
    print(f"🐛 Режим отладки: {'ВКЛЮЧЁН' if DEBUG else 'ВЫКЛЮЧЕН'}")
    print("📡 Ожидание запросов...\n")

    server_thread.join()
