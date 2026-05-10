
from __future__ import annotations

import math
import random

import pygame

from systems.localization import t

_MSG_KEYS = [
    "ending.text_1",
    "ending.text_2",
    "ending.text_3",
    "ending.text_4",
    "ending.text_5",
    "ending.text_6",
    "ending.text_7",
    "ending.text_8",
]

_INITIAL_BLACK  = 1.8   # seconds full black before first text
_FADE_IN_DUR    = 1.2   # seconds to fade text in
_HOLD_DUR       = 3.4   # seconds text stays fully visible
_FADE_OUT_DUR   = 1.0   # seconds to fade text out
_PAUSE_DUR      = 0.55  # dark gap between messages
_FINAL_HOLD_DUR = 2.2   # hold after last message fades before returning to menu


class EndingSystem:
    """Drives the 8-message narrative credits sequence. advance() accelerates timing but never skips messages."""

    def __init__(self) -> None:
        self._font_msg:  pygame.font.Font | None = None
        self._font_hint: pygame.font.Font | None = None
        self._dust: list[dict] = []
        self.reset()

    def _ensure_fonts(self) -> None:
        if self._font_msg is None:
            self._font_msg  = pygame.font.SysFont("segoeui", 24)
            self._font_hint = pygame.font.SysFont("segoeui", 14)

    def reset(self) -> None:
        self._phase    = "initial_black"
        self._phase_t  = 0.0
        self._msg_idx  = 0
        self._alpha    = 0.0   # current text alpha 0..1
        self._done     = False
        self._dust     = []
        for _ in range(42):
            self._dust.append(self._new_dust())

    def advance(self) -> None:
        """Skip current hold or fast-forward phase on SPACE press."""
        if self._phase == "text_hold":
            self._phase   = "text_fadeout"
            self._phase_t = 0.0
        elif self._phase == "initial_black":
            self._phase   = "text_fadein"
            self._phase_t = 0.0
        else:
            # Fast-forward whichever phase we're in
            self._phase_t += 999.0

    def update(self, dt: float) -> bool:
        """Advance the sequence. Returns True when all messages are done."""
        if self._done:
            return True

        from core import settings as S
        for d in self._dust:
            d["x"] += d["vx"] * dt
            d["y"] += d["vy"] * dt
            if d["x"] < -3 or d["x"] > S.SCREEN_WIDTH + 3:
                d.update(self._new_dust())
                d["x"] = -2 if d["vx"] > 0 else S.SCREEN_WIDTH + 2
            if d["y"] < -3 or d["y"] > S.SCREEN_HEIGHT + 3:
                d.update(self._new_dust())
                d["y"] = S.SCREEN_HEIGHT + 2

        self._phase_t += dt

        if self._phase == "initial_black":
            self._alpha = 0.0
            if self._phase_t >= _INITIAL_BLACK:
                self._next_phase("text_fadein")

        elif self._phase == "text_fadein":
            self._alpha = min(1.0, self._phase_t / _FADE_IN_DUR)
            if self._phase_t >= _FADE_IN_DUR:
                self._alpha = 1.0
                self._next_phase("text_hold")

        elif self._phase == "text_hold":
            self._alpha = 1.0
            if self._phase_t >= _HOLD_DUR:
                self._next_phase("text_fadeout")

        elif self._phase == "text_fadeout":
            self._alpha = max(0.0, 1.0 - self._phase_t / _FADE_OUT_DUR)
            if self._phase_t >= _FADE_OUT_DUR:
                self._alpha = 0.0
                self._msg_idx += 1
                if self._msg_idx >= len(_MSG_KEYS):
                    self._next_phase("final_hold")
                else:
                    self._next_phase("pause")

        elif self._phase == "pause":
            self._alpha = 0.0
            if self._phase_t >= _PAUSE_DUR:
                self._next_phase("text_fadein")

        elif self._phase == "final_hold":
            self._alpha = 0.0
            if self._phase_t >= _FINAL_HOLD_DUR:
                self._done = True
                return True

        return False

    def draw(self, surface: pygame.Surface, time_s: float) -> None:
        from core import settings as S
        self._ensure_fonts()
        W, H = S.SCREEN_WIDTH, S.SCREEN_HEIGHT
        cx   = W // 2
        cy   = H // 2

        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 245))
        surface.blit(overlay, (0, 0))

        band_h = int(H * 0.18)
        band = pygame.Surface((W, band_h), pygame.SRCALPHA)
        for row in range(band_h):
            frac = row / band_h
            a = int(30 * (1.0 - frac) ** 1.6)
            if a > 1:
                pygame.draw.line(band, (68, 30, 16, a), (0, row), (W, row))
        surface.blit(band, (0, H - band_h))

        sil = pygame.Surface((W, H), pygame.SRCALPHA)
        self._draw_silhouettes(sil, time_s, W, H)
        surface.blit(sil, (0, 0))

        dust_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        for d in self._dust:
            da = int(d["a"])
            if da > 2:
                r = max(1, int(d["r"]))
                pygame.draw.circle(dust_surf, (100, 72, 52, da),
                                   (int(d["x"]), int(d["y"])), r)
        surface.blit(dust_surf, (0, 0))

        if self._alpha > 0.008 and self._msg_idx < len(_MSG_KEYS):
            alpha_i = int(self._alpha * 255)
            text    = t(_MSG_KEYS[self._msg_idx])

            bar = pygame.Surface((W, 56), pygame.SRCALPHA)
            bar.fill((10, 14, 22, int(self._alpha * 38)))
            surface.blit(bar, (0, cy - 28))

            # Text color: neutral early, soft green for the last 2 messages
            if self._msg_idx >= 6:
                col = (148, 228, 168)
            elif self._msg_idx >= 4:
                col = (200, 212, 218)
            else:
                col = (218, 212, 206)

            msg_surf = self._font_msg.render(text, True, col)
            msg_surf.set_alpha(alpha_i)
            surface.blit(msg_surf,
                         (cx - msg_surf.get_width() // 2,
                          cy - msg_surf.get_height() // 2))

            if self._msg_idx < len(_MSG_KEYS) - 1:
                ctr_text = f"{self._msg_idx + 1}  /  {len(_MSG_KEYS)}"
                ctr_surf = self._font_hint.render(ctr_text, True, (55, 62, 68))
                ctr_surf.set_alpha(int(alpha_i * 0.52))
                surface.blit(ctr_surf,
                             (cx - ctr_surf.get_width() // 2, cy + 34))

        if self._phase == "text_hold" and self._alpha > 0.5:
            ha = int(70 * ((self._alpha - 0.5) / 0.5))
            hint_surf = self._font_hint.render("SPACE  —  continue", True, (52, 60, 65))
            hint_surf.set_alpha(ha)
            surface.blit(hint_surf,
                         (cx - hint_surf.get_width() // 2, H - 32))

    def _next_phase(self, phase: str) -> None:
        self._phase   = phase
        self._phase_t = 0.0

    @staticmethod
    def _new_dust() -> dict:
        from core import settings as S
        return {
            "x":  random.uniform(0, S.SCREEN_WIDTH),
            "y":  random.uniform(0, S.SCREEN_HEIGHT),
            "vx": random.uniform(-14.0, 14.0),
            "vy": random.uniform(-5.0, 2.0),
            "a":  random.uniform(12, 42),
            "r":  random.uniform(0.7, 2.0),
        }

    @staticmethod
    def _draw_silhouettes(
        sil: pygame.Surface, time_s: float, W: int, H: int
    ) -> None:
        """Two relay antenna silhouettes at the bottom screen edges."""
        by  = H - 1
        col = (28, 32, 36, 44)

        lx = int(W * 0.16)
        pygame.draw.line(sil, col, (lx, by),      (lx, by - 90),  2)
        pygame.draw.line(sil, col, (lx - 16, by - 30), (lx + 16, by - 30), 1)
        pygame.draw.line(sil, col, (lx - 12, by - 56), (lx + 12, by - 56), 1)
        pygame.draw.line(sil, col, (lx - 22, by - 80), (lx, by - 96), 2)
        pygame.draw.line(sil, col, (lx + 22, by - 80), (lx, by - 96), 2)
        # tiny dead beacon (no light — this was one of the lost towers)
        pygame.draw.circle(sil, (22, 26, 30, 38), (lx, by - 97), 3)

        rx = int(W * 0.84)
        pygame.draw.line(sil, col, (rx, by),      (rx, by - 72),  2)
        pygame.draw.line(sil, col, (rx - 12, by - 22), (rx + 12, by - 22), 1)
        pygame.draw.line(sil, col, (rx - 8,  by - 44), (rx + 8,  by - 44), 1)
        pygame.draw.line(sil, col, (rx - 18, by - 64), (rx, by - 78), 2)
        pygame.draw.line(sil, col, (rx + 18, by - 64), (rx, by - 78), 2)
        # faint surviving beacon pulse on the right tower
        pulse = abs(math.sin(time_s * 0.9))
        tip_a = int(50 + 38 * pulse)
        pygame.draw.circle(sil, (38, 96, 52, tip_a), (rx, by - 79), 2)
