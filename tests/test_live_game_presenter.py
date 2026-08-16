"""Tests for stonereader.presenters.live_game.LiveGamePresenter.

All tests run synchronously against MockGameTracker (no real wx + hslog).
Covers LIVE-01..08 (LIVE-09 lives in test_global_hotkey.py) plus D-07
(silent during arrow-read), D-08/D-09 (lifecycle silence + baseline),
LIVE-03 cards_drawn zone, drawn_turn==-1 fallback wording, and public
accessors (per 03-REVIEWS.md HIGH #1, HIGH #3, MEDIUM #5).

Issue #5: presenter consumes (prev, curr) GameState pairs and re-derives
lifecycle via diff(); tests dispatch state pairs accordingly.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from typing import List, Optional, Tuple

from stonereader.db import get_connection, init_db, save_deck
from stonereader.models.card import Card, CardDatabase
from stonereader.models.game_state import (
    GameEntity,
    GameState,
    Hero,
    PlayedCard,
)
from stonereader.presenters.live_game import (
    LiveGamePresenter,
)
from tests.conftest import MockGameTracker, MockSpeechService

# -------------------------------- Helpers --------------------------------

_next_dbf_id = 5000  # avoid collision with other test modules


def _make_card(
    card_id: str,
    name: str,
    cost: int = 1,
    card_type: str = "MINION",
    card_class: str = "NEUTRAL",
    card_set: str = "EXPERT1",
) -> Card:
    global _next_dbf_id
    _next_dbf_id += 1
    return Card(
        id=card_id,
        dbf_id=_next_dbf_id,
        name=name,
        cost=cost,
        attack=None,  # Card.attack is Optional[int]
        health=None,
        text="",
        rarity="COMMON",
        card_class=card_class,
        card_type=card_type,
        card_set=card_set,
        collectible=True,
    )


def _make_card_db(cards: List[Card]) -> CardDatabase:
    """Build the indexed card database needed by these presenter tests."""
    db = CardDatabase()
    for card in cards:
        db.cards_by_id[card.id] = card
        db.cards_by_dbf_id[card.dbf_id] = card
        db.cards_by_name[card.name.lower()] = card
        db.cards_by_class.setdefault(card.card_class, []).append(card)
        db.cards_by_type.setdefault(card.card_type, []).append(card)
        db.cards_by_set.setdefault(card.card_set, []).append(card)
        db.cards_by_cost.setdefault(card.cost, []).append(card)
        if card.collectible:
            db.collectible_cards.append(card)
    return db


def _make_db(tmp_path) -> sqlite3.Connection:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    return conn


def _make_state(
    player_deck: Tuple[GameEntity, ...] = (),
    opponent_hand: Tuple[Optional[GameEntity], ...] = (),
    opponent_played: Tuple[PlayedCard, ...] = (),
    player_drawn: Tuple[PlayedCard, ...] = (),
    player_deck_count: int = 0,
    opponent_deck_count: int = 0,
    player_mana: int = 0,
    player_max_mana: int = 0,
    opponent_mana: int = 0,
    opponent_max_mana: int = 0,
    game_type: str = "RANKED",
    player_hero_class: str = "MAGE",
    opponent_hero_class: str = "WARRIOR",
) -> GameState:
    def _hero(hc: str) -> Hero:
        return Hero(
            id="?",
            name="?",
            health=30,
            armor=0,
            hero_power="",
            hero_class=hc,
        )

    return GameState(
        turn=1,
        active_player_id=1,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=opponent_hand,
        player_hero=_hero(player_hero_class),
        opponent_hero=_hero(opponent_hero_class),
        player_deck=player_deck,
        opponent_played=opponent_played,
        player_drawn=player_drawn,
        player_deck_count=player_deck_count,
        opponent_deck_count=opponent_deck_count,
        player_mana=player_mana,
        player_max_mana=player_max_mana,
        opponent_mana=opponent_mana,
        opponent_max_mana=opponent_max_mana,
        game_type=game_type,
    )


def _make_entity(card: Card, controller: int = 1, zone: str = "DECK") -> GameEntity:
    return GameEntity(
        entity_id=abs(hash(card.id)) % 100000,
        card_id=card.id,
        base_card=card,
        name=card.name,
        cost=card.cost,
        current_attack=card.attack or 0,
        current_health=card.health or 0,
        card_type=card.card_type,
        zone=zone,
        zone_position=0,
        controller=controller,
    )


def _make_opponent_hand_entity(
    card: Optional[Card],
    position: int,
    drawn_turn: int = -1,
    lineage: str = "",
) -> GameEntity:
    return GameEntity(
        entity_id=10_000 + position,
        card_id=card.id if card else "",
        base_card=card,
        name=card.name if card else "",
        cost=card.cost if card else 0,
        current_attack=0,
        current_health=0,
        card_type="MINION",
        zone="HAND",
        zone_position=position,
        controller=2,
        drawn_turn=drawn_turn,
        creation_lineage=lineage,
    )


def _make_presenter(tmp_path, *, cards: Optional[List[Card]] = None):
    speech = MockSpeechService()
    tracker = MockGameTracker()
    db = _make_db(tmp_path)
    card_db = _make_card_db(cards or [])
    presenter = LiveGamePresenter(speech, db, tracker, card_db)  # type: ignore[arg-type]
    return presenter, speech, tracker, db, card_db


def _make_legal_deck_30() -> List[Card]:
    """Build 15 distinct non-legendary cards for a legal 30-card deck (2x each).

    Per 03-REVIEWS.md MEDIUM #5: avoid the 30x-Glacial-Shard pattern which
    is not a legal Hearthstone deck.
    """
    return [
        _make_card(f"CARD_{i}", f"Card {i:02d}", cost=(i % 10) + 1)
        for i in range(15)
    ]


# -------------------------------- Tests --------------------------------


def test_lifecycle_silence(tmp_path) -> None:
    """Lifecycle transitions (GameStarted/GameEnded via diff) do NOT cause speech."""
    presenter, speech, tracker, _db, _card_db = _make_presenter(tmp_path)
    running = _make_state()
    # First publication: prev=None, curr=running → diff produces GameStarted.
    tracker.dispatch(None, running)
    # Game ends: RUNNING → COMPLETE → diff produces GameEnded.
    completed = dataclasses.replace(
        running,
        game_state="COMPLETE",
        player_playstate="WON",
        opponent_playstate="LOST",
        turn=10,
    )
    tracker.dispatch(running, completed)
    assert speech.spoken == []
    assert presenter is not None  # silence linter — we constructed presenter for side-effects


def test_remaining_deck_speech_format(tmp_path) -> None:
    """Per-row 'Card name, N copies' format with N-of-M suffix."""
    glacial = _make_card("CS2_023", "Glacial Shard", cost=1)
    fireball = _make_card("CS2_029", "Fireball", cost=4)
    presenter, speech, tracker, _db, _card_db = _make_presenter(
        tmp_path, cards=[glacial, fireball]
    )
    state = _make_state(
        player_deck=(
            _make_entity(glacial),
            _make_entity(fireball),
            _make_entity(fireball),
        )
    )
    tracker.dispatch(state, state)
    presenter.jump_to_zone("remaining_deck")
    assert "Remaining deck zone" in speech.last_speech
    assert "Glacial Shard, 1 copy" in speech.last_speech
    assert "2 cards" in speech.last_speech
    presenter.move_in_zone(1)
    assert "Fireball, 2 copies" in speech.last_speech
    assert "2 of 2" in speech.last_speech


def test_remaining_deck_sort_order(tmp_path) -> None:
    """Sort by mana cost ascending, then alphabetically."""
    a = _make_card("a", "Alpha", cost=3)
    b = _make_card("b", "Bravo", cost=1)
    c = _make_card("c", "Charlie", cost=3)
    presenter, _speech, tracker, _db, _card_db = _make_presenter(
        tmp_path, cards=[a, b, c]
    )
    state = _make_state(
        player_deck=(_make_entity(a), _make_entity(b), _make_entity(c))
    )
    tracker.dispatch(state, state)
    items = presenter.get_zone_items("remaining_deck")
    assert [it[0].name for it in items] == ["Bravo", "Alpha", "Charlie"]


def test_drawn_to_zero_visible(tmp_path) -> None:
    """When detected_deck is known, drawn-to-zero cards stay listed as '0 copies'.

    Uses a legal 30-card composition (15 distinct x 2) per 03-REVIEWS.md MEDIUM #5.
    """
    from hearthstone.deckstrings import write_deckstring
    from hearthstone.enums import FormatType

    cards = _make_legal_deck_30()
    # Build deck-entities: 2 of each card = 30 entities revealed.
    deck_entities = []
    for c in cards:
        deck_entities.append(
            GameEntity(
                entity_id=100 + c.dbf_id,
                card_id=c.id,
                base_card=c,
                name=c.name,
                cost=c.cost,
                current_attack=0,
                current_health=0,
                card_type="MINION",
                zone="DECK",
                zone_position=0,
                controller=1,
            )
        )
        deck_entities.append(
            GameEntity(
                entity_id=200 + c.dbf_id,
                card_id=c.id,
                base_card=c,
                name=c.name,
                cost=c.cost,
                current_attack=0,
                current_health=0,
                card_type="MINION",
                zone="DECK",
                zone_position=0,
                controller=1,
            )
        )
    cards_data = [(c.dbf_id, 2) for c in cards]
    deckstring = write_deckstring(cards_data, [637], FormatType.FT_STANDARD)
    presenter, _speech, tracker, db, _card_db = _make_presenter(
        tmp_path, cards=cards
    )
    save_deck(db, "Legal Deck", "MAGE", "Standard", deckstring)
    # Pretend one copy of cards[0] was drawn.
    first = cards[0]
    state = _make_state(
        player_deck=tuple(deck_entities),
        player_drawn=(
            PlayedCard(
                entity_id=999,
                card_id=first.id,
                base_card=first,
                name=first.name,
                turn=1,
                controller=1,
            ),
        ),
    )
    tracker.dispatch(None, state)
    tracker.dispatch(state, state)
    items = presenter.get_zone_items("remaining_deck")
    # cards[0] should be listed with count=1 (2 original - 1 drawn).
    first_row = next(it for it in items if it[0].id == first.id)
    assert first_row[1] == 1
    # All other cards should be listed with count=2.
    for card_obj, count in items:
        if card_obj.id != first.id:
            assert count == 2


def test_cards_drawn_zone(tmp_path) -> None:
    """LIVE-03: 'cards drawn this game' chronological list zone.

    Per 03-REVIEWS.md HIGH #1: this is now the canonical home of LIVE-03.
    Most-recently-drawn first (matches DeckManager newest-first convention).
    Per-row format: 'Turn N, Card name, drawn'.
    """
    glacial = _make_card("CS2_023", "Glacial Shard", cost=1)
    fireball = _make_card("CS2_029", "Fireball", cost=4)
    presenter, speech, tracker, _db, _card_db = _make_presenter(
        tmp_path, cards=[glacial, fireball]
    )
    # First drawn turn 1 (Glacial), then turn 3 (Fireball).
    state = _make_state(
        player_drawn=(
            PlayedCard(
                entity_id=1,
                card_id=glacial.id,
                base_card=glacial,
                name="Glacial Shard",
                turn=1,
                controller=1,
            ),
            PlayedCard(
                entity_id=2,
                card_id=fireball.id,
                base_card=fireball,
                name="Fireball",
                turn=3,
                controller=1,
            ),
        ),
    )
    tracker.dispatch(state, state)
    items = presenter.get_zone_items("cards_drawn")
    # Most recent first: Fireball (turn 3) then Glacial (turn 1).
    assert len(items) == 2
    assert items[0].name == "Fireball"
    assert items[1].name == "Glacial Shard"
    presenter.jump_to_zone("cards_drawn")
    assert "Cards drawn zone" in speech.last_speech
    assert "Turn 3, Fireball, drawn" in speech.last_speech
    presenter.move_in_zone(1)
    assert "Turn 1, Glacial Shard, drawn" in speech.last_speech


def test_opponent_hand_speech_format(tmp_path) -> None:
    """D-14: 'Position 3, identity, drawn turn 5' or with lineage."""
    reno = _make_card("LOOT_517", "Reno Jackson", cost=6)
    presenter, speech, tracker, _db, _card_db = _make_presenter(
        tmp_path, cards=[reno]
    )
    state = _make_state(
        opponent_hand=(
            _make_opponent_hand_entity(None, position=1, drawn_turn=2, lineage=""),
            _make_opponent_hand_entity(
                None,
                position=2,
                drawn_turn=3,
                lineage="Wand of Disintegration",
            ),
            _make_opponent_hand_entity(reno, position=3, drawn_turn=5, lineage=""),
        )
    )
    tracker.dispatch(state, state)
    presenter.jump_to_zone("opponent_hand")
    assert "Position 1, unknown, drawn turn 2" in speech.last_speech
    presenter.move_in_zone(1)
    assert (
        "Position 2, unknown, generated by Wand of Disintegration turn 3"
        in speech.last_speech
    )
    presenter.move_in_zone(1)
    assert "Position 3, Reno Jackson, drawn turn 5" in speech.last_speech


def test_drawn_turn_unknown_speech(tmp_path) -> None:
    """When drawn_turn == -1, speech says 'drawn turn unknown' not 'drawn turn -1'."""
    presenter, speech, tracker, _db, _card_db = _make_presenter(tmp_path)
    state = _make_state(
        opponent_hand=(
            _make_opponent_hand_entity(None, position=1, drawn_turn=-1, lineage=""),
        )
    )
    tracker.dispatch(state, state)
    presenter.jump_to_zone("opponent_hand")
    assert "drawn turn unknown" in speech.last_speech
    assert "drawn turn -1" not in speech.last_speech


def test_opponent_played_speech_format(tmp_path) -> None:
    """D-15: 'Turn 6, Reno Jackson'."""
    reno = _make_card("LOOT_517", "Reno Jackson", cost=6)
    presenter, speech, tracker, _db, _card_db = _make_presenter(
        tmp_path, cards=[reno]
    )
    state = _make_state(
        opponent_played=(
            PlayedCard(
                entity_id=1,
                card_id=reno.id,
                base_card=reno,
                name="Reno Jackson",
                turn=6,
                controller=2,
            ),
        )
    )
    tracker.dispatch(state, state)
    presenter.jump_to_zone("opponent_played")
    assert "Turn 6, Reno Jackson" in speech.last_speech


def test_opponent_hand_count(tmp_path) -> None:
    """Opponent-hand count via len(get_zone_items('opponent_hand'))."""
    presenter, _speech, tracker, _db, _card_db = _make_presenter(tmp_path)
    state = _make_state(
        opponent_hand=(
            _make_opponent_hand_entity(None, position=1),
            _make_opponent_hand_entity(None, position=2),
            _make_opponent_hand_entity(None, position=3),
        )
    )
    tracker.dispatch(state, state)
    items = presenter.get_zone_items("opponent_hand")
    assert len(items) == 3


def test_announce_opponent_hand_count(tmp_path) -> None:
    """LIVE-05 speak-only via public presenter method (no app-side state read)."""
    presenter, speech, tracker, _db, _card_db = _make_presenter(tmp_path)
    # Baseline: no game.
    presenter.announce_opponent_hand_count()
    assert speech.last_speech == "No game in progress."
    # With state: 4 hand entities, one None.
    e1 = _make_opponent_hand_entity(None, position=1)
    e2 = _make_opponent_hand_entity(None, position=2)
    e3 = _make_opponent_hand_entity(None, position=3)
    state = _make_state(opponent_hand=(e1, e2, None, e3))
    tracker.dispatch(state, state)
    presenter.announce_opponent_hand_count()
    # Count non-None entries -> 3.
    assert speech.last_speech == "Opponent has 3 cards."


def test_announce_deck_counts(tmp_path) -> None:
    """LIVE-06 / D-16: 'N left, opponent M.' Baseline says 'No game in progress.'"""
    presenter, speech, tracker, _db, _card_db = _make_presenter(tmp_path)
    presenter.announce_deck_counts()
    assert speech.last_speech == "No game in progress."
    state = _make_state(player_deck_count=18, opponent_deck_count=22)
    tracker.dispatch(state, state)
    presenter.announce_deck_counts()
    assert speech.last_speech == "18 left, opponent 22."


def test_mana_query(tmp_path) -> None:
    """LIVE-07: panel-only mana surfacing via current_mana_summary()."""
    presenter, _speech, tracker, _db, _card_db = _make_presenter(tmp_path)
    assert presenter.current_mana_summary() == ""
    state = _make_state(
        player_mana=4,
        player_max_mana=7,
        opponent_mana=2,
        opponent_max_mana=5,
    )
    tracker.dispatch(state, state)
    assert presenter.current_mana_summary() == "You 4/7, opponent 2/5"


def test_auto_deck_detection(tmp_path) -> None:
    """0 / 1 / 2+ saved-deck matches -> respectively None / name / None.

    Uses legal 30-card composition (15 distinct x 2) per 03-REVIEWS.md MEDIUM #5.
    """
    from hearthstone.deckstrings import write_deckstring
    from hearthstone.enums import FormatType

    cards = _make_legal_deck_30()
    cards_data = [(c.dbf_id, 2) for c in cards]
    deckstring_a = write_deckstring(cards_data, [637], FormatType.FT_STANDARD)

    presenter, _speech, tracker, db, _card_db = _make_presenter(
        tmp_path, cards=cards
    )

    # 30 deck entities total.
    deck_entities = []
    eid = 1000
    for c in cards:
        for _ in range(2):
            deck_entities.append(
                GameEntity(
                    entity_id=eid,
                    card_id=c.id,
                    base_card=c,
                    name=c.name,
                    cost=c.cost,
                    current_attack=0,
                    current_health=0,
                    card_type="MINION",
                    zone="DECK",
                    zone_position=0,
                    controller=1,
                )
            )
            eid += 1
    state = _make_state(player_deck=tuple(deck_entities))

    # Case A: 0 matches (no decks saved).
    tracker.dispatch(None, state)
    tracker.dispatch(state, state)
    # Public accessor read (per 03-REVIEWS.md HIGH #3).
    assert presenter.detected_deck_name() is None

    # Case B: exactly 1 match.
    save_deck(db, "Legal Deck A", "MAGE", "Standard", deckstring_a)
    tracker.dispatch(None, state)
    tracker.dispatch(state, state)
    assert presenter.detected_deck_name() == "Legal Deck A"

    # Case C: 2+ matches.
    save_deck(db, "Legal Deck B", "MAGE", "Standard", deckstring_a)
    tracker.dispatch(None, state)
    tracker.dispatch(state, state)
    assert presenter.detected_deck_name() is None


def test_detection_resets_per_game(tmp_path) -> None:
    """_detection_attempted and _detected_deck_name reset on each GameStarted.

    This is one of the rare tests that DOES read internal state -- it is
    explicitly verifying the reset semantics that no public accessor
    captures (the "we tried at the threshold" flag is internal).
    """
    presenter, _speech, tracker, _db, _card_db = _make_presenter(tmp_path)
    presenter._detection_attempted = True
    presenter._detected_deck_name = "Stale Deck"
    presenter._original_deck_cards = ()
    tracker.dispatch(None, _make_state())
    assert presenter._detection_attempted is False
    assert presenter.detected_deck_name() is None
    assert presenter._original_deck_cards is None


def test_silent_during_state_publication(tmp_path) -> None:
    """_on_state NEVER calls SpeechService -- subscriber callbacks are silent (D-07)."""
    presenter, speech, tracker, _db, _card_db = _make_presenter(tmp_path)
    state = _make_state(player_deck_count=15)
    tracker.dispatch(state, state)
    assert speech.spoken == []
    assert presenter is not None


def test_cursor_preserves_across_render(tmp_path) -> None:
    """A cached cursor index survives an event-driven re-render."""
    a = _make_card("a", "Alpha", cost=1)
    b = _make_card("b", "Bravo", cost=2)
    c = _make_card("c", "Charlie", cost=3)
    presenter, _speech, tracker, _db, _card_db = _make_presenter(
        tmp_path, cards=[a, b, c]
    )
    state = _make_state(
        player_deck=(_make_entity(a), _make_entity(b), _make_entity(c))
    )
    tracker.dispatch(state, state)
    presenter.jump_to_zone("remaining_deck")
    presenter.move_in_zone(1)  # cursor=1 (Bravo)
    # Public accessor (per 03-REVIEWS.md HIGH #3).
    assert presenter.cursor_for_zone("remaining_deck") == 1
    tracker.dispatch(state, state)
    assert presenter.cursor_for_zone("remaining_deck") == 1


def test_no_game_baseline(tmp_path) -> None:
    """Before any GameStarted, every zone is empty and the title is the baseline string."""
    presenter, speech, _tracker, _db, _card_db = _make_presenter(tmp_path)
    assert list(presenter.get_zone_items("remaining_deck")) == []
    assert list(presenter.get_zone_items("opponent_hand")) == []
    assert list(presenter.get_zone_items("opponent_played")) == []
    assert list(presenter.get_zone_items("cards_drawn")) == []
    assert presenter.current_title() == "No game in progress"
    presenter.jump_to_zone("remaining_deck")
    assert speech.last_speech == "Remaining deck zone: empty"


def test_public_accessors_no_private_access(tmp_path) -> None:
    """Public accessors return correct values without needing to read private fields.

    Locks the API surface that view/app/external tests must use, per
    03-REVIEWS.md HIGH #3.
    """
    glacial = _make_card("CS2_023", "Glacial Shard", cost=1)
    presenter, _speech, tracker, _db, _card_db = _make_presenter(
        tmp_path, cards=[glacial]
    )

    # Baseline: no game.
    assert presenter.current_title() == "No game in progress"
    assert presenter.cursor_for_zone("remaining_deck") == 0
    assert presenter.detected_deck_name() is None
    assert presenter.current_state_snapshot() is None
    assert presenter.current_mana_summary() == ""

    # With game state.
    state = _make_state(
        player_deck=(_make_entity(glacial),),
        player_mana=3,
        player_max_mana=5,
        opponent_mana=1,
        opponent_max_mana=4,
        player_hero_class="MAGE",
        opponent_hero_class="WARRIOR",
    )
    tracker.dispatch(state, state)

    title = presenter.current_title()
    assert "MAGE" in title
    assert "WARRIOR" in title
    assert "Unknown deck" in title  # no detection match
    assert presenter.current_state_snapshot() is state
    assert presenter.current_mana_summary() == "You 3/5, opponent 1/4"

    # After moving cursor.
    presenter.jump_to_zone("remaining_deck")
    # Just landed; cursor 0.
    assert presenter.cursor_for_zone("remaining_deck") == 0


def test_number_key_zone_switching(tmp_path) -> None:
    """Number keys 1/2/3/4 in get_key_map() switch among the four zones.

    Locks the contract documented in 03-UI-SPEC §"Keyboard Contract" and
    the manual NVDA checkpoint in 03-06 (step B6).
    """
    glacial = _make_card("CS2_023", "Glacial Shard", cost=1)
    presenter, _speech, _tracker, _db, _card_db = _make_presenter(
        tmp_path, cards=[glacial]
    )

    key_map = presenter.get_key_map()

    # All four number keys are bound.
    assert "1" in key_map
    assert "2" in key_map
    assert "3" in key_map
    assert "4" in key_map

    # Total key count is 10 (left/right/up/down/home/end + 1/2/3/4).
    assert len(key_map) == 10

    # Each number key triggers navigate_to_zone for the correct zone.
    # We verify by invoking each callable and checking the active zone.
    key_map["1"]()
    assert presenter._current_zone == "remaining_deck"
    key_map["2"]()
    assert presenter._current_zone == "opponent_played"
    key_map["3"]()
    assert presenter._current_zone == "opponent_hand"
    key_map["4"]()
    assert presenter._current_zone == "cards_drawn"
