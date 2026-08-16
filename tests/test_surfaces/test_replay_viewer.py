from __future__ import annotations

from dataclasses import replace

from stonereader.models.card import Card
from stonereader.models.game_state import GameEntity, GameState, Hero, PlayedCard
from stonereader.models.replay import ReplayState
from stonereader.surfaces.replay_viewer import CurrentReplay, build_replay_viewer
from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.engines import HorizontalListEngine
from stonereader.ui.navigation import ActiveSurface, NavigationController
from stonereader.ui.registry import CommandRegistry
from stonereader.ui.surface import SurfaceSpec, WidgetType

from tests.test_ui.conftest import FakeSpeech


class _LandingEngine:
    def on_landing(self, queued: bool = False) -> None:
        pass


def _placeholder(name: str) -> ActiveSurface:
    return ActiveSurface(
        SurfaceSpec(name, WidgetType.VERTICAL_MENU, options=lambda: []),
        _LandingEngine(),
        CommandRegistry(),
    )


def _card(
    card_id: str,
    name: str,
    *,
    cost: int = 1,
    attack: int | None = 1,
    health: int | None = 1,
    card_type: str = "MINION",
    text: str = "",
) -> Card:
    return Card(
        card_id,
        len(card_id),
        name,
        cost,
        attack,
        health,
        text,
        "COMMON",
        "NEUTRAL",
        card_type,
    )


def _entity(
    entity_id: int,
    card: Card,
    *,
    controller: int = 1,
    zone: str = "PLAY",
    current_health: int | None = None,
    tags: dict[str, int] | None = None,
    lineage: str = "",
    name: str | None = None,
) -> GameEntity:
    return GameEntity(
        entity_id,
        card.id,
        card,
        card.name if name is None else name,
        card.cost,
        card.attack or 0,
        card.health if current_health is None else current_health,
        card.card_type,
        zone,
        1,
        controller,
        tags=tags or {},
        creation_lineage=lineage,
    )


def _played(entity_id: int, card: Card, turn: int, controller: int) -> PlayedCard:
    return PlayedCard(entity_id, card.id, card, card.name, turn, controller)


def _hero(
    entity_id: str,
    name: str,
    hero_class: str,
    *,
    armor: int = 0,
    power: str = "",
) -> Hero:
    return Hero(entity_id, name, 30, armor, power, hero_class)


def _empty_state(turn: int, active: int) -> GameState:
    return GameState(
        turn=turn,
        active_player_id=active,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=(),
        player_hero=_hero("p", "Jaina", "MAGE"),
        opponent_hero=_hero("o", "Garrosh", "WARRIOR", armor=5, power="Armor Up!"),
        game_type="RANKED",
        format_type="STANDARD",
    )


def _replay() -> ReplayState:
    boar = _card("BOAR", "Boar", attack=1, health=3, text="Charge.")
    yeti = _card("YETI", "Yeti", cost=4, attack=4, health=5)
    enemy = _card("ENEMY", "Enemy", cost=2, attack=2, health=2)
    fireball = _card(
        "FIREBALL",
        "Fireball",
        cost=4,
        attack=None,
        health=None,
        card_type="SPELL",
        text="Deal 6 damage.",
    )
    secret = _card(
        "SECRET",
        "Counterspell",
        cost=3,
        attack=None,
        health=None,
        card_type="SPELL",
    )
    axe = _card("AXE", "Fiery Axe", cost=3, attack=3, health=2, card_type="WEAPON")

    opening = _empty_state(0, 2)
    boar_before_damage = _entity(
        10,
        boar,
        current_health=3,
        tags={"TAUNT": 1, "DIVINE_SHIELD": 1, "FROZEN": 1, "DAMAGE": 0},
        lineage="Barnes",
    )
    rich = replace(
        opening,
        turn=1,
        active_player_id=1,
        player_board=(boar_before_damage, _entity(11, yeti)),
        opponent_board=(_entity(20, enemy, controller=2),),
        player_hand=(_entity(30, fireball, zone="HAND"),),
        opponent_hand=(
            None,
            _entity(31, enemy, controller=2, zone="HAND", name=""),
        ),
        player_secrets=(_entity(40, secret, zone="SECRET"),),
        opponent_secrets=(
            _entity(41, secret, controller=2, zone="SECRET"),
        ),
        opponent_weapon=_entity(50, axe, controller=2),
        player_deck=(_entity(60, yeti, zone="DECK"),),
        player_played=(_played(10, boar, 1, 1),),
        opponent_played=(_played(20, enemy, 1, 2),),
        player_drawn=(_played(30, fireball, 1, 1),),
        opponent_drawn=(_played(31, enemy, 1, 2),),
        player_mana=1,
        player_max_mana=3,
        opponent_mana=2,
        opponent_max_mana=4,
        opponent_deck_count=24,
        mulligan_complete=True,
        block_stack=("PLAY",),
    )
    damaged_boar = replace(
        boar_before_damage,
        current_health=2,
        tags={"TAUNT": 1, "DIVINE_SHIELD": 1, "FROZEN": 1, "DAMAGE": 1},
    )
    turn_one_end = replace(
        rich,
        player_board=(damaged_boar, rich.player_board[1]),
        block_stack=("POWER",),
    )
    turn_two = replace(
        turn_one_end,
        turn=2,
        active_player_id=2,
        player_board=(
            _entity(70, boar, name="First on turn two"),
            _entity(71, yeti, name="Second on turn two"),
        ),
        opponent_board=(_entity(72, enemy, controller=2, name="Enemy on turn two"),),
        block_stack=(),
    )
    return ReplayState(
        states=(opening, rich, turn_one_end, turn_two),
        friendly_player_id=1,
    )


def _harness(replay: ReplayState | None = None):
    speech = FakeSpeech()
    announcer = Announcer(speech)
    sink = _SinkCore(announcer, lambda: None)
    nav = NavigationController(
        lambda _title: None,
        announcer,
        lambda: None,
        lambda surface: sink.set_active(surface.registry),
    )
    current = CurrentReplay()
    current.set(replay or _replay())
    nav.register("Replays", lambda: _placeholder("Replays"))
    nav.register(
        "Replay Viewer",
        lambda: build_replay_viewer(announcer, [], nav, current),
    )
    nav.register("Child", lambda: _placeholder("Child"))
    nav.jump("Replays")
    speech.calls.clear()
    nav.drill_down("Replay Viewer")
    surface = nav._surfaces["Replay Viewer"]
    assert isinstance(surface.engine, HorizontalListEngine)
    return surface, sink, speech, nav, current


def test_entry_zone_switch_orientation_and_turn_step_share_one_template() -> None:
    surface, sink, speech, _nav, _current = _harness()
    assert speech.calls[-1] == (
        "Turn 1, yours, Your board, Boar, 1 of 2",
        True,
    )

    sink.handle_chord(Chord("g"))
    assert speech.calls[-1] == (
        "Turn 1, yours, Opponent board, Enemy, 1 of 1",
        True,
    )
    sink.handle_chord(Chord("up", shift=True))
    assert speech.calls[-1] == (
        "Turn 1, yours, Opponent board, Enemy, 1 of 1",
        True,
    )
    sink.handle_chord(Chord("pagedown"))
    assert speech.calls[-1] == (
        "Turn 2, opponent's, Opponent board, Enemy on turn two, 1 of 1",
        True,
    )
    assert surface.engine.current_zone().zone_id == "opponent_board"


def test_clamped_turn_step_repeats_only_the_bare_title() -> None:
    _surface, sink, speech, _nav, _current = _harness()
    speech.calls.clear()

    sink.handle_chord(Chord("pageup"))

    assert speech.calls == [("Boar", True)]


def test_all_zone_letters_shift_pairs_and_empty_weapon_phrase() -> None:
    surface, sink, speech, _nav, _current = _harness()
    cases = [
        (Chord("b"), "your_board"),
        (Chord("g"), "opponent_board"),
        (Chord("c"), "your_hand"),
        (Chord("c", shift=True), "opponent_hand"),
        (Chord("s"), "your_secrets"),
        (Chord("s", shift=True), "opponent_secrets"),
        (Chord("v"), "your_hero"),
        (Chord("f"), "opponent_hero"),
        (Chord("w", shift=True), "opponent_weapon"),
        (Chord("d"), "your_deck"),
        (Chord("p"), "your_played"),
        (Chord("p", shift=True), "opponent_played"),
        (Chord("n"), "your_drawn"),
        (Chord("n", shift=True), "opponent_drawn"),
        (Chord("y"), "events"),
    ]
    for chord, zone_id in cases:
        sink.handle_chord(chord)
        assert surface.engine.current_zone().zone_id == zone_id

    active_before = surface.engine.current_zone().zone_id
    sink.handle_chord(Chord("w"))
    assert surface.engine.current_zone().zone_id == active_before
    assert speech.calls[-1] == ("No Your weapon on this screen", True)


def test_card_hidden_status_hero_and_event_rows_follow_the_spec() -> None:
    surface, sink, _speech, _nav, _current = _harness()
    assert surface.engine.items_snapshot() == (
        ["Boar", "Yeti"],
        0,
        [
            "1 mana",
            "1 attack, 2 health",
            "Taunt",
            "Divine shield",
            "Frozen",
            "Damaged",
            "Charge.",
            "Created by Barnes",
        ],
    )

    sink.handle_chord(Chord("p"))
    assert surface.engine.items_snapshot()[0] == ["Boar, turn 1"]
    sink.handle_chord(Chord("n"))
    assert surface.engine.items_snapshot()[0] == ["Fireball, turn 1"]
    sink.handle_chord(Chord("c", shift=True))
    assert surface.engine.items_snapshot()[0] == ["Unknown card", "Unknown card"]

    sink.handle_chord(Chord("v"))
    assert surface.engine.items_snapshot() == (
        ["Jaina, 30 health"],
        0,
        ["No hero power", "No weapon", "1 secrets"],
    )
    sink.handle_chord(Chord("f"))
    assert surface.engine.items_snapshot() == (
        ["Garrosh, 30 health, 5 armor"],
        0,
        ["Armor Up!", "Fiery Axe", "1 secrets"],
    )

    sink.handle_chord(Chord("y"))
    titles = surface.engine.items_snapshot()[0]
    assert "Game started, Mage versus Warrior" in titles
    assert "Turn 1, yours" in titles
    assert "Mulligan complete" in titles
    assert not any("damage" in title.lower() for title in titles)
    played_index = titles.index("You played Boar")
    surface.engine.jump_to_position(played_index + 1)
    assert surface.engine.items_snapshot()[2] == ["Turn 1", "Boar"]


def test_speak_only_queries_are_subject_first_and_never_change_zone() -> None:
    surface, sink, speech, _nav, _current = _harness()
    expected = [
        (Chord("a"), "Your mana, 1 of 3"),
        (Chord("a", shift=True), "Opponent mana, 2 of 4"),
        (Chord("d", shift=True), "Opponent deck, 24 cards"),
        (Chord("r"), "Your hero power, No hero power"),
        (Chord("r", shift=True), "Opponent hero power, Armor Up!"),
    ]
    for chord, utterance in expected:
        sink.handle_chord(chord)
        assert speech.calls[-1] == (utterance, True)
        assert surface.engine.current_zone().zone_id == "your_board"


def test_digits_cursor_persistence_across_zones_and_turns() -> None:
    surface, sink, speech, _nav, _current = _harness()
    sink.handle_chord(Chord("2"))
    assert speech.calls[-1] == ("Yeti", True)
    sink.handle_chord(Chord("c"))
    sink.handle_chord(Chord("b"))
    assert speech.calls[-1] == (
        "Turn 1, yours, Your board, Yeti, 2 of 2",
        True,
    )

    sink.handle_chord(Chord("pagedown"))
    assert speech.calls[-1] == (
        "Turn 2, opponent's, Your board, Second on turn two, 2 of 2",
        True,
    )
    sink.handle_chord(Chord("pageup"))
    assert surface.engine.items_snapshot()[1] == 1
    sink.handle_chord(Chord("0"))
    assert speech.calls[-1] == ("Yeti", True)


def test_second_replay_resets_turn_but_back_reveal_does_not() -> None:
    _surface, sink, speech, nav, current = _harness()
    sink.handle_chord(Chord("pagedown"))
    nav.drill_down("Child")
    speech.calls.clear()

    nav.back()

    assert speech.calls[-1][0].startswith("Turn 2, opponent's, Your board")

    current.set(_replay())
    speech.calls.clear()
    nav._surfaces["Replay Viewer"].engine.on_landing()
    assert speech.calls[-1][0].startswith("Turn 1, yours, Your board")


def test_slots_and_unbound_keys_match_replay_viewer_contract() -> None:
    _surface, sink, speech, _nav, _current = _harness()
    cases = [
        (Chord("enter"), "Nothing to do here"),
        (Chord("l"), "Game audio is not available"),
        (Chord("tab"), "No groups on this screen"),
        (Chord("f", ctrl=True), "No search on this screen"),
    ]
    for chord, expected in cases:
        sink.handle_chord(chord)
        assert speech.calls[-1] == (expected, True)

    before = list(speech.calls)
    assert sink.handle_chord(Chord("delete")) is False
    assert sink.handle_chord(Chord("space")) is False
    assert speech.calls == before
