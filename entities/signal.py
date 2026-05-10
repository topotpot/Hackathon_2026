
import math
import random

import pygame
from pygame import Rect, Vector2

from core import settings as S


def _lerp3(a: tuple, b: tuple, t: float) -> tuple:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


class Signal:


    POLE_H = 32
    _ARM_W = 14

    _COL_IDLE      = (148, 98, 46)
    _COL_PROMPT    = (188, 130, 62)
    _COL_CONNECT   = (75, 185, 255)
    _COL_CORRUPT   = (175, 65, 215)
    _COL_FAIL      = (220, 55, 55)
    _COL_ACTIVATED = (50, 200, 130)

    _RING_IDLE     = (100, 64, 26)
    _RING_CONN     = (38, 115, 210)
    _RING_CORRUPT  = (112, 32, 158)

    def __init__(self, position: Vector2, is_real: bool = True) -> None:
        self.position = Vector2(position)
        self.is_real = is_real
        self.radius = S.SIGNAL_PICKUP_RADIUS
        self.connect_range = S.SIGNAL_CONNECT_RANGE
        self.prompt_range = S.SIGNAL_PROMPT_RANGE

        self._seed = random.random() * 1000.0
        self._state = "idle"
        self._connect_time = 0.0
        self._broken_t = 0.0
        self._fail_t = 0.0
        self._ring_phase = random.uniform(0.0, math.tau)
        self._corrupt_phase_t = 0.0
        self._fail_pending = False

        self._corrupt_reveal_t = (
            random.uniform(S.CORRUPT_REVEAL_MIN, S.CORRUPT_REVEAL_MAX)
            if not is_real else float("inf")
        )

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_connecting(self) -> bool:
        return self._state in ("connecting", "corrupt_early", "corrupt_mid")

    @property
    def show_prompt(self) -> bool:
        return self._state == "prompt"

    @property
    def connect_time(self) -> float:
        return self._connect_time

    @property
    def corruption_intensity(self) -> float:
        """0.0 = clean, 1.0 = maximum corruption."""
        if self._state == "corrupt_early":
            return min(1.0, self._corrupt_phase_t / max(S.CORRUPT_EARLY_DURATION, 0.01)) * 0.45
        if self._state == "corrupt_mid":
            return 0.45 + min(1.0, self._corrupt_phase_t / max(S.CORRUPT_MID_DURATION, 0.01)) * 0.55
        if self._state in ("corrupt_fail", "dead"):
            return 1.0
        return 0.0

    @property
    def rect(self) -> Rect:
        r = self.radius
        return Rect(int(self.position.x - r), int(self.position.y - r), r * 2, r * 2)

    def consume_fail(self) -> bool:
        if self._fail_pending:
            self._fail_pending = False
            return True
        return False

    def prompt_range_contains(self, pos: Vector2) -> bool:
        dx = pos.x - self.position.x
        dy = pos.y - self.position.y
        return dx * dx + dy * dy <= self.prompt_range * self.prompt_range

    def connect_range_contains(self, pos: Vector2) -> bool:
        dx = pos.x - self.position.x
        dy = pos.y - self.position.y
        return dx * dx + dy * dy <= self.connect_range * self.connect_range

    def enter_prompt(self) -> None:
        if self._state == "idle":
            self._state = "prompt"

    def exit_prompt(self) -> None:
        if self._state == "prompt":
            self._state = "idle"

    def start_connect(self) -> None:
        if self._state in ("prompt", "idle"):
            self._state = "connecting"
            self._connect_time = 0.0
            self._corrupt_phase_t = 0.0

    def break_connect(self) -> None:
        if self.is_connecting:
            self._state = "broken"
            self._connect_time = 0.0
            self._corrupt_phase_t = 0.0
            self._broken_t = 1.6

    def stop_connect(self) -> None:
        if self.is_connecting:
            self._state = "idle"
            self._connect_time = 0.0
            self._corrupt_phase_t = 0.0

    def activate(self) -> None:
        self._state = "activated"
        self._connect_time = 0.0

    def update(self, dt: float, corrupt_speed: float = 1.0, corrupt_reveal_mul: float = 1.0) -> None:
        ring_speed = 3.5 if self.is_connecting else 1.0
        self._ring_phase += dt * ring_speed

        if self._state == "broken":
            self._broken_t = max(0.0, self._broken_t - dt)
            if self._broken_t <= 0.0:
                self._state = "idle"

        elif self._state == "connecting":
            self._connect_time += dt
            if not self.is_real and self._connect_time >= self._corrupt_reveal_t * corrupt_reveal_mul:
                self._state = "corrupt_early"
                self._corrupt_phase_t = 0.0

        elif self._state == "corrupt_early":
            self._connect_time += dt
            self._corrupt_phase_t += dt * corrupt_speed
            if self._corrupt_phase_t >= S.CORRUPT_EARLY_DURATION:
                self._state = "corrupt_mid"
                self._corrupt_phase_t = 0.0

        elif self._state == "corrupt_mid":
            self._connect_time += dt
            self._corrupt_phase_t += dt * corrupt_speed
            if self._corrupt_phase_t >= S.CORRUPT_MID_DURATION:
                self._state = "corrupt_fail"
                self._corrupt_phase_t = 0.0
                self._fail_t = 1.0
                self._fail_pending = True

        elif self._state == "corrupt_fail":
            self._fail_t = max(0.0, self._fail_t - dt)
            if self._fail_t <= 0.0:
                self._state = "dead"

    def draw(self, surface: pygame.Surface, offset: Vector2, time_s: float) -> None:
        bx = int(self.position.x + offset.x)
        by = int(self.position.y + offset.y)
        state = self._state
        tip_y = by - self.POLE_H

        if state == "dead":
            dc = (20, 14, 12)
            db = (30, 20, 16)
            lean = int((self._seed * 0.003) % 5) - 2  # slight lean from damage
            pygame.draw.rect(surface, (24, 16, 12), pygame.Rect(bx - 7, by + 2, 14, 4), border_radius=2)
            pygame.draw.line(surface, dc, (bx, by - 1), (bx - 20, by + 4), 2)
            pygame.draw.line(surface, dc, (bx, by - 1), (bx + 18, by + 4), 2)
            pygame.draw.line(surface, dc, (bx, by - 1), (bx - 12, by + 2), 1)
            pygame.draw.line(surface, dc, (bx, by - 1), (bx + 12, by + 2), 1)
            pygame.draw.line(surface, dc, (bx, by - 2), (bx + lean, tip_y + 4), 3)
            pygame.draw.line(surface, dc, (bx, by - 2), (bx + lean, tip_y + 4), 1)
            pygame.draw.line(surface, dc, (bx - 9, tip_y + 10), (bx + 9, tip_y + 10), 1)
            aw = self._ARM_W
            pygame.draw.line(surface, dc, (bx - aw, tip_y + 11), (bx + lean, tip_y), 1)
            pygame.draw.line(surface, dc, (bx + aw, tip_y + 11), (bx + lean, tip_y), 1)
            d = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.circle(d, (48, 28, 22, 35), (5, 5), 4)
            surface.blit(d, (bx + lean - 5, tip_y - 5))
            return

        if state == "activated":
            base_col = self._COL_ACTIVATED
            ring_col = (28, 140, 85)
        elif state in ("connecting", "corrupt_early"):
            base_col = self._COL_CONNECT
            ring_col = self._RING_CONN
        elif state == "corrupt_mid":
            frac = min(1.0, self._corrupt_phase_t / max(S.CORRUPT_MID_DURATION, 0.01))
            base_col = _lerp3(self._COL_CONNECT, self._COL_CORRUPT, frac)
            ring_col = _lerp3(self._RING_CONN, self._RING_CORRUPT, frac)
        elif state == "corrupt_fail":
            base_col = self._COL_FAIL
            ring_col = (148, 28, 28)
        elif state == "prompt":
            base_col = self._COL_PROMPT
            ring_col = self._RING_IDLE
        else:
            base_col = self._COL_IDLE
            ring_col = self._RING_IDLE

        # Structural jitter for corruption
        jx = jy = 0
        if state == "corrupt_early":
            if random.random() < 0.07:
                jx = random.randint(-2, 2)
                jy = random.randint(-1, 1)
        elif state == "corrupt_mid":
            frac = min(1.0, self._corrupt_phase_t / max(S.CORRUPT_MID_DURATION, 0.01))
            if random.random() < 0.18 + 0.38 * frac:
                jx = random.randint(-3, 3)
                jy = random.randint(-2, 2)
        elif state == "corrupt_fail":
            jx = random.randint(-5, 5)
            jy = random.randint(-3, 3)

        bx += jx; by += jy; tip_y += jy

        if state not in ("broken", "corrupt_fail", "activated", "dead"):
            if state in ("connecting", "corrupt_early", "corrupt_mid"):
                n_rings = 3
                frac_mid = (
                    min(1.0, self._corrupt_phase_t / max(S.CORRUPT_MID_DURATION, 0.01))
                    if state == "corrupt_mid" else 0.0
                )
                intensity = 1.6 + 0.5 * frac_mid
            elif state == "prompt":
                n_rings, intensity = 2, 1.1
            else:
                n_rings, intensity = 2, 0.6

            for ri in range(n_rings):
                frac_r = (self._ring_phase + ri / n_rings) % 1.0
                r = int(self.connect_range * (0.22 + 0.78 * frac_r))
                alpha = int(78 * (1.0 - frac_r) * intensity)
                if alpha > 3 and r > 1:
                    rs = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
                    pygame.draw.circle(rs, (*ring_col, alpha), (r + 1, r + 1), r, 1)
                    surface.blit(rs, (bx - r - 1, by - r - 1))

        if state == "activated":
            halo_r = int(self.connect_range * 0.32)
            hs = pygame.Surface((halo_r * 2 + 2, halo_r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(hs, (50, 200, 130, 18), (halo_r + 1, halo_r + 1), halo_r, 1)
            surface.blit(hs, (bx - halo_r - 1, by - halo_r - 1))

        # Flicker skip
        if state == "broken" and random.random() < 0.50:
            return
        if state == "corrupt_fail" and random.random() < 0.42:
            return

        plate_col = (52, 44, 40) if state not in ("corrupt_mid", "corrupt_fail") else (58, 34, 34)
        pygame.draw.rect(surface, plate_col, pygame.Rect(bx - 7, by + 2, 14, 4), border_radius=2)
        pygame.draw.rect(surface, (68, 58, 52), pygame.Rect(bx - 7, by + 2, 14, 4), 1, border_radius=2)

        if state in ("idle", "prompt"):
            glow_intensity = 0.45 if state == "idle" else 0.72
            agl_r = 14
            agl = pygame.Surface((agl_r * 2, agl_r * 2), pygame.SRCALPHA)
            agl_a = int(28 * glow_intensity)
            pygame.draw.circle(agl, (*base_col, agl_a), (agl_r, agl_r), agl_r)
            surface.blit(agl, (bx - agl_r, by - agl_r), special_flags=pygame.BLEND_ADD)

        corrupt_struct = state in ("corrupt_mid", "corrupt_fail")
        mast_col  = (68, 46, 40) if corrupt_struct else (62, 52, 42)
        brace_col = (50, 32, 28) if corrupt_struct else (46, 38, 30)
        mast_hi   = (84, 56, 48) if corrupt_struct else (78, 66, 52)

        pygame.draw.line(surface, brace_col, (bx, by - 1), (bx - 20, by + 5), 2)
        pygame.draw.line(surface, brace_col, (bx, by - 1), (bx + 18, by + 5), 2)
        pygame.draw.line(surface, brace_col, (bx, by - 1), (bx - 12, by + 3), 1)
        pygame.draw.line(surface, brace_col, (bx, by - 1), (bx + 11, by + 3), 1)

        # Tapering mast — 4 segments, 4→2px width
        for seg in range(4):
            y0 = (by - 2) - seg * 8
            y1 = (by - 2) - (seg + 1) * 8
            pygame.draw.line(surface, mast_col, (bx, y0), (bx, y1), max(1, 4 - seg))
        pygame.draw.line(surface, mast_hi, (bx + 1, by - 5), (bx + 1, tip_y + 4), 1)

        cb1_y = tip_y + int(self.POLE_H * 0.30)
        pygame.draw.line(surface, mast_col, (bx - 10, cb1_y), (bx + 10, cb1_y), 1)
        pygame.draw.line(surface, brace_col, (bx - 10, cb1_y), (bx - 4, cb1_y + 10), 1)
        pygame.draw.line(surface, brace_col, (bx + 10, cb1_y), (bx + 4, cb1_y + 10), 1)

        cb2_y = tip_y + int(self.POLE_H * 0.62)
        pygame.draw.line(surface, mast_col, (bx - 7, cb2_y), (bx + 7, cb2_y), 1)

        aw = self._ARM_W
        pygame.draw.line(surface, base_col, (bx - aw, tip_y + 11), (bx, tip_y - 2), 2)
        pygame.draw.line(surface, base_col, (bx + aw, tip_y + 11), (bx, tip_y - 2), 2)

        # Dish arm — extends from upper crossbar level, side determined by seed
        arm_side = 1 if int(self._seed * 137) % 2 == 0 else -1
        arm_base_y = tip_y + int(self.POLE_H * 0.26)
        arm_ex = bx + arm_side * 16
        arm_ey = arm_base_y - 3
        pygame.draw.line(surface, base_col, (bx, arm_base_y), (arm_ex, arm_ey), 2)
        pygame.draw.arc(
            surface, base_col,
            pygame.Rect(arm_ex - 7, arm_ey - 9, 14, 10),
            math.pi * 0.05, math.pi * 0.95, 2,
        )
        pygame.draw.line(surface, base_col, (arm_ex, arm_ey - 5), (arm_ex, arm_ey), 1)

        scan_spd = 3.0 if self.is_connecting else (1.4 if state == "prompt" else 0.55)
        scan_ang = time_s * scan_spd + self._seed
        scan_len = 9
        tip_cx, tip_cy = bx, tip_y - 2
        sex = tip_cx + int(math.cos(scan_ang) * scan_len)
        sey = tip_cy + int(math.sin(scan_ang) * scan_len * 0.42)
        pygame.draw.line(surface, base_col, (tip_cx, tip_cy), (sex, sey), 1)

        if state in ("connecting", "corrupt_early"):
            t_pulse = 0.90 + 0.10 * math.sin(time_s * 14.0 + self._seed)
        elif state == "activated":
            t_pulse = 0.52 + 0.08 * math.sin(time_s * 1.8 + self._seed)
        elif state in ("broken", "corrupt_fail"):
            t_pulse = 0.28 + 0.72 * random.random()
        elif state == "corrupt_mid":
            frac = min(1.0, self._corrupt_phase_t / max(S.CORRUPT_MID_DURATION, 0.01))
            t_pulse = 0.65 + 0.35 * math.sin(time_s * (14.0 + frac * 24.0) + self._seed)
            if random.random() < 0.20 * (1.0 + frac):
                t_pulse = random.uniform(0.08, 1.5)
        elif state == "prompt":
            t_pulse = 0.52 + 0.48 * abs(math.sin(time_s * 3.8 + self._seed))
        else:
            t_pulse = 0.40 + 0.20 * math.sin(time_s * 2.2 + self._seed)

        tip_col = tuple(min(255, int(c * max(0.0, t_pulse))) for c in base_col)
        glow_r = 6 if self.is_connecting else 4
        glow_s = pygame.Surface((glow_r * 4, glow_r * 4), pygame.SRCALPHA)
        ga = int(158 * max(0.0, t_pulse)) if self.is_connecting else int(48 * max(0.0, t_pulse))
        pygame.draw.circle(glow_s, (*base_col, min(255, ga)), (glow_r * 2, glow_r * 2), glow_r * 2)
        surface.blit(glow_s, (bx - glow_r * 2, tip_y - 2 - glow_r * 2), special_flags=pygame.BLEND_ADD)
        pygame.draw.circle(surface, tip_col, (bx, tip_y - 2), 3 if self.is_connecting else 2)

        if state == "activated":
            mk = pygame.Surface((18, 18), pygame.SRCALPHA)
            pygame.draw.circle(mk, (50, 200, 130, 50), (9, 9), 8)
            pygame.draw.circle(mk, (50, 200, 130, 135), (9, 9), 3)
            surface.blit(mk, (bx - 9, tip_y - 11))

        if state == "connecting" and S.SIGNAL_CONNECT_DURATION > 0:
            frac = min(1.0, self._connect_time / S.SIGNAL_CONNECT_DURATION)
            arc_r = int(self.connect_range * 0.22)
            if arc_r > 2 and frac > 0.01:
                arc_s = pygame.Surface((arc_r * 2 + 4, arc_r * 2 + 4), pygame.SRCALPHA)
                end_angle = -math.pi / 2 + frac * math.tau
                pygame.draw.arc(
                    arc_s, (*base_col, 200),
                    pygame.Rect(2, 2, arc_r * 2, arc_r * 2),
                    -math.pi / 2, end_angle, 2,
                )
                surface.blit(arc_s, (bx - arc_r - 2, by - arc_r - 2))

        if state == "corrupt_mid":
            frac = min(1.0, self._corrupt_phase_t / max(S.CORRUPT_MID_DURATION, 0.01))
            if random.random() < 0.28 * (0.5 + frac):
                for _ in range(random.randint(1, max(1, int(2 + frac * 3)))):
                    gy = by + random.randint(-self.POLE_H, 12)
                    gw = random.randint(5, 18)
                    gx = bx + random.randint(-gw, 0)
                    gs = pygame.Surface((gw, 2), pygame.SRCALPHA)
                    gs.fill((*self._COL_CORRUPT, random.randint(65, 175)))
                    surface.blit(gs, (gx, gy))
