import math
import random

import pygame
from pygame import Vector2

from core import settings as S
from utils.helpers import clamp


class Resource:


    def __init__(
        self,
        position: Vector2,
        rtype: str = "relay",
        condition: str = "common",
    ) -> None:
        self.position  = Vector2(position)
        self.rtype     = rtype      # "relay" | "tech"
        self.condition = condition  # "common" | "damaged" | "unstable" | "corrupted"
        self.state     = "idle"     # idle → prompt → scavenging → done

        dur = S.RESOURCE_SCAVENGE_DURATIONS
        self._scavenge_t   = 0.0
        self._scavenge_dur = dur.get(condition, 2.0)

        # Stable random seeds for animation (avoid per-frame RNG outside sparks)
        self._angle   = random.uniform(0.0, math.tau)
        self._phase   = random.uniform(0.0, math.tau)
        self._blink_t = random.uniform(0.0, 2.0)
        self._pulse_t = random.uniform(0.0, 3.0)
        self._spark_t = 0.0
        # Lean offset for damaged relay mast
        self._lean = random.uniform(-0.20, 0.20) if condition == "damaged" else 0.0

    @property
    def scavenge_progress(self) -> float:
        return clamp(self._scavenge_t / max(self._scavenge_dur, 0.001), 0.0, 1.0)

    @property
    def show_prompt(self) -> bool:
        return self.state in ("prompt", "scavenging")

    def enter_prompt(self) -> None:
        if self.state == "idle":
            self.state = "prompt"

    def exit_prompt(self) -> None:
        if self.state == "prompt":
            self.state = "idle"

    def start_scavenge(self) -> None:
        if self.state == "prompt":
            self.state = "scavenging"
            self._scavenge_t = 0.0

    def cancel_scavenge(self) -> None:
        if self.state == "scavenging":
            self.state = "idle"
            self._scavenge_t = 0.0

    def update(self, dt: float) -> bool:
        """Advance animation and scavenging. Returns True when extraction completes."""
        rot = 1.5 if self.rtype == "tech" else 0.7
        if self.condition == "unstable":
            rot *= 1.9
        self._angle   += dt * rot
        self._phase   += dt * 3.6
        self._blink_t += dt
        self._pulse_t += dt
        self._spark_t += dt

        if self.state == "scavenging":
            self._scavenge_t += dt
            if self._scavenge_t >= self._scavenge_dur:
                self.state = "done"
                return True
        return False

    def draw(self, surface: pygame.Surface, offset: Vector2, time_s: float) -> None:
        cx = int(self.position.x + offset.x)
        cy = int(self.position.y + offset.y)
        sw, sh = surface.get_size()
        if not (-72 < cx < sw + 72 and -72 < cy < sh + 72):
            return  # off-screen culling

        if self.rtype == "relay":
            self._draw_relay(surface, cx, cy)
        else:
            self._draw_tech(surface, cx, cy)

        if self.state == "scavenging":
            self._draw_progress(surface, cx, cy)

    def _draw_relay(self, surf: pygame.Surface, cx: int, cy: int) -> None:
        corrupt = self.condition == "corrupted"
        blink   = 0.5 + 0.5 * math.sin(self._blink_t * 5.1)

        glow_r = 26
        ga = int(28 + 22 * blink)
        gcol = (180, 35, 35) if corrupt else (35, 110, 210)
        glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*gcol, ga), (glow_r, glow_r), glow_r)
        surf.blit(glow, (cx - glow_r, cy - glow_r), special_flags=pygame.BLEND_ADD)

        pygame.draw.ellipse(surf, (28, 22, 26), pygame.Rect(cx - 9, cy - 3, 18, 7))

        lean_dx = int(math.sin(self._lean) * 20)
        top_x, top_y = cx + lean_dx, cy - 22
        mcol = (72, 72, 82) if self.condition != "damaged" else (58, 52, 44)
        pygame.draw.line(surf, mcol, (cx, cy - 1), (top_x, top_y), 2)

        arm = 9
        aang = self._lean - 0.18
        ax1 = top_x + int(math.cos(aang) * arm)
        ay1 = top_y + int(math.sin(aang) * arm)
        ax2 = top_x - int(math.cos(aang) * arm // 2)
        ay2 = top_y - int(math.sin(aang) * arm // 2)
        pygame.draw.line(surf, mcol, (ax1, ay1), (ax2, ay2), 1)

        if blink > 0.4:
            lcol = (220, 55, 55) if corrupt else (55, 185, 255)
            pygame.draw.circle(surf, lcol, (top_x, top_y), 3)
            if blink > 0.70:
                lg = pygame.Surface((12, 12), pygame.SRCALPHA)
                pygame.draw.circle(lg, (*lcol, 70), (6, 6), 6)
                surf.blit(lg, (top_x - 6, top_y - 6), special_flags=pygame.BLEND_ADD)

        period = 1.1 if self.condition == "unstable" else 2.4
        pf = (self._pulse_t % period) / period
        if pf < 0.55:
            rr = int(5 + pf * 58)
            ra = int(75 * (1.0 - pf / 0.55))
            rcol = (195, 40, 40) if corrupt else (45, 145, 255)
            sz = rr * 2 + 4
            rs = pygame.Surface((sz, sz), pygame.SRCALPHA)
            pygame.draw.circle(rs, (*rcol, ra), (sz // 2, sz // 2), rr, 1)
            surf.blit(rs, (top_x - sz // 2, top_y - sz // 2))

        if self.condition in ("damaged", "corrupted"):
            sp = (self._spark_t % 0.32) / 0.32
            if sp < 0.25:
                sx = top_x + random.randint(-6, 6)
                sy = top_y + random.randint(-4, 4)
                pygame.draw.circle(surf, (255, 195, 75), (sx, sy), 1)

    def _draw_tech(self, surf: pygame.Surface, cx: int, cy: int) -> None:
        corrupt   = self.condition == "corrupted"
        unstable  = self.condition == "unstable"
        pulse_spd = 3.5 if unstable else 1.9
        pulse     = 0.62 + 0.38 * abs(math.sin(self._pulse_t * pulse_spd))

        glow_r = 22
        gcol   = (195, 55, 175) if corrupt else (215, 95, 18)
        ga     = int(38 * pulse)
        glow   = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*gcol, ga), (glow_r, glow_r), glow_r)
        surf.blit(glow, (cx - glow_r, cy - glow_r), special_flags=pygame.BLEND_ADD)

        pygame.draw.ellipse(surf, (22, 18, 16), pygame.Rect(cx - 8, cy + 6, 16, 5))

        bdcol  = (48, 43, 38)
        brcol  = (92, 78, 62) if not corrupt else (95, 38, 78)
        pygame.draw.rect(surf, bdcol, pygame.Rect(cx - 9, cy - 9, 18, 18), border_radius=2)
        pygame.draw.rect(surf, brcol, pygame.Rect(cx - 9, cy - 9, 18, 18), 1, border_radius=2)

        cr = int(min(255, 210 * pulse)) if not corrupt else 175
        cg = int(min(255, 85 * pulse))  if not corrupt else 38
        cb = 12 if not corrupt else int(145 * pulse)
        pygame.draw.rect(surf, (cr, cg, cb), pygame.Rect(cx - 4, cy - 4, 8, 8))

        rr   = 14
        nseg = 8
        for i in range(nseg):
            a0 = self._angle + i * math.tau / nseg
            a1 = a0 + math.tau / nseg * 0.60
            prev = None
            for s in range(5):
                af  = a0 + (a1 - a0) * s / 4
                px  = cx + int(math.cos(af) * rr)
                py  = cy + int(math.sin(af) * rr)
                if prev is not None:
                    sc = (132, 104, 66) if i % 2 == 0 else (68, 52, 35)
                    if corrupt:
                        sc = (125, 48, 108) if i % 2 == 0 else (65, 24, 55)
                    pygame.draw.line(surf, sc, prev, (px, py), 1)
                prev = (px, py)

        if (unstable or corrupt) and random.random() < 0.07:
            fy   = cy + random.randint(-7, 7)
            fcol = (172, 68, 155) if corrupt else (195, 118, 38)
            pygame.draw.line(surf, fcol, (cx - 8, fy), (cx + 8, fy), 1)

    def _draw_progress(self, surf: pygame.Surface, cx: int, cy: int) -> None:
        prog  = self.scavenge_progress
        arc_r = 24
        n     = 36
        n_lit = max(1, int(prog * n))
        fill  = (75, 218, 138) if self.rtype == "relay" else (255, 158, 55)

        for i in range(n):
            ang = -math.pi / 2 + i * math.tau / n
            px  = cx + int(math.cos(ang) * arc_r)
            py  = cy + int(math.sin(ang) * arc_r)
            col = fill if i < n_lit else (32, 32, 42)
            pygame.draw.circle(surf, col, (px, py), 2)
