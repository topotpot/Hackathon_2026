
import math
import random
from dataclasses import dataclass

import pygame
from pygame import Vector2

from core import settings as S
from utils.helpers import clamp


@dataclass
class _Spark:
    pos: Vector2
    vel: Vector2
    life: float
    max_life: float
    r: float
    col: tuple[int, int, int, int]


class MicroFX:

    def __init__(self) -> None:
        self._p: list[_Spark] = []
        self._acc_dust = 0.0

    def clear(self) -> None:
        self._p.clear()
        self._acc_dust = 0.0

    def _spawn(self, s: _Spark) -> None:
        if len(self._p) >= S.MICRO_FX_MAX:
            self._p.pop(0)
        self._p.append(s)

    def emit_rover_dust(self, pos: Vector2, velocity: Vector2, dt: float) -> None:
        sp = velocity.length()
        if sp < 28:
            return
        self._acc_dust += sp * dt * 0.018
        n = int(self._acc_dust)
        self._acc_dust -= n
        back = -velocity.normalize() if velocity.length_squared() > 1e-6 else Vector2(-1, 0)
        for _ in range(n):
            p = pos + Vector2(random.uniform(-8, 8), random.uniform(-6, 6)) + back * 10
            v = back * random.uniform(20, 85) + Vector2(random.uniform(-30, 30), random.uniform(-24, 24))
            life = random.uniform(0.18, 0.42)
            c = (200, 150, 120, random.randint(90, 180))
            self._spawn(_Spark(Vector2(p), v, life, life, random.uniform(1.2, 2.4), c))

    def burst_resource(self, pos: Vector2) -> None:
        for _ in range(14):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(40, 160)
            v = Vector2(math.cos(ang), math.sin(ang)) * spd
            life = random.uniform(0.2, 0.55)
            c = (
                random.randint(90, 180),
                random.randint(200, 255),
                random.randint(240, 255),
                random.randint(140, 240),
            )
            self._spawn(
                _Spark(Vector2(pos), v, life, life, random.uniform(1.5, 3.2), c)
            )

    def burst_signal(self, pos: Vector2, is_real: bool) -> None:
        n = 18 if is_real else 26
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(30, 140)
            v = Vector2(math.cos(ang), math.sin(ang)) * spd
            life = random.uniform(0.15, 0.45)
            if is_real:
                c = (120, 210, 255, random.randint(100, 220))
            else:
                c = (255, 80, 120, random.randint(120, 240))
            self._spawn(
                _Spark(Vector2(pos), v, life, life, random.uniform(1.2, 2.8), c)
            )

    def update(self, dt: float) -> None:
        alive: list[_Spark] = []
        for s in self._p:
            s.life -= dt
            if s.life <= 0:
                continue
            s.vel *= max(0.0, 1.0 - 2.4 * dt)
            s.pos += s.vel * dt
            alive.append(s)
        self._p = alive

    def draw(self, surface: pygame.Surface, offset: Vector2) -> None:
        for s in self._p:
            u = 1.0 - s.life / max(s.max_life, 1e-6)
            a = int(s.col[3] * (1.0 - u) ** 0.9)
            if a < 3:
                continue
            r = max(1, int(s.r * (1.0 - 0.4 * u)))
            ring = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, (s.col[0], s.col[1], s.col[2], a), (r, r), r)
            px = int(s.pos.x + offset.x) - r
            py = int(s.pos.y + offset.y) - r
            surface.blit(ring, (px, py), special_flags=pygame.BLEND_ADD)
