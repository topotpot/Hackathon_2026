
import math

import pygame

from utils.helpers import clamp


class AtmosphereSystem:
    def __init__(self, w: int, h: int) -> None:
        self._w = w
        self._h = h
        self._haze = self._build_haze(w, h)



    @staticmethod
    def _build_haze(w: int, h: int) -> pygame.Surface:

        s = pygame.Surface((w, h), pygame.SRCALPHA)
        top_band = int(h * 0.20)
        for row in range(top_band):
            frac = 1.0 - row / top_band
            a = int(28 * frac ** 1.5)
            if a > 0:
                pygame.draw.line(s, (162, 82, 42, a), (0, row), (w, row))
        bot_band = int(h * 0.10)
        for row in range(bot_band):
            frac = row / bot_band
            a = int(16 * frac ** 1.2)
            if a > 0:
                pygame.draw.line(s, (138, 68, 32, a),
                                 (0, h - bot_band + row), (w, h - bot_band + row))
        return s



    def update(
        self,
        dt: float,
        player_vel: object,
        storm_active: bool,
        storm_intensity: float,
    ) -> None:
        pass  



    def draw_haze(
        self,
        surface: pygame.Surface,
        storm_active: bool,
        storm_intensity: float,
        time_s: float,
    ) -> None:
        """Always-on surface depth haze, thickened during storms."""
        ha = int(22 + 10 * math.sin(time_s * 0.13))
        self._haze.set_alpha(ha)
        surface.blit(self._haze, (0, 0))

        if storm_active and storm_intensity > 0.4:
            si = clamp((storm_intensity - 0.4) / 1.6, 0.0, 1.0)
            extra_a = int(38 * si)
            if extra_a > 2:
                self._haze.set_alpha(extra_a)
                surface.blit(self._haze, (0, 0))
