
import math
import random

import pygame
from pygame import Vector2

from core import settings as S
from utils.helpers import clamp


def _lerp_rgb(
    a: tuple[int, int, int], b: tuple[int, int, int], t: float
) -> tuple[int, int, int]:
    t = clamp(t, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


class MarsBackdrop:

    def __init__(self, w: int, h: int) -> None:
        self._w = w
        self._h = h
        self._scroll = Vector2(0.0, 0.0)
        self._gradient = self._build_gradient(w, h)
        self._horizon = self._build_horizon(w, h)
        self._noise = self._build_noise(w, h)
        self._dust = self._build_dust_tile(256, 256)
        self._dust_tick = 0.0
        self._dust.set_alpha(42)

    def reset_scroll(self) -> None:
        self._scroll.update(0.0, 0.0)

    def _build_gradient(self, w: int, h: int) -> pygame.Surface:
        top = (68, 16, 20)
        mid = (22, 8, 18)   # more purple mid-range
        bot = (6, 3, 14)    # deep violet-black at bottom
        s = pygame.Surface((w, h))
        for y in range(h):
            frac = y / max(h - 1, 1)
            if frac < 0.42:
                c = _lerp_rgb(top, mid, frac / 0.42)
            else:
                c = _lerp_rgb(mid, bot, (frac - 0.42) / 0.58)
            pygame.draw.line(s, c, (0, y), (w, y))
        return s.convert()

    def _build_horizon(self, w: int, h: int) -> pygame.Surface:
        """Precomputed atmospheric glow band near the upper horizon."""
        band_h = 48
        band_y = int(h * 0.28)
        s = pygame.Surface((w, band_h), pygame.SRCALPHA)
        for row in range(band_h):
            dist = abs(row - band_h // 2) / (band_h // 2)
            a = int(38 * (1.0 - dist * dist))
            if a > 0:
                pygame.draw.line(s, (195, 90, 42, a), (0, row), (w, row))
        return s

    def _build_noise(self, w: int, h: int) -> pygame.Surface:
        rnd = random.Random(42)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        step = 4
        for y in range(0, h, step):
            for x in range(0, w, step):
                v = rnd.randint(0, 40)
                a = rnd.randint(10, 38)
                s.fill((v, v // 2, v // 3, a), (x, y, step, step))
        return s

    def _build_dust_tile(self, tw: int, th: int) -> pygame.Surface:
        rnd = random.Random(901)
        s = pygame.Surface((tw, th), pygame.SRCALPHA)
        for _ in range(320):
            x = rnd.randint(0, tw - 1)
            y = rnd.randint(0, th - 1)
            r = rnd.randint(1, 3)
            a = rnd.randint(10, 48)
            pygame.draw.circle(s, (200, 140, 110, a), (x, y), r)
        for _ in range(90):
            x = rnd.randint(0, tw - 1)
            y = rnd.randint(0, th - 1)
            lw = rnd.randint(4, 12)
            a = rnd.randint(8, 32)
            pygame.draw.line(s, (215, 155, 120, a), (x, y), (x + lw, y), 1)
        return s

    def update_parallax(self, player_velocity: Vector2, dt: float) -> None:
        self._scroll -= player_velocity * S.PARALLAX_SCROLL_MUL * dt
        self._scroll.x %= self._dust.get_width()
        self._scroll.y %= self._dust.get_height()

    def draw_background(self, target: pygame.Surface, time_s: float) -> None:
        target.blit(self._gradient, (0, 0))
        ha = int(22 + 14 * (0.5 + 0.5 * math.sin(time_s * 0.18)))
        self._horizon.set_alpha(ha)
        target.blit(self._horizon, (0, int(self._h * 0.28) - self._horizon.get_height() // 2))
        n = self._noise
        n.set_alpha(int(20 + 10 * (0.5 + 0.5 * math.sin(time_s * 0.35))))
        target.blit(n, (0, 0))

    def draw_parallax_dust(self, target: pygame.Surface, time_s: float) -> None:
        ox = int(self._scroll.x + 8 * math.sin(time_s * 0.12))
        oy = int(self._scroll.y + 6 * math.cos(time_s * 0.09))
        tw, th = self._dust.get_size()
        for ix in range(-1, self._w // tw + 2):
            for iy in range(-1, self._h // th + 2):
                px = ix * tw + ox % tw - tw
                py = iy * th + oy % th - th
                target.blit(self._dust, (px, py))
