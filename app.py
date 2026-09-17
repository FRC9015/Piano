import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from flask import Flask, request, render_template_string, jsonify
from flask_cors import CORS 
import mido
import serial

app = Flask(__name__)
CORS(app)
# --- State Management ---
song_queue = []
queue_lock = threading.Lock()

current_song_title = None
is_playing = False
is_paused = False
skip_current_song = False
stop_playback_flag = False

# Setup Serial Connection to Pico 2W
try:
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
    print("Successfully connected to Pico over serial.")
except Exception as e:
    print(f"Serial warning: {e}. Running in simulation mode.")
    ser = None

MIDI_DIR = "./midi_cache"
os.makedirs(MIDI_DIR, exist_ok=True)

# --- KEYBOARD NOTE MAP ---
NOTE_MAP = {
    # BOARD 0x42 (Bass - White keys)
    36: ("0x42", 0),   # C2
    38: ("0x42", 1),   # d2
    40: ("0x42", 2),   # E2
    41: ("0x42", 3),   # F2
    43: ("0x42", 4),   # g2
    45: ("0x42", 5),   # A2
    47: ("0x42", 6),   # b2
    48: ("0x42", 7),   # C3
    50: ("0x42", 8),   # d3
    52: ("0x42", 9),   # E3
    53: ("0x42", 10),  # F3
    55: ("0x42", 11),  # g3
    57: ("0x42", 12),  # A3
    59: ("0x42", 13),  # b3
    60: ("0x42", 14),  # C4
    62: ("0x42", 15),  # d4

    # BOARD 0x44 (Bass/Middle - Black keys)
    37: ("0x44", 0),  # C2#
    39: ("0x44", 1),  # D2#
    42: ("0x44", 2),  # F2#
    44: ("0x44", 3),   # g2#
    46: ("0x44", 4),   # A2#
    49: ("0x44", 5),   # C3#
    51: ("0x44", 6),   # D3#
    54: ("0x44", 7),   # F3#
    56: ("0x44", 8),   # g3#
    58: ("0x44", 9),   # A3#
    61: ("0x44", 10),   # C4#
    63: ("0x44", 11),   # D4#

    # BOARD 0x40 (Middle/High - White keys)
    64: ("0x40", 0),   # E4
    65: ("0x40", 1),   # F4
    67: ("0x40", 2),   # g4
    69: ("0x40", 3),   # A4
    71: ("0x40", 4),   # b4
    72: ("0x40", 5),   # C5
    74: ("0x40", 6),   # d5
    76: ("0x40", 7),   # E5

    # BOARD 0x41 (Middle/High - Black keys)
    66: ("0x41", 0),   # F4#
    68: ("0x41", 1),  # G4#
    70: ("0x41", 5),  # A4#
    73: ("0x41", 6),   # C5#
    75: ("0x41", 7),   # D5#
    78: ("0x41", 8),   # F5#
    80: ("0x41", 9),   # G5#
    82: ("0x41", 10),   # A5$ (A5# / Bb5)
    85: ("0x41", 11),   # C6#
    87: ("0x41", 12),   # D6#
    90: ("0x41", 13),   # F6#
    92: ("0x41", 14),   # G6#
    94: ("0x41", 15),   # A6#

    # BOARD 0x50 (High - White keys)
    77: ("0x50", 0),   # F5
    79: ("0x50", 1),   # g5
    81: ("0x50", 2),   # A5
    83: ("0x50", 3),   # b5
    84: ("0x50", 4),   # C6
    86: ("0x50", 5),   # d6
    88: ("0x50", 6),   # E6
    89: ("0x50", 7),   # F6
    91: ("0x50", 8),   # g6
    93: ("0x50", 9),   # A6
    95: ("0x50", 10),   # b6
    96: ("0x50", 11)    # C7
}

def send_pico_reset():
    if ser:
        ser.write(b"RESET\n")
        ser.flush()
def normalize_name(name):
    """Strips extensions, symbols, spaces, and casing for flexible matching."""
    base = os.path.splitext(name)[0]
    return "".join(c for c in base if c.isalnum()).lower()

def fetch_midi_from_web(song_name):
    """Searches local cache, then FreeMidi (using persistent Session cookies), then BitMidi."""
    query_norm = normalize_name(song_name)
    
    # 1. CHECK LOCAL CACHE
    if os.path.exists(MIDI_DIR):
        for filename in os.listdir(MIDI_DIR):
            if normalize_name(filename) == query_norm:
                cached_path = os.path.join(MIDI_DIR, filename)
                print(f"[Cache Hit] Found '{filename}' in cache for '{song_name}'")
                return cached_path

    safe_name = "".join(c for c in song_name if c.isalnum() or c in (' ', '_', '-')).strip().lower().replace(" ", "-")
    midi_path = os.path.join(MIDI_DIR, f"{safe_name}.mid")

    # Use a persistent Session to store cookies between page visit and download
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive'
    })

    # ==========================================
    # 2. SEARCH & DOWNLOAD FROM FREEMIDI.ORG
    # ==========================================
    try:
        print(f"[FreeMidi] Searching for '{song_name}'...")
        search_url = f"https://freemidi.org/search?q={quote(song_name)}"
        res = session.get(search_url, timeout=10)
        
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Find the song result page
            song_page_url = None
            for a in soup.find_all('a', href=True):
                href = a['href']
                if 'download-' in href or 'download3-' in href:
                    song_page_url = urljoin("https://freemidi.org/", href)
                    break
                    
            if song_page_url:
                print(f"[FreeMidi] Found song page: {song_page_url}")
                page_res = session.get(song_page_url, timeout=10)
                page_soup = BeautifulSoup(page_res.text, 'html.parser')
                
                # Find the download getter link
                getter_url = None
                for a in page_soup.find_all('a', href=True):
                    href = a['href']
                    if 'getter-' in href:
                        getter_url = urljoin("https://freemidi.org/", href)
                        break
                        
                if getter_url:
                    print(f"[FreeMidi] Downloading from: {getter_url}")
                    session.headers['Referer'] = song_page_url  # Required by FreeMidi
                    
                    midi_res = session.get(getter_url, timeout=15)
                    midi_data = midi_res.content
                    
                    # Verify MIDI header ('MThd')
                    if midi_data.startswith(b'MThd'):
                        with open(midi_path, 'wb') as f:
                            f.write(midi_data)
                        print(f"[FreeMidi] Successfully downloaded and cached to {midi_path}")
                        return midi_path
                    else:
                        print(f"[FreeMidi] Received non-MIDI data ({len(midi_data)} bytes). Falling back...")
    except Exception as e:
        print(f"[FreeMidi] Error: {e}")

    # ==========================================
    # 3. BACKUP: SEARCH BITMIDI.COM
    # ==========================================
    try:
        print(f"[BitMidi Backup] Searching for '{song_name}'...")
        search_url = f"https://bitmidi.com/search?q={quote(song_name)}"
        response = session.get(search_url, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            song_page_url = None
            for a in soup.find_all('a', href=True):
                href = a['href'].strip()
                if href.endswith('-mid') and not href.startswith('/random') and not href.startswith('/search'):
                    song_page_url = urljoin("https://bitmidi.com", href)
                    break
                    
            if song_page_url:
                page_res = session.get(song_page_url, timeout=10)
                page_soup = BeautifulSoup(page_res.text, 'html.parser')
                for a in page_soup.find_all('a', href=True):
                    href = a['href'].strip()
                    if '/uploads/' in href or href.endswith('.mid'):
                        file_url = urljoin("https://bitmidi.com", href)
                        midi_data = session.get(file_url, timeout=15).content
                        if midi_data.startswith(b'MThd'):
                            with open(midi_path, 'wb') as f:
                                f.write(midi_data)
                            print(f"[BitMidi] Successfully saved to {midi_path}")
                            return midi_path
    except Exception as e:
        print(f"[BitMidi Backup] Error: {e}")

    print(f"[Search Failed] Could not find '{song_name}' on FreeMidi or BitMidi.")
    return None



def stream_midi_live(midi_filename):
    global skip_current_song, stop_playback_flag, is_paused
    try:
        mid = mido.MidiFile(midi_filename)
    except Exception as e:
        print(f"Error parsing MIDI: {e}")
        return

    print(f"Streaming MIDI live: {midi_filename}")
    
    for msg in mid.play(meta_messages=False):
        # Check Stop or Skip flags
        if skip_current_song or stop_playback_flag:
            break

        # Handle Pause
        while is_paused:
            time.sleep(0.1)
            if skip_current_song or stop_playback_flag:
                break

        if msg.type not in ['note_on', 'note_off']:
            continue
        if msg.channel == 9:
            continue

        wait_ms = int(msg.time * 1000)
        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)

        note = msg.note
        if note in NOTE_MAP:
            addr, pin = NOTE_MAP[note]
            action = "1" if (msg.type == 'note_on' and msg.velocity > 0) else "0"
            packet = f"0,{addr},{pin},{action}\n"
            
            if ser:
                ser.write(packet.encode('utf-8'))
                ser.flush()

    # Reset keys at the end or on skip/stop
    send_pico_reset()

def playback_worker():
    global current_song_title, is_playing, skip_current_song, stop_playback_flag
    while True:
        item = None
        with queue_lock:
            if song_queue:
                item = song_queue.pop(0)

        if not item:
            current_song_title = None
            is_playing = False
            time.sleep(0.5)
            continue

        song_name, midi_file = item
        current_song_title = song_name
        is_playing = True
        skip_current_song = False
        stop_playback_flag = False

        print("Clearing/Resetting servos...")
        send_pico_reset()
        time.sleep(0.5)

        print(f"\n--- Queue Processing: {song_name} ---")
        if midi_file and os.path.exists(midi_file):
            stream_midi_live(midi_file)
        else:
            print(f"File missing for: {song_name}")

        send_pico_reset()
        time.sleep(1.2)


threading.Thread(target=playback_worker, daemon=True).start()

# --- WEB UI TEMPLATE ---
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FRC 9015 | Robotic Piano Jukebox</title>
    <style>
        :root {
            --bg-dark: #07090e;
            --card-bg: #0d1322;
            --navy-blue: #1b2a4a;
            --team-orange: #ff6600;
            --orange-glow: rgba(255, 102, 0, 0.4);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            margin: 0; padding: 0;
            display: flex; flex-direction: column; justify-content: center; align-items: center;
            min-height: 100vh;
        }
        .container {
            background-color: var(--card-bg);
            border: 2px solid var(--navy-blue);
            border-radius: 16px;
            width: 90%;
            max-width: 440px;
            box-shadow: 0 15px 30px rgba(0, 0, 0, 0.7), 0 0 20px var(--orange-glow);
            text-align: center;
            overflow: hidden;
            margin: 1.5rem 0;
        }
        .banner-container {
            width: 100%;
            background-color: #05070a;
            padding: 12px;
            box-sizing: border-box;
            border-bottom: 2px solid var(--navy-blue);
        }
        .banner-container img {
            width: 100%;
            height: auto;
            display: block;
            border-radius: 8px;
        }
        .content-padding {
            padding: 1.5rem 1.8rem 2rem 1.8rem;
        }
        
        /* Now Playing Bar & Equalizer */
        .now-playing-card {
            background: #060911;
            border: 1px solid var(--navy-blue);
            border-radius: 10px;
            padding: 0.8rem 1rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
        }
        .np-text {
            font-size: 0.88rem;
            text-align: left;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 80%;
        }
        .np-text span {
            display: block;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--team-orange);
            font-weight: 700;
        }
        .equalizer {
            display: flex;
            align-items: flex-end;
            gap: 3px;
            height: 18px;
        }
        .equalizer .bar {
            width: 3px;
            height: 4px;
            background: var(--team-orange);
            border-radius: 2px;
            transition: height 0.2s ease;
        }
        .equalizer.active .bar:nth-child(1) { animation: bounce 0.8s infinite alternate ease-in-out; }
        .equalizer.active .bar:nth-child(2) { animation: bounce 1.1s infinite alternate ease-in-out; }
        .equalizer.active .bar:nth-child(3) { animation: bounce 0.6s infinite alternate ease-in-out; }
        .equalizer.active .bar:nth-child(4) { animation: bounce 0.9s infinite alternate ease-in-out; }
        @keyframes bounce {
            0% { height: 4px; }
            100% { height: 18px; }
        }

        .team-title {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--team-orange);
            font-weight: 800;
            margin-bottom: 0.2rem;
        }
        h1 {
            font-size: 1.45rem;
            margin: 0.2rem 0 0.5rem 0;
            color: #ffffff;
        }
        p {
            color: var(--text-muted);
            font-size: 0.9rem;
            margin-bottom: 1.4rem;
        }
        
        /* Toast notification */
        .toast-banner {
            background: rgba(255, 102, 0, 0.15);
            border: 1px solid var(--team-orange);
            color: #ff944d;
            border-radius: 8px;
            padding: 0.75rem;
            margin-bottom: 1.2rem;
            font-size: 0.88rem;
            animation: fadeIn 0.3s ease-in-out;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }

        input[type="text"] {
            width: 100%;
            padding: 0.9rem;
            font-size: 1rem;
            background-color: #05070a;
            border: 1px solid var(--navy-blue);
            border-radius: 8px;
            color: white;
            box-sizing: border-box;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        input[type="text"]:focus {
            border-color: var(--team-orange);
            box-shadow: 0 0 0 3px var(--orange-glow);
        }
        .btn-submit {
            width: 100%;
            margin-top: 1rem;
            padding: 0.9rem;
            font-size: 1rem;
            font-weight: 700;
            background-color: var(--team-orange);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: background-color 0.2s, transform 0.1s;
        }
        .btn-submit:hover { background-color: #e55c00; }
        .btn-submit:active { transform: scale(0.98); }

        /* Controls Section */
        .controls-row {
            display: flex;
            gap: 8px;
            margin-top: 1.2rem;
        }
        .btn-ctrl {
            flex: 1;
            padding: 0.55rem;
            font-size: 0.78rem;
            font-weight: 600;
            background-color: #0d1322;
            color: var(--text-muted);
            border: 1px solid var(--navy-blue);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-ctrl:hover {
            color: #fff;
            border-color: var(--team-orange);
        }

        /* Dropdown Queue Section */
        .queue-toggle {
            margin-top: 1.5rem;
            padding-top: 1rem;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            cursor: pointer;
            user-select: none;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 6px;
            font-size: 0.9rem;
            color: var(--text-muted);
        }
        .queue-toggle strong {
            color: var(--team-orange);
        }
        .queue-toggle .arrow {
            font-size: 0.75rem;
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .queue-toggle.open .arrow {
            transform: rotate(180deg);
        }
        
        .queue-dropdown {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            text-align: left;
            margin-top: 0.5rem;
        }
        .queue-dropdown.open {
            max-height: 250px;
            overflow-y: auto;
        }
        .queue-list {
            list-style: none;
            padding: 0;
            margin: 0.5rem 0 0 0;
            font-size: 0.85rem;
            background: #060911;
            border-radius: 8px;
            border: 1px solid var(--navy-blue);
        }
        .queue-list li {
            padding: 0.6rem 0.8rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .queue-list li:last-child {
            border-bottom: none;
        }
        .queue-badge {
            background: var(--navy-blue);
            color: var(--team-orange);
            font-weight: bold;
            font-size: 0.7rem;
            padding: 2px 6px;
            border-radius: 4px;
        }

        .footer {
            margin-bottom: 2rem;
            font-size: 0.75rem;
            color: #6b7280;
        }
        .footer a {
            color: var(--team-orange);
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="banner-container">
            <img src="http://static1.squarespace.com/static/629ba0c6fa223a4e086940c9/t/63784055622e64425eb8beda/1668825173226/Untitled+design.png" alt="Questionable Engineering Banner">
        </div>
        <div class="content-padding">
            <!-- Now Playing & Equalizer -->
            <div class="now-playing-card">
                <div class="np-text">
                    <span>Now Playing</span>
                    <strong id="now-playing-title">{{ current_song if current_song else 'Piano is Idle' }}</strong>
                </div>
                <div id="equalizer" class="equalizer {{ 'active' if is_playing and not is_paused else '' }}">
                    <div class="bar"></div>
                    <div class="bar"></div>
                    <div class="bar"></div>
                    <div class="bar"></div>
                </div>
            </div>

            <div class="team-title">FRC Team 9015 • Questionable Engineering</div>
            <h1>Robotic Window Piano</h1>
            <p>Type a song below to queue it up live!</p>

            <!-- Success message toast if submitted -->
            {% if toast %}
            <div class="toast-banner">
                {{ toast }}
            </div>
            {% endif %}

            <form method="POST" action="/request">
                <input type="text" name="song" placeholder="e.g. Tetris, Bohemian Rhapsody, Fur Elise" autocomplete="off" required />
                <button type="submit" class="btn-submit">Queue Song</button>
            </form>

            <!-- Playback Control Bar -->
            <div class="controls-row">
                <button type="button" class="btn-ctrl" onclick="sendControl('pause')">⏸ Pause</button>
                <button type="button" class="btn-ctrl" onclick="sendControl('resume')">▶ Resume</button>
                <button type="button" class="btn-ctrl" onclick="sendControl('skip')">⏭ Skip</button>
                <button type="button" class="btn-ctrl" onclick="sendControl('stop')">⏹ Stop</button>
            </div>

            <!-- Expandable Queue -->
            <div class="queue-toggle" id="queue-toggle" onclick="toggleQueue()">
                <span>Songs in Queue: <strong id="queue-count">{{ queue|length }}</strong></span>
                <span class="arrow">▼</span>
            </div>

            <div class="queue-dropdown" id="queue-dropdown">
                <ul class="queue-list" id="queue-items">
                    {% if queue %}
                        {% for song in queue %}
                        <li><span class="queue-badge">#{{ loop.index }}</span> {{ song }}</li>
                        {% endfor %}
                    {% else %}
                        <li style="color: var(--text-muted); justify-content: center;">Queue is currently empty</li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </div>
    <div class="footer">
        Built by <a href="https://www.qefrc.tech" target="_blank">Questionable Engineering</a>
    </div>

    <script>
        function toggleQueue() {
            const toggle = document.getElementById('queue-toggle');
            const dropdown = document.getElementById('queue-dropdown');
            toggle.classList.toggle('open');
            dropdown.classList.toggle('open');
        }

        function sendControl(action) {
            fetch('/api/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: action })
            }).then(() => fetchStatus());
        }

        // Real-time polling so client updates automatically without page reloads
        function fetchStatus() {
            fetch('/api/status')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('now-playing-title').innerText = data.current_song || 'Piano is Idle';
                    document.getElementById('queue-count').innerText = data.queue.length;

                    const eq = document.getElementById('equalizer');
                    if (data.is_playing && !data.is_paused) {
                        eq.classList.add('active');
                    } else {
                        eq.classList.remove('active');
                    }

                    const list = document.getElementById('queue-items');
                    if (data.queue.length === 0) {
                        list.innerHTML = '<li style="color: var(--text-muted); justify-content: center;">Queue is currently empty</li>';
                    } else {
                        list.innerHTML = data.queue.map((s, idx) => `<li><span class="queue-badge">#${idx + 1}</span> ${s}</li>`).join('');
                    }
                })
                .catch(err => console.error("Poll error:", err));
        }

        // Refresh UI state every 2 seconds
        setInterval(fetchStatus, 2000);
    </script>
</body>
</html>"""

@app.route('/', methods=['GET'])
def index():
    toast = request.args.get('toast', None)
    with queue_lock:
        queue_copy = list(song_queue)
    return render_template_string(
        HTML_PAGE,
        current_song=current_song_title,
        is_playing=is_playing,
        is_paused=is_paused,
        queue=queue_copy,
        toast=toast
    )

@app.route('/request', methods=['POST'])
def handle_request():
    song = request.form.get('song', '').strip()
    if not song:
        return jsonify({'status': 'error', 'message': 'Please enter a song name.'}), 400

    print(f"[Request Received] Validating search for '{song}'...")
    
    # 1. Search cache and web immediately
    midi_file = fetch_midi_from_web(song)
    
    # 2. If NOT found, send 404 error back to the user
    if not midi_file:
        return jsonify({
            'status': 'not_found',
            'message': f"❌ Could not find a playable MIDI for '{song}'. Try another title or artist!"
        }), 404

    # 3. If found, add (song_name, midi_file) to the queue
    with queue_lock:
        song_queue.append((song, midi_file))
        position = len(song_queue)

    return jsonify({
        'status': 'success',
        'message': f"🎉 '{song}' added to queue! Position: {position}",
        'position': position
    })

@app.route('/api/status', methods=['GET'])
def api_status():
    with queue_lock:
        queue_names = [item[0] for item in song_queue]
    return jsonify({
        'current_song': current_song_title,
        'is_playing': is_playing,
        'is_paused': is_paused,
        'queue': queue_names
    })

# --- ADMIN CONFIGURATION ---
ADMIN_PIN = "qefrc"  # <--- Set your team PIN here

@app.route('/api/control', methods=['POST'])
def api_control():
    global is_paused, skip_current_song, stop_playback_flag
    data = request.get_json() or {}
    
    # 1. VERIFY TEAM PIN
    pin = str(data.get('pin', '')).strip()
    if pin != ADMIN_PIN:
        return jsonify({'status': 'error', 'message': 'Unauthorized: Invalid PIN'}), 403

    # 2. EXECUTE ACTION IF PIN IS VALID
    action = data.get('action')
    if action == 'pause':
        is_paused = True
        send_pico_reset()
    elif action == 'resume':
        is_paused = False
    elif action == 'skip':
        skip_current_song = True
    elif action == 'stop':
        stop_playback_flag = True
        with queue_lock:
            song_queue.clear()
        send_pico_reset()

    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
