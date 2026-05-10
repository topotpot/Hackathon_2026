"""Procedural WAV generation for all 21 game audio assets (stdlib only). Cached in assets/audio/ on first run."""
import math
import os
import struct
import wave


def _write_wav(path: str, samples: list[float], rate: int = 22050) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for x in samples:
            v = int(max(-1.0, min(1.0, x)) * 32767)
            frames.extend(struct.pack("<h", v))
        w.writeframes(frames)


def _smooth(buf: list[float], passes: int) -> list[float]:
    n = len(buf)
    for _ in range(passes):
        nb = buf[:]
        for i in range(1, n - 1):
            nb[i] = 0.4 * buf[i] + 0.3 * buf[i - 1] + 0.3 * buf[i + 1]
        buf = nb
    return buf


def _fade_ends(buf: list[float], fade_n: int) -> list[float]:
    """Fade amplitude to zero at both ends for seamless looping."""
    n = len(buf)
    out = buf[:]
    fade = min(fade_n, n // 4)
    for i in range(fade):
        t = i / fade
        out[i] *= t
        out[n - 1 - i] *= t
    return out


# ── Existing sounds (kept for backwards compat) ───────────────────────────────

def _sine_tone(freq: float, sec: float, rate: int, amp: float = 0.35) -> list[float]:
    n = int(rate * sec)
    out = []
    for i in range(n):
        env = min(1.0, i / (rate * 0.01)) * min(1.0, (n - i) / (rate * 0.02))
        out.append(math.sin(2 * math.pi * freq * i / rate) * amp * env)
    return out


def _noise_burst(sec: float, rate: int, amp: float = 0.45) -> list[float]:
    import random
    rng = random.Random(0x1234)
    n = int(rate * sec)
    return [rng.uniform(-1, 1) * amp for _ in range(n)]


def _wind_loop(sec: float, rate: int) -> list[float]:
    import random
    rng = random.Random(0xBEEF)
    n = int(rate * sec)
    buf = [rng.uniform(-0.08, 0.08) for _ in range(n)]
    return _smooth(buf, 2)


def _gust_burst(sec: float, rate: int, amp: float = 0.32) -> list[float]:
    import random
    rng = random.Random(0xCAFE)
    n = int(rate * sec)
    out: list[float] = []
    x = 0.0
    for i in range(n):
        x = x * 0.82 + rng.uniform(-1.0, 1.0) * 0.18
        env = (1.0 - i / max(1, n - 1)) ** 1.6
        out.append(x * amp * env)
    return out


def _energy_burst(sec: float, rate: int, amp: float = 0.45) -> list[float]:
    import random
    rng = random.Random(0xDEAD)
    n = int(rate * sec)
    out: list[float] = []
    for i in range(n):
        t = i / rate
        env = min(1.0, i / (rate * 0.01)) * (1.0 - i / max(1, n))
        tone = math.sin(2 * math.pi * (230.0 + 40.0 * math.sin(2 * math.pi * 2.1 * t)) * t)
        noise = rng.uniform(-1.0, 1.0)
        out.append((0.65 * tone + 0.35 * noise) * amp * env)
    return out


# ── Layered ambient loops ─────────────────────────────────────────────────────

def _ambient_mars_loop(sec: float, rate: int) -> list[float]:
    """Thin Mars atmosphere: heavy-filtered noise + 32 Hz sub-drone.
    32 Hz * 4 s = 128 exact cycles — seamless tonal loop."""
    import random
    rng = random.Random(0xA4B2)
    n = int(rate * sec)
    drone = [math.sin(2 * math.pi * 32.0 * i / rate) * 0.032 for i in range(n)]
    buf = [rng.uniform(-0.09, 0.09) for _ in range(n)]
    buf = _smooth(buf, 8)
    out = [drone[i] + buf[i] for i in range(n)]
    return _fade_ends(out, rate // 20)


def _engine_idle_loop(sec: float, rate: int) -> list[float]:
    """Low motor rumble: 70 Hz fundamental + harmonics + filtered noise.
    70 Hz * 1.5 s = 105 exact cycles — seamless tonal loop."""
    import random
    rng = random.Random(0xE1D1)
    n = int(rate * sec)
    tone_buf = []
    for i in range(n):
        t = i / rate
        tone = (
            math.sin(2 * math.pi * 70.0 * t) * 0.24
            + math.sin(2 * math.pi * 140.0 * t) * 0.09
            + math.sin(2 * math.pi * 210.0 * t) * 0.04
        )
        tone_buf.append(tone)
    noise = [rng.uniform(-0.04, 0.04) for _ in range(n)]
    noise = _smooth(noise, 4)
    out = [tone_buf[i] + noise[i] for i in range(n)]
    return _fade_ends(out, rate // 20)


def _station_hum_loop(sec: float, rate: int) -> list[float]:
    """Electronic station hum: 110 Hz fundamental + harmonics.
    110 Hz * 2 s = 220 exact cycles — seamless tonal loop."""
    import random
    rng = random.Random(0x5747)
    n = int(rate * sec)
    tone_buf = []
    for i in range(n):
        t = i / rate
        tone = (
            math.sin(2 * math.pi * 110.0 * t) * 0.30
            + math.sin(2 * math.pi * 220.0 * t) * 0.11
            + math.sin(2 * math.pi * 330.0 * t) * 0.04
        )
        tone_buf.append(tone)
    noise = [rng.uniform(-0.022, 0.022) for _ in range(n)]
    noise = _smooth(noise, 5)
    out = [tone_buf[i] + noise[i] for i in range(n)]
    return _fade_ends(out, rate // 20)


def _ending_drone_loop(sec: float, rate: int) -> list[float]:
    """Endgame ambient: slow modulated 55 + 82.5 Hz pad.
    55 Hz * 6 s = 330 exact cycles — seamless tonal loop."""
    import random
    rng = random.Random(0xED15)
    n = int(rate * sec)
    out = []
    for i in range(n):
        t = i / rate
        mod = 0.75 + 0.25 * math.sin(2 * math.pi * 0.18 * t)
        tone = (
            math.sin(2 * math.pi * 55.0 * t) * 0.55
            + math.sin(2 * math.pi * 82.5 * t) * 0.28
            + math.sin(2 * math.pi * 110.0 * t) * 0.12
        )
        out.append(tone * mod * 0.38)
    noise = [rng.uniform(-0.018, 0.018) for _ in range(n)]
    noise = _smooth(noise, 6)
    out = [out[i] + noise[i] for i in range(n)]
    return _fade_ends(out, rate // 10)


# ── Rover SFX ─────────────────────────────────────────────────────────────────

def _engine_rev(sec: float, rate: int) -> list[float]:
    """Rising engine rev: 80 → 200 Hz with brief decay."""
    n = int(rate * sec)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / n
        freq = 80.0 + 120.0 * t
        phase += 2 * math.pi * freq / rate
        tail = max(0.0, 1.0 - (t - 0.7) / 0.3) if t > 0.7 else 1.0
        env = min(1.0, i / (rate * 0.015)) * tail
        out.append(math.sin(phase) * 0.38 * env)
    return out


def _boost_surge(sec: float, rate: int) -> list[float]:
    """Boost: rising tone 180 → 400 Hz with noise, fast decay."""
    import random
    rng = random.Random(0xB005)
    n = int(rate * sec)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / n
        freq = 180.0 + 220.0 * t
        phase += 2 * math.pi * freq / rate
        env = min(1.0, i / (rate * 0.01)) * (1.0 - t) ** 0.7
        noise = rng.uniform(-1.0, 1.0) * 0.22
        out.append((math.sin(phase) * 0.75 + noise * 0.25) * 0.52 * env)
    return out


# ── Resource pickup SFX ───────────────────────────────────────────────────────

def _collect_relay(sec: float, rate: int) -> list[float]:
    """Relay pickup: deep resonant 220 Hz with harmonic."""
    n = int(rate * sec)
    out = []
    for i in range(n):
        t = i / rate
        env = min(1.0, i / (rate * 0.006)) * math.exp(-t * 13.0)
        tone = (
            math.sin(2 * math.pi * 220.0 * t) * 0.65
            + math.sin(2 * math.pi * 440.0 * t) * 0.22
        )
        out.append(tone * 0.52 * env)
    return out


def _collect_tech(sec: float, rate: int) -> list[float]:
    """Tech/data pickup: electronic spark at 1300 Hz."""
    import random
    rng = random.Random(0x7EC4)
    n = int(rate * sec)
    out = []
    for i in range(n):
        t = i / rate
        env = min(1.0, i / (rate * 0.003)) * math.exp(-t * 24.0)
        tone = math.sin(2 * math.pi * 1300.0 * t)
        noise = rng.uniform(-1.0, 1.0) * 0.38
        out.append((0.58 * tone + 0.42 * noise) * 0.55 * env)
    return out


def _collect_ancient(sec: float, rate: int) -> list[float]:
    """Ancient tech pickup: resonant 440 Hz harmonic triad, slow attack."""
    n = int(rate * sec)
    out = []
    for i in range(n):
        t = i / rate
        env = min(1.0, t / 0.035) * math.exp(-t * 5.5)
        tone = (
            math.sin(2 * math.pi * 440.0 * t) * 0.55
            + math.sin(2 * math.pi * 880.0 * t) * 0.26
            + math.sin(2 * math.pi * 660.0 * t) * 0.14
        )
        out.append(tone * 0.50 * env)
    return out


# ── UI SFX ────────────────────────────────────────────────────────────────────

def _ui_click(sec: float, rate: int) -> list[float]:
    """Menu navigation click: brief 900 Hz tick."""
    n = int(rate * sec)
    out = []
    for i in range(n):
        t = i / rate
        env = math.exp(-t / (sec * 0.35)) * min(1.0, i / 3.0)
        out.append(math.sin(2 * math.pi * 900.0 * t) * 0.26 * env)
    return out


def _ui_confirm(sec: float, rate: int) -> list[float]:
    """Confirm action: two ascending tones 660 → 880 Hz."""
    n = int(rate * sec)
    half = n // 2
    out = []
    for i in range(n):
        t = i / rate
        freq = 660.0 if i < half else 880.0
        base_t = (i / max(1, half)) * (sec / 2) if i < half else ((i - half) / max(1, n - half)) * (sec / 2)
        env = math.exp(-base_t * 10.0) * min(1.0, i / 4.0)
        out.append(math.sin(2 * math.pi * freq * t) * 0.30 * env)
    return out


def _ui_error_sound(sec: float, rate: int) -> list[float]:
    """Error / locked: descending buzz 280 → 90 Hz."""
    import random
    rng = random.Random(0xE440)
    n = int(rate * sec)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / n
        freq = 280.0 - 190.0 * t
        phase += 2 * math.pi * freq / rate
        env = (1.0 - t) ** 0.55 * min(1.0, i / (rate * 0.004))
        noise = rng.uniform(-1.0, 1.0) * 0.20
        out.append((math.sin(phase) * 0.72 + noise * 0.28) * 0.44 * env)
    return out


# ── Signal SFX ────────────────────────────────────────────────────────────────

def _signal_rise(sec: float, rate: int) -> list[float]:
    """Signal increase: 350 → 750 Hz upward sweep."""
    n = int(rate * sec)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / n
        freq = 350.0 + 400.0 * t
        phase += 2 * math.pi * freq / rate
        env = min(1.0, i / (rate * 0.008)) * (1.0 - t * 0.45)
        out.append(math.sin(phase) * 0.38 * env)
    return out


def _signal_drop(sec: float, rate: int) -> list[float]:
    """Signal decrease: 750 → 250 Hz downward sweep."""
    n = int(rate * sec)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / n
        freq = 750.0 - 500.0 * t
        phase += 2 * math.pi * freq / rate
        env = min(1.0, i / (rate * 0.008)) * (1.0 - t * 0.45)
        out.append(math.sin(phase) * 0.35 * env)
    return out


def _signal_glitch(sec: float, rate: int) -> list[float]:
    """Fake signal / glitch: irregular noise bursts with 180 Hz crackle."""
    import random
    rng = random.Random(0xABCD)
    n = int(rate * sec)
    out = []
    for i in range(n):
        t = i / rate
        crackle = math.sin(2 * math.pi * 180.0 * t) * 0.30
        noise = rng.uniform(-1.0, 1.0) * 0.60
        mod = abs(math.sin(2 * math.pi * 8.0 * t)) ** 0.4
        env = min(1.0, i / (rate * 0.005)) * (1.0 - t / max(sec, 0.001)) ** 0.3
        out.append((crackle + noise) * mod * 0.42 * env)
    return out


# ── Station / upgrade SFX ─────────────────────────────────────────────────────

def _upgrade_jingle(rate: int) -> list[float]:
    """Upgrade purchased: arpeggiated major triad C4 → E4 → G4 → C5."""
    freqs = [261.63, 329.63, 392.00, 523.25]
    note_n = int(rate * 0.12)
    out = [0.0] * (note_n * len(freqs))
    for k, freq in enumerate(freqs):
        offset = k * note_n
        for i in range(note_n):
            t = i / rate
            env = math.exp(-t * 14.0) * min(1.0, i / 5.0)
            out[offset + i] += math.sin(2 * math.pi * freq * t) * 0.36 * env
    return out


# ── File registry ─────────────────────────────────────────────────────────────

def ensure_audio_files(base_dir: str) -> dict[str, str]:
    root = os.path.join(base_dir, "assets")
    os.makedirs(root, exist_ok=True)

    files = {
        # Original sounds
        "collect":        os.path.join(root, "collect.wav"),
        "error":          os.path.join(root, "error.wav"),
        "wind":           os.path.join(root, "wind_loop.wav"),
        "gust":           os.path.join(root, "gust.wav"),
        "burst":          os.path.join(root, "energy_burst.wav"),
        # Ambient loops
        "ambient":        os.path.join(root, "ambient_mars.wav"),
        "engine":         os.path.join(root, "engine_idle.wav"),
        "station_hum":    os.path.join(root, "station_hum.wav"),
        "ending_drone":   os.path.join(root, "ending_drone.wav"),
        # Rover SFX
        "engine_rev":     os.path.join(root, "engine_rev.wav"),
        "boost":          os.path.join(root, "boost_surge.wav"),
        # Resource pickups
        "collect_relay":  os.path.join(root, "collect_relay.wav"),
        "collect_tech":   os.path.join(root, "collect_tech.wav"),
        "collect_ancient": os.path.join(root, "collect_ancient.wav"),
        # UI
        "ui_click":       os.path.join(root, "ui_click.wav"),
        "ui_confirm":     os.path.join(root, "ui_confirm.wav"),
        "ui_error":       os.path.join(root, "ui_error.wav"),
        # Signal events
        "signal_rise":    os.path.join(root, "signal_rise.wav"),
        "signal_drop":    os.path.join(root, "signal_drop.wav"),
        "signal_glitch":  os.path.join(root, "signal_glitch.wav"),
        # Station
        "upgrade_jingle": os.path.join(root, "upgrade_jingle.wav"),
    }

    # Original sounds (generate only if missing)
    if not os.path.isfile(files["collect"]):
        _write_wav(files["collect"], _sine_tone(880, 0.08, 22050, 0.4))
    if not os.path.isfile(files["error"]):
        s = _noise_burst(0.18, 22050, 0.55)
        for i, v in enumerate(s):
            s[i] = math.copysign(0.5, v) * 0.5
        _write_wav(files["error"], s)
    if not os.path.isfile(files["wind"]):
        _write_wav(files["wind"], _wind_loop(2.0, 22050))
    if not os.path.isfile(files["gust"]):
        _write_wav(files["gust"], _gust_burst(0.22, 22050, 0.36))
    if not os.path.isfile(files["burst"]):
        _write_wav(files["burst"], _energy_burst(0.26, 22050, 0.48))

    # Ambient loops
    if not os.path.isfile(files["ambient"]):
        _write_wav(files["ambient"], _ambient_mars_loop(4.0, 22050))
    if not os.path.isfile(files["engine"]):
        _write_wav(files["engine"], _engine_idle_loop(1.5, 22050))
    if not os.path.isfile(files["station_hum"]):
        _write_wav(files["station_hum"], _station_hum_loop(2.0, 22050))
    if not os.path.isfile(files["ending_drone"]):
        _write_wav(files["ending_drone"], _ending_drone_loop(6.0, 22050))

    # Rover SFX
    if not os.path.isfile(files["engine_rev"]):
        _write_wav(files["engine_rev"], _engine_rev(0.30, 22050))
    if not os.path.isfile(files["boost"]):
        _write_wav(files["boost"], _boost_surge(0.38, 22050))

    # Resource pickups
    if not os.path.isfile(files["collect_relay"]):
        _write_wav(files["collect_relay"], _collect_relay(0.18, 22050))
    if not os.path.isfile(files["collect_tech"]):
        _write_wav(files["collect_tech"], _collect_tech(0.14, 22050))
    if not os.path.isfile(files["collect_ancient"]):
        _write_wav(files["collect_ancient"], _collect_ancient(0.40, 22050))

    # UI
    if not os.path.isfile(files["ui_click"]):
        _write_wav(files["ui_click"], _ui_click(0.055, 22050))
    if not os.path.isfile(files["ui_confirm"]):
        _write_wav(files["ui_confirm"], _ui_confirm(0.22, 22050))
    if not os.path.isfile(files["ui_error"]):
        _write_wav(files["ui_error"], _ui_error_sound(0.22, 22050))

    # Signal events
    if not os.path.isfile(files["signal_rise"]):
        _write_wav(files["signal_rise"], _signal_rise(0.22, 22050))
    if not os.path.isfile(files["signal_drop"]):
        _write_wav(files["signal_drop"], _signal_drop(0.22, 22050))
    if not os.path.isfile(files["signal_glitch"]):
        _write_wav(files["signal_glitch"], _signal_glitch(0.28, 22050))

    # Station
    if not os.path.isfile(files["upgrade_jingle"]):
        _write_wav(files["upgrade_jingle"], _upgrade_jingle(22050))

    return files
