"""Turn-steppable, sixteen-zone Replay Viewer Surface."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from stonereader.models.game_state import GameEntity, GameState, Hero, PlayedCard
from stonereader.models.replay import ReplayState
from stonereader.services._event_phrases import phrase
from stonereader.services._events import (
    AttackStarted,
    CardDrawn,
    CardPlayed,
    CardRemoved,
    CardRevealed,
    GameEnded,
    GameEvent,
    MinionDied,
    SecretPlayed,
    SecretRevealed,
    TurnChanged,
)
from stonereader.surfaces._game_audio import CardAudioIndex, open_sounds_for_card
from stonereader.surfaces._replay_turns import TurnView, turns
from stonereader.surfaces._zone_format import (
    CardItem,
    card_detail_lines,
    card_name,
    card_title,
    hero_detail_lines,
    hero_title,
)
from stonereader.surfaces.sounds_menu import SoundsMenuHolder
from stonereader.ui.announcer import Announcer
from stonereader.ui.builder import build_active_surface
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import Command, Slot
from stonereader.ui.surface import Binding, SurfaceSpec, WidgetType, ZoneSpec

class CurrentReplay:
    """App-owned selected-replay seam shared by Replays and Replay Viewer."""

    def __init__(self) -> None:
        self._replay: ReplayState | None = None
        self._reset_viewer: Callable[[], None] | None = None

    def set(self, replay: ReplayState) -> None:
        self._replay = replay
        if self._reset_viewer is not None:
            # A different replay is new content, not a revisit. Found-as-left
            # still governs zone cursors while navigating one replay session.
            self._reset_viewer()

    def get(self) -> ReplayState:
        if self._replay is None:
            raise RuntimeError("No current replay has been selected")
        return self._replay

    def bind_viewer_reset(self, reset: Callable[[], None]) -> None:
        self._reset_viewer = reset


@dataclass(frozen=True)
class _EventItem:
    event: GameEvent
    title: str
    source_card_id: str | None
    source_title: str | None


class ReplayAudioIndex(CardAudioIndex, Protocol):
    def event_clip(self, card_id: str | None, kind: str) -> str | None: ...

    def decode(self, clip_key: str) -> bytes: ...


class ReplayAudioPlayer(Protocol):
    def play(self, wav_bytes: bytes) -> None: ...


def build_replay_viewer(
    announcer: Announcer,
    universal_bindings: list[tuple[Chord, Command]],
    nav: NavigationController,
    current_replay: CurrentReplay,
    *,
    audio_index: ReplayAudioIndex | None = None,
    player: ReplayAudioPlayer | None = None,
    replay_autoplay: Callable[[], bool] = lambda: True,
    sounds: SoundsMenuHolder | None = None,
) -> ActiveSurface:
    """Build the lazy singleton Replay Viewer for the selected replay."""
    turn_index = 0
    cached_replay: ReplayState | None = None
    cached_turns: list[TurnView] = []
    engine: HorizontalListEngine | None = None

    def reset_for_new_replay() -> None:
        nonlocal turn_index, cached_replay, cached_turns
        turn_index = 0
        cached_replay = None
        cached_turns = []

    def turn_views() -> list[TurnView]:
        nonlocal cached_replay, cached_turns
        replay = current_replay.get()
        if replay is not cached_replay:
            cached_replay = replay
            cached_turns = turns(replay)
        return cached_turns

    def current_turn() -> TurnView:
        nonlocal turn_index
        values = turn_views()
        if not values:
            raise RuntimeError("The current replay has no turns")
        turn_index = min(turn_index, len(values) - 1)
        return values[turn_index]

    def state() -> GameState:
        return current_turn().state

    def context_label() -> str:
        if engine is None:
            raise RuntimeError("Replay Viewer engine is not active")
        turn = current_turn()
        side = "yours" if turn.is_friendly else "opponent's"
        return f"Turn {turn.number}, {side}, {engine.current_zone().label}"

    def card_items(attribute: str) -> Callable[[], list[CardItem]]:
        return lambda: list(getattr(state(), attribute))

    def singleton(attribute: str) -> Callable[[], list[CardItem]]:
        def items() -> list[CardItem]:
            item = getattr(state(), attribute)
            return [] if item is None else [item]

        return items

    def player_hero_details(hero: Hero) -> list[str]:
        current = state()
        return hero_detail_lines(
            hero,
            current.player_weapon,
            len(current.player_secrets),
        )

    def opponent_hero_details(hero: Hero) -> list[str]:
        current = state()
        return hero_detail_lines(
            hero,
            current.opponent_weapon,
            len(current.opponent_secrets),
        )

    def event_items() -> list[_EventItem]:
        current = current_turn()
        values: list[_EventItem] = []
        for event in current.events:
            title = phrase(event, current.state)
            if title is not None:
                source_card_id, source_title = _event_source(event, current.state)
                values.append(
                    _EventItem(
                        event,
                        title,
                        source_card_id,
                        source_title,
                    )
                )
        return values

    def step_turn(delta: int) -> None:
        nonlocal turn_index
        values = turn_views()
        if not values or engine is None:
            return
        target = min(max(turn_index + delta, 0), len(values) - 1)
        if target == turn_index:
            item = engine.current_item()
            if item is None:
                announcer.context_empty(context_label())
            else:
                # A clamped coarse-axis step is a boundary, so it repeats the
                # current bare Title line rather than pretending to re-land.
                announcer.boundary(engine.current_zone().title(item))
            return
        turn_index = target
        engine.on_landing()

    def query(subject: str, value: str) -> None:
        announcer.query(subject, value)

    def listen() -> None:
        if engine is None or audio_index is None or sounds is None:
            raise RuntimeError("Replay Viewer game-audio dependencies are not active")
        zone_id = engine.current_zone().zone_id
        current = engine.current_item()
        if zone_id == "events" and isinstance(current, _EventItem):
            open_sounds_for_card(
                announcer,
                nav,
                audio_index,
                sounds,
                card_id=current.source_card_id,
                card_name=current.source_title or "",
                title=current.source_title or "No card focused",
            )
            return
        card_zone_ids = {
            "your_board",
            "opponent_board",
            "your_hand",
            "opponent_hand",
            "your_secrets",
            "opponent_secrets",
            "your_weapon",
            "opponent_weapon",
            "your_deck",
            "your_played",
            "opponent_played",
            "your_drawn",
            "opponent_drawn",
        }
        if zone_id not in card_zone_ids or current is None:
            announcer.noop("No card focused")
            return
        card_id = getattr(current, "card_id", "")
        name = card_name(current)
        open_sounds_for_card(
            announcer,
            nav,
            audio_index,
            sounds,
            card_id=card_id or None,
            card_name=name,
            title=engine.current_zone().title(current),
        )

    zones = [
        _card_zone("your_board", "Your board", "b", "B: your minions", card_items("player_board")),
        _card_zone("opponent_board", "Opponent board", "g", "G: opponent minions", card_items("opponent_board")),
        _card_zone("your_hand", "Your hand", "c", "C: your hand", card_items("player_hand")),
        _card_zone("opponent_hand", "Opponent hand", "c", "Shift+C: opponent hand", card_items("opponent_hand"), shift=True),
        _card_zone("your_secrets", "Your secrets", "s", "S: your secrets", card_items("player_secrets")),
        _card_zone("opponent_secrets", "Opponent secrets", "s", "Shift+S: opponent secrets", card_items("opponent_secrets"), shift=True),
        ZoneSpec("your_hero", "Your hero", lambda: [state().player_hero], hero_title, player_hero_details, Chord("v"), "V: your hero"),
        ZoneSpec("opponent_hero", "Opponent hero", lambda: [state().opponent_hero], hero_title, opponent_hero_details, Chord("f"), "F: opponent hero"),
        # An absent weapon is deliberately an empty zone: the engine composes
        # its constant "No {label} on this screen" phrase from this label.
        _card_zone("your_weapon", "Your weapon", "w", "W: your weapon", singleton("player_weapon")),
        _card_zone("opponent_weapon", "Opponent weapon", "w", "Shift+W: opponent weapon", singleton("opponent_weapon"), shift=True),
        _card_zone("your_deck", "Your deck", "d", "D: jump to Remaining Deck", card_items("player_deck")),
        _card_zone("your_played", "Your played", "p", "P: cards you played", card_items("player_played"), with_turn=True),
        _card_zone("opponent_played", "Opponent played", "p", "Shift+P: cards your opponent played", card_items("opponent_played"), shift=True, with_turn=True),
        _card_zone("your_drawn", "Your drawn", "n", "N: cards you drew", card_items("player_drawn"), with_turn=True),
        _card_zone("opponent_drawn", "Opponent drawn", "n", "Shift+N: cards your opponent drew", card_items("opponent_drawn"), shift=True, with_turn=True),
        ZoneSpec(
            "events",
            "Events",
            event_items,
            lambda item: item.title,
            lambda item: [
                f"Turn {item.event.turn}",
                *([item.source_title] if item.source_title is not None else []),
            ],
            Chord("y"),
            "Y: the game's events",
        ),
    ]

    bindings = [
        Binding(Chord("a"), Command("replay.query_mana", "A: how much mana you have", lambda: query("Your mana", f"{state().player_mana} of {state().player_max_mana}"))),
        Binding(Chord("a", shift=True), Command("replay.query_opponent_mana", "Shift+A: how much mana your opponent has", lambda: query("Opponent mana", f"{state().opponent_mana} of {state().opponent_max_mana}"))),
        Binding(Chord("d", shift=True), Command("replay.query_opponent_deck", "Shift+D: how many cards are in your opponent's deck", lambda: query("Opponent deck", f"{state().opponent_deck_count} cards"))),
        Binding(Chord("r"), Command("replay.query_hero_power", "R: your hero power", lambda: query("Your hero power", state().player_hero.hero_power or "No hero power"))),
        Binding(Chord("r", shift=True), Command("replay.query_opponent_hero_power", "Shift+R: your opponent's hero power", lambda: query("Opponent hero power", state().opponent_hero.hero_power or "No hero power"))),
    ]
    bindings.extend(
        Binding(
            Chord(str(position)),
            Command(
                f"replay.position.{position}",
                "1 to 9: jump to that position in the list",
                lambda position=position: _require_engine(engine).jump_to_position(position),
            ),
        )
        for position in range(1, 10)
    )
    bindings.append(
        Binding(
            Chord("0"),
            Command(
                "replay.position.10",
                "0: jump to the tenth item",
                lambda: _require_engine(engine).jump_to_position(10),
            ),
        )
    )

    forward_turn = Command(
        "replay.next_turn",
        "Page Down: go to the next turn",
        lambda: step_turn(1),
    )
    reverse_turn = Command(
        "replay.previous_turn",
        "Page Down: go to the next turn",
        lambda: step_turn(-1),
    )
    spec = SurfaceSpec(
        "Replay Viewer",
        WidgetType.HORIZONTAL_LIST,
        context_label=context_label,
        zones=zones,
        bindings=bindings,
        slot_reverse_fills={Slot.COARSE_AXIS: reverse_turn},
        slot_fills={
            Slot.COARSE_AXIS: forward_turn,
            **(
                {
                    Slot.LISTEN: Command(
                        "replay.listen",
                        "L: listen to this card's sounds",
                        listen,
                    )
                }
                if audio_index is not None and sounds is not None
                else {}
            ),
        },
        slot_noops=(
            {}
            if audio_index is not None and sounds is not None
            else {Slot.LISTEN: "Game audio is not available"}
        ),
    )
    surface = build_active_surface(spec, announcer, universal_bindings, nav)
    if not isinstance(surface.engine, HorizontalListEngine):
        raise TypeError("Replay Viewer requires a horizontal-list engine")
    engine = surface.engine

    last_transition = (engine.current_zone().zone_id, engine.items_snapshot()[1])

    def autoplay_on_cursor_transition() -> None:
        nonlocal last_transition
        if engine is None:
            return
        transition = (engine.current_zone().zone_id, engine.items_snapshot()[1])
        if transition == last_transition:
            return
        last_transition = transition
        if (
            transition[0] != "events"
            or audio_index is None
            or player is None
            or not replay_autoplay()
            or audio_index.status != "ready"
        ):
            return
        current = engine.current_item()
        if not isinstance(current, _EventItem):
            return
        kind = _event_audio_kind(current.event)
        if kind is None:
            return
        clip_key = audio_index.event_clip(current.source_card_id, kind)
        if clip_key is None:
            return
        wav_bytes = audio_index.decode(clip_key)
        if wav_bytes:
            player.play(wav_bytes)

    engine.subscribe(autoplay_on_cursor_transition)
    current_replay.bind_viewer_reset(reset_for_new_replay)
    return surface


def _card_zone(
    zone_id: str,
    label: str,
    key: str,
    help_phrase: str,
    items: Callable[[], list[CardItem]],
    *,
    shift: bool = False,
    with_turn: bool = False,
) -> ZoneSpec:
    return ZoneSpec(
        zone_id,
        label,
        items,
        lambda item: card_title(item, with_turn=with_turn),
        card_detail_lines,
        Chord(key, shift=shift),
        help_phrase,
    )

def _event_source(
    event: GameEvent,
    state: GameState,
) -> tuple[str | None, str | None]:
    entity_id: int | None = None
    if isinstance(event, AttackStarted):
        entity_id = event.attacker_entity_id
    elif isinstance(
        event,
        (CardDrawn, CardPlayed, CardRevealed, CardRemoved, MinionDied),
    ):
        entity_id = event.entity_id
    direct_card_id = getattr(event, "card_id", "") or None
    direct_name = getattr(event, "name", "") or None
    if entity_id is not None:
        for item in _state_cards(state):
            if item is not None and item.entity_id == entity_id:
                return item.card_id or direct_card_id, card_name(item) or direct_name
    base_card = getattr(event, "base_card", None)
    if base_card is not None:
        direct_name = direct_name or base_card.name
    return direct_card_id, direct_name


def _event_audio_kind(event: GameEvent) -> str | None:
    if isinstance(event, CardPlayed):
        return "play"
    if isinstance(event, AttackStarted):
        return "attack"
    if isinstance(event, MinionDied):
        return "minion_death"
    if isinstance(event, CardDrawn):
        return "draw"
    if isinstance(event, TurnChanged):
        return "turn"
    if isinstance(event, (SecretPlayed, SecretRevealed)):
        return "secret"
    if isinstance(event, GameEnded):
        if event.player_playstate == "WON":
            return "victory"
        if event.player_playstate == "LOST":
            return "defeat"
    return None


def _state_cards(state: GameState) -> Iterable[GameEntity | PlayedCard | None]:
    yield from state.player_board
    yield from state.opponent_board
    yield from state.player_hand
    yield from state.opponent_hand
    yield from state.player_secrets
    yield from state.opponent_secrets
    yield from state.player_deck
    yield from state.player_played
    yield from state.opponent_played
    yield from state.player_drawn
    yield from state.opponent_drawn
    yield from state.graveyard
    yield state.player_weapon
    yield state.opponent_weapon
    yield state.player_hero_entity
    yield state.opponent_hero_entity


def _require_engine(engine: HorizontalListEngine | None) -> HorizontalListEngine:
    if engine is None:
        raise RuntimeError("Replay Viewer engine is not active")
    return engine
