
from enum import Enum, auto


class GameState(Enum):
    MENU = auto()
    INFO = auto()
    PLAYING = auto()
    WIN = auto()
    EVACUATION_WIN = auto()
    CINEMATIC = auto()
    ENDING = auto()
    GAME_OVER = auto()


class StateManager:


    def __init__(self) -> None:
        self._state = GameState.MENU

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def game_state(self) -> str:

        return {
            GameState.MENU: "menu",
            GameState.INFO: "info",
            GameState.PLAYING: "game",
            GameState.WIN: "win",
            GameState.EVACUATION_WIN: "evacuation_win",
            GameState.CINEMATIC: "cinematic",
            GameState.ENDING: "ending",
            GameState.GAME_OVER: "game_over",
        }[self._state]

    def set_state(self, new_state: GameState) -> None:
        self._state = new_state

    def is_menu(self) -> bool:
        return self._state == GameState.MENU

    def is_info(self) -> bool:
        return self._state == GameState.INFO

    def is_playing(self) -> bool:
        return self._state == GameState.PLAYING

    def is_win(self) -> bool:
        return self._state == GameState.WIN

    def is_game_over(self) -> bool:
        return self._state == GameState.GAME_OVER

    def is_cinematic(self) -> bool:
        return self._state == GameState.CINEMATIC

    def is_evacuation_win(self) -> bool:
        return self._state == GameState.EVACUATION_WIN

    def is_ending(self) -> bool:
        return self._state == GameState.ENDING
