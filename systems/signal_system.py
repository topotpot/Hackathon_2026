
from entities.player import Player
from core import settings as S
from utils.helpers import clamp


class SignalSystem:
    def __init__(self) -> None:
        pass

    def update_player_signal(
        self,
        player: Player,
        dt: float,
        storm_active: bool,
        storm_intensity_n: float,
        signal_loss_mul: float,
        in_safe_zone: bool,
        biome_name: str,
    ) -> None:
        # Baseline passive drain (scaled by biome signal_loss_mul)
        player.signal -= S.SIGNAL_BASE_DRAIN * max(0.0, signal_loss_mul) * dt

        # Storm drain (proportional to normalized intensity; reduced inside safe zones)
        if storm_active and storm_intensity_n > 0.0:
            _drain = S.SIGNAL_STORM_DRAIN * storm_intensity_n
            if in_safe_zone:
                _drain *= S.STORM_SAFE_ZONE_SIGNAL_DRAIN_MUL
            player.signal -= _drain * dt

        # ROCKS biome: stable signal environment — passive regen
        if biome_name == "ROCKS":
            player.signal += S.SIGNAL_ROCKS_REGEN * dt

        # Storm safe zone: sheltered area provides signal recovery
        if in_safe_zone:
            player.signal += S.SIGNAL_SAFE_ZONE_REGEN * dt

        # Apply one-time pickup deltas (positive from real beacons, negative from fake)
        if player.signal_offset != 0.0:
            player.signal += player.signal_offset
            player.signal_offset = 0.0

        player.signal = clamp(player.signal, 0.0, S.SIGNAL_MAX)
