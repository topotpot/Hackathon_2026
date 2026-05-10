
import random

import pygame

from core import settings as S
from utils.helpers import clamp


def _smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class ScreenEffects:

    def __init__(self, w: int, h: int) -> None:
        self._w = w
        self._h = h
        self._vignette = self._build_vignette(w, h)
        self._vignette_work = self._vignette.copy()
        self._noise = pygame.Surface((w, h), pygame.SRCALPHA)
        self._storm_tint = pygame.Surface((w, h), pygame.SRCALPHA)
        self._storm_dark = pygame.Surface((w, h), pygame.SRCALPHA)
        self._storm_flash = pygame.Surface((w, h), pygame.SRCALPHA)
        self._noise_tick = 0.0
        self.shake_x = 0.0
        self.shake_y = 0.0
        self._shake_decay = 18.0
        self._row_cache: pygame.Surface | None = None
        self._grain_frames = self._build_grain_frames(w, h, 4)
        self._grain_idx = 0
        self._grain_tick = 0.0

    def _build_vignette(self, w: int, h: int) -> pygame.Surface:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w * 0.5, h * 0.5
        max_r = (w * w + h * h) ** 0.5 * 0.50
        for y in range(0, h, 3):
            for x in range(0, w, 3):
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                frac = _smoothstep(d / max_r)
                a = int(215 * frac ** 1.65)
                s.fill((0, 0, 0, a), (x, y, 3, 3))
        return s

    def _build_grain_frames(self, w: int, h: int, n: int) -> list:
        frames = []
        for k in range(n):
            rnd = random.Random(k * 0x5A3F + 0x2D71)
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            for _ in range(480):
                px = rnd.randint(0, w - 1)
                py = rnd.randint(0, h - 1)
                v = rnd.randint(55, 135)
                a = rnd.randint(5, 20)
                s.set_at((px, py), (v, v, v, a))
            frames.append(s)
        return frames

    def add_shake(self, amount: float) -> None:
        a = amount * random.choice([-1.0, 1.0])
        b = amount * random.choice([-1.0, 1.0])
        self.shake_x += a
        self.shake_y += b

    def update(self, dt: float) -> None:
        decay = max(0.0, 1.0 - self._shake_decay * dt)
        self.shake_x *= decay
        self.shake_y *= decay
        if abs(self.shake_x) < 0.05:
            self.shake_x = 0.0
        if abs(self.shake_y) < 0.05:
            self.shake_y = 0.0
        self._grain_tick += dt
        if self._grain_tick >= 1.0 / 12:
            self._grain_tick = 0.0
            self._grain_idx = (self._grain_idx + 1) % len(self._grain_frames)

    def storm_shake(self, intensity: float) -> tuple[int, int]:
        if intensity <= 0.05:
            return (0, 0)
        n = min(1.0, intensity / max(S.STORM_INTENSITY_MAX, 0.01))
        amp = int(3 + 10 * (n**1.12))
        return (random.randint(-amp, amp), random.randint(-amp, amp))

    def apply(
        self,
        target: pygame.Surface,
        signal_norm: float,
        storm_active: bool,
        storm_intensity: float,
        glitch_strength: float,
        vignette_mul: float = 1.0,
        storm_flash_strength: float = 0.0,
    ) -> None:
        # Vignette intensity scales inversely with signal — near-zero signal = nearly black edges
        sn = clamp(signal_norm, 0.0, 1.0)
        v_alpha = int((1.0 - sn) * 160 * max(0.0, float(vignette_mul)))
        if v_alpha > 0:
            v = self._vignette_work
            v.set_alpha(v_alpha)
            target.blit(v, (0, 0))

        # Static interference noise — regenerated at ~17fps to look like signal degradation
        if sn < 0.45:
            self._noise_tick += 1.0 / max(S.FPS, 1)
            if self._noise_tick >= 0.06:
                self._noise_tick = 0.0
                self._noise.fill((0, 0, 0, 0))
                amount = int((0.45 - sn) * 900)
                for _ in range(amount):
                    x = random.randint(0, self._w - 1)
                    y = random.randint(0, self._h - 1)
                    g = random.randint(40, 120)
                    a = random.randint(8, 28)
                    self._noise.set_at((x, y), (g, g, g, a))
            na = int((0.45 - sn) / 0.45 * 70)
            self._noise.set_alpha(na)
            target.blit(self._noise, (0, 0))

        # Storm: color tint + visibility darkening (separate layers so each scales independently)
        if storm_active:
            n = min(1.0, storm_intensity / max(S.STORM_INTENSITY_MAX, 0.01))
            a = int(22 + 70 * (n**1.05))
            self._storm_tint.fill((*S.COLOR_STORM_OVERLAY, a))
            target.blit(self._storm_tint, (0, 0))

            da = int(8 + 86 * (n**1.25))
            self._storm_dark.fill((0, 0, 0, da))
            target.blit(self._storm_dark, (0, 0))

            if storm_flash_strength > 0.01:
                f = min(1.0, storm_flash_strength)
                fa = int(18 + 190 * (f**1.35))
                self._storm_flash.fill((255, 220, 150, fa))
                target.blit(self._storm_flash, (0, 0), special_flags=pygame.BLEND_ADD)

        # Glitch scanline displacement — strip width drives how much the line shifts horizontally
        if glitch_strength > 0.02:
            h = int(glitch_strength * 10)
            h = clamp(h, 1, 14)
            step = 6
            for y in range(0, self._h, step):
                if random.random() < glitch_strength * 0.65:
                    dx = int(random.randint(-h, h))
                    strip_h = min(step, self._h - y)
                    rect = pygame.Rect(0, y, self._w, strip_h)
                    sub = target.subsurface(rect).copy()
                    target.blit(sub, (dx, y))

        # Film grain — pre-built static frames cycled at ~12fps
        target.blit(self._grain_frames[self._grain_idx], (0, 0))
