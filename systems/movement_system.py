
import pygame
from pygame import Vector2

from core import settings as S
from entities.player import Player
from utils.helpers import clamp


class MovementSystem:

    def __init__(self) -> None:
        self._prev_axis = Vector2(0, 0)

    def update(self, player: Player, raw_axis: Vector2, dt: float) -> None:
        if raw_axis.length_squared() > 1:
            raw_axis.normalize_ip()

        t = min(1.0, S.INPUT_SMOOTH_SPEED * dt)
        if raw_axis.length_squared() > 0:
            player.smoothed_input = player.smoothed_input.lerp(raw_axis, t)
            if player.smoothed_input.length_squared() > 1:
                player.smoothed_input.normalize_ip()
        else:
            player.smoothed_input = player.smoothed_input.lerp(Vector2(0, 0), t)

        axis = player.smoothed_input
        speed = player.velocity.length()

        burst = False
        if raw_axis.length_squared() > 0.2 and self._prev_axis.length_squared() < 0.04:
            burst = True
        sharp_turn = False
        if (
            raw_axis.length_squared() > 0.2
            and self._prev_axis.length_squared() > 0.2
            and speed > 40
        ):
            dot = clamp(raw_axis.normalize().dot(self._prev_axis.normalize()), -1.0, 1.0)
            if dot < S.TURN_DOT_THRESHOLD:
                sharp_turn = True

        if burst:
            player.micro_shake_impulse = max(player.micro_shake_impulse, S.MICRO_SHAKE_ON_BURST)
        if sharp_turn:
            player.micro_shake_impulse = max(player.micro_shake_impulse, S.MICRO_SHAKE_ON_TURN)

        self._prev_axis = Vector2(raw_axis)

        # SHIFT boost: short acceleration burst, cooldown-gated.
        keys = pygame.key.get_pressed()
        shift = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        player.boost_cooldown = max(0.0, player.boost_cooldown - dt)
        player.boost_active = max(0.0, player.boost_active - dt)
        if shift and player.boost_cooldown <= 0.0 and axis.length_squared() > 0.01:
            player.boost_active = S.BOOST_DURATION
            player.boost_cooldown = S.BOOST_COOLDOWN
            player.micro_shake_impulse = max(player.micro_shake_impulse, 4.5)

        boost_mul = S.BOOST_ACCEL_MUL if player.boost_active > 0.0 else 1.0

        if axis.length_squared() > 0.01:
            player.apply_acceleration(axis * boost_mul, dt)
            player.apply_friction(S.PLAYER_COAST_FRICTION, dt)
        else:
            player.apply_friction(S.PLAYER_BRAKE_FRICTION, dt)

        player.cap_speed()
        player.integrate(dt)
        player.update_tilt(dt)
        player.decay_micro_shake(dt)
