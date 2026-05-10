
from __future__ import annotations

from core import settings as S


class ProgressionSystem:


    PHASE_SURVIVAL   = 1
    PHASE_RECOVERY   = 2
    PHASE_EVACUATION = 3

    def __init__(self) -> None:
        self._beacon_activated   = False
        self._countdown_active   = False
        self._countdown_remaining = S.FINAL_MISSION_COUNTDOWN
        self._countdown_expired  = False
        self._last_notified_phase = 0
        self._last_notified_level = -1

    def reset(self) -> None:
        self._beacon_activated    = False
        self._countdown_active    = False
        self._countdown_remaining = S.FINAL_MISSION_COUNTDOWN
        self._countdown_expired   = False
        self._last_notified_phase = 0
        self._last_notified_level = -1

    @property
    def beacon_activated(self) -> bool:
        return self._beacon_activated

    @property
    def countdown_active(self) -> bool:
        return self._countdown_active

    @property
    def countdown_remaining(self) -> float:
        return self._countdown_remaining

    @property
    def countdown_expired(self) -> bool:
        return self._countdown_expired

    def base_level(self, station) -> int:
        """0 = Damaged Outpost, 1 = Partial Restoration, 2 = Active Station, 3 = Evacuation Ready."""
        return station.station_level()

    def current_phase(self, station) -> int:
        lvl = self.base_level(station)
        if lvl >= 3:
            return self.PHASE_EVACUATION
        if lvl >= 1:
            return self.PHASE_RECOVERY
        return self.PHASE_SURVIVAL

    def final_mission_unlocked(self, station) -> bool:
        return self.base_level(station) >= 3

    def poll_phase_change(self, station) -> int | None:
        """Return the new phase number if it just changed, else None."""
        phase = self.current_phase(station)
        if phase != self._last_notified_phase:
            self._last_notified_phase = phase
            return phase
        return None

    def poll_level_change(self, station) -> int | None:
        """Return the new base level if it just changed, else None."""
        lvl = self.base_level(station)
        if lvl != self._last_notified_level:
            self._last_notified_level = lvl
            return lvl
        return None

    def activate_beacon(self) -> None:
        if not self._beacon_activated:
            self._beacon_activated    = True
            self._countdown_active    = True
            self._countdown_remaining = S.FINAL_MISSION_COUNTDOWN

    def update(self, dt: float) -> None:
        if self._countdown_active and not self._countdown_expired:
            self._countdown_remaining -= dt
            if self._countdown_remaining <= 0.0:
                self._countdown_remaining = 0.0
                self._countdown_expired   = True
                self._countdown_active    = False
