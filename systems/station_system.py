
import math
import random

import pygame
from pygame import Vector2

from core import settings as S

CATS = ["ENERGY", "SIGNAL", "MOVEMENT", "EXPLORE", "FINAL"]

UPGRADES = [
    # ENERGY
    dict(id="battery_ext",    cat="ENERGY",    cost=dict(salvage=2)),
    dict(id="solar_panel",    cat="ENERGY",    cost=dict(salvage=2, relay=1)),
    dict(id="storm_shield",   cat="ENERGY",    cost=dict(relay=3)),
    dict(id="emergency_cell", cat="ENERGY",    cost=dict(salvage=2, data=2), experimental=True),
    # SIGNAL
    dict(id="signal_stab",    cat="SIGNAL",    cost=dict(data=2)),
    dict(id="long_range_rx",  cat="SIGNAL",    cost=dict(data=3, relay=1)),
    dict(id="int_filter",     cat="SIGNAL",    cost=dict(ancient=2, data=1)),
    dict(id="tower_decoder",  cat="SIGNAL",    cost=dict(ancient=2, relay=1), experimental=True),
    # MOVEMENT
    dict(id="engine_upg",     cat="MOVEMENT",  cost=dict(salvage=3)),
    dict(id="boost_cooling",  cat="MOVEMENT",  cost=dict(salvage=2, relay=2)),
    dict(id="suspension",     cat="MOVEMENT",  cost=dict(salvage=2, data=1)),
    dict(id="terrain_grip",   cat="MOVEMENT",  cost=dict(salvage=3, ancient=1), experimental=True),
    # EXPLORE
    dict(id="thermal_scan",   cat="EXPLORE",   cost=dict(data=2, ancient=1)),
    dict(id="storm_pred",     cat="EXPLORE",   cost=dict(data=3)),
    dict(id="fog_vision",     cat="EXPLORE",   cost=dict(relay=2, data=2)),
    dict(id="deep_scan",      cat="EXPLORE",   cost=dict(ancient=3, relay=2), experimental=True),
    # FINAL — only available after ALL 16 rover upgrades are purchased
    dict(id="evac_protocol",  cat="FINAL",     cost=dict(relay=5, data=5, ancient=3, salvage=4), requires_all_upgrades=True),
]

_BY_ID  = {u["id"]: u for u in UPGRADES}
_BY_CAT = {c: [u for u in UPGRADES if u["cat"] == c] for c in CATS}

REGULAR_UPGRADE_IDS: frozenset[str] = frozenset(u["id"] for u in UPGRADES if u["cat"] != "FINAL")

_ALL_COSTS: dict[str, int] = {}
for _u in UPGRADES:
    for _k, _v in _u["cost"].items():
        _ALL_COSTS[_k] = _ALL_COSTS.get(_k, 0) + _v
TOTAL_UPGRADE_COSTS: dict[str, int] = _ALL_COSTS


def _circ(surface: pygame.Surface, color: tuple, center: tuple, r: int, w: int = 0) -> None:
    if r < 1:
        return
    s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
    pygame.draw.circle(s, color, (r + 1, r + 1), r, w)
    surface.blit(s, (center[0] - r - 1, center[1] - r - 1))


def _rect_a(surface: pygame.Surface, color: tuple, rect: tuple) -> None:
    s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    s.fill(color)
    surface.blit(s, (rect[0], rect[1]))


def _line_a(surface: pygame.Surface, color: tuple, p1: tuple, p2: tuple, w: int = 1) -> None:
    s = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
    pygame.draw.line(s, color, p1, p2, w)
    surface.blit(s, (0, 0))


class StationSystem:

    def __init__(self) -> None:
        self.purchased: set[str] = set()
        # Expedition resources
        self.salvage: int = 0
        self.data_fragments: int = 0
        self.relay_components: int = 0
        self.ancient_tech: int = 0
        self._blink = random.uniform(0.0, math.tau)

    def reset(self) -> None:
        """Full progression reset — called on death. Clears upgrades and all resources."""
        self.purchased.clear()
        self.salvage = 0
        self.data_fragments = 0
        self.relay_components = 0
        self.ancient_tech = 0

    def add_salvage(self, n: int = 1) -> None:
        self.salvage += n

    def add_data(self, n: int = 1) -> None:
        self.data_fragments += n

    def add_relay(self, n: int = 1) -> None:
        self.relay_components += n

    def add_ancient(self, n: int = 1) -> None:
        self.ancient_tech += n

    def has(self, uid: str) -> bool:
        return uid in self.purchased

    def all_upgrades_complete(self) -> bool:
        """True when every regular (non-FINAL) upgrade has been purchased."""
        return REGULAR_UPGRADE_IDS.issubset(self.purchased)

    def lock_message_key(self, uid: str) -> str:
        """Return the station_ui t()-key suffix describing why uid is locked."""
        u = _BY_ID.get(uid)
        if u is None:
            return "requires_level_3"
        if u.get("requires_all_upgrades", False) and not self.all_upgrades_complete():
            return "rover_incomplete"
        return "requires_level_3"

    def can_afford(self, uid: str) -> bool:
        u = _BY_ID.get(uid)
        if u is None or uid in self.purchased:
            return False
        if u.get("requires_all_upgrades", False) and not self.all_upgrades_complete():
            return False
        c = u["cost"]
        return (
            self.salvage          >= c.get("salvage", 0)
            and self.data_fragments   >= c.get("data", 0)
            and self.relay_components >= c.get("relay", 0)
            and self.ancient_tech     >= c.get("ancient", 0)
        )

    def is_locked(self, uid: str) -> bool:
        """True when the prerequisite requirement is not yet met."""
        u = _BY_ID.get(uid)
        if u is None:
            return True
        return u.get("requires_all_upgrades", False) and not self.all_upgrades_complete()

    def purchase(self, uid: str) -> bool:
        if not self.can_afford(uid):
            return False
        c = _BY_ID[uid]["cost"]
        self.salvage          -= c.get("salvage", 0)
        self.data_fragments   -= c.get("data", 0)
        self.relay_components -= c.get("relay", 0)
        self.ancient_tech     -= c.get("ancient", 0)
        self.purchased.add(uid)
        return True

    def station_level(self) -> int:
        n = len(self.purchased - {"evac_protocol"})
        if n >= S.UPGRADE_THRESHOLD_L3:
            return 3
        if n >= S.UPGRADE_THRESHOLD_L2:
            return 2
        if n >= S.UPGRADE_THRESHOLD_L1:
            return 1
        return 0

    @property
    def energy_max(self) -> float:
        return 140.0 if self.has("battery_ext") else 100.0

    @property
    def energy_drain_mul(self) -> float:
        return 0.75 if self.has("solar_panel") else 1.0

    @property
    def storm_energy_drain_mul(self) -> float:
        return 0.50 if self.has("storm_shield") else 1.0

    @property
    def signal_drain_mul(self) -> float:
        return 0.70 if self.has("signal_stab") else 1.0

    @property
    def prompt_range_mul(self) -> float:
        return 1.35 if self.has("long_range_rx") else 1.0

    @property
    def storm_prompt_range_mul(self) -> float:
        return 1.40 if self.has("fog_vision") else 1.0

    @property
    def corrupt_reveal_mul(self) -> float:
        return 1.60 if self.has("int_filter") else 1.0

    @property
    def biome_speed_bonus(self) -> float:
        return 1.20 if self.has("engine_upg") else 1.0

    @property
    def boost_extra_drain_rate(self) -> float:
        """Extra boost_cooldown reduction per second (beyond movement system's 1/s)."""
        if self.has("boost_cooling"):
            return S.BOOST_COOLDOWN / 1.8 - 1.0  # ≈ 0.39
        return 0.0

    @property
    def storm_resistance_bonus(self) -> bool:
        return self.has("suspension")

    @property
    def shadow_grip(self) -> bool:
        return self.has("terrain_grip")

    @property
    def thermal_scanner(self) -> bool:
        return self.has("thermal_scan")

    @property
    def storm_predictor(self) -> bool:
        return self.has("storm_pred")

    @property
    def emergency_cell(self) -> bool:
        return self.has("emergency_cell")

    @property
    def deep_scan(self) -> bool:
        return self.has("deep_scan")

    @property
    def tower_decoder(self) -> bool:
        return self.has("tower_decoder")

    def draw(self, surface: pygame.Surface, draw_off: Vector2, time_s: float) -> None:
        cx = int(S.BASE_POSITION.x + draw_off.x)
        cy = int(S.BASE_POSITION.y + draw_off.y)
        margin = int(S.START_CRATER_RADIUS) + 60
        if cx < -margin or cx > S.SCREEN_WIDTH + margin or cy < -margin or cy > S.SCREEN_HEIGHT + margin:
            return
        self._draw_structures(surface, cx, cy, self.station_level(), time_s)

    def _draw_structures(
        self, surface: pygame.Surface, cx: int, cy: int, level: int, t: float
    ) -> None:
        cr = int(S.START_CRATER_RADIUS)

        ring_col = (90, 210, 130, 55 + level * 18) if level >= 3 else (62, 50, 78, 38 + level * 12)
        _circ(surface, ring_col, (cx, cy), cr, 2)
        _circ(surface, (55, 44, 68, 20), (cx, cy), int(cr * 0.62), 1)

        comp_r = 76
        inner_col = (90, 210, 140, 85 + level * 14) if level >= 3 else (88, 70, 108, 50 + level * 14)
        _circ(surface, inner_col, (cx, cy), comp_r, 2)

        if level >= 3:
            pad_r = comp_r + 14
            n_pad = 12
            for i in range(n_pad):
                ang = (i / n_pad) * math.tau
                px = int(cx + math.cos(ang) * pad_r)
                py = int(cy + math.sin(ang) * pad_r)
                pa = int(110 + 100 * abs(math.sin(t * 1.4 + i * 0.52)))
                _circ(surface, (80, 240, 140, pa), (px, py), 3)

        pad_alpha = 110 + level * 28
        _rect_a(surface, (52, 44, 60, pad_alpha), (cx - 26, cy - 20, 52, 38))
        if level >= 1:
            pygame.draw.line(surface, (72, 62, 82), (cx - 26, cy - 5), (cx + 26, cy - 5), 1)
            pygame.draw.line(surface, (72, 62, 82), (cx - 26, cy + 8), (cx + 26, cy + 8), 1)

        if level >= 1:
            conduit_a = 70 + level * 22
            cond_col = (90, 220, 140) if level >= 3 else (78, 62, 95)
            _circ(surface, (*cond_col, conduit_a), (cx, cy), 1)
            _line_a(surface, (*cond_col, conduit_a), (cx + 22, cy - 4), (cx + 62, cy - 10))
            _line_a(surface, (*cond_col, conduit_a), (cx - 22, cy + 4), (cx - 68, cy + 14))
            _line_a(surface, (*cond_col, conduit_a), (cx + 4, cy - 20), (cx + 12, cy - 72))

        bw, bh = 44, 32
        bldg_alpha = 165 + level * 22
        _rect_a(surface, (60, 52, 70, bldg_alpha), (cx - bw // 2, cy - bh // 2, bw, bh))
        win_col = (80, 255, 140) if level >= 3 else (120, 180, 220)
        win_a = 55 + level * 48
        for wx in (cx - bw // 2 + 5, cx - bw // 2 + 18, cx - bw // 2 + 31):
            _rect_a(surface, (*win_col, win_a), (wx, cy - bh // 2 + 8, 8, 4))
        pygame.draw.line(surface, (80, 68, 92),
                         (cx - bw // 2, cy - bh // 2), (cx + bw // 2, cy - bh // 2), 1)
        # Status blinker (level 0 = critical red, level 3 = bright evacuation green)
        blink_colors = [(220, 90, 50), (205, 170, 50), (95, 210, 140), (60, 255, 120)]
        if math.sin(t * 1.8 + self._blink) > 0.35:
            warn_col = blink_colors[level]
            warn_a = 180 if level == 0 else 130 + level * 18
            _circ(surface, (*warn_col, warn_a), (cx + bw // 2 - 4, cy - bh // 2 - 5), 3)

        pu = (cx + 64, cy - 10)
        _rect_a(surface, (55, 48, 66, 148 + level * 20), (pu[0] - 14, pu[1] - 10, 28, 20))
        if level >= 1:
            gp = 0.5 + 0.5 * math.sin(t * 2.4)
            pu_col = (80, 230, 140) if level >= 3 else (100, 175, 255)
            _circ(surface, (*pu_col, int(28 + 46 * gp)), pu, 10)
            pygame.draw.circle(surface, pu_col, pu, 2)

        rn = (cx - 72, cy + 14)
        _rect_a(surface, (52, 46, 62, 142 + level * 20), (rn[0] - 10, rn[1] - 14, 20, 28))
        if level >= 1 and math.sin(t * 3.1 + 1.5) > 0.18:
            rn_col = (80, 255, 160) if level >= 3 else (80, 220, 140)
            _circ(surface, (*rn_col, 155), (rn[0], rn[1] - 18), 3)

        ax, ay = cx + 12, cy - 70
        atop = ay - 30
        pygame.draw.line(surface, (70, 60, 80), (ax, ay), (ax, atop), 2)
        pygame.draw.line(surface, (70, 60, 80), (ax - 8, ay + 14), (ax + 8, ay + 14), 1)
        pygame.draw.line(surface, (70, 60, 80), (ax - 4, ay + 22), (ax + 4, ay + 22), 1)
        arm_col = (88, 145, 205) if level >= 1 else (62, 56, 72)
        pygame.draw.line(surface, arm_col, (ax - 12, atop + 10), (ax, atop - 2), 2)
        pygame.draw.line(surface, arm_col, (ax + 12, atop + 10), (ax, atop - 2), 2)
        tp = 0.5 + 0.5 * math.sin(t * 5.0 + self._blink)
        tip_a = int(70 * tp) if level == 0 else int(125 + 65 * tp)
        tip_c = (60, 255, 140) if level >= 3 else ((88, 145, 205) if level >= 1 else (118, 88, 55))
        _circ(surface, (*tip_c, tip_a), (ax, atop - 2), 5)
        pygame.draw.circle(surface, tip_c, (ax, atop - 2), 2)

        db = (cx - 16, cy + 56)
        _rect_a(surface, (50, 44, 58, 128 + level * 16), (db[0] - 22, db[1] - 8, 44, 14))
        pygame.draw.line(surface, (38, 32, 46), (db[0] - 14, db[1] - 2), (db[0] + 14, db[1] - 2), 1)

        if level >= 3:
            doc_a = int(80 + 60 * abs(math.sin(t * 0.9)))
            _rect_a(surface, (50, 70, 55, doc_a), (db[0] - 38, db[1] - 4, 76, 6))
            pygame.draw.line(surface, (50, 200, 100), (db[0] - 36, db[1] + 3), (db[0] + 36, db[1] + 3), 1)
            for sign in (-1, 1):
                dx = db[0] + sign * 34
                da = int(140 + 100 * abs(math.sin(t * 3.8 + (0 if sign > 0 else math.pi))))
                _circ(surface, (80, 240, 120, da), (dx, db[1] - 1), 2)

        n_lights = 6 + level * 2
        lit_r = comp_r - 12
        lit_col = (95, 240, 140) if level >= 3 else ((95, 210, 140) if level >= 2 else (175, 108, 58))
        for i in range(n_lights):
            ang = (i / n_lights) * math.tau + t * 0.12
            lx = int(cx + math.cos(ang) * lit_r)
            ly = int(cy + math.sin(ang) * lit_r)
            if math.sin(t * 2.5 + i * 1.8) > 0.25:
                la = 115 + level * 30
                _circ(surface, (*lit_col, la), (lx, ly), 3)

        if level >= 2:
            ph = (t * 1.6) % 1.0
            pulse_col = (80, 220, 140) if level >= 3 else (100, 180, 255)
            dx_p = int(cx + 22 + (cx + 62 - (cx + 22)) * ph)
            dy_p = int(cy - 4 + (-10 - (-4)) * ph)
            _circ(surface, (*pulse_col, 145), (dx_p, dy_p), 3)

        if level >= 3:
            for i in range(4):
                ang = (i / 4) * math.tau + math.pi / 4
                sx = int(cx + math.cos(ang) * (comp_r + 6))
                sy = int(cy + math.sin(ang) * (comp_r + 6))
                ex = int(cx + math.cos(ang) * (comp_r + 24))
                ey = int(cy + math.sin(ang) * (comp_r + 24))
                pygame.draw.line(surface, (55, 185, 100), (sx, sy), (ex, ey), 2)

        if level >= 3:
            bx, by = cx - 58, cy - 20
            pygame.draw.line(surface, (55, 168, 80), (bx, by), (bx, by - 44), 2)
            pygame.draw.line(surface, (38, 120, 55), (bx - 6, by - 6), (bx + 6, by - 6), 1)
            pygame.draw.line(surface, (38, 120, 55), (bx - 4, by - 18), (bx + 4, by - 18), 1)
            bp = 0.55 + 0.45 * abs(math.sin(t * 4.5))
            ba = int(160 + 90 * bp)
            _circ(surface, (60, 255, 120, ba), (bx, by - 48), 5)
            pygame.draw.circle(surface, (60, 255, 120), (bx, by - 48), 2)
            beam_a = int(30 + 40 * bp)
            for row in range(40):
                row_a = int(beam_a * (1.0 - row / 40.0) ** 1.5)
                if row_a > 2:
                    pygame.draw.line(surface, (60, 255, 120, row_a),
                                     (bx - 1, by - 52 - row), (bx + 1, by - 52 - row), 1)
