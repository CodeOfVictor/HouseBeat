"""HouseBeat: play your PC audio on every speaker in the house, in sync.

Windows sends its audio to a virtual device (the source). HouseBeat captures it and:
  - plays it on any Windows output (headphones, Bluetooth speakers...) with its own delay,
  - streams it as MP3/WAV to every Chromecast / Google Cast device with its own delay.
Cast devices are measured and aligned automatically; whatever cannot be measured
(TV processing, Bluetooth, distance) is fine-tuned by ear with a per-speaker trim.

Control panel: http://localhost:8770
"""
import json
import os
import socket
import sys
import threading
import time
import warnings
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote, unquote, urlparse, parse_qs

import winaudio

if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--set-default":
    # Helper process: must run before soundcard initializes COM (see winaudio.py)
    winaudio.set_default_now(sys.argv[2])
    sys.exit(0)

import numpy as np
import soundcard as sc
import lameenc
import pychromecast

VERSION = "1.0.0"
SR = 48000
CH = 2
BLOCK = 480                 # 10 ms
RING_SECS = 20
MAX_DELAY_MS = 15000
PORT = int(os.environ.get("HOUSEBEAT_PORT", "8770"))
MEDIA_RECEIVER = "CC1AD845"   # Google's Default Media Receiver app
# Virtual output devices that can act as the source (first match wins)
VIRTUAL_CANDIDATES = ("CABLE Input", "Steam Streaming Speakers", "Voicemeeter Input", "VB-Audio")

FROZEN = getattr(sys, "frozen", False)
APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(APP_DIR, "web")
DATA_DIR = os.environ.get("HOUSEBEAT_DATA_DIR") or os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "HouseBeat")
CFG_PATH = os.path.join(DATA_DIR, "config.json")

warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)

cfg = {
    "mode": "sync",         # sync: everything delayed and aligned / direct: main output plays live
    "main": "",             # real main output (e.g. headphones): where Windows plays when HouseBeat is off
    "virtual": "",          # optional override for the virtual source device
    "outputs": {},          # Windows outputs (headphones, Bluetooth speakers...) -> settings
    "master": 1.0,
    "casts": {},
}
active = False              # master switch: always starts off and is never saved
source = ""                 # device being captured right now
routed_at = 0.0             # last time HouseBeat itself changed the Windows default output
cfg_lock = threading.Lock()
log_lines = []


def log(key, **params):
    """Log entries are translation keys + parameters: the panel shows them in the user's language."""
    entry = {"t": time.strftime("%H:%M:%S"), "k": key, "p": params}
    print(entry["t"], key, params, flush=True)
    log_lines.append(entry)
    del log_lines[:-50]


def load_cfg():
    if os.path.exists(CFG_PATH):
        with open(CFG_PATH, encoding="utf-8-sig") as f:
            saved = json.load(f)
        for key in ("mode", "main", "virtual", "master"):
            if key in saved:
                cfg[key] = saved[key]
        cfg["outputs"].update(saved.get("outputs", {}))
        cfg["casts"].update(saved.get("casts", {}))


def save_cfg():
    with cfg_lock:
        data = json.dumps(cfg, indent=2, ensure_ascii=False)
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = CFG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, CFG_PATH)


def ms_to_frames(ms):
    return int(max(0, min(MAX_DELAY_MS, ms)) * SR / 1000)


def local_ip():
    """LAN address the Cast devices can reach (no packet is actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def short(dev):
    return dev[dev.find("(") + 1:dev.rfind(")")] if "(" in dev else dev


def find_virtual():
    """The virtual device used as source, or None if there is none installed."""
    speakers = sc.all_speakers()
    if cfg["virtual"]:
        for s in speakers:
            if s.name == cfg["virtual"]:
                return s
    for candidate in VIRTUAL_CANDIDATES:
        for s in speakers:
            if candidate.lower() in s.name.lower():
                return s
    return None


def is_virtual(dev):
    v = find_virtual()
    return bool(v and v.name == dev)


# ---------------------------------------------------------------- ring buffer

class Ring:
    def __init__(self):
        self.n = SR * RING_SECS
        self.buf = np.zeros((self.n, CH), np.float32)
        self.total = 0          # frames written since start
        self.cv = threading.Condition()

    def write(self, data):
        k = len(data)
        i = self.total % self.n
        end = min(k, self.n - i)
        self.buf[i:i + end] = data[:end]
        self.buf[:k - end] = data[end:]
        with self.cv:
            self.total += k
            self.cv.notify_all()

    def read(self, pos, k):
        i = pos % self.n
        end = min(k, self.n - i)
        return np.concatenate([self.buf[i:i + end], self.buf[:k - end]])

    def wait(self, pos, timeout=1.0):
        with self.cv:
            return self.cv.wait_for(lambda: self.total >= pos, timeout)


ring = Ring()
click_until = 0.0
BEEP = (0.5 * np.sin(2 * np.pi * 1000 * np.arange(int(SR * 0.03)) / SR)).astype(np.float32)


def out_cfg(dev):
    with cfg_lock:
        return cfg["outputs"].setdefault(dev, {"enabled": False, "volume": 1.0, "delay_ms": 0, "trim_ms": 0})


def is_direct(dev):
    """This output is the source itself: the music already plays there live.
    Playing it again would create a feedback loop, so only the test beep is played."""
    return dev == source


def beep_played_locally():
    """In direct mode the beep is played on the source output and captured back from it."""
    return any(is_direct(d) and o["enabled"] for d, o in cfg["outputs"].items())


def add_beep(data, phase):
    idx = (phase + np.arange(len(data))) % SR
    hit = idx < len(BEEP)
    data[hit] += BEEP[idx[hit]][:, None]


def capture_loop():
    """Captures the source (WASAPI loopback) forever; reopens it when the source changes."""
    phase = 0
    while True:
        current = source
        if not current:
            time.sleep(0.5)
            continue
        try:
            mic = sc.get_microphone(current, include_loopback=True)
            log("capturing", dev=short(mic.name))
            with mic.recorder(samplerate=SR, channels=CH, blocksize=BLOCK) as rec:
                while source == current:
                    data = rec.record(numframes=BLOCK).astype(np.float32)
                    if time.time() < click_until and not beep_played_locally():
                        # 30 ms beep every second to align speakers by ear
                        add_beep(data, phase)
                    phase = (phase + len(data)) % SR
                    ring.write(data)
        except Exception as e:
            log("capture_error", dev=short(current), err=str(e))
            time.sleep(2)


# ---------------------------------------------------------------- Windows outputs

running_outputs = set()
output_stats = {}    # dev -> current drift and corrections made (shown in the panel)


def output_wanted(dev):
    o = cfg["outputs"].get(dev)
    return bool(o and o["enabled"] and active)


def output_loop(dev):
    """Plays the buffer on a Windows output with its own delay.
    Every device has its own clock: drift is corrected by dropping or repeating one sample
    every 10 ms (0.2 % speed change, inaudible) instead of jumping."""
    o = out_cfg(dev)
    try:
        spk = sc.get_speaker(dev)
        direct = is_direct(dev)
        log("output_direct" if direct else "output_started", dev=short(spk.name))
        with spk.player(samplerate=SR, channels=CH, blocksize=BLOCK) as player:
            if direct:
                phase = 0
                while output_wanted(dev) and is_direct(dev):
                    if time.time() < click_until:
                        data = np.zeros((BLOCK, CH), np.float32)
                        add_beep(data, phase)
                        player.play(data * float(o["volume"]) * float(cfg["master"]))
                        phase = (phase + BLOCK) % SR
                    else:
                        phase = 0
                        time.sleep(0.05)
                return
            pos = ring.total - ms_to_frames(o["delay_ms"])
            err_avg = 0.0
            base = None             # what the device keeps in its own buffer: not drift
            warm = []
            stats = output_stats[dev] = {"drift_ms": 0.0, "fixes": 0}
            while output_wanted(dev) and not is_direct(dev):
                err = pos - (ring.total - ms_to_frames(o["delay_ms"]))
                if abs(err) > SR * 0.25:        # delay changed or stalled: jump straight there
                    pos -= err - (base or 0)
                    err_avg = 0.0
                    continue
                if base is None:
                    warm.append(err)
                    if len(warm) >= 200:        # 2 s to learn the device's own buffer
                        base = int(np.median(warm[50:]))
                else:
                    err_avg = 0.98 * err_avg + 0.02 * (err - base)
                # Running late: consume a few extra samples; early: a few less.
                # 1 sample per 10 ms per 3 ms of error, at most 4 (0.8 % speed)
                step = BLOCK
                err_ms = err_avg / SR * 1000
                if abs(err_ms) > 3:
                    step = BLOCK - int(np.clip(round(err_ms / 3), -4, 4))
                if not ring.wait(pos + step):
                    continue
                data = ring.read(pos, step)
                if step != BLOCK:
                    x = np.linspace(0, step - 1, BLOCK)
                    data = np.stack([np.interp(x, np.arange(step), data[:, ch]) for ch in range(CH)], axis=1)
                    stats["fixes"] += 1
                stats["drift_ms"] = round(err_avg / SR * 1000, 1)
                player.play(data * float(o["volume"]) * float(cfg["master"]))
                pos += step
    except Exception as e:
        log("output_error", dev=short(dev), err=str(e))
        time.sleep(2)
    finally:
        running_outputs.discard(dev)


def keep_virtual_default():
    """When a Bluetooth device connects, Windows makes it the default output and the music
    escapes the virtual device, leaving every other speaker silent. Put it back."""
    if not active or cfg["mode"] != "sync" or time.time() - routed_at < 5:
        return
    virt = find_virtual()
    if not virt:
        return
    default = sc.default_speaker().name
    if default == virt.name:
        return
    winaudio.set_default_output(virt.id)
    log("default_restored", dev=short(default))


def outputs_manager():
    """Starts one thread per enabled output that is connected (Bluetooth devices come and go)."""
    while True:
        try:
            keep_virtual_default()
            present = {s.name for s in sc.all_speakers()}
            for dev in list(cfg["outputs"]):
                if dev in present and output_wanted(dev) and dev not in running_outputs:
                    running_outputs.add(dev)
                    threading.Thread(target=output_loop, args=(dev,), daemon=True).start()
        except Exception as e:
            log("outputs_error", err=str(e))
        time.sleep(1)


# ---------------------------------------------------------------- Chromecast

casts = {}          # name -> Chromecast
sessions = {}       # name -> id of the current streaming session
recast_timers = {}
streams = {}        # name -> {sid, offset}: buffer position matching second 0 of the stream
browsers = []
pending_casts = set()
started_at = {}     # name -> launch time: the watchdog leaves it alone while starting


def cast_cfg(name):
    with cfg_lock:
        return cfg["casts"].setdefault(name, {"enabled": False, "volume": None, "delay_ms": 0, "trim_ms": 0})


def add_cast(cc):
    name = cc.cast_info.friendly_name
    if name in casts or name in pending_casts:
        return
    pending_casts.add(name)
    try:
        cc.wait(timeout=10)
        casts[name] = cc
        c = cast_cfg(name)
        log("found", name=name, host=cc.cast_info.host)
        save_cfg()
        if c["enabled"] and active:
            start_cast(name)
    except Exception as e:
        log("connect_failed", name=name, err=str(e))
    finally:
        pending_casts.discard(name)


def start_discovery():
    """Listens to the network forever: a Cast device that powers on shows up by itself."""
    log("searching")
    browsers.append(pychromecast.get_chromecasts(
        blocking=False, callback=lambda cc: threading.Thread(target=add_cast, args=(cc,), daemon=True).start()))


def discover():
    log("searching")
    found, browser = pychromecast.get_chromecasts(timeout=8)
    browsers.append(browser)    # never stopped: connections use its zeroconf instance
    for cc in found:
        add_cast(cc)


def start_cast(name):
    cc = casts.get(name)
    if not cc or not active:
        return
    c = cast_cfg(name)
    sid = str(int(time.time() * 1000))
    sessions[name] = sid
    started_at[name] = time.time()
    fmt = c.get("format", "mp3")
    url = f"http://{local_ip()}:{PORT}/s/{quote(name)}.{fmt}?sid={sid}"
    try:
        apply_cast_volume(name)
        cc.media_controller.play_media(url, "audio/wav" if fmt == "wav" else "audio/mpeg",
                                       title="HouseBeat", stream_type="LIVE")
        log("casting", name=name)
        schedule_autosync()
    except Exception as e:
        log("cast_error", name=name, err=str(e))


def apply_cast_volume(name):
    cc = casts.get(name)
    c = cast_cfg(name)
    if cc and c.get("volume") is not None:
        cc.set_volume(float(c["volume"]) * float(cfg["master"]))


def cast_latency(name):
    """Seconds between the source and what is playing right now on the Cast device."""
    cc = casts.get(name)
    m = streams.get(name)
    if not cc or not m or m["sid"] != sessions.get(name):
        return None
    st = cc.media_controller.status
    if st.player_state != "PLAYING" or st.current_time is None:
        return None
    return (ring.total - (m["offset"] + st.adjusted_current_time * SR)) / SR


def stop_cast(name):
    sessions.pop(name, None)
    cc = casts.get(name)
    if cc:
        try:
            if cc.app_id == MEDIA_RECEIVER:
                cc.quit_app()
        except Exception as e:
            log("stop_error", name=name, err=str(e))
    log("stopped", name=name)


def schedule_recast(name, wait=0.8):
    old = recast_timers.pop(name, None)
    if old:
        old.cancel()
    t = threading.Timer(wait, start_cast, args=(name,))
    recast_timers[name] = t
    t.start()


def watchdog_loop():
    """Relaunches an enabled Cast device that stopped playing our stream.
    If another app (YouTube...) took it over, it is disabled instead of fighting for it."""
    while True:
        time.sleep(10)
        if not active:
            continue
        for name, cc in list(casts.items()):
            c = cast_cfg(name)
            if not c["enabled"] or name in recast_timers and recast_timers[name].is_alive():
                continue
            if time.time() - started_at.get(name, 0) < 30:
                continue
            try:
                app = cc.app_id
                state = cc.media_controller.status.player_state
                if app not in (None, MEDIA_RECEIVER):
                    log("taken_over", name=name)
                    c["enabled"] = False
                    sessions.pop(name, None)
                    save_cfg()
                elif app is None or state in ("IDLE", "UNKNOWN"):
                    log("relaunch", name=name)
                    start_cast(name)
            except Exception as e:
                log("watchdog_error", name=name, err=str(e))


class WavEncoder:
    """Uncompressed PCM: much bigger, so devices that wait for N bytes before playing
    start sooner and add less latency of their own."""
    def header(self):
        import struct
        size = 0xFFFFFFF0       # live stream: no known size, use the maximum
        return (b"RIFF" + struct.pack("<I", size) + b"WAVEfmt " +
                struct.pack("<IHHIIHH", 16, 1, CH, SR, SR * CH * 2, CH * 2, 16) +
                b"data" + struct.pack("<I", size - 36))

    def encode(self, pcm):
        return pcm


def new_encoder():
    enc = lameenc.Encoder()
    enc.set_bit_rate(192)
    enc.set_in_sample_rate(SR)
    enc.set_channels(CH)
    enc.set_quality(2)
    return enc


def to_pcm16(data):
    return (np.clip(data, -1, 1) * 32767).astype("<i2").tobytes()


def serve_stream(handler, name, sid, fmt):
    c = cast_cfg(name)
    handler.send_response(200)
    handler.send_header("Content-Type", "audio/wav" if fmt == "wav" else "audio/mpeg")
    handler.send_header("Cache-Control", "no-cache, no-store")
    handler.send_header("Connection", "close")
    handler.end_headers()
    if fmt == "wav":
        enc = WavEncoder()
        handler.wfile.write(enc.header())
    else:
        enc = new_encoder()
    applied = ms_to_frames(c["delay_ms"])
    pos = ring.total - applied          # the delay is sent at once: the device plays behind it
    info = {"sid": sid, "offset": pos}
    streams[name] = info
    chunk = SR // 20
    try:
        while sessions.get(name) == sid:
            want = ms_to_frames(c["delay_ms"])
            if want > applied:
                # more delay: insert silence, everything after it plays later
                silence = np.zeros((want - applied, CH), np.float32)
                handler.wfile.write(enc.encode(to_pcm16(silence)))
                info["offset"] -= want - applied
                applied = want
            elif want < applied:
                applied = want          # less delay: handled by relaunching (schedule_recast)
            if not ring.wait(pos + chunk):
                continue
            if pos < ring.total - ring.n + SR:
                info["offset"] += ring.total - SR - pos
                pos = ring.total - SR   # fell too far behind
            k = min(ring.total - pos, SR // 2)
            out = enc.encode(to_pcm16(ring.read(pos, k)))
            pos += k
            if out:
                handler.wfile.write(out)
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
        pass


# ---------------------------------------------------------------- synchronization

def auto_sync():
    """Measures how late every Cast device is and delays the rest to match the slowest one.
    Cast devices only get more delay (inserting silence never cuts the audio); Windows outputs
    are set directly. trim_ms is what a device adds after what can be measured (TV, Bluetooth,
    distance): it is tuned by ear and added to the measurement."""
    lats = {}
    for name in casts:
        if cast_cfg(name)["enabled"]:
            vals = []
            for _ in range(5):
                lat = cast_latency(name)
                if lat is not None:
                    vals.append(lat)
                time.sleep(0.2)
            if vals:
                lats[name] = sorted(vals)[len(vals) // 2] + cast_cfg(name).get("trim_ms", 0) / 1000
    outs = {d: o for d, o in cfg["outputs"].items() if o["enabled"] and not is_direct(d)}
    if not lats and not outs:
        log("sync_nothing")
        return
    target = max(list(lats.values()) + [o.get("trim_ms", 0) / 1000 for o in outs.values()])
    for name, lat in lats.items():
        c = cast_cfg(name)
        c["delay_ms"] = min(MAX_DELAY_MS, c["delay_ms"] + int(round((target - lat) * 100)) * 10)
    for o in outs.values():
        o["delay_ms"] = min(MAX_DELAY_MS, max(0, int(round((target - o.get("trim_ms", 0) / 1000) * 100)) * 10))
    save_cfg()
    log("sync_done", target=f"{target:.2f}",
        items=", ".join([f"{n} {l:.2f}s" for n, l in lats.items()] +
                        [f"{short(d)} {o['delay_ms']} ms" for d, o in outs.items()]))


autosync_pending = threading.Event()


def schedule_autosync():
    """Waits until every enabled Cast device is playing, then synchronizes."""
    if autosync_pending.is_set():
        return
    autosync_pending.set()

    def run():
        try:
            time.sleep(5)
            deadline = time.time() + 90
            while time.time() < deadline:
                enabled = [n for n in casts if cast_cfg(n)["enabled"]]
                if enabled and all(cast_latency(n) is not None for n in enabled):
                    time.sleep(3)       # let the start settle
                    auto_sync()
                    return
                time.sleep(2)
        finally:
            autosync_pending.clear()
    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------- routing

def main_output():
    """The real output Windows plays on when HouseBeat is off or in direct mode."""
    names = [s.name for s in sc.all_speakers() if not is_virtual(s.name)]
    if cfg["main"] in names:
        return cfg["main"]
    default = sc.default_speaker().name
    return default if default in names else (names[0] if names else "")


def apply_routing():
    """On + sync mode: Windows plays into the virtual device and every output is delayed.
    Otherwise Windows plays live on the main output (HouseBeat off = normal PC audio)."""
    global source, routed_at
    routed_at = time.time()
    main = main_output()
    virt = find_virtual()
    if active and cfg["mode"] == "sync":
        if virt:
            winaudio.set_default_output(virt.id)
            source = virt.name
            log("mode_sync", dev=short(virt.name))
            return
        log("no_virtual")
    if main:
        winaudio.set_default_output(sc.get_speaker(main).id)
        source = main
        if active:
            log("mode_direct", dev=short(main))


def set_active(on):
    global active
    active = bool(on)
    try:
        apply_routing()
    except Exception as e:
        log("mode_error", err=str(e))
    if active:
        log("all_on")
        enabled = [n for n in casts if cast_cfg(n)["enabled"]]
        for name in enabled:
            threading.Thread(target=start_cast, args=(name,), daemon=True).start()
        if not enabled:         # with Cast devices, start_cast syncs once they are playing
            threading.Thread(target=auto_sync, daemon=True).start()
    else:
        log("all_off")
        for name in list(sessions):
            threading.Thread(target=stop_cast, args=(name,), daemon=True).start()


def set_mode(mode):
    cfg["mode"] = "direct" if mode == "direct" else "sync"
    if cfg["main"]:
        out_cfg(cfg["main"])["enabled"] = True
    save_cfg()
    try:
        apply_routing()
    except Exception as e:
        log("mode_error", err=str(e))
    if active:
        threading.Thread(target=auto_sync, daemon=True).start()


def shutdown():
    """Leaves Windows playing on the main output and stops every Cast device."""
    global active
    active = False
    try:
        apply_routing()
    finally:
        for name in list(sessions):
            stop_cast(name)


# ---------------------------------------------------------------- web panel

def state():
    with cfg_lock:
        data = json.loads(json.dumps(cfg))
    for name, c in data["casts"].items():
        cc = casts.get(name)
        c["online"] = cc is not None
        c["host"] = cc.cast_info.host if cc else ""
        c["model"] = cc.cast_info.model_name if cc else ""
        if cc and c.get("volume") is None:
            try:
                c["volume"] = cc.status.volume_level
            except Exception:
                c["volume"] = 0.5
        try:
            lat = cast_latency(name)
        except Exception:
            lat = None
        c["latency_ms"] = None if lat is None else int(lat * 1000)
    virt = find_virtual()
    present = [s.name for s in sc.all_speakers() if not (virt and s.name == virt.name)]
    main = main_output()
    outs = {}
    for dev in present + [d for d in data["outputs"] if d not in present]:
        o = dict(data["outputs"].get(dev) or {"enabled": False, "volume": 1.0, "delay_ms": 0, "trim_ms": 0})
        o["present"] = dev in present
        o["direct"] = is_direct(dev)
        o["main"] = dev == main
        o["stats"] = output_stats.get(dev) if dev in running_outputs else None
        outs[dev] = o
    data["outputs"] = outs
    data["active"] = active
    data["source"] = source
    data["virtual_device"] = virt.name if virt else None
    data["click"] = time.time() < click_until
    data["version"] = VERSION
    data["log"] = log_lines[-12:]
    return data


def apply_set(body):
    target = body.get("target")
    key = body.get("key")
    value = body.get("value")
    if target == "active":
        set_active(value)
        return
    if target == "master":
        cfg["master"] = max(0.0, min(1.0, float(value)))
        for name in casts:
            threading.Thread(target=apply_cast_volume, args=(name,), daemon=True).start()
    elif target in ("output", "cast") and key == "trim_ms":
        c = out_cfg(body["name"]) if target == "output" else cast_cfg(body["name"])
        c["trim_ms"] = max(-1000, min(1000, int(value)))
        threading.Thread(target=auto_sync, daemon=True).start()
    elif target == "output":
        dev = body["name"]
        o = out_cfg(dev)
        if key == "main":
            cfg["main"] = dev
            o["enabled"] = True
            threading.Thread(target=apply_routing, daemon=True).start()
        elif key == "delay_ms":
            o[key] = max(0, min(MAX_DELAY_MS, int(value)))
        elif key == "volume":
            o[key] = max(0.0, min(1.5, float(value)))
        elif key == "enabled":
            o[key] = bool(value)
            if value and active:
                threading.Thread(target=auto_sync, daemon=True).start()
    elif target == "cast":
        name = body["name"]
        c = cast_cfg(name)
        if key == "enabled":
            c["enabled"] = bool(value)
            threading.Thread(target=start_cast if value else stop_cast, args=(name,), daemon=True).start()
        elif key == "volume":
            c["volume"] = max(0.0, min(1.0, float(value)))
            if casts.get(name):
                threading.Thread(target=apply_cast_volume, args=(name,), daemon=True).start()
        elif key == "format" and value in ("mp3", "wav"):
            c["format"] = value
            if c["enabled"] and active:
                schedule_recast(name, 0)
        elif key == "delay_ms":
            new = max(0, min(MAX_DELAY_MS, int(value)))
            old = c["delay_ms"]
            c["delay_ms"] = new
            if new < old and c["enabled"] and active:
                schedule_recast(name)
    save_cfg()


STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, rel):
        path = os.path.normpath(os.path.join(WEB_DIR, rel))
        ext = os.path.splitext(path)[1]
        if not path.startswith(WEB_DIR) or ext not in STATIC_TYPES or not os.path.isfile(path):
            self.send_error(404)
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", STATIC_TYPES[ext])
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self.send_static("index.html")
        elif u.path == "/api/state":
            self.send_json(state())
        elif u.path.startswith("/s/") and u.path.endswith((".mp3", ".wav")):
            name = unquote(u.path[3:-4])
            fmt = u.path[-3:]
            sid = parse_qs(u.query).get("sid", [""])[0]
            if sessions.get(name) != sid:
                self.send_error(410)
                return
            serve_stream(self, name, sid, fmt)
        else:
            self.send_static(u.path.lstrip("/"))

    def do_POST(self):
        global click_until
        # The panel is only for this PC: Cast devices on the LAN just need the GET stream
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self.send_error(403)
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        u = urlparse(self.path)
        if u.path == "/api/set":
            apply_set(body)
        elif u.path == "/api/click":
            click_until = 0 if time.time() < click_until else time.time() + 20
        elif u.path == "/api/discover":
            threading.Thread(target=discover, daemon=True).start()
        elif u.path == "/api/mode":
            set_mode(body.get("mode"))
        elif u.path == "/api/quit":
            self.send_json({"ok": True})
            threading.Thread(target=quit_app, daemon=True).start()
            return
        elif u.path == "/api/autosync":
            threading.Thread(target=auto_sync, daemon=True).start()
        elif u.path == "/api/recast":
            if active:
                schedule_recast(body["name"], 0)
        else:
            self.send_error(404)
            return
        self.send_json({"ok": True})


# ---------------------------------------------------------------- app

tray_icon = None


def quit_app():
    try:
        shutdown()
    finally:
        if tray_icon:
            tray_icon.stop()
        os._exit(0)


def open_panel():
    webbrowser.open(f"http://localhost:{PORT}")


def already_running():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
            return True
    except OSError:
        return False


def system_is_spanish():
    try:
        import ctypes
        return ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x0A
    except Exception:
        return False


def run_tray():
    """Tray icon with Open / Quit. Without pystray the app just keeps running."""
    global tray_icon
    try:
        import pystray
        from PIL import Image
    except ImportError:
        threading.Event().wait()
        return
    es = system_is_spanish()
    image = Image.open(os.path.join(WEB_DIR, "icon.ico"))
    tray_icon = pystray.Icon("HouseBeat", image, "HouseBeat", menu=pystray.Menu(
        pystray.MenuItem("Abrir HouseBeat" if es else "Open HouseBeat", lambda: open_panel(), default=True),
        pystray.MenuItem("Salir" if es else "Quit", lambda: quit_app())))
    tray_icon.run()


def main():
    if already_running():
        open_panel()
        return
    load_cfg()
    if not cfg["main"]:
        cfg["main"] = main_output()
    if cfg["main"]:
        out_cfg(cfg["main"])["enabled"] = True
    save_cfg()
    try:
        apply_routing()             # starts off: Windows plays normally on the main output
    except Exception as e:
        log("mode_error", err=str(e))
    if not find_virtual():
        log("no_virtual")
    threading.Thread(target=capture_loop, daemon=True).start()
    threading.Thread(target=outputs_manager, daemon=True).start()
    start_discovery()
    threading.Thread(target=watchdog_loop, daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log("panel_at", url=f"http://localhost:{PORT}")
    if os.environ.get("HOUSEBEAT_NO_BROWSER") != "1":
        open_panel()
    run_tray()


if __name__ == "__main__":
    main()
