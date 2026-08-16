from __future__ import annotations

from dataclasses import replace

from stonereader.models.card import Card
from stonereader.models.game_state import GameEntity, GameState, Hero, PlayedCard
from stonereader.models.replay import ReplayState
from stonereader.services._audio_index import CardClip
from stonereader.services._events import (
    AttackStarted,
    CardDrawn,
    CardPlayed,
    GameEnded,
    MinionDied,
    SecretPlayed,
    SecretRevealed,
    TurnChanged,
)
from stonereader.surfaces.sounds_menu import SoundsMenuHolder
from stonereader.surfaces.replay_viewer import (
    CurrentReplay,
    _event_audio_kind,
    build_replay_viewer,
)
from stonereader.ui.chords import Chord

from .conftest import Harness, make_harness, placeholder_surface


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
        (card.health or 0) if current_health is None else current_health,
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


class FakeAudioIndex:
    def __init__(
        self,
        status: str = "ready",
        reason: str = "",
        clips: list[CardClip] | None = None,
    ) -> None:
        self.status = status
        self.reason = reason
        self.clips = clips or []
        self.event_requests: list[tuple[str | None, str]] = []

    def clips_for_card(self, card_id: str) -> list[CardClip]:
        del card_id
        return list(self.clips)

    def event_clip(self, card_id: str | None, kind: str) -> str | None:
        self.event_requests.append((card_id, kind))
        return f"{kind}-key"

    def decode(self, clip_key: str) -> bytes:
        return f"wav:{clip_key}".encode()


class FakePlayer:
    def __init__(self) -> None:
        self.played: list[bytes] = []

    def play(self, wav_bytes: bytes) -> None:
        self.played.append(wav_bytes)


def _harness(
    replay: ReplayState | None = None,
    *,
    audio_index: FakeAudioIndex | None = None,
    player: FakePlayer | None = None,
    autoplay: bool = True,
    sounds: SoundsMenuHolder | None = None,
) -> Harness[CurrentReplay]:
    current = CurrentReplay()
    current.set(replay or _replay())
    harness = make_harness(current)
    harness.nav.register("Replays", lambda: placeholder_surface("Replays"))
    harness.nav.register(
        "Replay Viewer",
        lambda: build_replay_viewer(
            harness.announcer,
            [],
            harness.nav,
            current,
            audio_index=audio_index,
            player=player,
            replay_autoplay=lambda: autoplay,
            sounds=sounds,
        ),
    )
    harness.nav.register("Child", lambda: placeholder_surface("Child"))
    harness.nav.register(
        "Sounds menu", lambda: placeholder_surface("Sounds menu")
    )
    harness.nav.jump("Replays")
    harness.speech.calls.clear()
    harness.nav.drill_down("Replay Viewer")
    return harness


def test_entry_zone_switch_orientation_and_turn_step_share_one_template() -> None:
    harness = _harness()
    assert harness.speech.calls[-1] == (
        "Turn 1, yours, Your board, Boar, 1 of 2",
        True,
    )

    harness.press(Chord("g"))
    assert harness.speech.calls[-1] == (
        "Turn 1, yours, Opponent board, Enemy, 1 of 1",
        True,
    )
    harness.press(Chord("up", shift=True))
    assert harness.speech.calls[-1] == (
        "Turn 1, yours, Opponent board, Enemy, 1 of 1",
        True,
    )
    harness.press(Chord("pagedown"))
    assert harness.speech.calls[-1] == (
        "Turn 2, opponent's, Opponent board, Enemy on turn two, 1 of 1",
        True,
    )
    assert harness.horizontal.current_zone().zone_id == "opponent_board"


def test_clamped_turn_step_repeats_only_the_bare_title() -> None:
    harness = _harness()
    harness.speech.calls.clear()

    harness.press(Chord("pageup"))

    assert harness.speech.calls == [("Boar", True)]


def test_all_zone_letters_shift_pairs_and_empty_weapon_phrase() -> None:
    harness = _harness()
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
        harness.press(chord)
        assert harness.horizontal.current_zone().zone_id == zone_id

    active_before = harness.horizontal.current_zone().zone_id
    harness.press(Chord("w"))
    assert harness.horizontal.current_zone().zone_id == active_before
    assert harness.speech.calls[-1] == ("No Your weapon on this screen", True)


def test_card_hidden_status_hero_and_event_rows_follow_the_spec() -> None:
    harness = _harness()
    assert harness.horizontal.items_snapshot() == (
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

    harness.press(Chord("p"))
    assert harness.horizontal.items_snapshot()[0] == ["Boar, turn 1"]
    harness.press(Chord("n"))
    assert harness.horizontal.items_snapshot()[0] == ["Fireball, turn 1"]
    harness.press(Chord("c", shift=True))
    assert harness.horizontal.items_snapshot()[0] == ["Unknown card", "Unknown card"]

    harness.press(Chord("v"))
    assert harness.horizontal.items_snapshot() == (
        ["Jaina, 30 health"],
        0,
        ["No hero power", "No weapon", "1 secrets"],
    )
    harness.press(Chord("f"))
    assert harness.horizontal.items_snapshot() == (
        ["Garrosh, 30 health, 5 armor"],
        0,
        ["Armor Up!", "Fiery Axe", "1 secrets"],
    )

    harness.press(Chord("y"))
    titles = harness.horizontal.items_snapshot()[0]
    assert "Game started, Mage versus Warrior" in titles
    assert "Turn 1, yours" in titles
    assert "Mulligan complete" in titles
    assert not any("damage" in title.lower() for title in titles)
    played_index = titles.index("You played Boar")
    harness.horizontal.jump_to_position(played_index + 1)
    assert harness.horizontal.items_snapshot()[2] == ["Turn 1", "Boar"]


def test_event_scrubbing_renders_the_selected_moment_and_end_restores_turn_final() -> None:
    harness = _harness()
    harness.press(Chord("y"))
    titles = harness.horizontal.items_snapshot()[0]
    harness.horizontal.jump_to_position(titles.index("Turn 1, yours") + 1)

    harness.press(Chord("b"))
    assert harness.horizontal.items_snapshot()[2][1] == "1 attack, 3 health"

    harness.press(Chord("y"))
    harness.press(Chord("end"))
    harness.press(Chord("b"))
    assert harness.horizontal.items_snapshot()[2][1] == "1 attack, 2 health"


def test_speak_only_queries_are_subject_first_and_never_change_zone() -> None:
    harness = _harness()
    expected = [
        (Chord("a"), "Your mana, 1 of 3"),
        (Chord("a", shift=True), "Opponent mana, 2 of 4"),
        (Chord("d", shift=True), "Opponent deck, 24 cards"),
        (Chord("r"), "Your hero power, No hero power"),
        (Chord("r", shift=True), "Opponent hero power, Armor Up!"),
    ]
    for chord, utterance in expected:
        harness.press(chord)
        assert harness.speech.calls[-1] == (utterance, True)
        assert harness.horizontal.current_zone().zone_id == "your_board"


def test_digits_cursor_persistence_across_zones_and_turns() -> None:
    harness = _harness()
    harness.press(Chord("2"))
    assert harness.speech.calls[-1] == ("Yeti", True)
    harness.press(Chord("c"))
    harness.press(Chord("b"))
    assert harness.speech.calls[-1] == (
        "Turn 1, yours, Your board, Yeti, 2 of 2",
        True,
    )

    harness.press(Chord("pagedown"))
    assert harness.speech.calls[-1] == (
        "Turn 2, opponent's, Your board, Second on turn two, 2 of 2",
        True,
    )
    harness.press(Chord("pageup"))
    assert harness.horizontal.items_snapshot()[1] == 1
    harness.press(Chord("0"))
    assert harness.speech.calls[-1] == ("Yeti", True)


def test_turn_step_positions_events_at_turn_end_and_renders_final_state() -> None:
    harness = _harness()
    harness.press(Chord("y"))
    harness.press(Chord("home"))
    assert harness.horizontal.items_snapshot()[1] == 0

    harness.press(Chord("b"))
    harness.press(Chord("pagedown"))
    harness.press(Chord("pageup"))
    harness.press(Chord("y"))

    titles, cursor, _details = harness.horizontal.items_snapshot()
    assert cursor == len(titles) - 1
    harness.press(Chord("b"))
    assert harness.horizontal.items_snapshot()[2][1] == "1 attack, 2 health"


def test_events_cursor_persists_across_zone_switch_and_back_reveal() -> None:
    harness = _harness()
    harness.press(Chord("y"))
    harness.press(Chord("home"))
    harness.press(Chord("right"))
    expected_cursor = harness.horizontal.items_snapshot()[1]

    harness.press(Chord("b"))
    harness.press(Chord("y"))
    assert harness.horizontal.items_snapshot()[1] == expected_cursor

    harness.nav.drill_down("Child")
    harness.nav.back()
    assert harness.horizontal.current_zone().zone_id == "events"
    assert harness.horizontal.items_snapshot()[1] == expected_cursor


def test_second_replay_resets_turn_but_back_reveal_does_not() -> None:
    harness = _harness()
    harness.press(Chord("pagedown"))
    harness.nav.drill_down("Child")
    harness.speech.calls.clear()

    harness.nav.back()

    assert harness.speech.calls[-1][0].startswith("Turn 2, opponent's, Your board")

    harness.context.set(_replay())
    harness.speech.calls.clear()
    harness.list_engine("Replay Viewer").on_landing()
    assert harness.speech.calls[-1][0].startswith("Turn 1, yours, Your board")


def test_slots_and_unbound_keys_match_replay_viewer_contract() -> None:
    harness = _harness()
    surface = harness.active_surface
    help_by_chord = {
        str(chord): command.help_phrase
        for chord, command in surface.registry.surface_bindings()
    }
    assert help_by_chord["pageup"] == "Page Up: go to the previous turn"
    assert help_by_chord["pagedown"] == "Page Down: go to the next turn"

    cases = [
        (Chord("enter"), "Nothing to do here"),
        (Chord("l"), "Game audio is not available"),
        (Chord("tab"), "No groups on this screen"),
        (Chord("f", ctrl=True), "No search on this screen"),
    ]
    for chord, expected in cases:
        harness.press(chord)
        assert harness.speech.calls[-1] == (expected, True)

    before = list(harness.speech.calls)
    assert harness.press(Chord("delete")) is False
    assert harness.press(Chord("space")) is False
    assert harness.speech.calls == before


def test_listen_handles_card_event_source_and_all_no_push_cases() -> None:
    sounds = SoundsMenuHolder()
    ready_index = FakeAudioIndex(clips=[CardClip("Play", "key")])
    harness = _harness(
        audio_index=ready_index,
        player=FakePlayer(),
        sounds=sounds,
    )
    harness.press(Chord("l"))
    assert harness.nav.stack[-1] == "Sounds menu"
    assert sounds.get().card_name == "Boar"

    warming = FakeAudioIndex("indexing", "Game audio is not ready yet")
    harness = _harness(
        audio_index=warming,
        player=FakePlayer(),
        sounds=SoundsMenuHolder(),
    )
    harness.press(Chord("l"))
    assert harness.nav.stack[-1] == "Replay Viewer"
    assert harness.speech.calls[-1] == ("Game audio is not ready yet", True)

    silent = FakeAudioIndex(clips=[])
    harness = _harness(
        audio_index=silent,
        player=FakePlayer(),
        sounds=SoundsMenuHolder(),
    )
    harness.press(Chord("l"))
    assert harness.nav.stack[-1] == "Replay Viewer"
    assert harness.speech.calls[-1] == ("Boar: no sounds", True)

    event_sounds = SoundsMenuHolder()
    event_index = FakeAudioIndex(clips=[CardClip("Play", "key")])
    harness = _harness(
        audio_index=event_index,
        player=FakePlayer(),
        sounds=event_sounds,
    )
    harness.press(Chord("y"))
    harness.press(Chord("home"))
    harness.press(Chord("l"))
    assert harness.nav.stack[-1] == "Replay Viewer"
    titles = harness.horizontal.items_snapshot()[0]
    harness.horizontal.jump_to_position(titles.index("You played Boar") + 1)
    harness.press(Chord("l"))
    assert harness.nav.stack[-1] == "Sounds menu"
    assert event_sounds.get().card_name == "Boar"


def test_events_zone_autoplay_gates_and_turn_step_is_silent() -> None:
    disabled_index = FakeAudioIndex()
    disabled_player = FakePlayer()
    harness = _harness(
        audio_index=disabled_index,
        player=disabled_player,
        autoplay=False,
        sounds=SoundsMenuHolder(),
    )
    harness.press(Chord("y"))
    titles = harness.horizontal.items_snapshot()[0]
    harness.horizontal.jump_to_position(titles.index("You played Boar"))
    harness.press(Chord("right"))
    assert disabled_player.played == []

    warming_index = FakeAudioIndex("indexing", "Game audio is not ready yet")
    warming_player = FakePlayer()
    harness = _harness(
        audio_index=warming_index,
        player=warming_player,
        sounds=SoundsMenuHolder(),
    )
    harness.press(Chord("y"))
    titles = harness.horizontal.items_snapshot()[0]
    harness.horizontal.jump_to_position(titles.index("You played Boar"))
    harness.press(Chord("right"))
    assert warming_player.played == []

    ready_index = FakeAudioIndex()
    ready_player = FakePlayer()
    harness = _harness(
        audio_index=ready_index,
        player=ready_player,
        sounds=SoundsMenuHolder(),
    )
    harness.press(Chord("y"))
    titles = harness.horizontal.items_snapshot()[0]
    harness.horizontal.jump_to_position(titles.index("You played Boar"))
    harness.press(Chord("right"))
    assert ready_index.event_requests[-1] == ("BOAR", "play")
    assert ready_player.played[-1] == b"wav:play-key"

    ready_player.played.clear()
    harness.horizontal.jump_to_position(10)
    ready_player.played.clear()
    # Stepping into a shorter turn clamps the item cursor; that clamp is part
    # of the turn step, so it stays silent like the step itself.
    assert harness.horizontal.items_snapshot()[1] == 9
    harness.press(Chord("pagedown"))
    assert harness.horizontal.items_snapshot()[1] == 0
    assert ready_player.played == []
    harness.press(Chord("pagedown"))
    assert ready_player.played == []


def test_events_autoplay_on_event_item_landing_transitions() -> None:
    audio_index = FakeAudioIndex()
    player = FakePlayer()
    harness = _harness(
        audio_index=audio_index,
        player=player,
        sounds=SoundsMenuHolder(),
    )
    harness.press(Chord("y"))
    player.played.clear()
    titles = harness.horizontal.items_snapshot()[0]
    played_position = titles.index("You played Boar") + 1

    harness.press(Chord(str(played_position)))
    assert player.played == [b"wav:play-key"]

    player.played.clear()
    harness.press(Chord("b"))
    harness.press(Chord("y"))
    assert player.played == [b"wav:play-key"]

    player.played.clear()
    harness.press(Chord("home"))
    assert player.played == []
    harness.press(Chord("end"))
    assert player.played == [b"wav:play-key"]

    player.played.clear()
    harness.press(Chord("end"))
    assert player.played == []

    harness.press(Chord("left"))
    assert player.played == []
    harness.press(Chord("right"))
    assert audio_index.event_requests[-1] == ("AXE", "play")
    assert player.played == [b"wav:play-key"]

    player.played.clear()
    # Right at the last event clamps: a boundary repeats the Title line but
    # must not replay the clip already heard on landing there.
    harness.press(Chord("right"))
    assert player.played == []


def test_event_autoplay_coverage_is_play_attack_and_death_only() -> None:
    card = _card("BOAR", "Boar")
    supported = [
        (CardPlayed(0, 1, 1, "BOAR", card, "Boar", 1), "play"),
        (AttackStarted(0, 1, 1, 2, 1), "attack"),
        (MinionDied(0, 1, 1, "BOAR", "Boar", 1), "minion_death"),
    ]
    unsupported = [
        CardDrawn(0, 1, 1, "BOAR", card, "Boar", 1),
        TurnChanged(0, 1, 1),
        SecretPlayed(0, 1, 1),
        SecretRevealed(0, 1, "Counterspell", 1),
        GameEnded(0, 1, "WON", "LOST"),
        GameEnded(0, 1, "LOST", "WON"),
    ]

    assert [(_event_audio_kind(event), kind) for event, kind in supported] == [
        (kind, kind) for _event, kind in supported
    ]
    assert all(_event_audio_kind(event) is None for event in unsupported)
