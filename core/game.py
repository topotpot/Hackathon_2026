
import math
import os
import random

import pygame
from pygame import Vector2

from core import settings as S
from core.world_gen import BIOME_COLORS, BIOME_NAMES, EFFECTS, BiomeMap, WorldGenerator
from core.state_manager import GameState, StateManager
from entities.landmark import Landmark
from entities.player import Player
from entities.resource import Resource
from entities.signal import Signal as MapSignal
from systems.localization import next_language, t
from systems.audio_manager import AudioManager
from systems.collision_system import CollisionSystem
from systems.atmosphere import AtmosphereSystem
from systems.mars_backdrop import MarsBackdrop
from systems.micro_fx import MicroFX
from systems.movement_system import MovementSystem
from systems.particle_system import ParticleSystem
from systems.ending_system import EndingSystem
from systems.progression_system import ProgressionSystem
from systems.screen_effects import ScreenEffects
from systems.signal_system import SignalSystem
from systems.station_system import StationSystem
from systems.storm_system import StormSystem
from systems.terminal_system import TerminalSystem
from ui.endgame_ui import EndgameUI
from ui.hud import HUD
from ui.screens import Screens
from ui.station_ui import StationUI
from ui.terminal_ui import TerminalUI
from utils.helpers import clamp

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Game:
    """Top-level coordinator — owns every subsystem and drives handle_events → update → draw."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(S.TITLE)
        self.screen = pygame.display.set_mode((S.SCREEN_WIDTH, S.SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True

        self.audio = AudioManager(ROOT)
        self.screen_fx = ScreenEffects(S.SCREEN_WIDTH, S.SCREEN_HEIGHT)

        self.states = StateManager()
        self.hud = HUD()
        self.screens = Screens()

        self.movement = MovementSystem()
        self.collision = CollisionSystem()
        self.signal_system = SignalSystem()
        self.storm_system = StormSystem()
        self.micro_fx = MicroFX()
        self.backdrop = MarsBackdrop(S.SCREEN_WIDTH, S.SCREEN_HEIGHT)
        self.atmosphere = AtmosphereSystem(S.SCREEN_WIDTH, S.SCREEN_HEIGHT)
        self.station = StationSystem()
        self._station_ui = StationUI()
        self._station_ui_open = False
        self._in_station_zone = False
        self._in_any_storm_safe_zone = False
        self._terminal = TerminalSystem()
        self._terminal_ui = TerminalUI()
        self._terminal_open = False
        self.progression    = ProgressionSystem()
        self.endgame_ui     = EndgameUI()
        self.ending_system  = EndingSystem()
        self._game_completed = False
        self._final_beacon: "Landmark | None" = None
        self._beacon_prompt = False
        self._cinematic_t   = 0.0
        self.world_seed = random.randint(S.WORLD_SEED_MIN, S.WORLD_SEED_MAX)
        self.biome_map: BiomeMap | None = None
        self.screen_rect = self.screen.get_rect()
        self.particles = ParticleSystem(self.screen_rect)

        self.world = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT))

        self.player: Player
        self.resources: list[Resource]
        self.signals: list[MapSignal]
        self.landmarks: list[Landmark] = []
        self.collected_resources = 0
        self.activated_signals = 0
        self._storm_was_active = False
        self._signal_connected = False
        self._e_just_pressed = False
        self._e_for_beacon   = False
        self._connect_key = ""
        self._resource_connect_key = ""
        self._status_message = ""
        self._status_color: tuple = (255, 255, 255)
        self._status_t = 0.0
        self._cam_jitter_t = 0.0

        self._time_s = 0.0
        self.camera_offset = Vector2(0.0, 0.0)
        self.time_s = 0.0
        self._intro_fade = 0.0
        self._outro_fade = 0.0
        self._bursts: list[dict] = []
        self._biome_name = "DUNES"
        self._biome_params: dict = {
            "signal_loss_mul": 1.0,
            "glitch_add": 0.0,
            "vignette_mul": 1.0,
            "magnetic_jitter": 0.0,
            "fake_signal_bonus": 0.0,
            "resource_respawn_mul": 1.0,
        }
        self._resource_spawn_acc = 0.0
        self._safe_zones: list[dict] = []
        self._debug_cooldown = 0.0
        self._softlock_bonus_given = False
        self._dev_overlay = 0
        self._dev_font = pygame.font.SysFont("consolas", 16)

        self._reset_world()

    def _reset_world(self) -> None:
        """Rebuild all world state for a new run: seed, world gen, entity placement, subsystem reset."""
        self.audio.set_endgame_mode(False)
        self.station.reset()
        self.world_seed = random.randint(S.WORLD_SEED_MIN, S.WORLD_SEED_MAX)
        self.player = Player(S.PLAYER_START_X, S.PLAYER_START_Y)
        self.player.energy = 100.0
        self.player.signal = 100.0
        self.player.start_protection = 3.0
        self.player.signal_offset = 0.0
        self.collected_resources = 0
        self.activated_signals = 0

        gen = WorldGenerator(self.world_seed)
        bm, res_pos, sig_pos = gen.generate(
            resource_total=S.RESOURCE_COUNT,
            signal_total=S.SIGNAL_PICKUP_COUNT,
            real_signal_chance=S.REAL_SIGNAL_CHANCE,
        )
        self.biome_map = bm

        self.resources = [self._make_random_resource(Vector2(p)) for p in res_pos]
        center_v = Vector2(S.PLAYER_START_X, S.PLAYER_START_Y)
        self.signals = [
            MapSignal(
                Vector2(p),
                # Force stable inside safety radius — no corrupted towers near home
                is_real=True if (Vector2(p) - center_v).length() < S.SAFE_STATION_NO_CORRUPT_RADIUS else is_real,
            )
            for (p, is_real) in sig_pos
        ]
        self._station_ui_open = False
        self._terminal_open = False

        # Guarantee 2 relay/common resources within reach of center spawn
        center = Vector2(S.PLAYER_START_X, S.PLAYER_START_Y)
        nearby = sum(1 for r in self.resources if (r.position - center).length() < 420)
        for _ in range(max(0, 2 - nearby)):
            ang  = random.uniform(0, math.tau)
            dist = random.uniform(180.0, 370.0)
            pos  = center + Vector2(math.cos(ang), math.sin(ang)) * dist
            self.resources.append(Resource(pos, "relay", "common"))

        self._ensure_resource_sufficiency()

        self.landmarks = self._generate_landmarks()
        self._final_beacon = next(
            (lm for lm in self.landmarks if lm.ltype == "mega_relay"), None
        )
        self._safe_zones = self._generate_safe_zones()
        self.progression.reset()
        self._debug_cooldown = 0.0
        self._softlock_bonus_given = False
        self._beacon_prompt = False
        self._cinematic_t   = 0.0
        self.storm_system = StormSystem()
        self.storm_system.reset()
        self._storm_was_active = False
        self._signal_connected = False
        self._e_just_pressed = False
        self._connect_key = ""
        self._resource_connect_key = ""
        self._status_message = ""
        self._status_t = 0.0
        self._cam_jitter_t = 0.0
        self._bursts.clear()
        self._outro_fade = 0.0
        self._in_any_storm_safe_zone = False
        self.movement = MovementSystem()
        self.micro_fx.clear()
        self.backdrop.reset_scroll()
        self.camera_offset.update(0.0, 0.0)
        self._resource_spawn_acc = 0.0

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(S.FPS) / 1000.0
            self._handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if self._station_ui_open:
                    self._handle_station_ui_key(event.key)
                    continue
                if self._terminal_open:
                    self._handle_terminal_key(event.key)
                    continue

                if event.key == pygame.K_ESCAPE:
                    if self.states.is_info():
                        self.audio.play_ui("back")
                        self.states.set_state(GameState.MENU)
                    else:
                        self.running = False
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if self.states.is_menu():
                        self.audio.play_ui("click")
                        self.states.set_state(GameState.INFO)
                    elif self.states.is_info():
                        self.audio.play_ui("back")
                        self.states.set_state(GameState.MENU)
                elif event.key == pygame.K_SPACE:
                    if self.states.is_menu():
                        self.audio.play_ui("confirm")
                        self._reset_world()
                        self.states.set_state(GameState.PLAYING)
                        self._intro_fade = 1.0
                    elif self.states.is_game_over() or self.states.is_win() or self.states.is_evacuation_win():
                        self.audio.play_ui("click")
                        self.states.set_state(GameState.MENU)
                        self._outro_fade = 0.0
                    elif self.states.is_cinematic():
                        self._cinematic_t = S.CINEMATIC_DURATION
                    elif self.states.is_ending():
                        self.ending_system.advance()
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    if self.states.is_info():
                        self.audio.play_ui("click")
                        self.screens.nav_info(-1)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    if self.states.is_info():
                        self.audio.play_ui("click")
                        self.screens.nav_info(1)
                elif event.key == pygame.K_l:
                    if self.states.is_menu() or self.states.is_info():
                        self.audio.play_ui("click")
                        next_language()
                elif event.key == pygame.K_e:
                    if self.states.is_playing():
                        center_v = Vector2(S.PLAYER_START_X, S.PLAYER_START_Y)
                        if (self.player.position - center_v).length() < S.SAFE_STATION_INTERACT_RANGE:
                            self._station_ui_open = True
                        else:
                            self._e_just_pressed = True
                elif event.key == pygame.K_t:
                    if self.states.is_playing():
                        center_v = Vector2(S.PLAYER_START_X, S.PLAYER_START_Y)
                        if (self.player.position - center_v).length() < S.SAFE_STATION_INTERACT_RANGE:
                            self._terminal_open = True
                            self._terminal_ui.open()
                elif event.key == pygame.K_F1:
                    self._dev_overlay = (self._dev_overlay + 1) % 4

    def _handle_station_ui_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            self.audio.play_ui("back")
            self._station_ui_open = False
        elif key in (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER):
            if self._station_ui.try_purchase(self.station):
                self.audio.play_upgrade()
                if self.station.has("evac_protocol"):
                    self._start_ending_sequence()
            else:
                self.audio.play_ui("error")
        elif key in (pygame.K_UP, pygame.K_w):
            self.audio.play_ui("click")
            self._station_ui.nav_up()
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.audio.play_ui("click")
            self._station_ui.nav_down()
        elif key in (pygame.K_LEFT, pygame.K_a, pygame.K_TAB):
            self.audio.play_ui("click")
            self._station_ui.prev_cat()
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.audio.play_ui("click")
            self._station_ui.next_cat()

    def _handle_terminal_key(self, key: int) -> None:
        gs = self._make_terminal_gs()
        n = len(self._terminal.get_all_for_section(self._terminal_ui.current_section, gs))
        if key == pygame.K_ESCAPE:
            self._terminal_open = False
        elif key in (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER):
            if self._terminal_ui.current_section == "SETTINGS":
                next_language()
        elif key in (pygame.K_UP, pygame.K_w):
            self._terminal_ui.nav_up()
        elif key in (pygame.K_DOWN, pygame.K_s):
            self._terminal_ui.nav_down(n)
        elif key in (pygame.K_LEFT, pygame.K_a, pygame.K_TAB):
            self._terminal_ui.prev_section()
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._terminal_ui.next_section()
        elif key == pygame.K_PAGEUP:
            self._terminal_ui.scroll_content_up()
        elif key == pygame.K_PAGEDOWN:
            self._terminal_ui.scroll_content_down()

    def _make_terminal_gs(self) -> dict:
        return {
            "biomes_visited":    self._terminal.biomes_visited,
            "storms_survived":   self._terminal.storms_survived,
            "towers_activated":  self.activated_signals,
            "data_fragments":    self.station.data_fragments,
            "station_level":     self.station.station_level(),
            "resources_collected": self.collected_resources,
            "station":           self.station,
        }

    def update(self, dt: float) -> None:
        self._time_s += dt
        self.time_s = self._time_s
        self.screen_fx.update(dt)
        self.endgame_ui.update(dt)
        self.atmosphere.update(
            dt,
            self.player.velocity,
            self.storm_system.active,
            self.storm_system.intensity,
        )

        if self.states.is_playing():
            self._intro_fade = max(0.0, self._intro_fade - dt * S.FADE_IN_SPEED)
            if self._station_ui_open:
                self._station_ui.update(dt)
            elif self._terminal_open:
                self._terminal_ui.update(dt)
            else:
                self._update_playing(dt)
        elif self.states.is_cinematic():
            self._cinematic_t += dt
            progress = self._cinematic_t / S.CINEMATIC_DURATION
            if progress >= 1.0:
                self.states.set_state(GameState.EVACUATION_WIN)
        elif self.states.is_ending():
            if self.ending_system.update(dt):
                self._game_completed = True
                self.screens.set_completed(True)
                self.states.set_state(GameState.MENU)
        elif self.states.is_game_over():
            self._outro_fade = min(1.0, self._outro_fade + dt * S.FADE_OUT_SPEED)
        elif self.states.is_menu() or self.states.is_info():
            self._outro_fade = max(0.0, self._outro_fade - dt * S.FADE_OUT_SPEED)

        if self.states.is_menu() or self.states.is_info() or self.states.is_ending():
            self.hud.update(dt, 100.0, 100.0)
        elif self.states.is_playing():
            self.hud.update(dt, self.player.energy, self.player.signal)
        elif self.states.is_win() or self.states.is_evacuation_win() or self.states.is_game_over():
            self.hud.update(dt, self.player.energy, self.player.signal)

        _is_active = self.states.is_playing() or self.states.is_ending()
        _rover_spd = (
            min(1.0, self.player.velocity.length() / max(S.PLAYER_MAX_SPEED, 1.0))
            if _is_active else 0.0
        )
        self.audio.update_loops(
            dt,
            _is_active,
            self.storm_system.active and self.states.is_playing(),
            self.storm_system.intensity,
            self._in_station_zone,
            _rover_spd,
            self.station.station_level(),
            self._in_any_storm_safe_zone,
        )

    def _update_playing(self, dt: float) -> None:
        """Per-frame gameplay tick. Tick order: input → biome → storm → energy drain → resources → signals → camera."""
        # Capture E state before signal connections clear it
        self._e_for_beacon = self._e_just_pressed
        _prev_boost = self.player.boost_active
        axis = self._read_input_axis()
        self.movement.update(self.player, axis, dt)
        if _prev_boost <= 0.0 and self.player.boost_active > 0.0:
            self.audio.play_boost()
        if self.station.boost_extra_drain_rate > 0.0 and self.player.boost_cooldown > 0.0:
            self.player.boost_cooldown = max(0.0, self.player.boost_cooldown - self.station.boost_extra_drain_rate * dt)

        if self.player.micro_shake_impulse > 0.08:
            self.screen_fx.add_shake(self.player.micro_shake_impulse * 0.38)

        if self.player.start_protection > 0.0:
            self.player.start_protection = max(0.0, self.player.start_protection - dt)

        if self.biome_map is not None:
            a, b, blend_frac = self.biome_map.blend_at(self.player.position.x, self.player.position.y)
        else:
            a, b, blend_frac = (0, 0, 0.0)

        self._biome_name = BIOME_NAMES.get(a, "DUNES") if blend_frac < 0.5 else BIOME_NAMES.get(b, "DUNES")
        self._terminal.notify_biome(self._biome_name)

        if self.player.start_protection > 0.0:
            self.player.biome_speed_mul = 1.0
            self.storm_system.biome_intensity_mul = 1.0
            self._biome_params = {
                "signal_loss_mul": 1.0,
                "glitch_add": 0.0,
                "vignette_mul": 1.0,
                "magnetic_jitter": 0.0,
                "fake_signal_bonus": 0.0,
                "resource_respawn_mul": 1.0,
            }
        else:
            eff_a = EFFECTS[a]
            eff_b = EFFECTS[b]
            blend = max(0.0, min(1.0, float(blend_frac)))
            self.player.biome_speed_mul = eff_a.speed_mul * (1.0 - blend) + eff_b.speed_mul * blend
            self.storm_system.biome_intensity_mul = eff_a.storm_mul * (1.0 - blend) + eff_b.storm_mul * blend
            self._biome_params = {
                "signal_loss_mul": eff_a.signal_loss_mul * (1.0 - blend) + eff_b.signal_loss_mul * blend,
                "glitch_add": eff_a.glitch_add * (1.0 - blend) + eff_b.glitch_add * blend,
                "vignette_mul": eff_a.vignette_mul * (1.0 - blend) + eff_b.vignette_mul * blend,
                "magnetic_jitter": eff_a.magnetic_jitter * (1.0 - blend) + eff_b.magnetic_jitter * blend,
                "fake_signal_bonus": eff_a.fake_signal_bonus * (1.0 - blend) + eff_b.fake_signal_bonus * blend,
                "resource_respawn_mul": eff_a.resource_density_mul * (1.0 - blend) + eff_b.resource_density_mul * blend,
            }

        # ---- Upgrade: movement modifiers ----
        if self.station.biome_speed_bonus != 1.0:
            self.player.biome_speed_mul *= self.station.biome_speed_bonus
        if self.station.shadow_grip and self._biome_name == "SHADOW":
            self.player.biome_speed_mul = max(self.player.biome_speed_mul, 1.0)
        if self.station.storm_resistance_bonus:
            self.player.storm_resistance = min(1.0, S.PLAYER_STORM_RESISTANCE * 1.40)
        else:
            self.player.storm_resistance = S.PLAYER_STORM_RESISTANCE

        # ---- Safe station zone ----
        _station_center = Vector2(S.PLAYER_START_X, S.PLAYER_START_Y)
        in_station_zone = (self.player.position - _station_center).length() < S.SAFE_STATION_RADIUS
        self._in_station_zone = in_station_zone

        was_storm = self._storm_was_active
        if in_station_zone:
            _vel_pre = Vector2(self.player.velocity)
        self.storm_system.update(dt, self.player)
        if in_station_zone:
            # Dampen wind push inside the base — station provides structural shelter.
            wind_delta = self.player.velocity - _vel_pre
            self.player.velocity = _vel_pre + wind_delta * S.STATION_STORM_DAMPEN

        # Universal storm energy drain — everywhere except the base safe zone.
        # Permanent safe-storm zones reduce drain dramatically; storm_shield upgrade
        # scales it further.
        if self.storm_system.active and not in_station_zone:
            _eff_n = self.storm_system.effective_intensity_n()
            storm_drain = (
                _eff_n
                * S.STORM_ENERGY_DRAIN
                * S.FPS * dt
                * self.station.storm_energy_drain_mul
            )
            _in_sz = self._player_in_safe_zone()
            if _in_sz is not None:
                storm_drain *= (1.0 - _in_sz['reduction'])
            elif self.storm_system.player_in_safe_zone(self.player):
                storm_drain *= S.STORM_SAFE_ZONE_DAMAGE_MUL
            self.player.energy = max(0.0, self.player.energy - storm_drain)
        if self.storm_system.active and not was_storm:
            self.particles.on_storm_started(self.storm_system.wind)
        if not self.storm_system.active and was_storm:
            self.station.add_relay(2)
            self._terminal.notify_storm()
            self._status_message = t("status.relay_recovered")
            self._status_color = (140, 220, 160)
            self._status_t = 2.2
        self._storm_was_active = self.storm_system.active

        self.particles.update(
            dt,
            self.storm_system.active,
            self.storm_system.wind,
            self.storm_system.intensity,
            self.storm_system.state,
            player=self.player,
            camera_offset=self.camera_offset,
        )

        if self.storm_system.consume_gust_sound():
            self.audio.play_gust(self.storm_system.intensity)
        if self.storm_system.consume_energy_burst_sound():
            self.audio.play_energy_burst(self.storm_system.intensity)

        base_drain = S.ENERGY_DRAIN_PER_SECOND * self.station.energy_drain_mul
        self.player.energy = max(0.0, self.player.energy - base_drain * dt)
        spd = self.player.velocity.length()
        if spd > 1.0:
            self.player.energy = max(0.0, self.player.energy - S.ENERGY_DRAIN_MOVE_COEF * spd * dt)
        if self.station.emergency_cell and self.player.energy < self.station.energy_max * 0.20:
            self.player.energy = min(self.station.energy_max * 0.20, self.player.energy + 3.5 * dt)
        if in_station_zone:
            self.player.signal = clamp(self.player.signal + S.STATION_SIGNAL_REGEN * dt, 0.0, S.SIGNAL_MAX)
            if spd < 40.0:
                self.player.energy = min(self.station.energy_max, self.player.energy + S.STATION_ENERGY_REGEN * dt)

        self._update_resources(dt)
        if self._status_t > 0.0:
            self._status_t = max(0.0, self._status_t - dt)
            if self._status_t <= 0.0:
                self._status_message = ""
        if self._cam_jitter_t > 0.0:
            self._cam_jitter_t = max(0.0, self._cam_jitter_t - dt)
        self._update_signal_connections(dt)
        # Resource prompt only shows when no signal key is active
        if not self._connect_key and self._resource_connect_key:
            self._connect_key = self._resource_connect_key

        _sig_eff_n = (
            self.storm_system.effective_intensity_n()
            if self.storm_system.active else 0.0
        )
        in_safe = (
            self.storm_system.player_in_safe_zone(self.player)
            or (self._player_in_safe_zone() is not None)
        )
        self._in_any_storm_safe_zone = in_safe
        _sig_loss_mul = self._biome_params.get("signal_loss_mul", 1.0) * self.station.signal_drain_mul
        self.signal_system.update_player_signal(
            self.player,
            dt,
            self.storm_system.active and not in_station_zone,
            _sig_eff_n if not in_station_zone else 0.0,
            _sig_loss_mul,
            in_safe or in_station_zone,
            self._biome_name,
        )
        mj = float(self._biome_params.get("magnetic_jitter", 0.0))
        if mj > 0.01:
            self.player.signal = clamp(
                self.player.signal + random.uniform(-mj, mj),
                0.0,
                S.SIGNAL_MAX,
            )

        self._update_bursts(dt)

        self.backdrop.update_parallax(self.player.velocity, dt)
        self.micro_fx.emit_rover_dust(self.player.position, self.player.velocity, dt)
        self.micro_fx.update(dt)
        for lm in self.landmarks:
            lm.update(dt)

        # Debug cheat: SHIFT + K + O + P simultaneously → max resources
        self._debug_cooldown = max(0.0, self._debug_cooldown - dt)
        if self._debug_cooldown <= 0.0:
            _keys = pygame.key.get_pressed()
            if (
                (_keys[pygame.K_LSHIFT] or _keys[pygame.K_RSHIFT])
                and _keys[pygame.K_k]
                and _keys[pygame.K_o]
                and _keys[pygame.K_p]
            ):
                self._activate_debug_mode()
                self._debug_cooldown = 5.0

        if self.player.boost_active > 0.0:
            self.player.energy = max(0.0, self.player.energy - S.ENERGY_DRAIN_BOOST_PER_SEC * dt)

        self._clamp_player_to_world()
        self._update_camera(dt)
        if self.station.deep_scan and random.random() < 0.0025 * dt:
            self.station.add_ancient()
            self._status_message = t("status.ancient_detected")
            self._status_color = (220, 140, 255)
            self._status_t = 2.0
        self._maybe_respawn_resources(dt)

        if self.player.energy <= 0:
            self.audio.play_error()
            self.screen_fx.add_shake(6.0)
            self.states.set_state(GameState.GAME_OVER)
            self._outro_fade = 0.0
            return

        self._update_progression(dt)

    def _update_resources(self, dt: float) -> None:
        """Advance resource state machines; signal tower prompts take E-key priority over scavenging."""
        self._resource_connect_key = ""
        spd = self.player.velocity.length()

        # Signals take E-key priority: check before iterating resources
        signal_has_prompt = any(s.show_prompt or s.is_connecting for s in self.signals)

        any_prompt     = False
        any_scavenging = False
        completed: list[Resource] = []

        for r in self.resources:
            if r.state == "done":
                continue
            dist     = (self.player.position - r.position).length()
            in_range = dist < S.RESOURCE_PROMPT_RANGE

            # State transitions
            if r.state == "idle" and in_range and spd <= S.RESOURCE_SCAVENGE_SPEED_LIMIT:
                r.enter_prompt()
            elif r.state == "prompt" and not in_range:
                r.exit_prompt()
            elif r.state == "scavenging" and not in_range:
                r.cancel_scavenge()

            # E key: resources only consume it when no signal prompt is active
            if self._e_just_pressed and r.state == "prompt" and not signal_has_prompt:
                r.start_scavenge()

            if r.show_prompt:
                any_prompt = True
            if r.state == "scavenging":
                any_scavenging = True

            if r.update(dt):
                completed.append(r)

        for r in completed:
            self._complete_resource(r)

        self.resources = [r for r in self.resources if r.state != "done"]

        # Prompt key fed into connect_key priority after signal connections
        if any_scavenging:
            self._resource_connect_key = "prompts.scavenging"
        elif any_prompt:
            self._resource_connect_key = "prompts.scavenge"

    def _complete_resource(self, r: Resource) -> None:
        self.collected_resources += 1
        self.station.add_salvage()

        if r.condition == "corrupted":
            self.player.signal = clamp(
                self.player.signal - S.RESOURCE_CORRUPTED_SIGNAL_DRAIN, 0.0, S.SIGNAL_MAX
            )
            self.player.energy = max(0.0, self.player.energy - S.RESOURCE_CORRUPTED_ENERGY_DRAIN)
            self.screen_fx.add_shake(2.8)
            self._status_message = t("status.corrupted_resource")
            self._status_color    = (220, 60, 180)
            self._status_t        = 2.5
        else:
            gain = S.RESOURCE_ENERGY_RELAY if r.rtype == "relay" else S.RESOURCE_ENERGY_TECH
            if r.condition == "damaged":
                gain *= 0.55
            self.player.energy = min(self.station.energy_max, self.player.energy + gain)
            if r.rtype == "tech":
                self.station.add_data()
                self._status_message = t("status.tech_recovered")
                self._status_color    = (255, 158, 55)
            else:
                self._status_message = t("status.resource_recovered")
                self._status_color    = (95, 218, 138)
            self._status_t = 2.0

        # Biome bonus — ancient tech chance (higher in SHADOW)
        _ancient_found = False
        if self._biome_name == "SHADOW" and random.random() < S.ANCIENT_SHADOW_CHANCE:
            self.station.add_ancient()
            self._status_message = t("status.ancient_salvaged")
            self._status_color   = (220, 140, 255)
            self._status_t       = 2.4
            _ancient_found = True
        elif self._biome_name != "SHADOW" and random.random() < S.ANCIENT_NONSHADOW_CHANCE:
            self.station.add_ancient()
            self._status_message = t("status.ancient_salvaged")
            self._status_color   = (220, 140, 255)
            self._status_t       = 2.4
            _ancient_found = True

        self.audio.play_collect("ancient" if _ancient_found else r.rtype)
        burst_col = (60, 200, 255) if r.rtype == "relay" else (255, 148, 38)
        self._bursts.append({"pos": Vector2(r.position), "t": 0.0, "real": True, "col": burst_col})

    def _make_random_resource(self, pos: Vector2) -> Resource:
        biome_id   = self.biome_map.biome_at(pos.x, pos.y) if self.biome_map else 0
        biome_name = BIOME_NAMES.get(biome_id, "DUNES")
        rtype      = self._pick_resource_type(biome_name)
        condition  = self._pick_resource_condition(biome_name)
        return Resource(pos, rtype, condition)

    @staticmethod
    def _pick_resource_type(biome_name: str) -> str:
        relay_chance = {"DUNES": 0.70, "ROCKS": 0.40, "MAGNETIC": 0.28, "SHADOW": 0.18}
        return "relay" if random.random() < relay_chance.get(biome_name, 0.50) else "tech"

    @staticmethod
    def _pick_resource_condition(biome_name: str) -> str:
        corrupted_ch = 0.14 if biome_name == "MAGNETIC" else 0.06
        unstable_ch  = 0.20 if biome_name == "MAGNETIC" else 0.14
        damaged_ch   = 0.30
        rv = random.random()
        if rv < corrupted_ch:
            return "corrupted"
        if rv < corrupted_ch + unstable_ch:
            return "unstable"
        if rv < corrupted_ch + unstable_ch + damaged_ch:
            return "damaged"
        return "common"

    def _read_input_axis(self) -> Vector2:
        keys = pygame.key.get_pressed()
        ax = 0.0
        ay = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            ax -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            ax += 1.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            ay -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            ay += 1.0
        v = Vector2(ax, ay)
        if v.length_squared() > 1:
            v.normalize_ip()
        return v

    def _update_signal_connections(self, dt: float) -> None:
        """Drive per-tower corruption state machines and signal pickup logic. E-key consumed here."""
        spd = self.player.velocity.length()
        self._signal_connected = False
        self._connect_key = ""
        any_prompt = False

        intensity_n = min(1.0, self.storm_system.intensity / max(S.STORM_INTENSITY_MAX, 0.01))

        for sig in self.signals:
            # Per-tower corruption speed based on its biome position + current storm
            corrupt_speed = 1.0
            if self.biome_map is not None and not sig.is_real:
                ba, bb, bt = self.biome_map.blend_at(sig.position.x, sig.position.y)
                tower_biome = BIOME_NAMES.get(ba, "DUNES") if bt < 0.5 else BIOME_NAMES.get(bb, "DUNES")
                if tower_biome == "MAGNETIC":
                    corrupt_speed += S.MAGNETIC_CORRUPT_SPEED_ADD
            if self.storm_system.active:
                corrupt_speed += intensity_n * S.STORM_CORRUPT_SPEED_ADD

            sig.update(dt, corrupt_speed, self.station.corrupt_reveal_mul)

            if sig.consume_fail():
                self._apply_corrupt_fail(sig)

            if sig.state in ("activated", "dead"):
                continue

            dist_sq = (self.player.position - sig.position).length_squared()
            prompt_r = S.SIGNAL_PROMPT_RANGE * self.station.prompt_range_mul
            if self.storm_system.active:
                prompt_r *= self.station.storm_prompt_range_mul
            in_prompt = dist_sq <= prompt_r * prompt_r
            in_connect = sig.connect_range_contains(self.player.position)
            can_speed = spd <= S.SIGNAL_CONNECT_SPEED_LIMIT

            # Prompt state management
            if sig.state == "idle" and in_prompt and can_speed:
                sig.enter_prompt()
            elif sig.state == "prompt" and (not in_prompt or not can_speed):
                sig.exit_prompt()

            if sig.show_prompt:
                any_prompt = True

            # E key initiates connection when in prompt range and slow enough
            if self._e_just_pressed and sig.show_prompt and in_connect and can_speed:
                sig.start_connect()

            # Connection interruption checks
            if sig.is_connecting:
                if not in_connect:
                    sig.stop_connect()
                elif spd > S.SIGNAL_CONNECT_SPEED_LIMIT:
                    sig.break_connect()
                    self.player.signal = clamp(
                        self.player.signal - S.SIGNAL_CONNECT_BREAK_PENALTY, 0.0, S.SIGNAL_MAX
                    )

            # Per-frame effects while actively connecting
            if sig.state == "connecting":
                self._signal_connected = True
                if sig.is_real:
                    self.player.signal = clamp(
                        self.player.signal + S.SIGNAL_CONNECT_RATE * dt, 0.0, S.SIGNAL_MAX
                    )
                    if sig.connect_time >= S.SIGNAL_CONNECT_DURATION:
                        sig.activate()
                        self.activated_signals += 1
                        self.station.add_data()
                        self._bursts.append({"pos": Vector2(sig.position), "t": 0.0, "real": True})
                        self.player.signal = clamp(self.player.signal + 8.0, 0.0, S.SIGNAL_MAX)
                        self.audio.play_signal_event("rise")
                        self.screen_fx.add_shake(1.8)
                        self._status_message = t("status.signal_restored")
                        self._status_color = (80, 220, 140)
                        self._status_t = 2.0
                else:
                    # Corrupted tower pre-reveal: deceptive small regen
                    self.player.signal = clamp(
                        self.player.signal + S.CORRUPT_FAKE_REGEN * dt, 0.0, S.SIGNAL_MAX
                    )

            elif sig.state == "corrupt_early":
                # Deceptive: still looks normal
                self._signal_connected = True
                self.player.signal = clamp(
                    self.player.signal + S.CORRUPT_FAKE_REGEN * dt, 0.0, S.SIGNAL_MAX
                )

            elif sig.state == "corrupt_mid":
                self._signal_connected = True
                frac = sig.corruption_intensity
                drain = S.SIGNAL_FAKE_DRAIN_RATE * frac
                self.player.signal = clamp(
                    self.player.signal - drain * dt, 0.0, S.SIGNAL_MAX
                )
                if random.random() < 0.04:
                    self.screen_fx.add_shake(0.5 * frac)

        self._e_just_pressed = False

        # Set connect_key from current aggregate connection state
        if self._signal_connected:
            if any(s.state == "corrupt_mid" for s in self.signals):
                self._connect_key = "prompts.unstable"
            else:
                self._connect_key = "prompts.connecting"
        elif any_prompt:
            self._connect_key = "prompts.press_e_connect"
        else:
            center_v = Vector2(S.PLAYER_START_X, S.PLAYER_START_Y)
            if (self.player.position - center_v).length() < S.SAFE_STATION_INTERACT_RANGE:
                self._connect_key = "prompts.station_dual"

    def _apply_corrupt_fail(self, sig: "MapSignal") -> None:
        self.player.signal = clamp(
            self.player.signal - S.CORRUPT_FAIL_SIGNAL_PENALTY, 0.0, S.SIGNAL_MAX
        )
        self.screen_fx.add_shake(3.8)
        self.audio.play_error()

        self._status_message = t(random.choice([
            "status.connection_failed",
            "status.source_corrupted",
            "status.relay_error",
            "prompts.unstable",
        ]))
        self._status_color = (230, 65, 65)
        self._status_t = 2.8

        if random.random() < S.CORRUPT_CAM_JITTER_CHANCE:
            self._cam_jitter_t = S.CORRUPT_CAM_JITTER_T
            self.screen_fx.add_shake(2.2)

    def _update_bursts(self, dt: float) -> None:
        alive = []
        for b in self._bursts:
            b["t"] += dt
            if b["t"] < S.SIGNAL_FLASH_DURATION:
                alive.append(b)
        self._bursts = alive

    def _clamp_player_to_world(self) -> None:
        m = 4
        half_w = S.PLAYER_SIZE[0] / 2
        half_h = S.PLAYER_SIZE[1] / 2
        self.player.position.x = clamp(self.player.position.x, half_w + m, S.WORLD_WIDTH - half_w - m)
        self.player.position.y = clamp(self.player.position.y, half_h + m, S.WORLD_HEIGHT - half_h - m)

    def _update_camera(self, dt: float) -> None:
        """Framerate-independent exponential lerp follow (1 - 0.001**dt) with world-edge clamping."""
        sc = Vector2(S.SCREEN_WIDTH * 0.5, S.SCREEN_HEIGHT * 0.5)
        target = Vector2(self.player.position.x - sc.x, self.player.position.y - sc.y)
        target.x = clamp(target.x, 0.0, S.WORLD_WIDTH - S.SCREEN_WIDTH)
        target.y = clamp(target.y, 0.0, S.WORLD_HEIGHT - S.SCREEN_HEIGHT)
        k = 1.0 - (0.001 ** (dt * S.CAMERA_LERP))
        self.camera_offset += (target - self.camera_offset) * k
        if self._cam_jitter_t > 0.0:
            self.camera_offset.x += random.uniform(-3.5, 3.5)
            self.camera_offset.y += random.uniform(-2.5, 2.5)

    def _find_shadow_spawn_pos(self) -> "Vector2 | None":
        """Try up to 30 positions to find one in the SHADOW biome."""
        if self.biome_map is None:
            return None
        for _ in range(30):
            x = random.uniform(64, S.WORLD_WIDTH - 64)
            y = random.uniform(64, S.WORLD_HEIGHT - 64)
            if BIOME_NAMES.get(self.biome_map.biome_at(x, y), "") == "SHADOW":
                return Vector2(x, y)
        return None

    def _maybe_respawn_resources(self, dt: float) -> None:
        if len(self.resources) >= S.RESOURCE_COUNT:
            self._resource_spawn_acc = 0.0
            return
        mul = float(self._biome_params.get("resource_respawn_mul", 1.0))
        rate = S.RESOURCE_RESPAWN_PER_SEC * max(0.0, mul)
        self._resource_spawn_acc += rate * dt
        n = int(self._resource_spawn_acc)
        self._resource_spawn_acc -= n
        for _ in range(n):
            if len(self.resources) >= S.RESOURCE_COUNT:
                break
            # Late-game emergency: bias toward SHADOW when ancient is critically low
            late_game = len(self.station.purchased) >= 8 and self.station.ancient_tech < 2
            pos = (self._find_shadow_spawn_pos() if late_game else None) or Vector2(
                random.uniform(64, S.WORLD_WIDTH - 64),
                random.uniform(64, S.WORLD_HEIGHT - 64),
            )
            self.resources.append(self._make_random_resource(pos))

    def _ensure_resource_sufficiency(self) -> None:
        """Post-generation pass: guarantee enough ancient and data resources exist."""
        from systems.station_system import TOTAL_UPGRADE_COSTS
        rng = random.Random(self.world_seed ^ 0xC4F9A2)

        # Ancient: need 12 total (upgrade cost). 50% SHADOW chance → need ≥24 SHADOW resources.
        SHADOW_TARGET = 24
        shadow_res = [
            r for r in self.resources
            if self.biome_map and BIOME_NAMES.get(self.biome_map.biome_at(r.position.x, r.position.y), "") == "SHADOW"
        ]
        shadow_deficit = max(0, SHADOW_TARGET - len(shadow_res))
        placed = 0
        for _ in range(shadow_deficit * 10):
            if placed >= shadow_deficit:
                break
            x = rng.uniform(80, S.WORLD_WIDTH - 80)
            y = rng.uniform(80, S.WORLD_HEIGHT - 80)
            if self.biome_map and BIOME_NAMES.get(self.biome_map.biome_at(x, y), "") == "SHADOW":
                self.resources.append(Resource(Vector2(x, y), "tech", "common"))
                placed += 1

        # Data: need 21 total. Signals give ~7-8 data. Target ≥18 tech resources.
        TECH_TARGET = 18
        tech_count = sum(1 for r in self.resources if r.rtype == "tech")
        for _ in range(max(0, TECH_TARGET - tech_count)):
            x = rng.uniform(80, S.WORLD_WIDTH - 80)
            y = rng.uniform(80, S.WORLD_HEIGHT - 80)
            self.resources.append(Resource(Vector2(x, y), "tech", "common"))

    def _start_ending_sequence(self) -> None:
        """Close station UI and begin the atmospheric text ending."""
        self._station_ui_open = False
        self.ending_system.reset()
        self.audio.set_endgame_mode(True)
        self.states.set_state(GameState.ENDING)

    def _activate_debug_mode(self) -> None:
        self.station.salvage          += 50
        self.station.data_fragments   += 50
        self.station.relay_components += 50
        self.station.ancient_tech     += 50
        self._status_message = "DEBUG MODE ENABLED"
        self._status_color   = (255, 230, 60)
        self._status_t       = 3.5

    def _update_progression(self, dt: float) -> None:
        """Phase/base-level tracking, beacon interaction, and countdown management."""
        self.progression.update(dt)

        # Phase / level change notifications
        new_phase = self.progression.poll_phase_change(self.station)
        if new_phase is not None:
            self.endgame_ui.notify_phase(new_phase)

        new_level = self.progression.poll_level_change(self.station)
        if new_level is not None and new_level > 0:
            self.endgame_ui.notify_level(new_level)
            self._status_message = f"BASE LEVEL {new_level} REACHED"
            self._status_color = (80, 240, 140)
            self._status_t = 3.0
            self.screen_fx.add_shake(1.5)
            # Anti-softlock: one-time resource cache when station reaches level 3
            if new_level == 3 and not self._softlock_bonus_given:
                self._softlock_bonus_given = True
                self.station.add_ancient(2)
                self.station.add_relay(2)
                self.station.add_data(2)
                self._status_message = "EMERGENCY CACHE RECOVERED — ANCIENT TECH FOUND"
                self._status_color = (220, 140, 255)
                self._status_t = 4.5

        # Beacon proximity check (only when final mission is unlocked)
        self._beacon_prompt = False
        if (
            self._final_beacon is not None
            and not self.progression.beacon_activated
            and self.progression.final_mission_unlocked(self.station)
        ):
            dist = (self.player.position - self._final_beacon.position).length()
            if dist < S.BEACON_INTERACT_RANGE:
                self._beacon_prompt = True
                if self._e_for_beacon:
                    self.progression.activate_beacon()
                    self._status_message = "EVACUATION BEACON ACTIVATED — RETURN TO BASE"
                    self._status_color = (60, 255, 120)
                    self._status_t = 5.0
                    self.screen_fx.add_shake(3.5)

        # Countdown expired → cinematic anyway (shuttle comes regardless)
        if self.progression.countdown_expired:
            self.states.set_state(GameState.CINEMATIC)
            self._cinematic_t = 0.0
            return

        # Player reaches base during countdown → cinematic win
        if self.progression.countdown_active:
            center_v = Vector2(S.PLAYER_START_X, S.PLAYER_START_Y)
            if (self.player.position - center_v).length() < S.SAFE_STATION_INTERACT_RANGE:
                self.states.set_state(GameState.CINEMATIC)
                self._cinematic_t = 0.0

    def _generate_safe_zones(self) -> list[dict]:
        """Deterministic permanent safe-storm zones distributed across the world."""
        rng = random.Random(self.world_seed ^ 0x4F2A1C)
        zones: list[dict] = []
        placed: list[Vector2] = []
        center = Vector2(S.PLAYER_START_X, S.PLAYER_START_Y)
        margin = 120.0
        for _ in range(S.SAFE_ZONE_COUNT * 14):
            if len(zones) >= S.SAFE_ZONE_COUNT:
                break
            x = rng.uniform(margin, S.WORLD_WIDTH  - margin)
            y = rng.uniform(margin, S.WORLD_HEIGHT - margin)
            pos = Vector2(x, y)
            if (pos - center).length() < S.SAFE_ZONE_MIN_PLAYER_DIST:
                continue
            if any((pos - p).length() < S.SAFE_ZONE_MIN_DIST for p in placed):
                continue
            placed.append(pos)
            zones.append({
                "pos":       pos,
                "radius":    int(rng.uniform(S.SAFE_ZONE_RADIUS_MIN, S.SAFE_ZONE_RADIUS_MAX)),
                "reduction": rng.uniform(S.SAFE_ZONE_DRAIN_REDUCTION_MIN, S.SAFE_ZONE_DRAIN_REDUCTION_MAX),
                "phase":     rng.uniform(0.0, math.tau),
            })
        return zones

    def _player_in_safe_zone(self) -> dict | None:
        px, py = self.player.position.x, self.player.position.y
        for zone in self._safe_zones:
            r = zone["radius"]
            if (px - zone["pos"].x) ** 2 + (py - zone["pos"].y) ** 2 <= r * r:
                return zone
        return None

    def _draw_safe_zones(self, draw_off: Vector2) -> None:
        """Cinematic green safe-storm zone markers — always visible, effect only during storms."""
        t = self.time_s
        px, py = self.player.position.x, self.player.position.y
        for zone in self._safe_zones:
            sx = int(zone["pos"].x + draw_off.x)
            sy = int(zone["pos"].y + draw_off.y)
            r  = zone["radius"]
            ph = zone["phase"]
            m  = r + 24
            if not (-m < sx < S.SCREEN_WIDTH + m and -m < sy < S.SCREEN_HEIGHT + m):
                continue

            inside = (px - zone["pos"].x) ** 2 + (py - zone["pos"].y) ** 2 <= r * r

            pulse = 0.5 + 0.5 * math.sin(t * 0.75 + ph)
            d  = (r + 22) * 2
            cx = cy = d // 2
            cnv = pygame.Surface((d, d), pygame.SRCALPHA)

            if inside:
                # Player sheltered: deeper fill, brighter ring, faster pulse
                inner_a = int(22 + 22 * pulse)
                ring_col = (72, 220, 118)
                ring_a   = int(72 + 48 * pulse)
                outer_a  = int(22 + 20 * pulse)
                tick_a   = int(90 + 55 * pulse)
                dot_base = (80, 220, 120)
            else:
                inner_a = int(8 + 8 * pulse)
                ring_col = (44, 182, 92)
                ring_a   = int(36 + 24 * pulse)
                outer_a  = int(10 + 9 * pulse)
                tick_a   = int(55 + 32 * pulse)
                dot_base = (54, 192, 92)

            # Inner atmospheric fill
            pygame.draw.circle(cnv, (32, 135, 65, inner_a), (cx, cy), r)

            # Ring border
            pygame.draw.circle(cnv, (*ring_col, ring_a), (cx, cy), r, 2)

            # Outer diffuse glow ring
            pygame.draw.circle(cnv, (22, 105, 50, outer_a), (cx, cy), r + 12, 7)

            # Four compass tick marks (slowly rotate)
            for i in range(4):
                ang = (i * math.pi * 0.5) + t * 0.06 + ph
                ix = cx + int(math.cos(ang) * (r - 10))
                iy = cy + int(math.sin(ang) * (r - 10))
                ox = cx + int(math.cos(ang) * (r - 2))
                oy = cy + int(math.sin(ang) * (r - 2))
                pygame.draw.line(cnv, (*ring_col, tick_a), (ix, iy), (ox, oy), 1)

            # Six tech dots at perimeter
            for i in range(6):
                ang = (i / 6) * math.tau + t * 0.08 + ph
                dx_d = cx + int(math.cos(ang) * (r - 4))
                dy_d = cy + int(math.sin(ang) * (r - 4))
                da = int(62 + 54 * abs(math.sin(t * 1.8 + i * 1.05 + ph)))
                pygame.draw.circle(cnv, (*dot_base, da), (dx_d, dy_d), 2)

            # Slow expanding scan ring (period 7 s)
            scan_frac = ((t / 7.0) + ph * 0.16) % 1.0
            scan_r = int(r * scan_frac)
            if scan_r > 4:
                sa = int(20 * (1.0 - scan_frac))
                if inside:
                    sa = int(sa * 2.2)
                if sa > 1:
                    pygame.draw.circle(cnv, (52, 196, 96, sa), (cx, cy), scan_r, 1)

            self.world.blit(cnv, (sx - cx, sy - cy))

            # Additive outer glow — more intense when player is sheltered
            gr = r + 14
            gw = gr * 2
            glow = pygame.Surface((gw, gw), pygame.SRCALPHA)
            if inside:
                pygame.draw.circle(glow, (28, 130, 65, int(22 + 18 * pulse)), (gr, gr), gr, 10)
            else:
                pygame.draw.circle(glow, (18, 88, 42, int(8 + 7 * pulse)), (gr, gr), gr, 8)
            self.world.blit(glow, (sx - gr, sy - gr), special_flags=pygame.BLEND_ADD)

    def _draw_beacon_effects(self, draw_off: Vector2) -> None:
        """Draw animated effects around the final beacon landmark."""
        if self._final_beacon is None:
            return
        bx = int(self._final_beacon.position.x + draw_off.x)
        by = int(self._final_beacon.position.y + draw_off.y)

        unlocked  = self.progression.final_mission_unlocked(self.station)
        activated = self.progression.beacon_activated

        if not unlocked and not activated:
            return

        t = self.time_s
        if activated:
            # Persistent upward beam after activation
            pulse = 0.7 + 0.3 * math.sin(t * 6.0)
            beam_a = int(60 + 50 * pulse)
            for row in range(120):
                row_a = int(beam_a * (1.0 - row / 120.0) ** 1.2)
                if row_a > 2:
                    col = (int(40 * pulse), int(255 * pulse), int(100 * pulse), row_a)
                    line_s = pygame.Surface((4, 1), pygame.SRCALPHA)
                    line_s.fill(col)
                    self.world.blit(line_s, (bx - 1, by - 220 - row))
            # Pulsing outer ring on the ground
            ring_r = int(38 + 12 * pulse)
            ring_s = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring_s, (60, 255, 120, int(55 + 40 * pulse)),
                               (ring_r + 2, ring_r + 2), ring_r, 2)
            self.world.blit(ring_s, (bx - ring_r - 2, by - ring_r - 2),
                           special_flags=pygame.BLEND_ADD)
        elif unlocked:
            # "Ready to activate" — slow pulsing green halo
            pulse = 0.5 + 0.5 * abs(math.sin(t * 1.8))
            halo_r = 28
            halo_s = pygame.Surface((halo_r * 2 + 4, halo_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(halo_s, (60, 200, 100, int(50 + 40 * pulse)),
                               (halo_r + 2, halo_r + 2), halo_r, 3)
            self.world.blit(halo_s, (bx - halo_r - 2, by - halo_r - 2),
                           special_flags=pygame.BLEND_ADD)

    def _draw_bursts(self, surface: pygame.Surface) -> None:
        for b in self._bursts:
            u   = b["t"] / S.SIGNAL_FLASH_DURATION
            r   = int(8 + 36 * u)
            a   = int(220 * (1.0 - u))
            base = b.get("col", (120, 220, 255) if b["real"] else (255, 80, 90))
            col = (*base, a)
            ring = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, col, (r, r), r, 3)
            p = b["pos"]
            surface.blit(ring, (int(p.x - r), int(p.y - r)))

    def _generate_landmarks(self) -> list:
        """Distribute 11 large atmospheric structures across the world, seeded from world_seed."""
        rng = random.Random(self.world_seed ^ 0xA3D7F)
        cx_w = S.WORLD_WIDTH / 2.0
        cy_w = S.WORLD_HEIGHT / 2.0
        min_center_dist = 680.0   # keep clear of player start area
        min_landmark_dist = 420.0  # landmarks don't cluster
        types = [
            "mega_relay", "mega_relay", "mega_relay",
            "colony_ship", "colony_ship", "colony_ship",
            "buried_facility", "buried_facility",
            "satellite_dish", "satellite_dish", "satellite_dish",
        ]
        rng.shuffle(types)
        placed: list[Vector2] = []
        landmarks: list[Landmark] = []
        margin = 280.0  # distance from world edge

        for ltype in types:
            for _attempt in range(120):
                x = rng.uniform(margin, S.WORLD_WIDTH - margin)
                y = rng.uniform(margin, S.WORLD_HEIGHT - margin)
                pos = Vector2(x, y)
                if (pos - Vector2(cx_w, cy_w)).length() < min_center_dist:
                    continue
                too_close = any((pos - p).length() < min_landmark_dist for p in placed)
                if too_close:
                    continue
                placed.append(pos)
                landmarks.append(Landmark(pos, ltype, rng.randint(0, 0x7FFFFFFF)))
                break

        return landmarks

    def _draw_biome_detail(self, draw_off: Vector2) -> None:
        """Deterministic per-cell surface micro-detail: ROCKS pebbles, DUNES ripples."""
        if self.biome_map is None:
            return
        cell = self.biome_map.cell
        left   = max(0, int(self.camera_offset.x // cell) - 1)
        top    = max(0, int(self.camera_offset.y // cell) - 1)
        right  = min(self.biome_map.cols, int((self.camera_offset.x + S.SCREEN_WIDTH)  // cell) + 2)
        bottom = min(self.biome_map.rows, int((self.camera_offset.y + S.SCREEN_HEIGHT) // cell) + 2)
        for cy in range(top, bottom):
            for cx in range(left, right):
                bid = self.biome_map.primary[cy * self.biome_map.cols + cx]
                if bid not in (0, 1):
                    continue
                rx = int(cx * cell + draw_off.x)
                ry = int(cy * cell + draw_off.y)
                seed = (cx * 1009 + cy * 9371) & 0x7FFFFFFF
                if bid == 1:  # ROCKS — scattered dark pebbles
                    n = (seed % 3) + 2
                    for j in range(n):
                        h = (seed >> (j * 5 + 3)) & 0xFFFF
                        px = rx + (h % (cell - 8)) + 4
                        py = ry + ((h >> 6) % (cell - 8)) + 4
                        ew = (seed >> (j * 7 + 1)) % 4 + 3
                        eh = (seed >> (j * 7 + 9)) % 3 + 2
                        pygame.draw.ellipse(self.world, (20, 13, 10), pygame.Rect(px, py, ew, eh))
                else:  # DUNES (bid==0) — faint wind ripple lines
                    n = (seed % 2) + 1
                    for j in range(n):
                        h = (seed >> (j * 7 + 2)) & 0xFFFF
                        lx = rx + (h % (cell - 24)) + 8
                        ly = ry + ((h >> 5) % (cell - 6)) + 3
                        lw = 14 + (h >> 11) % 10
                        dy = j % 2
                        pygame.draw.line(self.world, (92, 28, 20), (lx, ly), (lx + lw, ly + dy), 1)

    def _draw_world(self) -> None:
        self.world.fill((10, 8, 12))
        draw_off = Vector2(-self.camera_offset.x, -self.camera_offset.y)
        if self.biome_map is not None:
            cell = self.biome_map.cell
            left = int(self.camera_offset.x // cell) - 1
            top = int(self.camera_offset.y // cell) - 1
            right = int((self.camera_offset.x + S.SCREEN_WIDTH) // cell) + 2
            bottom = int((self.camera_offset.y + S.SCREEN_HEIGHT) // cell) + 2
            left = 0 if left < 0 else left
            top = 0 if top < 0 else top
            right = self.biome_map.cols if right > self.biome_map.cols else right
            bottom = self.biome_map.rows if bottom > self.biome_map.rows else bottom
            for cy in range(top, bottom):
                for cx in range(left, right):
                    i = cy * self.biome_map.cols + cx
                    bid = self.biome_map.primary[i]
                    col = BIOME_COLORS.get(bid, (10, 8, 12))
                    rx = int(cx * cell + draw_off.x)
                    ry = int(cy * cell + draw_off.y)
                    self.world.fill(col, pygame.Rect(rx, ry, cell + 1, cell + 1))

        self._draw_biome_detail(draw_off)
        self._draw_safe_zones(draw_off)

        # World landmarks — massive structures visible from across the world
        for lm in self.landmarks:
            cam_dist = (self.player.position - lm.position).length()
            lm.draw(self.world, draw_off, cam_dist, self.time_s)

        # Final beacon effects drawn after landmarks
        self._draw_beacon_effects(draw_off)

        self.backdrop.draw_parallax_dust(self.world, self.time_s)

        self.station.draw(self.world, draw_off, self.time_s)

        for r in self.resources:
            if self.station.thermal_scanner:
                rx = int(r.position.x + draw_off.x)
                ry = int(r.position.y + draw_off.y)
                ts = pygame.Surface((28, 28), pygame.SRCALPHA)
                tp = 0.4 + 0.6 * abs(math.sin(self.time_s * 3.2 + r.position.x * 0.01))
                pygame.draw.circle(ts, (255, 180, 60, int(38 * tp)), (14, 14), 13, 1)
                self.world.blit(ts, (rx - 14, ry - 14))
            r.draw(self.world, draw_off, self.time_s)
        for s in self.signals:
            s.draw(self.world, draw_off, self.time_s)

        # Connection beam: dashed line from tower tip to player, color tracks corruption
        for sig in self.signals:
            if not sig.is_connecting:
                continue
            ci = sig.corruption_intensity
            # Beam color interpolates from blue to purple as corruption intensifies
            beam_col = (
                int(75 + (175 - 75) * ci),
                int(185 - (185 - 65) * ci),
                int(255 - (255 - 215) * ci),
            )
            tx = int(sig.position.x + draw_off.x)
            ty = int(sig.position.y + draw_off.y - sig.POLE_H - 2)
            px_c = int(self.player.position.x + draw_off.x)
            py_c = int(self.player.position.y + draw_off.y)
            # Jitter beam endpoint during high corruption
            if ci > 0.45 and random.random() < 0.5:
                jitter_mag = int(ci * 6)
                tx += random.randint(-jitter_mag, jitter_mag)
                ty += random.randint(-jitter_mag, jitter_mag)
            dx_b = px_c - tx
            dy_b = py_c - ty
            length = max(1.0, math.sqrt(dx_b * dx_b + dy_b * dy_b))
            # Shorter dashes during corruption for a crackle effect
            dash_len = max(5, int(9 - ci * 5))
            n_dashes = max(2, int(length / dash_len))
            for i in range(0, n_dashes, 2):
                t0 = i / n_dashes
                t1 = min(1.0, (i + 1) / n_dashes)
                pygame.draw.line(
                    self.world,
                    beam_col,
                    (int(tx + dx_b * t0), int(ty + dy_b * t0)),
                    (int(tx + dx_b * t1), int(ty + dy_b * t1)),
                    1,
                )

        self._draw_bursts(self.world)
        self.micro_fx.draw(self.world, draw_off)
        self.player.draw(self.world, draw_off, self.time_s)

        if self.storm_system.active:
            self.storm_system.draw_overlays(self.world, draw_off)
            self.particles.draw(self.world, True)

        # Atmosphere foreground: surface depth haze
        self.atmosphere.draw_haze(
            self.world,
            self.storm_system.active,
            self.storm_system.intensity,
            self.time_s,
        )

        if self._dev_overlay != 0:
            self._draw_dev_overlay(draw_off)

    def _draw_dev_overlay(self, draw_off: Vector2) -> None:
        if self.biome_map is None:
            return
        if self._dev_overlay == 2:
            cell = self.biome_map.cell
            left = int(self.camera_offset.x // cell) - 1
            top = int(self.camera_offset.y // cell) - 1
            right = int((self.camera_offset.x + S.SCREEN_WIDTH) // cell) + 2
            bottom = int((self.camera_offset.y + S.SCREEN_HEIGHT) // cell) + 2
            left = 0 if left < 0 else left
            top = 0 if top < 0 else top
            right = self.biome_map.cols if right > self.biome_map.cols else right
            bottom = self.biome_map.rows if bottom > self.biome_map.rows else bottom
            for cy in range(top, bottom):
                for cx in range(left, right):
                    i = cy * self.biome_map.cols + cx
                    blend_frac = self.biome_map.blend_t[i]
                    if blend_frac <= 0.01:
                        continue
                    a = int(140 * min(1.0, blend_frac))
                    o = pygame.Surface((cell, cell), pygame.SRCALPHA)
                    o.fill((200, 200, 255, a))
                    self.world.blit(o, (int(cx * cell + draw_off.x), int(cy * cell + draw_off.y)))
        elif self._dev_overlay == 3:
            for r in self.resources:
                pygame.draw.circle(
                    self.world,
                    (255, 255, 255),
                    (int(r.position.x + draw_off.x), int(r.position.y + draw_off.y)),
                    2,
                )

        txt = self._dev_font.render(
            f"DEV[F1]: {self._dev_overlay}  seed={self.world_seed}",
            True,
            (230, 230, 230),
        )
        self.world.blit(txt, (10, S.SCREEN_HEIGHT - 22))

    def _compose_frame(self, for_menu: bool = False) -> None:
        """Render world to back buffer and apply post-processing. for_menu=True suppresses storm shake and glitch."""
        self._draw_world()
        storm_ox, storm_oy = (0, 0)
        if self.storm_system.active and not for_menu:
            storm_ox, storm_oy = self.screen_fx.storm_shake(self.storm_system.intensity)
        ox = self.screen_fx.shake_x + storm_ox
        oy = self.screen_fx.shake_y + storm_oy
        if self.storm_system.active and not for_menu and self.storm_system.wind.length_squared() > 1e-6:
            n = min(1.0, self.storm_system.intensity / max(S.STORM_INTENSITY_MAX, 0.01))
            push = self.storm_system.wind * (10.0 * (n**0.9) * float(getattr(self.storm_system, "_wind_mul_current", 1.0)))
            ox += push.x
            oy += push.y
        ox = int(round(ox))
        oy = int(round(oy))

        self.screen.fill(S.COLOR_BG)
        self.screen.blit(self.world, (ox, oy))

        sig_n = self.player.signal / 100.0 if not for_menu else 1.0
        g = 0.0
        if sig_n < S.GLITCH_SIGNAL_THRESHOLD:
            g = (S.GLITCH_SIGNAL_THRESHOLD - sig_n) / S.GLITCH_SIGNAL_THRESHOLD

        self.screen_fx.apply(
            self.screen,
            sig_n,
            self.storm_system.active and not for_menu,
            self.storm_system.intensity,
            g + float(self._biome_params.get("glitch_add", 0.0)),
            float(self._biome_params.get("vignette_mul", 1.0)),
            storm_flash_strength=self.storm_system.flash_strength if not for_menu else 0.0,
        )

    def _fade_overlay(self, alpha: float) -> None:
        if alpha <= 0.01:
            return
        a = int(clamp(alpha, 0.0, 1.0) * 255)
        o = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        o.fill((0, 0, 0, a))
        self.screen.blit(o, (0, 0))

    def draw(self) -> None:
        if self.states.is_playing():
            self._compose_frame(False)
            self.hud.draw(
                self.screen,
                self.player.energy,
                self.player.signal,
                {
                    "salvage": self.station.salvage,
                    "data":    self.station.data_fragments,
                    "relay":   self.station.relay_components,
                    "ancient": self.station.ancient_tech,
                },
                self._biome_name,
                storm_state=self.storm_system.state,
                signal_connected=self._signal_connected,
                connect_key=self._connect_key,
                status_message=self._status_message,
                status_color=self._status_color,
            )
            if self._station_ui_open:
                self._station_ui.draw(self.screen, self.station, self.time_s)
            elif self._terminal_open:
                self._terminal_ui.draw(
                    self.screen, self._terminal, self._make_terminal_gs(), self.time_s
                )
            else:
                # Endgame overlays (only while gameplay is live, no UI open)
                self.endgame_ui.draw_notifications(self.screen)
                if self.progression.countdown_active:
                    self.endgame_ui.draw_countdown(
                        self.screen, self.progression.countdown_remaining, self.time_s
                    )
                    self.endgame_ui.draw_return_prompt(self.screen, self.time_s)
                elif self._beacon_prompt:
                    self.endgame_ui.draw_beacon_prompt(self.screen, self.time_s)
            self._fade_overlay(self._intro_fade)

        elif self.states.is_cinematic():
            self._compose_frame(False)
            progress = clamp(self._cinematic_t / S.CINEMATIC_DURATION, 0.0, 1.0)
            self.endgame_ui.draw_cinematic(self.screen, progress, self.time_s)

        elif self.states.is_ending():
            self._compose_frame(True)
            self.ending_system.draw(self.screen, self.time_s)

        elif self.states.is_menu() or self.states.is_info():
            self._compose_frame(True)
            self.hud.draw(self.screen, 100.0, 100.0, {}, "")
            self.screens.draw(self.screen, self.states.state)

        else:
            self._compose_frame(False)
            self.hud.draw(
                self.screen,
                self.player.energy,
                self.player.signal,
                {
                    "salvage": self.station.salvage,
                    "data":    self.station.data_fragments,
                    "relay":   self.station.relay_components,
                    "ancient": self.station.ancient_tech,
                },
                self._biome_name,
            )
            if self.states.is_game_over():
                self._fade_overlay(self._outro_fade * 0.92)
            self.screens.draw(self.screen, self.states.state)

        pygame.display.flip()
