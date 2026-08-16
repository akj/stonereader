from __future__ import annotations

from dataclasses import replace

from stonereader.models.card import Card, CardDatabase
from stonereader.models.game_state import AttackInProgress, GameEntity, GameState, Hero
from stonereader.services._narrator import Narrator


class _FakeAnnouncer:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def narrate(self, text: str) -> None:
        self.spoken.append(text)


def _card(card_id: str, name: str) -> Card:
    return Card(
        card_id,
        len(card_id),
        name,
        1,
        1,
        1,
        "",
        "COMMON",
        "NEUTRAL",
        "MINION",
    )


def _entity(
    entity_id: int,
    card: Card | None,
    zone: str,
    controller: int,
    *,
    name: str | None = None,
) -> GameEntity:
    return GameEntity(
        entity_id=entity_id,
        card_id=card.id if card is not None else "",
        base_card=card,
        name=(card.name if card is not None else "") if name is None else name,
        cost=card.cost if card is not None else 0,
        current_attack=card.attack or 0 if card is not None else 0,
        current_health=card.health or 0 if card is not None else 0,
        card_type=card.card_type if card is not None else "",
        zone=zone,
        zone_position=1,
        controller=controller,
    )


def _state(**overrides: object) -> GameState:
    values: dict[str, object] = {
        "turn": 1,
        "active_player_id": 1,
        "player_board": (),
        "opponent_board": (),
        "player_hand": (),
        "opponent_hand": (),
        "player_hero": Hero("p", "Jaina", 30, 0, "", "MAGE"),
        "opponent_hero": Hero("o", "Garrosh", 30, 0, "", "WARRIOR"),
    }
    values.update(overrides)
    return GameState(**values)  # type: ignore[arg-type]


def _narrator(preset: list[str], *cards: Card) -> tuple[Narrator, _FakeAnnouncer]:
    announcer = _FakeAnnouncer()
    card_db = CardDatabase(cards_by_id={card.id: card for card in cards})
    narrator = Narrator(announcer, lambda: preset[0], card_db)  # type: ignore[arg-type]
    return narrator, announcer


def test_off_and_live_preset_changes_filter_at_each_state_update() -> None:
    preset = ["off"]
    narrator, announcer = _narrator(preset)
    prev = _state(active_player_id=1)
    curr = replace(prev, turn=2, active_player_id=2)

    narrator.on_state(prev, curr)
    assert announcer.spoken == []

    preset[0] = "key_moments"
    narrator.on_state(prev, curr)
    assert announcer.spoken == ["Turn 2, opponent's"]


def test_key_moments_speaks_decision_changing_events_only() -> None:
    fireball = _card("FIREBALL", "Fireball")
    yeti = _card("YETI", "Yeti")
    trap = _card("TRAP", "Freezing Trap")
    preset = ["key_moments"]
    narrator, announcer = _narrator(preset, fireball, yeti, trap)

    narrator.on_state(_state(active_player_id=1), _state(turn=2, active_player_id=2))

    enemy_hand = _entity(10, fireball, "HAND", 2)
    enemy_play = _entity(10, fireball, "PLAY", 2)
    narrator.on_state(
        _state(opponent_hand=(enemy_hand,), block_stack=("PLAY",)),
        _state(opponent_board=(enemy_play,), block_stack=("PLAY",)),
    )

    alive = _entity(20, yeti, "PLAY", 2)
    dead = _entity(20, yeti, "GRAVEYARD", 2)
    narrator.on_state(
        _state(opponent_board=(alive,)),
        _state(graveyard=(dead,)),
    )

    hidden_hand = _entity(30, None, "HAND", 2)
    hidden_secret = _entity(30, None, "SECRET", 2)
    narrator.on_state(
        _state(opponent_hand=(hidden_hand,)),
        _state(opponent_secrets=(hidden_secret,)),
    )
    revealed_secret = _entity(30, trap, "GRAVEYARD", 2)
    narrator.on_state(
        _state(opponent_secrets=(hidden_secret,)),
        _state(graveyard=(revealed_secret,)),
    )

    narrator.on_state(
        _state(game_state="RUNNING"),
        _state(
            game_state="COMPLETE",
            player_playstate="WON",
            opponent_playstate="LOST",
        ),
    )

    assert announcer.spoken == [
        "Turn 2, opponent's",
        "Opponent played Fireball",
        "Yeti died",
        "Opponent played a secret",
        "Secret revealed, Freezing Trap",
        "Game over, won",
    ]


def test_everything_adds_draws_and_attacks_but_never_friendly_plays() -> None:
    fireball = _card("FIREBALL", "Fireball")
    boar = _card("BOAR", "Boar")
    yeti = _card("YETI", "Yeti")
    preset = ["everything"]
    narrator, announcer = _narrator(preset, fireball, boar, yeti)

    friendly_deck = _entity(40, fireball, "DECK", 1, name="")
    friendly_hand = _entity(40, fireball, "HAND", 1, name="")
    narrator.on_state(
        _state(player_deck=(friendly_deck,)),
        _state(player_hand=(friendly_hand,)),
    )

    opponent_deck = _entity(41, fireball, "DECK", 2)
    opponent_hand = _entity(41, fireball, "HAND", 2)
    narrator.on_state(
        _state(player_deck=(opponent_deck,)),
        _state(opponent_hand=(opponent_hand,)),
    )

    attacker = _entity(50, boar, "PLAY", 1)
    defender = _entity(51, yeti, "PLAY", 2)
    narrator.on_state(
        _state(player_board=(attacker,), opponent_board=(defender,)),
        _state(
            player_board=(attacker,),
            opponent_board=(defender,),
            attack_in_progress=AttackInProgress(50, 51, 1),
        ),
    )

    friendly_play = _entity(40, fireball, "PLAY", 1)
    narrator.on_state(
        _state(player_hand=(friendly_hand,), block_stack=("PLAY",)),
        _state(player_board=(friendly_play,), block_stack=("PLAY",)),
    )

    assert announcer.spoken == [
        "You drew Fireball",
        "Opponent drew a card",
        "Boar attacks Yeti",
    ]


def test_key_moments_excludes_draws_and_attacks() -> None:
    card = _card("CARD", "Known Name")
    preset = ["key_moments"]
    narrator, announcer = _narrator(preset, card)
    in_deck = _entity(70, card, "DECK", 1)
    in_hand = _entity(70, card, "HAND", 1)
    narrator.on_state(_state(player_deck=(in_deck,)), _state(player_hand=(in_hand,)))

    attacker = _entity(71, card, "PLAY", 1)
    target = _entity(72, card, "PLAY", 2)
    narrator.on_state(
        _state(player_board=(attacker,), opponent_board=(target,)),
        _state(
            player_board=(attacker,),
            opponent_board=(target,),
            attack_in_progress=AttackInProgress(71, 72, 1),
        ),
    )

    assert announcer.spoken == []
