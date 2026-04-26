"""Game engine: consume Packets, emit typed events, maintain frozen GameState (D-05/D-06/D-07)."""

from __future__ import annotations

import dataclasses
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from hearthstone.enums import FormatType, GameType, Zone

from stonereader.models.card import Card, CardDatabase
from stonereader.models.game_state import GameEntity, GameState, Hero, PlayedCard
from stonereader.services._events import (
    AttackStarted,
    CardDrawn,
    CardPlayed,
    CardRemoved,
    CardRevealed,
    DamageDealt,
    GameEnded,
    GameEvent,
    GameStarted,
    MinionDied,
    MulliganDone,
    TurnChanged,
)
from stonereader.services._packets import (
    BlockEndPacket,
    BlockStartPacket,
    ChangeEntityPacket,
    CreateGamePacket,
    FullEntityPacket,
    HideEntityPacket,
    Packet,
    ShowEntityPacket,
    TagChangePacket,
)

logger = logging.getLogger(__name__)


_PLAYSTATE_NAMES: Dict[int, str] = {1: "PLAYING", 4: "WON", 5: "LOST", 8: "TIED"}

# Mulligan DONE state (hearthstone.enums.Mulligan.DONE = 4)
_MULLIGAN_DONE = 4


class GameEngine:
    """Translate internal Packets into GameEvents and frozen GameState snapshots.

    Engine NEVER imports hslog (D-10) and NEVER imports wx (kept reusable for Phase 4 replays).
    Subscribers see frozen snapshots only — internal bookkeeping (dicts, lists) is hidden.
    """

    def __init__(
        self,
        card_db: Optional[CardDatabase] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._card_db = card_db
        self._clock = clock
        self._start_time = self._clock()
        self._current_state: Optional[GameState] = None
        # Internal mutable bookkeeping (does not leak to subscribers)
        self._entities: Dict[int, dict] = {}  # entity_id -> mutable attrs
        self._block_stack: List[str] = []  # block types currently open
        self._block_subjects: List[int] = []  # entity_ids of current blocks
        self._player_played: List[PlayedCard] = []
        self._opponent_played: List[PlayedCard] = []
        self._player_drawn: List[PlayedCard] = []
        self._opponent_drawn: List[PlayedCard] = []
        self._player_starting_hand_ids: List[int] = []
        self._game_started_emitted = False
        self._game_ended_emitted = False
        self._mulligan_done_emitted = False
        # Default friendly player_id is 1.
        # TODO(WR-02): This stub is incorrect for the ~50 % of games where the
        # local player is assigned CONTROLLER=2 by the server coin-flip.  To
        # refine it we need the local player's BattleTag hi/lo (from the OS
        # account APIs or a Hearthstone startup log line) and compare against
        # CreateGamePacket.players hi/lo fields.  Until that data is wired in,
        # card draw / play events for local-player-as-entity-2 games will have
        # their controller attribution inverted.  See WR-02 in 02-REVIEW.md.
        self._friendly_player_id = 1

    @property
    def current_state(self) -> Optional[GameState]:
        return self._current_state

    def reset(self) -> None:
        """Drop ALL game state. Called by tracker on file rotation or process gone."""
        self._current_state = None
        self._entities.clear()
        self._block_stack.clear()
        self._block_subjects.clear()
        self._player_played.clear()
        self._opponent_played.clear()
        self._player_drawn.clear()
        self._opponent_drawn.clear()
        self._player_starting_hand_ids.clear()
        self._game_started_emitted = False
        self._game_ended_emitted = False
        self._mulligan_done_emitted = False

    def apply(self, packet: Packet) -> List[GameEvent]:
        """Apply a packet; return a list of zero or more events emitted."""
        events: List[GameEvent] = []
        try:
            if isinstance(packet, CreateGamePacket):
                events.extend(self._on_create_game(packet))
            elif isinstance(packet, TagChangePacket):
                events.extend(self._on_tag_change(packet))
            elif isinstance(packet, BlockStartPacket):
                events.extend(self._on_block_start(packet))
            elif isinstance(packet, BlockEndPacket):
                events.extend(self._on_block_end(packet))
            elif isinstance(packet, FullEntityPacket):
                self._record_entity(packet.entity_id, packet.card_id, packet.tags)
            elif isinstance(packet, ShowEntityPacket):
                events.extend(self._on_show_entity(packet))
            elif isinstance(packet, HideEntityPacket):
                events.extend(self._on_hide_entity(packet))
            elif isinstance(packet, ChangeEntityPacket):
                self._record_entity(packet.entity_id, packet.card_id, packet.tags)
        except Exception:
            # D-04 / Pitfall 3: never let one packet kill the engine
            logger.exception("engine apply failed for %s", type(packet).__name__)
        return events

    # ----------------------------------------------------------------- helpers

    def _now(self) -> float:
        return self._clock() - self._start_time

    def _current_turn(self) -> int:
        return self._current_state.turn if self._current_state is not None else 0

    def _record_entity(self, eid: int, card_id: str, tags: Dict[str, int]) -> None:
        ent = self._entities.setdefault(eid, {})
        if card_id:
            ent["card_id"] = card_id
        for k, v in tags.items():
            ent[k] = v

    def _lookup_card(self, card_id: str) -> Optional[Card]:
        if not card_id or self._card_db is None:
            return None
        try:
            return self._card_db.get_card_by_id(card_id)
        except Exception:
            return None

    @staticmethod
    def _enum_name(enum_cls: Any, value: int) -> str:
        try:
            return enum_cls(value).name.replace("GT_", "").replace("FT_", "")
        except (ValueError, KeyError):
            return ""

    # ----------------------------------------------------------------- handlers

    def _on_create_game(self, p: CreateGamePacket) -> List[GameEvent]:
        if self._game_started_emitted:
            # A second CREATE_GAME arrived before game ended (e.g. reconnect to
            # an in-progress game).  Log a warning so it is detectable, then
            # fall through to reset and re-emit — callers must handle duplicate
            # GameStarted events gracefully.
            logger.warning(
                "CREATE_GAME received while game already in progress — resetting"
            )
        self.reset()
        # Initialize entities for the GameEntity and Players
        self._record_entity(p.game_entity_id, "", p.initial_tags)
        for entity_id, name, _hi, _lo in p.players:
            self._record_entity(entity_id, "", {})
            self._entities[entity_id]["player_name"] = name
        # Build minimal initial GameState
        empty_hero = Hero(
            id="?",
            name="?",
            health=30,
            armor=0,
            hero_power="",
            hero_class="",
        )
        game_type_name = self._enum_name(GameType, p.initial_tags.get("GAME_TYPE", 0))
        format_type_name = self._enum_name(
            FormatType, p.initial_tags.get("FORMAT_TYPE", 0)
        )
        self._current_state = GameState(
            turn=0,
            active_player_id=1,
            player_board=(),
            opponent_board=(),
            player_hand=(),
            opponent_hand=(),
            player_hero=empty_hero,
            opponent_hero=empty_hero,
            game_type=game_type_name,
            format_type=format_type_name,
        )
        self._game_started_emitted = True
        return [
            GameStarted(
                timestamp=self._now(),
                turn=0,
                player_class="",
                opponent_class="",
                game_type=game_type_name,
                format_type=format_type_name,
            )
        ]

    def _on_tag_change(self, p: TagChangePacket) -> List[GameEvent]:
        ent = self._entities.setdefault(p.entity_id, {})
        prev = ent.get(p.tag)
        ent[p.tag] = p.value

        events: List[GameEvent] = []
        if p.tag == "TURN" and self._current_state is not None:
            self._current_state = dataclasses.replace(self._current_state, turn=p.value)
        elif (
            p.tag == "CURRENT_PLAYER"
            and p.value == 1
            and self._current_state is not None
        ):
            self._current_state = dataclasses.replace(
                self._current_state, active_player_id=p.entity_id
            )
            events.append(
                TurnChanged(
                    timestamp=self._now(),
                    turn=self._current_turn(),
                    active_player_id=p.entity_id,
                )
            )
        elif p.tag == "ZONE":
            events.extend(self._handle_zone_change(p.entity_id, prev, p.value))
        elif p.tag == "PLAYSTATE":
            events.extend(self._handle_playstate(p.entity_id, p.value))
        elif (
            p.tag == "DAMAGE"
            and self._block_stack
            and self._block_stack[-1] in ("ATTACK", "POWER")
        ):
            ent_data = self._entities.get(p.entity_id, {})
            events.append(
                DamageDealt(
                    timestamp=self._now(),
                    turn=self._current_turn(),
                    target_entity_id=p.entity_id,
                    amount=p.value,
                    target_controller=ent_data.get("CONTROLLER", 0),
                )
            )
        elif p.tag == "MULLIGAN_STATE" and p.value == _MULLIGAN_DONE:
            if not self._mulligan_done_emitted:
                self._mulligan_done_emitted = True
                events.append(
                    MulliganDone(timestamp=self._now(), turn=self._current_turn())
                )
        return events

    def _handle_zone_change(
        self, eid: int, prev: Any, new_zone: int
    ) -> List[GameEvent]:
        ent = self._entities.get(eid, {})
        controller = ent.get("CONTROLLER", 0)
        card_id = ent.get("card_id", "")
        base = self._lookup_card(card_id)
        name = base.name if base else card_id
        evs: List[GameEvent] = []
        if new_zone == int(Zone.HAND) and prev != int(Zone.HAND):
            pc = PlayedCard(
                entity_id=eid,
                card_id=card_id,
                base_card=base,
                name=name,
                turn=self._current_turn(),
                controller=controller,
            )
            if controller == self._friendly_player_id:
                self._player_drawn.append(pc)
            else:
                self._opponent_drawn.append(pc)
            evs.append(
                CardDrawn(
                    timestamp=self._now(),
                    turn=self._current_turn(),
                    entity_id=eid,
                    card_id=card_id,
                    base_card=base,
                    name=name,
                    controller=controller,
                )
            )
        elif new_zone == int(Zone.PLAY) and prev != int(Zone.PLAY):
            if self._block_stack and self._block_stack[-1] == "PLAY":
                pc = PlayedCard(
                    entity_id=eid,
                    card_id=card_id,
                    base_card=base,
                    name=name,
                    turn=self._current_turn(),
                    controller=controller,
                )
                if controller == self._friendly_player_id:
                    self._player_played.append(pc)
                else:
                    self._opponent_played.append(pc)
                evs.append(
                    CardPlayed(
                        timestamp=self._now(),
                        turn=self._current_turn(),
                        entity_id=eid,
                        card_id=card_id,
                        base_card=base,
                        name=name,
                        controller=controller,
                    )
                )
        elif new_zone == int(Zone.GRAVEYARD) and prev == int(Zone.PLAY):
            evs.append(
                MinionDied(
                    timestamp=self._now(),
                    turn=self._current_turn(),
                    entity_id=eid,
                    card_id=card_id,
                    name=name,
                    controller=controller,
                )
            )
        self._refresh_state()
        return evs

    def _handle_playstate(self, eid: int, value: int) -> List[GameEvent]:
        name = _PLAYSTATE_NAMES.get(value, "")
        if (
            value in (4, 5, 8)
            and self._current_state is not None
            and not self._game_ended_emitted
        ):
            self._game_ended_emitted = True
            new_player_state = (
                name
                if eid == self._friendly_player_id
                else self._current_state.player_playstate
            )
            new_opponent_state = (
                name
                if eid != self._friendly_player_id
                else self._current_state.opponent_playstate
            )
            self._current_state = dataclasses.replace(
                self._current_state,
                game_state="COMPLETE",
                player_playstate=new_player_state,
                opponent_playstate=new_opponent_state,
            )
            return [
                GameEnded(
                    timestamp=self._now(),
                    turn=self._current_turn(),
                    player_playstate=self._current_state.player_playstate,
                    opponent_playstate=self._current_state.opponent_playstate,
                )
            ]
        return []

    def _on_block_start(self, p: BlockStartPacket) -> List[GameEvent]:
        self._block_stack.append(p.block_type)
        self._block_subjects.append(p.entity_id)
        if p.block_type == "ATTACK":
            ent = self._entities.get(p.entity_id, {})
            return [
                AttackStarted(
                    timestamp=self._now(),
                    turn=self._current_turn(),
                    attacker_entity_id=p.entity_id,
                    defender_entity_id=p.target_id or 0,
                    attacker_controller=ent.get("CONTROLLER", 0),
                )
            ]
        return []

    def _on_block_end(self, _p: BlockEndPacket) -> List[GameEvent]:
        if self._block_stack:
            self._block_stack.pop()
        if self._block_subjects:
            self._block_subjects.pop()
        return []

    def _on_show_entity(self, p: ShowEntityPacket) -> List[GameEvent]:
        ent = self._entities.get(p.entity_id, {})
        previously_hidden = not ent.get("card_id")
        self._record_entity(p.entity_id, p.card_id, p.tags)
        if previously_hidden and p.card_id:
            base = self._lookup_card(p.card_id)
            return [
                CardRevealed(
                    timestamp=self._now(),
                    turn=self._current_turn(),
                    entity_id=p.entity_id,
                    card_id=p.card_id,
                    base_card=base,
                    name=base.name if base else p.card_id,
                    controller=ent.get("CONTROLLER", 0),
                )
            ]
        return []

    def _on_hide_entity(self, p: HideEntityPacket) -> List[GameEvent]:
        ent = self._entities.get(p.entity_id, {})
        return [
            CardRemoved(
                timestamp=self._now(),
                turn=self._current_turn(),
                entity_id=p.entity_id,
                card_id=ent.get("card_id", ""),
                controller=ent.get("CONTROLLER", 0),
            )
        ]

    def _refresh_state(self) -> None:
        """Rebuild the published snapshot from internal bookkeeping."""
        if self._current_state is None:
            return
        self._current_state = dataclasses.replace(
            self._current_state,
            player_played=tuple(self._player_played),
            opponent_played=tuple(self._opponent_played),
            player_drawn=tuple(self._player_drawn),
            opponent_drawn=tuple(self._opponent_drawn),
        )


# Quiet "unused import" warnings for symbols we want re-exported via type hints.
_ = GameEntity
