

import random

import math
import pygame
from pygame import Vector2

from core import settings as S
from entities.player import Player
from utils.helpers import clamp


class StormSystem:

    def __init__(self) -> None:
        self.active = False
        self.state = "idle"  # idle | buildup | peak | fade
        self.intensity = 0.0  # 0..S.STORM_INTENSITY_MAX
        self.wind = Vector2(0, 0)
        self.biome_intensity_mul = 1.0
        self.start_delay = 5.0

        self._t = 0.0
        self._buildup_dur = 0.0
        self._peak_dur = 0.0
        self._fade_dur = 0.0
        self._target = 0.0  # 0..1
        self._gust = 0.0

        self.safe_zones: list[dict] = []
        self.micro_storms: list[dict] = []
        self.energy_bursts: list[dict] = []

        self.flash_strength = 0.0
        self._control_loss_t = 0.0

        self._micro_touch_cd = 0.0
        self._safe_zone_spawn_cd = 0.0
        self._micro_spawn_cd = 0.0
        self._energy_burst_cd = 0.0

        self._gust_sound_req = False
        self._energy_burst_sound_req = False

        self._wind_mul_current = 1.0
        self._damage_mul_current = 1.0

        self._active = False

    def reset(self) -> None:
        self.active = False
        self.state = "idle"
        self.intensity = 0.0
        self.wind.update(0, 0)
        self.biome_intensity_mul = 1.0
        self.start_delay = 5.0
        self._t = 0.0
        self._buildup_dur = 0.0
        self._peak_dur = 0.0
        self._fade_dur = 0.0
        self._target = 0.0
        self._gust = 0.0

        self.safe_zones.clear()
        self.micro_storms.clear()
        self.energy_bursts.clear()

        self.flash_strength = 0.0
        self._control_loss_t = 0.0

        self._micro_touch_cd = 0.0
        self._safe_zone_spawn_cd = 0.0
        self._micro_spawn_cd = 0.0
        self._energy_burst_cd = 0.0

        self._gust_sound_req = False
        self._energy_burst_sound_req = False

        self._active = False

        self._wind_mul_current = 1.0
        self._damage_mul_current = 1.0

    def _player_safe_zone(self, player: Player) -> dict | None:
        px, py = player.position.x, player.position.y
        for z in self.safe_zones:
            r = z["radius"]
            if (px - z["pos"].x) ** 2 + (py - z["pos"].y) ** 2 <= r * r:
                return z
        return None

    def player_in_safe_zone(self, player: Player) -> bool:
        return self._player_safe_zone(player) is not None

    def effective_intensity_n(self) -> float:
        """Normalized intensity (0..1) with phase floors so buildup/fade phases still deal meaningful damage."""
        raw = min(1.0, self.intensity / max(S.STORM_INTENSITY_MAX, 0.01))
        if self.state == "buildup":
            return max(raw, S.STORM_BUILDUP_INTENSITY_FLOOR)
        if self.state == "fade":
            return max(raw, S.STORM_FADE_INTENSITY_FLOOR)
        return raw  # peak: already at 1.0, no floor needed

    def consume_gust_sound(self) -> bool:
        ok = self._gust_sound_req
        self._gust_sound_req = False
        return ok

    def consume_energy_burst_sound(self) -> bool:
        ok = self._energy_burst_sound_req
        self._energy_burst_sound_req = False
        return ok

    def update(self, dt: float, player: Player) -> None:
        scale = S.FPS * dt

        if self.state == "idle":
            if self.start_delay > 0.0:
                self.start_delay = max(0.0, self.start_delay - dt)
                self.active = False
                self.intensity = 0.0
                self.flash_strength = 0.0
                return
            self.active = False
            self.intensity = max(0.0, self.intensity - 4.0 * dt)
            if random.random() < S.STORM_START_CHANCE_PER_SEC * dt:
                self._start_storm()
            return

        self.active = True
        self._t += dt
        self._gust_sound_req = False
        self._energy_burst_sound_req = False

        if self.state == "buildup":
            self._target = min(1.0, self._t / max(self._buildup_dur, 1e-6))
            if self._t >= self._buildup_dur:
                self.state = "peak"
                self._t = 0.0
        elif self.state == "peak":
            self._target = 1.0
            if self._t >= self._peak_dur:
                self.state = "fade"
                self._t = 0.0
        elif self.state == "fade":
            self._target = 1.0 - min(1.0, self._t / max(self._fade_dur, 1e-6))
            if self._t >= self._fade_dur:
                self._end_storm()
                return

        self._gust = clamp(self._gust + random.uniform(-0.9, 0.9) * dt, -1.0, 1.0)
        lerp_k = 1.0 - (0.001**dt)
        intensity_n = (self.intensity / max(S.STORM_INTENSITY_MAX, 0.01))
        intensity_n += (self._target - intensity_n) * lerp_k
        intensity_n = clamp(intensity_n, 0.0, 1.0)
        self.intensity = (
            intensity_n
            * S.STORM_INTENSITY_MAX
            * max(0.0, float(self.biome_intensity_mul))
        )

        self.flash_strength = max(0.0, self.flash_strength - S.STORM_FLASH_DECAY * dt)

        self._micro_touch_cd = max(0.0, self._micro_touch_cd - dt)
        self._safe_zone_spawn_cd = max(0.0, self._safe_zone_spawn_cd - dt)
        self._micro_spawn_cd = max(0.0, self._micro_spawn_cd - dt)
        self._energy_burst_cd = max(0.0, self._energy_burst_cd - dt)

        # - safe zones appear around peak to create tactical "calm".
        # - micro storms appear during peak, move around, and punish contact.
        # - energy bursts are rare but reward risky movement (bigger reward outside safe zones).
        if intensity_n > 0.12 and len(self.safe_zones) < S.STORM_SAFE_ZONE_COUNT_MAX:
            if self._safe_zone_spawn_cd <= 0.0 and intensity_n > 0.35:
                self._safe_zone_spawn_cd = random.uniform(2.0, 4.2) / max(0.25, intensity_n)
                self._spawn_safe_zone(player)

        if intensity_n > 0.16 and len(self.micro_storms) < S.STORM_MICRO_STORM_COUNT_MAX:
            if self._micro_spawn_cd <= 0.0 and self.state in ("buildup", "peak"):
                self._micro_spawn_cd = S.STORM_MICRO_STORM_SPAWN_COOLDOWN * random.uniform(0.85, 1.25)
                self._spawn_micro_storm(player)

        if (
            intensity_n > 0.25
            and self.state in ("peak", "buildup")
            and len(self.energy_bursts) < S.STORM_ENERGY_BURST_COUNT_MAX
        ):
            if self._energy_burst_cd <= 0.0 and random.random() < S.STORM_ENERGY_BURST_PROB_PER_SEC * dt * (0.6 + 0.9 * intensity_n):
                self._energy_burst_cd = random.uniform(2.0, 5.5) / max(0.2, intensity_n)
                self._spawn_energy_burst(player)

        zone = self._player_safe_zone(player)
        wind_mul = float(zone.get("wind_mul", 1.0)) if zone else 1.0
        damage_mul = float(zone.get("damage_mul", 1.0)) if zone else 1.0
        self._wind_mul_current = wind_mul
        self._damage_mul_current = damage_mul

        self.safe_zones = [z for z in self.safe_zones if self._update_safe_zone(z, dt, wind_mul, intensity_n)]

        self._update_micro_storms(player, dt, intensity_n, wind_mul, damage_mul)

        self.energy_bursts = [
            b for b in self.energy_bursts if self._update_energy_burst(b, dt, player, intensity_n, zone is not None)
        ]

        # storm_resistance (0..1) scales down wind force and drag so player stays controllable.
        resist = 1.0 - player.storm_resistance * 0.5
        wind_push = (
            S.STORM_WIND_ON_VELOCITY
            * scale
            * (0.35 + 0.65 * intensity_n)
            * wind_mul
            * resist
        )
        player.velocity += self.wind * wind_push

        # Base continuous energy drain is now applied in game.py, gated on
        # the main base safe zone only.  Keeping player.energy mutation here
        # limited to impulse events (micro-storms, energy bursts).
        player.energy = max(0.0, player.energy)

        extra_drag = S.STORM_TURBULENCE_DRAG * intensity_n * (1.0 + 0.35 * abs(self._gust)) * resist
        if self._control_loss_t > 0.0:
            extra_drag += S.STORM_CONTROL_LOSS_EXTRA_DRAG * resist
            self._control_loss_t = max(0.0, self._control_loss_t - dt)
        player.apply_friction(extra_drag, dt)

        if intensity_n > 0.02:
            perp = Vector2(-self.wind.y, self.wind.x)
            if perp.length_squared() < 1e-6:
                perp = Vector2(1, 0)
            perp.normalize_ip()
            # Turbulence drives "unwanted drift" perpendicular to wind.
            jitter = perp * random.uniform(-1.0, 1.0) * S.STORM_TURBULENCE_JITTER * intensity_n * dt * resist
            player.velocity += jitter * (0.1 + 0.6 * damage_mul)

        if intensity_n > S.STORM_GUST_SOUND_INTENSITY_MIN:
            if random.random() < S.STORM_GUST_SOUND_PROB_PER_SEC * dt * (0.3 + 0.7 * intensity_n):
                self._gust_sound_req = True

    def _spawn_safe_zone(self, player: Player) -> None:
        # Spawn near player to feel interactive.
        r = random.uniform(S.STORM_SAFE_ZONE_RADIUS_MIN, S.STORM_SAFE_ZONE_RADIUS_MAX)
        life = random.uniform(S.STORM_SAFE_ZONE_LIFETIME_MIN, S.STORM_SAFE_ZONE_LIFETIME_MAX)

        # Bias zone placement away from rover direction to reduce "free safe camping".
        off = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        if off.length_squared() > 1e-6:
            off.normalize_ip()
        dist = random.uniform(160.0, 340.0) * (0.8 + 0.4 * random.random())
        pos = player.position + off * dist
        pos.x = clamp(pos.x, 80.0, S.WORLD_WIDTH - 80.0)
        pos.y = clamp(pos.y, 80.0, S.WORLD_HEIGHT - 80.0)

        self.safe_zones.append(
            {
                "pos": pos,
                "radius": r,
                "life": life,
                "wind_mul": S.STORM_SAFE_ZONE_WIND_MUL,
                "damage_mul": S.STORM_SAFE_ZONE_DAMAGE_MUL,
            }
        )

    def _update_safe_zone(self, zone: dict, dt: float, wind_mul: float, intensity_n: float) -> bool:
        zone["life"] -= dt
        drift = (0.25 + 0.75 * intensity_n) * wind_mul
        zone["pos"] += self.wind * (42.0 * drift) * dt
        zone["pos"].x = clamp(zone["pos"].x, 70.0, S.WORLD_WIDTH - 70.0)
        zone["pos"].y = clamp(zone["pos"].y, 70.0, S.WORLD_HEIGHT - 70.0)
        return zone["life"] > 0.0

    def _spawn_micro_storm(self, player: Player) -> None:
        r = random.uniform(S.STORM_MICRO_STORM_RADIUS_MIN, S.STORM_MICRO_STORM_RADIUS_MAX)
        life = random.uniform(S.STORM_MICRO_STORM_LIFETIME_MIN, S.STORM_MICRO_STORM_LIFETIME_MAX)
        spin = random.uniform(-1.0, 1.0)

        # Try to spawn in front of the player so it's a "decision".
        forward = Vector2(player.velocity)
        if forward.length_squared() < 1e-6:
            forward = -self.wind
        if forward.length_squared() > 1e-6:
            forward.normalize_ip()
        side = Vector2(-forward.y, forward.x)
        pos = player.position + forward * random.uniform(200.0, 420.0) + side * random.uniform(-160.0, 160.0)
        pos.x = clamp(pos.x, 90.0, S.WORLD_WIDTH - 90.0)
        pos.y = clamp(pos.y, 90.0, S.WORLD_HEIGHT - 90.0)

        self.micro_storms.append(
            {
                "pos": pos,
                "radius": r,
                "life": life,
                "spin": spin,
                "phase": random.uniform(0.0, 10.0),
            }
        )

    def _update_micro_storms(
        self,
        player: Player,
        dt: float,
        intensity_n: float,
        wind_mul: float,
        damage_mul: float,
    ) -> None:
        alive: list[dict] = []
        for v in self.micro_storms:
            v["life"] -= dt
            if v["life"] <= 0.0:
                continue

            v["phase"] += dt * (1.5 + 2.2 * intensity_n)
            wobble = Vector2(-self.wind.y, self.wind.x)
            wobble_len2 = wobble.length_squared()
            if wobble_len2 > 1e-6:
                wobble.normalize_ip()
            orb = math.sin(v["phase"])
            v["pos"] += (
                self.wind * (110.0 + 180.0 * intensity_n)
                + wobble * (80.0 * orb)
            ) * dt
            v["pos"].x = clamp(v["pos"].x, 70.0, S.WORLD_WIDTH - 70.0)
            v["pos"].y = clamp(v["pos"].y, 70.0, S.WORLD_HEIGHT - 70.0)

            d2 = (player.position.x - v["pos"].x) ** 2 + (player.position.y - v["pos"].y) ** 2
            if d2 <= v["radius"] * v["radius"] and self._micro_touch_cd <= 0.0:
                self._micro_touch_cd = 0.85 + 0.55 * (1.0 - intensity_n)

                radial = Vector2(player.position - v["pos"])
                if radial.length_squared() > 1e-6:
                    radial.normalize_ip()
                tang = Vector2(-radial.y, radial.x) * float(v["spin"])
                push = tang * S.STORM_MICRO_STORM_PUSH_BASE * intensity_n

                if wind_mul < 0.99 or damage_mul < 0.99:
                    push *= 0.45

                player.velocity += push
                self._control_loss_t = max(self._control_loss_t, S.STORM_MICRO_STORM_CONTROL_LOSS_TIME * (0.7 + 0.6 * intensity_n))
                player.micro_shake_impulse = max(player.micro_shake_impulse, 3.0 + 7.0 * intensity_n)
                player.energy -= S.STORM_MICRO_STORM_ENERGY_PENALTY * intensity_n * damage_mul

                self.flash_strength = max(self.flash_strength, 0.65 + 0.35 * intensity_n)
                self._gust_sound_req = True

            alive.append(v)
        self.micro_storms = alive

    def _spawn_energy_burst(self, player: Player) -> None:
        # Rare, high-visibility area to encourage risk.
        r = S.STORM_ENERGY_BURST_RADIUS
        life = S.STORM_ENERGY_BURST_LIFETIME

        off = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        if off.length_squared() > 1e-6:
            off.normalize_ip()
        dist = random.uniform(180.0, 420.0)
        pos = player.position + off * dist
        pos.x = clamp(pos.x, 90.0, S.WORLD_WIDTH - 90.0)
        pos.y = clamp(pos.y, 90.0, S.WORLD_HEIGHT - 90.0)

        self.energy_bursts.append(
            {
                "pos": pos,
                "radius": r,
                "life": life,
                "fx_t": None,  # None until collected
            }
        )

    def _update_energy_burst(
        self,
        burst: dict,
        dt: float,
        player: Player,
        intensity_n: float,
        in_safe_zone: bool,
    ) -> bool:
        scale = S.FPS * dt
        burst["life"] -= dt

        if burst["fx_t"] is not None:
            burst["fx_t"] += dt
            return burst["fx_t"] < 0.95

        d2 = (player.position.x - burst["pos"].x) ** 2 + (player.position.y - burst["pos"].y) ** 2
        if d2 <= burst["radius"] * burst["radius"]:
            # Risk is higher outside safe zones (bigger reward + bigger penalty).
            if in_safe_zone:
                bonus_mul = 0.68
                risk_mul = 0.45
            else:
                bonus_mul = 1.20
                risk_mul = 1.0

            bonus = S.STORM_ENERGY_BURST_BONUS_BASE * intensity_n * bonus_mul
            penalty = S.STORM_ENERGY_BURST_RISK_PENALTY_BASE * intensity_n * risk_mul

            player.energy += bonus
            player.energy -= penalty
            player.energy = max(0.0, player.energy)

            # Slight signal hit to keep "risk" meaningful.
            player.signal_offset -= (
                0.10 + 0.24 * (1.0 - bonus_mul)
            ) * intensity_n * scale

            player.micro_shake_impulse = max(player.micro_shake_impulse, 2.2 + 5.0 * intensity_n)
            self.flash_strength = max(self.flash_strength, 0.72 + 0.25 * intensity_n)

            self._energy_burst_sound_req = True
            burst["fx_t"] = 0.0
            return True

        return burst["life"] > 0.0

    def _start_storm(self) -> None:
        self.state = "buildup"
        self._t = 0.0
        self._buildup_dur = random.uniform(2.0, 4.0)
        self._peak_dur = random.uniform(5.0, 10.0)
        self._fade_dur = random.uniform(2.0, 4.0)
        self._target = 0.0
        self._gust = 0.0
        angle_deg = random.uniform(0.0, 360.0)
        self.wind = Vector2(1, 0).rotate(angle_deg)
        if self.wind.length_squared() > 1e-6:
            self.wind.normalize_ip()

        self.safe_zones.clear()
        self.micro_storms.clear()
        self.energy_bursts.clear()
        self._control_loss_t = 0.0
        self.flash_strength = 0.0

        self._safe_zone_spawn_cd = random.uniform(0.8, 2.4)
        self._micro_spawn_cd = random.uniform(0.7, 1.7)
        self._energy_burst_cd = random.uniform(1.2, 4.0)

    def _end_storm(self) -> None:
        self.state = "idle"
        self.active = False
        self.intensity = 0.0
        self.wind.update(0, 0)
        self._t = 0.0
        self._target = 0.0
        self._gust = 0.0

        self.safe_zones.clear()
        self.micro_storms.clear()
        self.energy_bursts.clear()

        self._control_loss_t = 0.0
        self.flash_strength = 0.0

    def draw_overlays(self, surface: pygame.Surface, draw_off: Vector2) -> None:
        if not self.active:
            return
        n = min(1.0, self.intensity / max(S.STORM_INTENSITY_MAX, 0.01))

        for z in self.safe_zones:
            cx = int(z["pos"].x + draw_off.x)
            cy = int(z["pos"].y + draw_off.y)
            r = int(z["radius"])
            pygame.draw.circle(surface, (80, 220, 160), (cx, cy), r, 2)
            inner = max(5, int(r * 0.35))
            pygame.draw.circle(surface, (140, 255, 210), (cx, cy), inner, 1)

        for v in self.micro_storms:
            cx = int(v["pos"].x + draw_off.x)
            cy = int(v["pos"].y + draw_off.y)
            r = int(v["radius"])
            pygame.draw.circle(surface, (255, 70, 80), (cx, cy), r, 2)

            ang = v["phase"] + n * 0.6
            dx = math.cos(ang) * r
            dy = math.sin(ang) * r
            pygame.draw.line(surface, (255, 180, 80), (cx, cy), (int(cx + dx), int(cy + dy)), 2)

        for b in self.energy_bursts:
            cx = int(b["pos"].x + draw_off.x)
            cy = int(b["pos"].y + draw_off.y)
            r = int(b["radius"])

            if b["fx_t"] is not None:
                u = min(1.0, float(b["fx_t"]) / 0.95)
                rr = int(r * (1.0 + 3.2 * u))
                pygame.draw.circle(surface, (255, 240, 120), (cx, cy), rr, 2)
                pygame.draw.circle(surface, (255, 160, 80), (cx, cy), max(4, int(r * 0.18)), 0)
            else:
                pygame.draw.circle(surface, (255, 200, 70), (cx, cy), r, 1)
