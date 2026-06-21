"""Replay viewer presenter — turn-first navigation + event drilldown (Slice #15).

The capstone of the replay feature. Mirrors the Hearthstone Access (HSA)
keymap from ADR-0003 exactly, including its friendly/opponent asymmetry.

Model
-----
Input is a ReplayState: an ordered Tuple[GameState, ...]. From it we build a
list of *transitions* — (prev, curr) pairs whose diff() yields the meaningful
GameEvents — and group them by post-state turn:

    transitions = [(None, states[0])]
                + [(states[i], states[i+1]) for i in range(len(states)-1)]

    turn_numbers = sorted distinct post_state.turn

The TURN CURSOR indexes ``turn_numbers`` and starts at 0 (the first turn).
``next_turn``/``prev_turn`` step it (clamped). For a turn T:

    end_of_turn_state = curr of the LAST transition with post_state.turn == T
    events_for_turn(T) = concatenation of each such transition's diff events,
                         each paired with its post_state.

RESOLVED STATE
--------------
Every ``get_zone_items`` reads from a single *resolved* GameState so all zones
reflect the same moment:

  * If an event is selected in the events ("Y") zone, the resolved state is
    that event's post_state.
  * Otherwise (a turn is selected, no event) the resolved state is the
    end-of-turn state of the current turn.

ZONES + HSA KEYMAP
------------------
See ADR-0003. List zones are activated by letter keys; left/right step items;
up/down step detail lines; number keys 1-10 positionally jump. Speak-only keys
(A/Shift+A/Shift+D/R/Shift+R) are drive-by queries that NEVER change the active
zone. pagedown/pageup step turns.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence, Tuple

from stonereader.models.game_state import GameEntity, GameState, PlayedCard
from stonereader.models.replay import ReplayState
from stonereader.presenters.base import BasePresenter, ZoneNavigationMixin
from stonereader.services._diff import diff
from stonereader.services._events import GameEvent
from stonereader.speech_service import SpeechService

# -------------------------------- Zone names --------------------------------

_YOUR_BOARD = "your_board"
_OPP_BOARD = "opponent_board"
_YOUR_HAND = "your_hand"
_OPP_HAND = "opponent_hand"
_YOUR_SECRETS = "your_secrets"
_OPP_SECRETS = "opponent_secrets"
_YOUR_HERO = "your_hero"
_OPP_HERO = "opponent_hero"
_YOUR_WEAPON = "your_weapon"
_OPP_WEAPON = "opponent_weapon"
_YOUR_DECK = "your_deck"
_EVENTS = "events"
_YOUR_PLAYED = "your_played"
_OPP_PLAYED = "opponent_played"
_YOUR_DRAWN = "your_drawn"
_OPP_DRAWN = "opponent_drawn"

# Ordered for _init_navigation (first entry is the default active zone).
_ZONE_ORDER = [
    _YOUR_BOARD,
    _OPP_BOARD,
    _YOUR_HAND,
    _OPP_HAND,
    _YOUR_SECRETS,
    _OPP_SECRETS,
    _YOUR_HERO,
    _OPP_HERO,
    _YOUR_WEAPON,
    _OPP_WEAPON,
    _YOUR_DECK,
    _EVENTS,
    _YOUR_PLAYED,
    _OPP_PLAYED,
    _YOUR_DRAWN,
    _OPP_DRAWN,
]

_ZONE_LABELS = {
    _YOUR_BOARD: "Your board",
    _OPP_BOARD: "Opponent board",
    _YOUR_HAND: "Your hand",
    _OPP_HAND: "Opponent hand",
    _YOUR_SECRETS: "Your secrets",
    _OPP_SECRETS: "Opponent secrets",
    _YOUR_HERO: "Your hero",
    _OPP_HERO: "Opponent hero",
    _YOUR_WEAPON: "Your weapon",
    _OPP_WEAPON: "Opponent weapon",
    _YOUR_DECK: "Your deck",
    _EVENTS: "Events",
    _YOUR_PLAYED: "Your played",
    _OPP_PLAYED: "Opponent played",
    _YOUR_DRAWN: "Your drawn",
    _OPP_DRAWN: "Opponent drawn",
}


class ReplayViewerPresenter(ZoneNavigationMixin, BasePresenter):
    """Turn-first replay navigation with event drilldown and the HSA keymap."""

    def __init__(
        self,
        speech: SpeechService,
        replay: ReplayState,
        card_db: Any = None,
    ) -> None:
        super().__init__(speech)
        self._replay = replay
        self._card_db = card_db

        # Build transitions: [(None, s0), (s0, s1), (s1, s2), ...].
        states = replay.states
        transitions: List[Tuple[Optional[GameState], GameState]] = []
        if states:
            transitions.append((None, states[0]))
            for i in range(len(states) - 1):
                transitions.append((states[i], states[i + 1]))
        self._transitions = transitions

        # Group by post-state turn; precompute end-of-turn states and events.
        # events_by_turn[T] = list of (GameEvent, post_state) pairs.
        self._turn_numbers: List[int] = sorted(
            {curr.turn for _prev, curr in transitions}
        )
        self._end_of_turn: dict[int, GameState] = {}
        self._events_by_turn: dict[int, List[Tuple[GameEvent, GameState]]] = {}
        for prev, curr in transitions:
            t = curr.turn
            self._end_of_turn[t] = curr  # last writer wins => end-of-turn state
            evs = self._events_by_turn.setdefault(t, [])
            for ev in diff(prev, curr):
                evs.append((ev, curr))

        # Turn cursor indexes _turn_numbers; starts at the first turn.
        self._turn_index = 0
        # Event cursor: -1 means "no event selected" (turn-level resolution).
        self._event_index = -1

        self._init_navigation(_ZONE_ORDER)

        # View callback (optional).
        self._on_state_changed: Optional[Callable[[], None]] = None

        # Opening announcement.
        self._announce_turn_entry()

    # ----------------------------------------------------- Turn helpers

    def current_turn_number(self) -> int:
        """The in-game turn number currently selected (public accessor)."""
        if not self._turn_numbers:
            return 0
        idx = max(0, min(self._turn_index, len(self._turn_numbers) - 1))
        return self._turn_numbers[idx]

    def _current_turn(self) -> int:
        return self.current_turn_number()

    def _events_for_current_turn(self) -> List[Tuple[GameEvent, GameState]]:
        return self._events_by_turn.get(self._current_turn(), [])

    def _resolved_state(self) -> Optional[GameState]:
        """The GameState all zones read from.

        If an event is selected in the events zone, use that event's
        post_state; otherwise use the current turn's end-of-turn state.
        """
        if not self._turn_numbers:
            return None
        events = self._events_for_current_turn()
        if self._current_zone == _EVENTS and 0 <= self._event_index < len(events):
            return events[self._event_index][1]
        return self._end_of_turn.get(self._current_turn())

    # ----------------------------------------------------- Temporal navigation

    def next_turn(self) -> None:
        if not self._turn_numbers:
            return
        self._turn_index = min(self._turn_index + 1, len(self._turn_numbers) - 1)
        self._event_index = -1
        self._zone_cursors[_EVENTS] = 0
        self._announce_turn_entry()
        self._notify_view()

    def prev_turn(self) -> None:
        if not self._turn_numbers:
            return
        self._turn_index = max(self._turn_index - 1, 0)
        self._event_index = -1
        self._zone_cursors[_EVENTS] = 0
        self._announce_turn_entry()
        self._notify_view()

    def jump_to_turn_number(self, turn_number: int) -> None:
        """Public test/app helper: select the turn with the given number."""
        if turn_number in self._turn_numbers:
            self._turn_index = self._turn_numbers.index(turn_number)
            self._event_index = -1
            self._zone_cursors[_EVENTS] = 0
            self._notify_view()

    def _announce_turn_entry(self) -> None:
        turn = self._current_turn()
        state = self._end_of_turn.get(turn)
        if state is None:
            self._speech.speak(f"Turn {turn}")
            return
        active = "your turn" if state.active_player_id == 1 else "opponent's turn"
        n_events = len(self._events_by_turn.get(turn, []))
        event_word = "event" if n_events == 1 else "events"
        self._speech.speak(f"Turn {turn}, {active}, {n_events} {event_word}.")

    # ----------------------------------------------------- Zone items

    def get_zone_items(self, zone_name: str) -> Sequence[Any]:
        state = self._resolved_state()
        if state is None:
            return []
        if zone_name == _YOUR_BOARD:
            return list(state.player_board)
        if zone_name == _OPP_BOARD:
            return list(state.opponent_board)
        if zone_name == _YOUR_HAND:
            return list(state.player_hand)
        if zone_name == _OPP_HAND:
            return list(state.opponent_hand)
        if zone_name == _YOUR_SECRETS:
            return list(state.player_secrets)
        if zone_name == _OPP_SECRETS:
            return list(state.opponent_secrets)
        if zone_name == _YOUR_HERO:
            return [state.player_hero]
        if zone_name == _OPP_HERO:
            return [state.opponent_hero]
        if zone_name == _YOUR_WEAPON:
            return [state.player_weapon] if state.player_weapon is not None else []
        if zone_name == _OPP_WEAPON:
            return [state.opponent_weapon] if state.opponent_weapon is not None else []
        if zone_name == _YOUR_DECK:
            return list(state.player_deck)
        if zone_name == _EVENTS:
            return [ev for ev, _post in self._events_for_current_turn()]
        if zone_name == _YOUR_PLAYED:
            return list(state.player_played)
        if zone_name == _OPP_PLAYED:
            return list(state.opponent_played)
        if zone_name == _YOUR_DRAWN:
            return list(state.player_drawn)
        if zone_name == _OPP_DRAWN:
            return list(state.opponent_drawn)
        return []

    # ----------------------------------------------------- Speech formatting

    def _format_item_speech(self, item: Any, position: int, total: int) -> str:
        suffix = f", {position} of {total}"
        zone = self._current_zone

        if zone == _OPP_HAND and item is None:
            return "Hidden card" + suffix

        if isinstance(item, GameEntity):
            return self._format_entity(item, zone) + suffix

        if isinstance(item, PlayedCard):
            return f"Turn {item.turn}, {item.name}" + suffix

        if isinstance(item, GameEvent):
            return self._format_event(item) + suffix

        # Hero is the only remaining shape we surface as a list item.
        name = getattr(item, "name", None)
        if name is not None:
            hero_class = getattr(item, "hero_class", "")
            if hero_class:
                return f"{name}, {hero_class.title()}" + suffix
            return f"{name}" + suffix

        return super()._format_item_speech(item, position, total)

    def _format_entity(self, ent: GameEntity, zone: str) -> str:
        name = ent.name or "Hidden card"
        if ent.card_type == "WEAPON":
            return (
                f"{name}, {ent.current_attack} attack, {ent.current_health} durability"
            )
        if ent.card_type == "MINION":
            return f"{name}, {ent.current_attack} attack, {ent.current_health} health"
        # Spells/secrets/etc. — name only.
        return name

    def _format_event(self, ev: GameEvent) -> str:
        # Human-readable, drilldown-friendly description of the event.
        kind = type(ev).__name__
        name = getattr(ev, "name", "")
        if name:
            return f"{kind}: {name}"
        return kind

    # ----------------------------------------------------- Zone activation

    def _activate_list_zone(self, zone_name: str) -> None:
        label = _ZONE_LABELS.get(zone_name, zone_name)
        self.navigate_to_zone(zone_name, label)
        self._notify_view()

    def _activate_events_zone(self) -> None:
        self._current_zone = _EVENTS
        self._detail_cursor = 0
        self._orienting_counts.clear()
        self._event_index = -1
        events = self.get_zone_items(_EVENTS)
        label = _ZONE_LABELS[_EVENTS]
        if not events:
            self._speech.speak(f"{label}: empty")
            self._notify_view()
            return
        cursor = self._zone_cursors.get(_EVENTS, 0)
        cursor = max(0, min(cursor, len(events) - 1))
        self._zone_cursors[_EVENTS] = cursor
        self._event_index = cursor
        text = (
            f"{label}, "
            f"{self._format_item_speech(events[cursor], cursor + 1, len(events))}"
        )
        self._speech.speak(text)
        self._notify_view()

    # ----------------------------------------------------- Nav overrides

    def move_in_zone(self, delta: int) -> None:
        super().move_in_zone(delta)
        if self._current_zone == _EVENTS:
            # Keep the event cursor in sync so the resolved state follows.
            self._event_index = self._zone_cursors.get(_EVENTS, 0)
        self._notify_view()

    def jump_to_position(self, pos: int) -> None:
        super().jump_to_position(pos)
        if self._current_zone == _EVENTS:
            self._event_index = self._zone_cursors.get(_EVENTS, 0)
        self._notify_view()

    def jump_to_first(self) -> None:
        super().jump_to_first()
        if self._current_zone == _EVENTS:
            self._event_index = self._zone_cursors.get(_EVENTS, 0)
        self._notify_view()

    def jump_to_last(self) -> None:
        super().jump_to_last()
        if self._current_zone == _EVENTS:
            self._event_index = self._zone_cursors.get(_EVENTS, 0)
        self._notify_view()

    def read_detail_lines(self, item: Any, direction: int = 1) -> None:
        # Heroes carry their own detail-line shape (name/health/class/power).
        from stonereader.models.game_state import Hero

        if isinstance(item, Hero):
            self._read_hero_detail(item, direction)
            return
        super().read_detail_lines(item, direction)

    def _read_hero_detail(self, hero: Any, direction: int) -> None:
        lines = [
            hero.name,
            f"{hero.health} health, {hero.armor} armor",
            (hero.hero_class or "").title() or "Unknown class",
            f"Hero power: {hero.hero_power}" if hero.hero_power else "No hero power",
        ]
        self._detail_cursor = max(
            0, min(self._detail_cursor + direction, len(lines) - 1)
        )
        self._speech.speak(lines[self._detail_cursor])

    def _read_current_detail(self, direction: int) -> None:
        item = self._current_item()
        if item is not None:
            self.read_detail_lines(item, direction)

    # ----------------------------------------------------- Speak-only queries

    def announce_your_mana(self) -> None:
        state = self._resolved_state()
        if state is None:
            self._speech.speak("No game state.")
            return
        self._speech.speak(f"Your mana, {state.player_mana} of {state.player_max_mana}")

    def announce_opponent_mana(self) -> None:
        state = self._resolved_state()
        if state is None:
            self._speech.speak("No game state.")
            return
        self._speech.speak(
            f"Opponent mana, {state.opponent_mana} of {state.opponent_max_mana}"
        )

    def announce_opponent_deck_count(self) -> None:
        state = self._resolved_state()
        if state is None:
            self._speech.speak("No game state.")
            return
        self._speech.speak(f"Opponent deck, {state.opponent_deck_count} cards")

    def announce_your_hero_power(self) -> None:
        state = self._resolved_state()
        if state is None:
            self._speech.speak("No game state.")
            return
        power = state.player_hero.hero_power or "none"
        self._speech.speak(f"Your hero power, {power}")

    def announce_opponent_hero_power(self) -> None:
        state = self._resolved_state()
        if state is None:
            self._speech.speak("No game state.")
            return
        power = state.opponent_hero.hero_power or "none"
        self._speech.speak(f"Opponent hero power, {power}")

    # ----------------------------------------------------- View callback

    def set_on_state_changed(self, callback: Callable[[], None]) -> None:
        self._on_state_changed = callback

    def _notify_view(self) -> None:
        if self._on_state_changed is not None:
            self._on_state_changed()

    # ----------------------------------------------------- Key map

    def get_key_map(self) -> dict[str, Callable[[], None]]:
        key_map: dict[str, Callable[[], None]] = {
            # Item / detail navigation.
            "left": lambda: self.move_in_zone(-1),
            "right": lambda: self.move_in_zone(1),
            "down": lambda: self._read_current_detail(1),
            "up": lambda: self._read_current_detail(-1),
            "home": self.jump_to_first,
            "end": self.jump_to_last,
            # Temporal navigation.
            "pagedown": self.next_turn,
            "pageup": self.prev_turn,
            # List zones (HSA letters, ADR-0003).
            "b": lambda: self._activate_list_zone(_YOUR_BOARD),
            "g": lambda: self._activate_list_zone(_OPP_BOARD),
            "c": lambda: self._activate_list_zone(_YOUR_HAND),
            "shift+c": lambda: self._activate_list_zone(_OPP_HAND),
            "s": lambda: self._activate_list_zone(_YOUR_SECRETS),
            "shift+s": lambda: self._activate_list_zone(_OPP_SECRETS),
            "v": lambda: self._activate_list_zone(_YOUR_HERO),
            "f": lambda: self._activate_list_zone(_OPP_HERO),
            "w": lambda: self._activate_list_zone(_YOUR_WEAPON),
            "shift+w": lambda: self._activate_list_zone(_OPP_WEAPON),
            "d": lambda: self._activate_list_zone(_YOUR_DECK),
            "y": self._activate_events_zone,
            "p": lambda: self._activate_list_zone(_YOUR_PLAYED),
            "shift+p": lambda: self._activate_list_zone(_OPP_PLAYED),
            "n": lambda: self._activate_list_zone(_YOUR_DRAWN),
            "shift+n": lambda: self._activate_list_zone(_OPP_DRAWN),
            # Speak-only drive-by queries (never change the active zone).
            "a": self.announce_your_mana,
            "shift+a": self.announce_opponent_mana,
            "shift+d": self.announce_opponent_deck_count,
            "r": self.announce_your_hero_power,
            "shift+r": self.announce_opponent_hero_power,
        }
        # Positional jumps 1-9, plus 0 -> position 10.
        for digit in range(1, 10):
            key_map[str(digit)] = lambda d=digit: self.jump_to_position(d)
        key_map["0"] = lambda: self.jump_to_position(10)
        return key_map
