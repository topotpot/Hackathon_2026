
import math

import pygame
from pygame import Rect, Vector2

from core import settings as S
from utils.helpers import clamp


class Player:


    def __init__(self, x: float, y: float) -> None:
        self.position = Vector2(x, y)
        self.velocity = Vector2(0, 0)
        self.acceleration = S.PLAYER_ACCELERATION
        self.smoothed_input = Vector2(0, 0)
        self.tilt = 0.0
        self.micro_shake_impulse = 0.0
        self.energy = S.PLAYER_START_ENERGY
        self.signal = S.SIGNAL_MAX
        self.signal_offset = 0.0
        self._lean = 0.0
        self._breath = 0.0
        self.biome_speed_mul = 1.0
        self.start_protection = 0.0
        self.storm_resistance = S.PLAYER_STORM_RESISTANCE
        self.boost_cooldown = 0.0
        self.boost_active = 0.0
        self._wheel_angle = 0.0
        self._ant_sway = 0.0

    @property
    def rect(self) -> Rect:
        w, h = S.PLAYER_SIZE
        return Rect(int(self.position.x - w / 2), int(self.position.y - h / 2), w, h)

    def apply_acceleration(self, axis: Vector2, dt: float) -> None:
        if axis.length_squared() > 0:
            self.velocity += axis * self.acceleration * dt

    def apply_friction(self, strength: float, dt: float) -> None:
        if self.velocity.length_squared() < 1e-6:
            self.velocity.update(0, 0)
            return
        factor = max(0.0, 1.0 - strength * dt)
        self.velocity *= factor

    def cap_speed(self) -> None:
        max_s = S.PLAYER_MAX_SPEED * max(0.3, float(self.biome_speed_mul))
        if self.velocity.length() > max_s:
            self.velocity.scale_to_length(max_s)

    def integrate(self, dt: float) -> None:
        self.position += self.velocity * dt

    def drain_energy(self, dt: float) -> None:
        self.energy -= S.ENERGY_DRAIN_PER_SECOND * dt
        self.energy = max(0.0, self.energy)

    def add_energy(self, amount: float) -> None:
        self.energy = min(100.0, self.energy + amount)

    def modify_signal_offset(self, delta: float) -> None:
        self.signal_offset += delta

    def update_tilt(self, dt: float) -> None:
        """Update cosmetic lean/tilt driven by lateral velocity."""
        target = clamp(
            -self.velocity.x * 0.065,
            -S.PLAYER_TILT_MAX_DEG,
            S.PLAYER_TILT_MAX_DEG,
        )
        self.tilt += (target - self.tilt) * min(1.0, 12.0 * dt)
        lean_tgt = clamp(-self.velocity.x * 0.04, -6.0, 6.0)
        self._lean += (lean_tgt - self._lean) * min(1.0, 8.0 * dt)
        self._wheel_angle += self.velocity.length() * 0.06 * dt
        sway_tgt = clamp(-self.velocity.x * 0.022, -0.8, 0.8)
        self._ant_sway += (sway_tgt - self._ant_sway) * min(1.0, 6.0 * dt)

    def decay_micro_shake(self, dt: float) -> None:
        self.micro_shake_impulse = max(0.0, self.micro_shake_impulse - 14.0 * dt)

    def draw(self, surface: pygame.Surface, offset: Vector2, time_s: float) -> None:
        cx = int(self.position.x + offset.x)
        cy = int(self.position.y + offset.y)
        self._breath = 1.0 + 0.04 * math.sin(time_s * 2.2)
        sc = self._breath
        w, h = S.PLAYER_SIZE
        w = int(w * sc)
        h = int(h * sc)

        if self.boost_active > 0:
            ba = self.boost_active
            bg_r = int(24 + 12 * ba)
            bg_surf = pygame.Surface((bg_r * 2, bg_r), pygame.SRCALPHA)
            pygame.draw.ellipse(bg_surf, (255, 130, 40, int(80 * ba)), bg_surf.get_rect())
            surface.blit(bg_surf, (cx - bg_r, cy - bg_r // 2 + 6), special_flags=pygame.BLEND_ADD)

        glow_r = max(18, int(14 + self.velocity.length() * 0.055))
        glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 160, 90, 26), glow.get_rect().inflate(-4, -8))
        surface.blit(glow, (cx - glow_r, cy - glow_r + 4), special_flags=pygame.BLEND_ADD)

        # Off-screen surface (wider to accommodate wheels below body)
        surf = pygame.Surface((max(48, w + 22), max(40, h + 22)), pygame.SRCALPHA)
        sw, sh = surf.get_size()
        ox, oy = sw // 2, sh // 2

        body = pygame.Rect(ox - w // 2, oy - h // 2 - 2, w, h)

        panel_x = body.left - 5
        panel_y = body.top + 3
        panel_h = h - 6
        pygame.draw.rect(surf, (24, 40, 28), (panel_x, panel_y, 5, panel_h))
        for lp in range(panel_y + 2, panel_y + panel_h - 1, 4):
            pygame.draw.line(surf, (18, 30, 20), (panel_x + 1, lp), (panel_x + 4, lp), 1)

        pygame.draw.rect(surf, (38, 28, 22), body, border_radius=5)
        pygame.draw.rect(surf, (56, 42, 34), body.inflate(-4, -4), border_radius=4)
        pygame.draw.rect(surf, (68, 52, 42), body.inflate(-8, -6), border_radius=3)
        pygame.draw.rect(surf, (88, 68, 52), body, 2, border_radius=5)

        mx = body.right - 2
        my = body.centery
        pygame.draw.circle(surf, (255, 220, 110), (mx, my), 2)
        fl = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(fl, (255, 200, 80, 50), (4, 4), 4)
        surf.blit(fl, (mx - 4, my - 4), special_flags=pygame.BLEND_ADD)

        wheel_r = 5
        wl = body.left + 4
        for i in range(3):
            wx_i = wl + i * (body.w // 3)
            wy_i = body.bottom + 2
            pygame.draw.circle(surf, (20, 18, 22), (wx_i, wy_i), wheel_r)
            pygame.draw.circle(surf, (55, 52, 58), (wx_i, wy_i), wheel_r, 1)
            pygame.draw.circle(surf, (75, 72, 80), (wx_i, wy_i), 2)
            ang = self._wheel_angle + i * 1.05
            spx = wx_i + int(math.cos(ang) * (wheel_r - 1))
            spy = wy_i + int(math.sin(ang) * (wheel_r - 1))
            pygame.draw.line(surf, (95, 90, 100), (wx_i, wy_i), (spx, spy), 1)

        ax0, ay0 = body.centerx, body.top + 1
        sway_px = int(self._ant_sway * 7)
        ax1 = body.centerx + 3 + sway_px
        ay1 = body.top - 10
        pygame.draw.line(surf, (90, 88, 95), (ax0, ay0), (ax1, ay1), 2)
        pygame.draw.circle(surf, (255, 230, 200), (ax1, ay1), 3)
        pygame.draw.circle(surf, (120, 200, 255), (ax1 + 1, ay1), 2)
        sensor = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.circle(sensor, (160, 220, 255, 200), (5, 5), 3)
        surf.blit(sensor, (ax1 - 5, ay1 - 5), special_flags=pygame.BLEND_ADD)

        rot = pygame.transform.rotate(surf, -self.tilt - self._lean)
        rr = rot.get_rect(center=(cx, cy))
        surface.blit(rot, rr.topleft)
