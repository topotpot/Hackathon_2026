
import pygame

from core import settings as S
from utils.audio_assets import ensure_audio_files

# Dedicated loop channel indices (reserved from find_channel via pygame.mixer.reserve)
_CH_AMBIENT = 0
_CH_WIND    = 1
_CH_ENGINE  = 2
_CH_STATION = 3
_LOOP_COUNT = 4   # channels 0-3 reserved for loops
_SFX_TOTAL  = 16  # total mixer channels (4 loops + 12 SFX pool)


class AudioManager:
    """Four reserved loop channels (ambient/wind/engine/station) + 12-channel SFX pool with cooldown timers."""

    def __init__(self, project_root: str) -> None:
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        pygame.mixer.set_num_channels(_SFX_TOTAL)
        pygame.mixer.set_reserved(_LOOP_COUNT)  # keeps find_channel out of 0-3

        paths = ensure_audio_files(project_root)

        self._ambient = pygame.mixer.Sound(paths["ambient"])
        self._wind    = pygame.mixer.Sound(paths["wind"])
        self._engine  = pygame.mixer.Sound(paths["engine"])
        self._station = pygame.mixer.Sound(paths["station_hum"])
        self._ending  = pygame.mixer.Sound(paths["ending_drone"])

        self._gust          = pygame.mixer.Sound(paths["gust"])
        self._burst         = pygame.mixer.Sound(paths["burst"])
        self._error         = pygame.mixer.Sound(paths["error"])
        self._engine_rev    = pygame.mixer.Sound(paths["engine_rev"])
        self._boost         = pygame.mixer.Sound(paths["boost"])
        self._upgrade       = pygame.mixer.Sound(paths["upgrade_jingle"])
        self._ui_click      = pygame.mixer.Sound(paths["ui_click"])
        self._ui_confirm    = pygame.mixer.Sound(paths["ui_confirm"])
        self._ui_error      = pygame.mixer.Sound(paths["ui_error"])
        self._signal_rise   = pygame.mixer.Sound(paths["signal_rise"])
        self._signal_drop   = pygame.mixer.Sound(paths["signal_drop"])
        self._signal_glitch = pygame.mixer.Sound(paths["signal_glitch"])
        self._collect_sfx: dict[str, pygame.mixer.Sound] = {
            "relay":   pygame.mixer.Sound(paths["collect_relay"]),
            "tech":    pygame.mixer.Sound(paths["collect_tech"]),
            "ancient": pygame.mixer.Sound(paths["collect_ancient"]),
            "salvage": pygame.mixer.Sound(paths["collect"]),
            "data":    pygame.mixer.Sound(paths["collect_tech"]),  # alias
        }

        self._ch = [pygame.mixer.Channel(i) for i in range(_LOOP_COUNT)]
        self._ch[_CH_AMBIENT].play(self._ambient, loops=-1)
        self._ch[_CH_WIND].play(self._wind,       loops=-1)
        self._ch[_CH_ENGINE].play(self._engine,   loops=-1)
        self._ch[_CH_STATION].play(self._station, loops=-1)
        for ch in self._ch:
            ch.set_volume(0.0)

        # Smoothed volume state per loop channel
        self._cur_vol = [0.0] * _LOOP_COUNT
        self._endgame = False

        # SFX cooldown timers (seconds remaining per sound key)
        self._cd: dict[str, float] = {}

    def update_loops(
        self,
        dt: float,
        is_active: bool,
        storm_active: bool,
        storm_intensity: float,
        in_station: bool,
        rover_speed_frac: float,
        station_level: int,
        in_safe_zone: bool = False,
    ) -> None:
        """Lerp loop channel volumes to targets. Wind hierarchy: in_station(0.28×) → safe_zone(0.16×) → open(1.0×)."""
        if is_active:
            t_amb = 0.22 if self._endgame else 0.045
        else:
            t_amb = 0.0

        # Storm wind (muffled in station or safe zone)
        if is_active and storm_active:
            v = min(1.0, storm_intensity / max(S.STORM_INTENSITY_MAX, 0.01))
            if in_station:
                _wind_spatial = 0.28
            elif in_safe_zone:
                _wind_spatial = S.STORM_SAFE_ZONE_WIND_MUL
            else:
                _wind_spatial = 1.0
            t_wind = (0.06 + 0.58 * v) * _wind_spatial
            if self._endgame:
                t_wind *= 0.25
        else:
            t_wind = 0.0

        # Engine idle (quieter inside station)
        if is_active and not self._endgame:
            spd = max(0.0, min(1.0, rover_speed_frac))
            t_eng = (0.05 + 0.28 * spd) * (0.30 if in_station else 1.0)
        elif is_active and self._endgame:
            t_eng = 0.04 * (0.30 if in_station else 1.0)
        else:
            t_eng = 0.0

        # Station hum (grows with level, only audible near station)
        if is_active and in_station and station_level > 0:
            hum = (0.0, 0.09, 0.15, 0.22)[min(station_level, 3)]
            t_sta = hum * (0.55 if self._endgame else 1.0)
        else:
            t_sta = 0.0

        targets = [t_amb, t_wind, t_eng, t_sta]
        k = min(1.0, 4.5 * dt)
        for i in range(_LOOP_COUNT):
            self._cur_vol[i] += (targets[i] - self._cur_vol[i]) * k
            self._ch[i].set_volume(max(0.0, self._cur_vol[i]))

        for key in list(self._cd):
            self._cd[key] = max(0.0, self._cd[key] - dt)

    def set_endgame_mode(self, active: bool) -> None:
        self._endgame = active
        if active:
            self._ch[_CH_AMBIENT].stop()
            self._ch[_CH_AMBIENT].play(self._ending, loops=-1)
        else:
            self._ch[_CH_AMBIENT].stop()
            self._ch[_CH_AMBIENT].play(self._ambient, loops=-1)
        self._ch[_CH_AMBIENT].set_volume(0.0)
        self._cur_vol[_CH_AMBIENT] = 0.0

    def _sfx(
        self,
        sound: pygame.mixer.Sound,
        vol: float,
        cd_key: str = "",
        cd_sec: float = 0.0,
    ) -> None:
        if cd_key and self._cd.get(cd_key, 0.0) > 0.0:
            return
        ch = pygame.mixer.find_channel(True)
        if ch is None:
            return
        ch.play(sound)
        ch.set_volume(max(0.0, min(1.0, vol)))
        if cd_key:
            self._cd[cd_key] = cd_sec

    def play_gust(self, intensity: float, strength: float = 1.0) -> None:
        v = min(1.0, intensity / max(S.STORM_INTENSITY_MAX, 0.01))
        self._sfx(self._gust, (0.12 + 0.55 * v) * strength, "gust", 0.15)

    def play_energy_burst(self, intensity: float) -> None:
        v = min(1.0, intensity / max(S.STORM_INTENSITY_MAX, 0.01))
        vol = S.STORM_ENERGY_BURST_SOUND_VOLUME * (0.35 + 0.85 * v)
        self._sfx(self._burst, vol, "burst", 0.10)

    def play_error(self) -> None:
        self._sfx(self._error, 0.60, "error", 0.30)

    def play_boost(self) -> None:
        self._sfx(self._boost, 0.58, "boost", 0.50)

    def play_collect(self, rtype: str = "salvage") -> None:
        sound = self._collect_sfx.get(rtype, self._collect_sfx["salvage"])
        self._sfx(sound, 0.62, f"collect_{rtype}", 0.08)

    def play_signal_event(self, etype: str) -> None:
        _map = {
            "rise":   (self._signal_rise,   0.45),
            "drop":   (self._signal_drop,   0.40),
            "glitch": (self._signal_glitch, 0.50),
        }
        entry = _map.get(etype)
        if entry:
            self._sfx(entry[0], entry[1], f"sig_{etype}", 0.25)

    def play_upgrade(self) -> None:
        self._sfx(self._upgrade, 0.65, "upgrade", 0.80)

    def play_ui(self, action: str) -> None:
        _map = {
            "click":   (self._ui_click,   0.34),
            "confirm": (self._ui_confirm, 0.46),
            "error":   (self._ui_error,   0.42),
            "back":    (self._ui_click,   0.26),
        }
        entry = _map.get(action)
        if entry:
            self._sfx(entry[0], entry[1], f"ui_{action}", 0.06)
