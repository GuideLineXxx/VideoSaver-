import os
import re
import glob
import uuid
import threading
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

active_tasks = {}

# ─────────────────────────────────────────────────────────
#  DAFTAR LENGKAP POLA URL  (HP + PC + link pendek)
# ─────────────────────────────────────────────────────────
URL_PATTERNS = [

    # ── YOUTUBE ──────────────────────────────────────────
    # PC : youtube.com/watch?v=...
    # PC : youtube.com/shorts/...
    # HP : m.youtube.com/watch?v=...
    # App: youtu.be/...  (link pendek share)
    # Music: music.youtube.com/watch?v=...
    r'https?://(www\.|m\.)?youtube\.com/watch\?',
    r'https?://(www\.|m\.)?youtube\.com/shorts/\S+',
    r'https?://(www\.|m\.)?youtube\.com/live/\S+',
    r'https?://(www\.|m\.)?youtube\.com/embed/\S+',
    r'https?://youtu\.be/\S+',
    r'https?://music\.youtube\.com/watch\?',

    # ── TIKTOK ───────────────────────────────────────────
    # PC : www.tiktok.com/@user/video/123...
    # HP : m.tiktok.com/@user/video/123...
    # App pendek: vm.tiktok.com/XXXXX  (share dari app)
    # App pendek: vt.tiktok.com/XXXXX
    # App pendek: www.tiktok.com/t/XXXXX
    r'https?://(www\.|m\.)?tiktok\.com/@\S+',
    r'https?://(www\.|m\.)?tiktok\.com/video/\d+',
    r'https?://vm\.tiktok\.com/\S+',
    r'https?://vt\.tiktok\.com/\S+',
    r'https?://(www\.)?tiktok\.com/t/\S+',

    # ── FACEBOOK ─────────────────────────────────────────
    # PC : facebook.com/watch/?v=...
    # PC : facebook.com/video/...
    # PC : facebook.com/reel/...
    # PC : facebook.com/share/v/...  (link share baru)
    # HP : m.facebook.com/...
    # App: fb.watch/XXXXX  (link pendek)
    r'https?://(www\.|m\.)?facebook\.com/watch',
    r'https?://(www\.|m\.)?facebook\.com/\S+/videos/\S+',
    r'https?://(www\.|m\.)?facebook\.com/video/\S+',
    r'https?://(www\.|m\.)?facebook\.com/reel/\S+',
    r'https?://(www\.|m\.)?facebook\.com/share/(v|r)/\S+',
    r'https?://(www\.|m\.)?facebook\.com/story\.php',
    r'https?://fb\.watch/\S+',

    # ── INSTAGRAM ────────────────────────────────────────
    # PC/HP : instagram.com/p/...  (post)
    # PC/HP : instagram.com/reel/...  (reels)
    # PC/HP : instagram.com/tv/...  (IGTV)
    # App pendek: instagr.am/p/...
    r'https?://(www\.)?instagram\.com/p/\S+',
    r'https?://(www\.)?instagram\.com/reel/\S+',
    r'https?://(www\.)?instagram\.com/reels/\S+',
    r'https?://(www\.)?instagram\.com/tv/\S+',
    r'https?://instagr\.am/(p|reel|tv)/\S+',
    
    # ── TWITTER (X) ──────────────────────────────────────
    r'https?://(www\.|m\.)?(twitter|x)\.com/\S+/status/\d+',
    
    # ── PINTEREST ────────────────────────────────────────
    r'https?://([a-zA-Z0-9-]+\.)?pinterest\.[a-z\.]+/pin/\d+',
    r'https?://pin\.it/\S+',
    
    # ── REDDIT ───────────────────────────────────────────
    r'https?://(www\.)?reddit\.com/r/\S+/comments/\S+',
    
    # ── TWITCH ───────────────────────────────────────────
    r'https?://(www\.)?twitch\.tv/\S+',
    r'https?://clips\.twitch\.tv/\S+',
]

def is_valid_url(url):
    url = url.strip()
    for pattern in URL_PATTERNS:
        if re.match(pattern, url, re.IGNORECASE):
            return True
    return False

def detect_platform(url):
    u = url.lower()
    if 'tiktok.com' in u: return 'tiktok'
    if 'youtube.com' in u or 'youtu.be' in u: return 'youtube'
    if 'facebook.com' in u or 'fb.watch' in u: return 'facebook'
    if 'instagram.com' in u or 'instagr.am' in u: return 'instagram'
    if 'twitter.com' in u or 'x.com' in u: return 'twitter'
    if 'pinterest.com' in u or 'pin.it' in u: return 'pinterest'
    if 'reddit.com' in u: return 'reddit'
    if 'twitch.tv' in u: return 'twitch'
    return 'unknown'

# ─────────────────────────────────────────────────────────
#  OPSI yt-dlp per platform  (User-Agent HP/PC & headers)
# ─────────────────────────────────────────────────────────
UA_DESKTOP = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)
UA_MOBILE = (
    'Mozilla/5.0 (Linux; Android 13; Pixel 7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.6367.82 Mobile Safari/537.36'
)

def get_ydl_opts(platform, skip_download=True):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': skip_download,
        'nocheckcertificate': True,
        'noplaylist': True,
    }

    if platform == 'tiktok':
        opts['http_headers'] = {
            'User-Agent': UA_DESKTOP,
            'Referer': 'https://www.tiktok.com/',
            'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        # Paksa resolusi web agar tidak dapat format "default" kosong
        opts['extractor_args'] = {
            'tiktok': {'webpage_download': ['true']}
        }

    elif platform == 'facebook':
        opts['http_headers'] = {
            'User-Agent': UA_DESKTOP,
            'Accept-Language': 'id-ID,id;q=0.9',
        }

    elif platform == 'instagram':
        opts['http_headers'] = {
            'User-Agent': UA_MOBILE,          # Instagram lebih suka UA mobile
            'Accept-Language': 'id-ID,id;q=0.9',
        }

    # Untuk youtube kita biarkan default yt-dlp karena override player_client bisa membatasi format ke 360p
    elif platform == 'youtube':
        pass

    return opts


# ─────────────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────────────
@app.route('/')
def index():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/manifest.json')
def serve_manifest():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'manifest.json'), mimetype='application/json')

@app.route('/sw.js')
def serve_sw():
    return send_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sw.js'), mimetype='application/javascript')


@app.route('/get_formats', methods=['POST'])
def get_formats():
    data = request.get_json()
    url  = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL tidak boleh kosong.'}), 400

    if not is_valid_url(url):
        return jsonify({
            'error': (
                'Link tidak dikenali.\n'
                'Pastikan link berasal dari: YouTube, TikTok, Facebook, Instagram, Twitter(X), Pinterest, Reddit, atau Twitch.\n'
                'Link pendek (youtu.be, vm.tiktok.com, pin.it) juga didukung.'
            )
        }), 400

    platform = detect_platform(url)
    ydl_opts = get_ydl_opts(platform, skip_download=True)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Playlist → ambil entry pertama
            if info.get('_type') == 'playlist':
                entries = [e for e in (info.get('entries') or []) if e]
                if not entries:
                    return jsonify({'error': 'Playlist kosong atau tidak dapat diakses.'}), 400
                entry = entries[0]
                # Jika entry hanya referensi, ekstrak penuh
                if not entry.get('formats') and entry.get('url'):
                    info = ydl.extract_info(entry['url'], download=False)
                else:
                    info = entry

        title     = info.get('title', 'Video')
        thumbnail = info.get('thumbnail', '')
        duration  = info.get('duration') or 0
        formats   = info.get('formats') or []

        available = []
        seen_h    = set()

        # ── 1. Format yang sudah mengandung video + audio ──
        for f in formats:
            h      = f.get('height')
            vc     = f.get('vcodec', 'none')
            ac     = f.get('acodec', 'none')
            if h and vc and vc != 'none' and ac and ac != 'none':
                if h not in seen_h:
                    seen_h.add(h)
                    available.append({
                        'format_id': f['format_id'],
                        'label':     f'{h}p',
                        'detail':    'Video + Audio',
                        'height':    h,
                        'type':      'video',
                        'ext':       f.get('ext', 'mp4'),
                        'filesize':  f.get('filesize') or f.get('filesize_approx') or 0,
                    })

        # ── 2. Video-only → akan di-merge dengan bestaudio ──
        for f in formats:
            h  = f.get('height')
            vc = f.get('vcodec', 'none')
            ac = f.get('acodec', 'none')
            if h and vc and vc != 'none' and (not ac or ac == 'none'):
                if h not in seen_h:
                    seen_h.add(h)
                    available.append({
                        'format_id': f'{f["format_id"]}+bestaudio/best',
                        'label':     f'{h}p',
                        'detail':    'Video HD',
                        'height':    h,
                        'type':      'video_merge',
                        'ext':       'mp4',
                        'filesize':  f.get('filesize') or f.get('filesize_approx') or 0,
                    })

        # ── 3. Fallback: tidak ada format terdeteksi ──
        if not available:
            available.append({
                'format_id': 'best',
                'label':     'Kualitas Terbaik',
                'detail':    'Auto',
                'height':    9999,
                'type':      'video',
                'ext':       'mp4',
                'filesize':  0,
            })

        # ── 4. Audio MP3 selalu tersedia ──
        available.append({
            'format_id': 'bestaudio/best',
            'label':     'Audio',
            'detail':    'MP3 192kbps',
            'height':    -1,
            'type':      'audio',
            'ext':       'mp3',
            'filesize':  0,
        })

        available.sort(key=lambda x: x['height'], reverse=True)

        mins = int(duration // 60)
        secs = int(duration % 60)

        return jsonify({
            'title':     title,
            'thumbnail': thumbnail,
            'duration':  f'{mins}:{secs:02d}' if duration else 'N/A',
            'platform':  platform,
            'formats':   available,
        })

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if 'private' in msg.lower():
            return jsonify({'error': 'Video bersifat privat dan tidak dapat didownload.'}), 400
        if 'age' in msg.lower():
            return jsonify({'error': 'Video dibatasi usia dan memerlukan login.'}), 400
        if 'login' in msg.lower() or 'sign in' in msg.lower():
            return jsonify({'error': 'Video ini memerlukan login akun.'}), 400
        return jsonify({'error': f'Gagal membaca video: {msg}'}), 500
    except Exception as e:
        return jsonify({'error': f'Kesalahan server: {str(e)}'}), 500


@app.route('/start_download', methods=['POST'])
def start_download():
    data       = request.get_json()
    url        = data.get('url', '').strip()
    format_id  = data.get('format_id', 'best')
    fmt_type   = data.get('type', 'video')

    if not url:
        return jsonify({'error': 'URL tidak boleh kosong.'}), 400

    task_id = str(uuid.uuid4())
    active_tasks[task_id] = {
        'status': 'downloading',
        'progress': '0%',
        'eta': '',
        'filepath': None,
        'cancel': False,
        'error': None
    }

    def download_thread(tid, t_url, t_format_id, t_fmt_type):
        try:
            platform = detect_platform(t_url)
            tmpl     = os.path.join(DOWNLOAD_FOLDER, f'{tid}_%(title).120s.%(ext)s')

            ydl_opts = get_ydl_opts(platform, skip_download=False)
            ydl_opts.update({
                'quiet':               False,
                'outtmpl':             tmpl,
                'merge_output_format': 'mp4',
                'noplaylist':          True,
            })

            if t_fmt_type == 'audio':
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key':             'FFmpegExtractAudio',
                    'preferredcodec':  'mp3',
                    'preferredquality':'192',
                }]
            else:
                ydl_opts['format'] = t_format_id

            last_file = [None]

            def hook(d):
                if active_tasks[tid].get('cancel'):
                    raise Exception("CANCELLED_BY_USER")
                
                if d['status'] == 'downloading':
                    p = d.get('_percent_str', '0%').strip('\x1b[0;94m').strip('\x1b[0m').strip()
                    e = d.get('_eta_str', '')
                    active_tasks[tid]['progress'] = p
                    active_tasks[tid]['eta'] = e
                elif d['status'] == 'finished':
                    last_file[0] = d.get('filename')

            ydl_opts['progress_hooks'] = [hook]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info     = ydl.extract_info(t_url, download=True)
                prepared = ydl.prepare_filename(info)

            if active_tasks[tid].get('cancel'):
                return

            candidates = []
            if last_file[0] and os.path.exists(last_file[0]):
                candidates.append(last_file[0])

            base = os.path.splitext(prepared)[0]
            for ext in ('.mp4', '.mp3', '.mkv', '.webm', '.m4a', '.mov', '.avi'):
                p = base + ext
                if os.path.exists(p):
                    candidates.append(p)

            all_files = glob.glob(os.path.join(DOWNLOAD_FOLDER, f'{tid}_*'))
            if all_files:
                candidates.append(max(all_files, key=os.path.getctime))

            if not candidates:
                active_tasks[tid]['status'] = 'error'
                active_tasks[tid]['error'] = 'File tidak ditemukan setelah download.'
                return

            active_tasks[tid]['filepath'] = candidates[0]
            active_tasks[tid]['status'] = 'finished'

        except Exception as e:
            msg = str(e)
            if 'CANCELLED_BY_USER' in msg:
                active_tasks[tid]['status'] = 'cancelled'
            else:
                active_tasks[tid]['status'] = 'error'
                active_tasks[tid]['error'] = f'Gagal mendownload: {msg}'

            # Cleanup any partial files for this task
            for f in glob.glob(os.path.join(DOWNLOAD_FOLDER, f'{tid}_*')):
                try: os.remove(f)
                except: pass

    threading.Thread(target=download_thread, args=(task_id, url, format_id, fmt_type), daemon=True).start()
    return jsonify({'task_id': task_id})


@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    if task_id not in active_tasks:
        return jsonify({'error': 'Task tidak ditemukan'}), 404
    return jsonify(active_tasks[task_id])


@app.route('/cancel/<task_id>', methods=['POST'])
def cancel_task(task_id):
    if task_id in active_tasks:
        active_tasks[task_id]['cancel'] = True
        return jsonify({'message': 'Task cancelled'})
    return jsonify({'error': 'Task tidak ditemukan'}), 404


@app.route('/file/<task_id>', methods=['GET'])
def get_file(task_id):
    if task_id not in active_tasks:
        return "Not found", 404
    t = active_tasks[task_id]
    if t['status'] != 'finished' or not t.get('filepath'):
        return "File not ready", 400
    
    fp = t['filepath']
    
    # Remove task_id prefix for the downloaded filename
    dl_name = os.path.basename(fp)
    if dl_name.startswith(f'{task_id}_'):
        dl_name = dl_name[len(task_id)+1:]

    return send_file(
        fp,
        as_attachment=True,
        download_name=dl_name
    )


if __name__ == '__main__':
    print('=' * 75)
    print('  VideoSaver — YT · TT · FB · IG · Twitter · Pinterest · Reddit · Twitch')
    print('=' * 75)
    print('  Buka browser: http://localhost:5000')
    print('=' * 75)
    app.run(debug=False, host='0.0.0.0', port=5000)
