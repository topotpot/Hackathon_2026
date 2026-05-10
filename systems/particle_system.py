
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import pygame
from pygame import Vector2

from core import settings as S
from entities.player import Player


def _state_spawn_mul(state: str) -> float:
    if state == "buildup":
        return 0.32
    if state == "peak":
        return 1.0
    return 0.48


@dataclass
class Particle:
    position: Vector2
    prev_position: Vector2
    velocity: Vector2
    max_life: float
    age: float
    size: float  # 2..6 px (approx visual thickness)
    base_alpha: int
    rgb: tuple[int, int, int]
    layer: int  # 0=bg dust, 1=main, 2=foreground streaks
    wind_push_mul: float
    line_ext: float
    width_mul: float

    @property
    def alive(self) -> bool:
        return self.age < self.max_life

    def update(self, dt: float, bounds: pygame.Rect, wind: Vector2, gust: float) -> None:
        self.age += dt
        self.prev_position.update(self.position)


        wind_strength = (10.0 + gust * 26.0) * self.wind_push_mul
        self.velocity += wind * wind_strength * dt
        self.position += self.velocity * dt

        if self.position.x < bounds.left:
            self.position.x = bounds.right
        elif self.position.x > bounds.right:
            self.position.x = bounds.left
        if self.position.y < bounds.top:
            self.position.y = bounds.bottom
        elif self.position.y > bounds.bottom:
            self.position.y = bounds.top


class ParticleSystem:
    """
    Pool-based storm particle manager.

    update() spawns and advances particles; draw() renders them to a shared overlay.
    Call on_storm_started() whenever a new storm begins to flush any leftover particles
    and reset wind direction so the first frame doesn't show stale trajectories.
    """

    _LAYER_BG = 0
    _LAYER_MAIN = 1
    _LAYER_STREAK = 2

    def __init__(self, screen_rect: pygame.Rect) -> None:
        self._bounds = screen_rect
        self._wind = Vector2(1, 0)

        self._pool: list[Particle] = []
        self._free: list[Particle] = []
        self._active: list[Particle] = []
        self._alive_buf: list[Particle] = []

        for _ in range(S.PARTICLE_MAX):
            p = Particle(
                position=Vector2(0, 0),
                prev_position=Vector2(0, 0),
                velocity=Vector2(0, 0),
                max_life=0.0,
                age=999.0,
                size=2.0,
                base_alpha=0,
                rgb=(255, 165, 80),
                layer=self._LAYER_MAIN,
                wind_push_mul=1.0,
                line_ext=0.4,
                width_mul=0.7,
            )
            self._pool.append(p)
            self._free.append(p)

        self._overlay = pygame.Surface((screen_rect.w, screen_rect.h), pygame.SRCALPHA)
        self._acc_bg = 0.0
        self._acc_main = 0.0
        self._acc_streak = 0.0
        self._acc_trail = 0.0

        self._rgb_candidates = [
            ((255, 180, 90), 1.2),
            ((255, 140, 90), 0.9),
            ((255, 220, 70), 1.1),
            ((220, 40, 40), 0.7),
            ((255, 90, 60), 0.55),
        ]

    def _pick_rgb(self) -> tuple[int, int, int]:
        tot = sum(w for _, w in self._rgb_candidates)
        r = random.random() * tot
        for rgb, w in self._rgb_candidates:
            r -= w
            if r <= 0.0:
                return rgb
        return self._rgb_candidates[0][0]

    def _deactivate_all(self) -> None:
        for p in self._active:
            p.age = p.max_life + 999.0
            self._free.append(p)
        self._active.clear()
        self._acc_bg = 0.0
        self._acc_main = 0.0
        self._acc_streak = 0.0
        self._acc_trail = 0.0

    def on_storm_started(self, wind: Vector2) -> None:
        if wind.length_squared() < 1e-6:
            wind = Vector2(1, 0)
        self._wind = wind.normalize()
        self._deactivate_all()

    def _spawn_particle(
        self,
        layer: int,
        pos: Vector2,
        wind_dir: Vector2,
        norm: float,
        storm_mul: float,
        trail_like: bool = False,
        trail_dir: Optional[Vector2] = None,
    ) -> None:
        if not self._free:
            return

        p = self._free.pop()
        p.age = 0.0
        p.prev_position.update(pos)
        p.position.update(pos)
        p.layer = layer
        p.rgb = self._pick_rgb()

        if layer == self._LAYER_BG:
            p.size = random.uniform(2.0, 4.2)
            p.base_alpha = random.randint(35, 85)
            p.max_life = random.uniform(1.15, 2.4) * (1.1 - 0.2 * storm_mul)
            spd = random.uniform(18.0, 70.0) * (0.5 + 0.35 * norm)
            p.wind_push_mul = 0.55
            p.line_ext = 0.25 if not trail_like else 0.35
            p.width_mul = 0.5
            jitter = Vector2(random.uniform(-18, 18), random.uniform(-18, 18))
            p.velocity = wind_dir * spd + jitter * (0.55 + 0.25 * norm)
        elif layer == self._LAYER_MAIN:
            p.size = random.uniform(2.2, 5.0)
            p.base_alpha = random.randint(90, 205)
            p.max_life = random.uniform(0.35, 1.05) * (1.15 - 0.3 * storm_mul)
            spd = random.uniform(S.PARTICLE_SPEED_MIN * 0.75, S.PARTICLE_SPEED_MAX * 0.78) * (
                0.52 + 0.55 * norm
            )
            p.wind_push_mul = 1.0
            p.line_ext = 0.55 if not trail_like else 0.65
            p.width_mul = 0.78
            jitter = Vector2(random.uniform(-22, 22), random.uniform(-22, 22))
            p.velocity = wind_dir * spd + jitter * (0.6 + 0.35 * norm)
        else:
            p.size = random.uniform(4.2, 6.2)
            p.base_alpha = random.randint(160, 255)
            p.max_life = random.uniform(0.18, 0.55) * (1.1 - 0.2 * storm_mul)
            spd = random.uniform(140.0, 260.0) * (0.65 + 0.5 * norm)
            p.wind_push_mul = 1.25
            p.line_ext = 0.95 if not trail_like else 1.05
            p.width_mul = 1.0
            jitter = Vector2(random.uniform(-40, 40), random.uniform(-40, 40))
            p.velocity = wind_dir * spd + jitter * (0.35 + 0.35 * norm)

        if trail_like and trail_dir is not None and trail_dir.length_squared() > 1e-6:
            back = trail_dir
            p.velocity += back * random.uniform(10.0, 55.0) * (0.35 + 0.45 * norm)

        self._active.append(p)

    def update(
        self,
        dt: float,
        storm_active: bool,
        wind: Vector2,
        storm_intensity: float,
        state: str,
        player: Optional[Player] = None,
        camera_offset: Optional[Vector2] = None,
    ) -> None:
        if not storm_active:
            self._deactivate_all()
            return

        if wind.length_squared() > 1e-6:
            self._wind = wind.normalize()
        wind_dir = self._wind

        norm = min(1.0, storm_intensity / max(S.STORM_INTENSITY_MAX, 0.01))
        storm_mul = _state_spawn_mul(state)

        self._acc_bg += (S.PARTICLE_SPAWN_BASE * 1.85 * norm * storm_mul) * dt
        self._acc_main += (S.PARTICLE_SPAWN_BASE * 1.10 * norm * storm_mul) * dt
        self._acc_streak += (S.PARTICLE_SPAWN_BASE * 0.72 * norm * storm_mul) * dt

        spawn_bg = int(self._acc_bg)
        spawn_main = int(self._acc_main)
        spawn_streak = int(self._acc_streak)
        self._acc_bg -= spawn_bg
        self._acc_main -= spawn_main
        self._acc_streak -= spawn_streak

        for _ in range(spawn_bg):
            if len(self._active) >= S.PARTICLE_MAX:
                break
            self._spawn_particle(
                self._LAYER_BG,
                Vector2(
                    random.uniform(self._bounds.left, self._bounds.right),
                    random.uniform(self._bounds.top, self._bounds.bottom),
                ),
                wind_dir,
                norm,
                storm_mul,
            )
        for _ in range(spawn_main):
            if len(self._active) >= S.PARTICLE_MAX:
                break
            self._spawn_particle(
                self._LAYER_MAIN,
                Vector2(
                    random.uniform(self._bounds.left, self._bounds.right),
                    random.uniform(self._bounds.top, self._bounds.bottom),
                ),
                wind_dir,
                norm,
                storm_mul,
            )
        for _ in range(spawn_streak):
            if len(self._active) >= S.PARTICLE_MAX:
                break
            self._spawn_particle(
                self._LAYER_STREAK,
                Vector2(
                    random.uniform(self._bounds.left, self._bounds.right),
                    random.uniform(self._bounds.top, self._bounds.bottom),
                ),
                wind_dir,
                norm,
                storm_mul,
            )

        if player is not None:
            v = player.velocity
            spd = v.length()
            if spd > 22.0:
                # "Behind" direction (where the rover is coming from).
                trail_dir = Vector2(-v.x, -v.y)
                if trail_dir.length_squared() > 1e-6:
                    trail_dir.normalize_ip()
                rate = (spd / 220.0) * (0.65 + 0.65 * norm) * (0.35 + 0.65 * storm_mul) * 68.0
                self._acc_trail += rate * dt
                spawn_trail = int(self._acc_trail)
                self._acc_trail -= spawn_trail
                for _ in range(spawn_trail):
                    if len(self._active) >= S.PARTICLE_MAX:
                        break
                    # Convert world->screen for draw (world is shifted by camera_offset in Game).
                    if camera_offset is None:
                        pos = Vector2(player.position.x, player.position.y)
                    else:
                        pos = Vector2(
                            player.position.x - camera_offset.x,
                            player.position.y - camera_offset.y,
                        )
                    off = random.uniform(-6.0, 6.0)
                    perp = Vector2(-trail_dir.y, trail_dir.x) * off
                    self._spawn_particle(
                        self._LAYER_BG,
                        pos + perp,
                        wind_dir,
                        norm,
                        storm_mul,
                        trail_like=True,
                        trail_dir=trail_dir,
                    )

        gust = norm
        alive = self._alive_buf
        alive.clear()
        for p in self._active:
            p.update(dt, self._bounds, wind_dir, gust)
            if p.alive:
                alive.append(p)
            else:
                self._free.append(p)
        self._active, self._alive_buf = alive, self._active

    def draw(self, surface: pygame.Surface, storm_active: bool) -> None:
        if not storm_active:
            return
        self._overlay.fill((0, 0, 0, 0))

        for p in self._active:
            t = p.age / max(p.max_life, 1e-6)
            alpha = int(p.base_alpha * (1.0 - t) ** 1.15)
            if alpha <= 2:
                continue

            start = (int(p.prev_position.x), int(p.prev_position.y))
            end = Vector2(p.position.x, p.position.y)
            dx = end.x - p.prev_position.x
            dy = end.y - p.prev_position.y
            end.x = end.x + dx * p.line_ext
            end.y = end.y + dy * p.line_ext
            end_xy = (int(end.x), int(end.y))

            width = max(1, int(p.size * p.width_mul))
            col = (p.rgb[0], p.rgb[1], p.rgb[2], alpha)
            pygame.draw.line(self._overlay, col, start, end_xy, width)

        surface.blit(self._overlay, (0, 0))
