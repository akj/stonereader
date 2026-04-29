"""Game engine: consume Packets, emit typed events, maintain frozen GameState (D-05/D-06/D-07)."""

from __future__ import annotations

import dataclasses
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from hearthstone.enums import CardType, FormatType, GameType, Zone

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
        # WR-02 / D-18: friendly player resolution.
        # Default to 1 (correct for vs-AI captures and for the half of games
        # where the local player is Player 1). The AI heuristic at CREATE_GAME
        # refines this immediately; the SHOW_ENTITY-into-HAND fallback handles
        # multiplayer games where both players have lo != 0. On resolution,
        # _rebucket_from_entities recomputes the published drawn/played lists
        # from authoritative _entities CONTROLLER tags so MIXED-timing events
        # (some before resolution, some after) are all correctly attributed in
        # the final GameState.
        self._friendly_player_id: int = 1
        self._friendly_player_resolved: bool = False

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
        # WR-02: clear friendly-player resolution so a new CREATE_GAME (e.g.
        # reconnect to a different server-assigned slot) re-resolves cleanly.
        self._friendly_player_resolved = False
        self._friendly_player_id = 1

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
        # D-19: lineage capture — opponent-hand entities generated inside a POWER block.
        #
        # Captures the INNERMOST POWER block subject (top of _block_subjects stack).
        # Lineage is best-effort and approximate (see GameEntity.creation_lineage docs):
        # - Only fires when the innermost open block is POWER.
        # - Sticky once set ("creation_lineage" not in ent): later TAG_CHANGE or
        #   SHOW_ENTITY reveals do NOT overwrite (verified by test_show_entity_after_lineage).
        # - Friendly entities are excluded (controller == _friendly_player_id).
        if (
            self._block_stack
            and self._block_stack[-1] == "POWER"
            and self._block_subjects
            and ent.get("ZONE") == int(Zone.HAND)
            and ent.get("CONTROLLER") is not None
            and ent.get("CONTROLLER") != self._friendly_player_id
            and "creation_lineage" not in ent
        ):
            subject_eid = self._block_subjects[-1]  # INNERMOST subject
            subject_card_id = self._entities.get(subject_eid, {}).get("card_id", "")
            subject_card = (
                self._lookup_card(subject_card_id) if subject_card_id else None
            )
            if subject_card:
                ent["creation_lineage"] = subject_card.name
        # D-19: bookkeeping changed → republish the snapshot so opponent_hand
        # reflects newly-arrived / updated entities. _refresh_state is a no-op
        # if _current_state is None (pre-CREATE_GAME), so this is safe to
        # invoke unconditionally for every record. Existing zone-change events
        # already call _refresh_state from _handle_zone_change.
        self._refresh_state()
        # gap-closure 03-07: late-arriving FullEntity packets for hero entities
        # (FULL_ENTITY may bring CARDTYPE/CONTROLLER after CREATE_GAME's initial
        # placeholder Hero is published). Cheap CARDTYPE guard avoids running
        # the hero loop for every minion record.
        if ent.get("CARDTYPE") == int(CardType.HERO):
            self._resolve_heroes()

    def _lookup_card(self, card_id: str) -> Optional[Card]:
        if not card_id or self._card_db is None:
            return None
        try:
            return self._card_db.get_card_by_id(card_id)
        except Exception:
            return None

    # ----------------------------------------------------------------- hero resolution (gap-closure 03-07)
    def _resolve_heroes(self) -> None:
        """Refine player_hero / opponent_hero from CARDTYPE==HERO entities.

        Iterates self._entities for hero entities, looks up the hero Card
        via card_db, and replaces the empty placeholder Hero on the
        published state with a real Hero (id, name, hero_class).

        Idempotent — safe to call multiple times. When card_id is unknown
        or card_db is None, the hero entity is skipped and we'll re-resolve
        on the next packet that fills in card_id (typically SHOW_ENTITY).
        """
        if self._current_state is None:
            return
        new_player_hero: Optional[Hero] = None
        new_opponent_hero: Optional[Hero] = None
        for ent in self._entities.values():
            if ent.get("CARDTYPE") != int(CardType.HERO):
                continue
            controller = ent.get("CONTROLLER")
            if controller is None:
                continue
            card_id = ent.get("card_id", "") or ""
            card = self._lookup_card(card_id)
            if card is None:
                continue
            # WR-02: use `is None` rather than `or` so a legitimate HEALTH=0
            # in the log (e.g. SHOW_ENTITY rebroadcast after lethal) is
            # preserved instead of being clamped back to 30.
            health_raw = ent.get("HEALTH")
            health = 30 if health_raw is None else int(health_raw)
            armor_raw = ent.get("ARMOR")
            armor = 0 if armor_raw is None else int(armor_raw)
            hero = Hero(
                id=card.id,
                name=card.name,
                health=health,
                armor=armor,
                hero_power="",
                hero_class=card.card_class,
            )
            if int(controller) == self._friendly_player_id:
                new_player_hero = hero
            else:
                new_opponent_hero = hero
        if new_player_hero is None and new_opponent_hero is None:
            return
        replacements: Dict[str, Any] = {}
        if new_player_hero is not None:
            replacements["player_hero"] = new_player_hero
        if new_opponent_hero is not None:
            replacements["opponent_hero"] = new_opponent_hero
        self._current_state = dataclasses.replace(self._current_state, **replacements)

    @staticmethod
    def _enum_name(enum_cls: Any, value: int) -> str:
        try:
            return enum_cls(value).name.replace("GT_", "").replace("FT_", "")
        except (ValueError, KeyError):
            return ""

    # ----------------------------------------------------------------- WR-02

    def _resolve_friendly_player_ai_heuristic(self, players: Any) -> None:
        """WR-02 fast-path. Mirrors hslog.export.FriendlyPlayerExporter logic.

        If exactly one player has lo == 0 (AI account) and one has lo != 0
        (real account), the real account is friendly. Resolves immediately
        on CREATE_GAME consumption.
        """
        ai_pids: List[int] = []
        real_pids: List[int] = []
        for _entity_id, player_id, _name, _hi, lo in players:
            if lo == 0:
                ai_pids.append(player_id)
            else:
                real_pids.append(player_id)
        if len(ai_pids) == 1 and len(real_pids) == 1:
            new_friendly = real_pids[0]
            if new_friendly != self._friendly_player_id:
                self._friendly_player_id = new_friendly
                self._rebucket_from_entities()
            self._friendly_player_resolved = True

    def _resolve_friendly_player_show_entity_fallback(
        self, p: ShowEntityPacket
    ) -> None:
        """WR-02 slow-path. The first SHOW_ENTITY into HAND determines friendly.

        Per FriendlyPlayerExporter: in multiplayer games (both players have
        lo != 0), watch CONTROLLER tags during FULL_ENTITY/SHOW_ENTITY. The
        first SHOW_ENTITY whose target zone is HAND is the friendly player's
        first revealed mulligan card → that entity's controller IS the friendly
        player_id.
        """
        new_zone = p.tags.get("ZONE")
        if new_zone != int(Zone.HAND):
            return
        controller = p.tags.get("CONTROLLER")
        if controller is None:
            ent = self._entities.get(p.entity_id, {})
            controller = ent.get("CONTROLLER")
        if controller is None:
            return
        new_friendly = int(controller)
        if new_friendly != self._friendly_player_id:
            self._friendly_player_id = new_friendly
            self._rebucket_from_entities()
        self._friendly_player_resolved = True

    def _rebucket_from_entities(self) -> None:
        """Re-attribute prior drawn/played rows using AUTHORITATIVE _entities CONTROLLER state.

        Replaces the old 'swap accumulated lists' approach (03-REVIEWS.md
        HIGH #2): the swap was correct only when ALL pre-resolution events
        were uniformly inverted. With mixed timing — some events before
        resolution (potentially wrong bucket using default _friendly_player_id=1),
        some after (correct bucket) — the swap would un-correct the
        post-resolution rows.

        This implementation walks each row, looks up the authoritative
        CONTROLLER from self._entities[row.entity_id], and places the row in
        the correct bucket based on the now-resolved _friendly_player_id.
        Rows whose entity is no longer in _entities (extremely rare) fall
        back to their own .controller attribute.
        """

        def _is_friendly(entity_id: int, fallback_controller: int) -> bool:
            ent = self._entities.get(entity_id, {})
            controller = ent.get("CONTROLLER", fallback_controller)
            return int(controller) == self._friendly_player_id

        all_drawn = list(self._player_drawn) + list(self._opponent_drawn)
        new_player_drawn: List[PlayedCard] = []
        new_opponent_drawn: List[PlayedCard] = []
        for row in all_drawn:
            if _is_friendly(row.entity_id, row.controller):
                new_player_drawn.append(row)
            else:
                new_opponent_drawn.append(row)
        self._player_drawn = new_player_drawn
        self._opponent_drawn = new_opponent_drawn

        all_played = list(self._player_played) + list(self._opponent_played)
        new_player_played: List[PlayedCard] = []
        new_opponent_played: List[PlayedCard] = []
        for row in all_played:
            if _is_friendly(row.entity_id, row.controller):
                new_player_played.append(row)
            else:
                new_opponent_played.append(row)
        self._player_played = new_player_played
        self._opponent_played = new_opponent_played

        # gap-closure 03-07 follow-up (BL-01): heroes were classified at
        # FULL_ENTITY/CREATE_GAME time using the previous _friendly_player_id.
        # Re-run the full hero pass so player_hero / opponent_hero swap when
        # friendly flips from default 1 → real friendly player_id (multiplayer
        # SHOW_ENTITY-into-HAND fallback path).
        self._resolve_heroes()
        # gap-closure 03-07 follow-up (WR-01): RESOURCES rows on the player
        # entities still carry the correct PLAYER_ID; re-derive mana for both
        # sides from authoritative state so any pre-resolution RESOURCES /
        # RESOURCES_USED updates that wrote to the wrong side are corrected.
        self._reapply_mana_from_entities()

        self._refresh_state()

    def _reapply_mana_from_entities(self) -> None:
        """Re-derive player/opponent mana from authoritative PLAYER_ID rows.

        gap-closure 03-07 follow-up (WR-01): RESOURCES / RESOURCES_USED tag
        changes that arrived before the SHOW_ENTITY-into-HAND fallback
        resolved friendly_player_id were classified using the default
        `_friendly_player_id == 1`. After the fallback flips the friendly
        player_id, the mana fields on the published GameState are stale.
        This helper walks each player entity row, reads RESOURCES /
        RESOURCES_USED off the row, and re-attributes mana using the now-
        resolved _friendly_player_id.
        """
        if self._current_state is None:
            return
        replacements: Dict[str, Any] = {}
        for ent in self._entities.values():
            player_id = ent.get("PLAYER_ID")
            if player_id is None:
                continue
            resources = ent.get("RESOURCES", 0) or 0
            resources_used = ent.get("RESOURCES_USED", 0) or 0
            mana = max(0, resources - resources_used)
            if int(player_id) == self._friendly_player_id:
                replacements["player_mana"] = mana
                replacements["player_max_mana"] = resources
            else:
                replacements["opponent_mana"] = mana
                replacements["opponent_max_mana"] = resources
        if replacements:
            self._current_state = dataclasses.replace(
                self._current_state, **replacements
            )

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
        for entity_id, player_id, name, _hi, _lo in p.players:
            self._record_entity(entity_id, "", {})
            self._entities[entity_id]["player_name"] = name
            self._entities[entity_id]["PLAYER_ID"] = player_id
        # WR-02: AI heuristic for friendly player resolution.
        self._resolve_friendly_player_ai_heuristic(p.players)
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
        # gap-closure 03-07: hero entities for both players are typically
        # recorded inside the CREATE_GAME block via FullEntity packets BEFORE
        # the GameState is constructed above (every preceding _record_entity
        # call has already populated _entities). Resolve heroes once so the
        # initial GameState carries non-empty player_hero / opponent_hero.
        self._resolve_heroes()
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
        elif (
            p.tag in ("RESOURCES", "RESOURCES_USED") and self._current_state is not None
        ):
            # gap-closure 03-07: RESOURCES is the per-turn max mana the player
            # has access to (Hearthstone displays this as "Y" in the X/Y mana
            # crystal HUD); RESOURCES_USED is what was spent this turn. The
            # rendered mana value is RESOURCES - RESOURCES_USED, clamped at 0.
            #
            # Tag attaches to the player entity, so PLAYER_ID on the same
            # entity row identifies which side to update. setdefault above
            # has already written p.value to ent[p.tag], so re-reading the
            # complementary tag from _entities is safe.
            player_id = ent.get("PLAYER_ID")
            if player_id is not None:
                resources = ent.get("RESOURCES", 0) or 0
                resources_used = ent.get("RESOURCES_USED", 0) or 0
                mana = max(0, resources - resources_used)
                if int(player_id) == self._friendly_player_id:
                    self._current_state = dataclasses.replace(
                        self._current_state,
                        player_mana=mana,
                        player_max_mana=resources,
                    )
                else:
                    self._current_state = dataclasses.replace(
                        self._current_state,
                        opponent_mana=mana,
                        opponent_max_mana=resources,
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
        # gap-closure 03-07: SHOW_ENTITY may reveal a hero card_id that was
        # missing on initial CREATE_GAME. Re-resolve heroes BEFORE the
        # friendly-player fallback so the early-return path on previously
        # hidden cards still benefits from hero resolution.
        if self._entities.get(p.entity_id, {}).get("CARDTYPE") == int(CardType.HERO):
            self._resolve_heroes()
        # WR-02: SHOW_ENTITY-into-HAND fallback (multiplayer games where both
        # players have lo != 0 and the AI heuristic at CREATE_GAME could not
        # disambiguate).
        if not self._friendly_player_resolved:
            self._resolve_friendly_player_show_entity_fallback(p)
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
        """Rebuild the published snapshot from internal bookkeeping.

        D-19: reconstructs opponent_hand from self._entities. Iteration over
        the dict (keyed by entity_id) implicitly dedupes — there is exactly
        one bookkeeping entry per entity, so duplicate hand entries are
        impossible by construction.

        Gap-closure 03-07: also rebuilds player_deck (live remaining-deck
        for the friendly player) and derives player_deck_count /
        opponent_deck_count from per-controller ZONE==DECK counts. NUM_CARDS
        _IN_DECK is NOT exposed as a GameTag in hearthstone.enums, so the
        count must be computed here.
        """
        if self._current_state is None:
            return
        opponent_hand_entities: List[GameEntity] = []
        player_deck_entities: List[GameEntity] = []
        player_deck_count = 0
        opponent_deck_count = 0
        deck_zone = int(Zone.DECK)
        hand_zone = int(Zone.HAND)
        for eid, ent in self._entities.items():
            zone = ent.get("ZONE")
            controller = ent.get("CONTROLLER")
            if controller is None:
                continue
            controller_int = int(controller)
            if zone == deck_zone:
                if controller_int == self._friendly_player_id:
                    player_deck_count += 1
                    card_id = ent.get("card_id", "") or ""
                    base = self._lookup_card(card_id) if card_id else None
                    drawn_turn_raw = ent.get("drawn_turn", -1)
                    drawn_turn = (
                        drawn_turn_raw if isinstance(drawn_turn_raw, int) else -1
                    )
                    player_deck_entities.append(
                        GameEntity(
                            entity_id=eid,
                            card_id=card_id,
                            base_card=base,
                            name=base.name if base else "",
                            cost=base.cost if base else 0,
                            current_attack=ent.get("ATK", 0) or 0,
                            current_health=ent.get("HEALTH", 0) or 0,
                            card_type=base.card_type if base else "",
                            zone="DECK",
                            zone_position=ent.get("ZONE_POSITION", 0) or 0,
                            controller=controller_int,
                            drawn_turn=drawn_turn,
                            creation_lineage=ent.get("creation_lineage", "") or "",
                        )
                    )
                else:
                    opponent_deck_count += 1
                continue
            if zone == hand_zone and controller_int != self._friendly_player_id:
                card_id = ent.get("card_id", "") or ""
                base = self._lookup_card(card_id) if card_id else None
                drawn_turn_raw = ent.get("drawn_turn", -1)
                drawn_turn = drawn_turn_raw if isinstance(drawn_turn_raw, int) else -1
                opponent_hand_entities.append(
                    GameEntity(
                        entity_id=eid,
                        card_id=card_id,
                        base_card=base,
                        name=base.name if base else "",
                        cost=base.cost if base else 0,
                        current_attack=ent.get("ATK", 0) or 0,
                        current_health=ent.get("HEALTH", 0) or 0,
                        card_type=base.card_type if base else "",
                        zone="HAND",
                        zone_position=ent.get("ZONE_POSITION", 0) or 0,
                        controller=controller_int,
                        drawn_turn=drawn_turn,
                        creation_lineage=ent.get("creation_lineage", "") or "",
                    )
                )
        opponent_hand_entities.sort(key=lambda e: e.zone_position)
        player_deck_entities.sort(key=lambda e: e.zone_position)
        self._current_state = dataclasses.replace(
            self._current_state,
            player_played=tuple(self._player_played),
            opponent_played=tuple(self._opponent_played),
            player_drawn=tuple(self._player_drawn),
            opponent_drawn=tuple(self._opponent_drawn),
            opponent_hand=tuple(opponent_hand_entities),
            player_deck=tuple(player_deck_entities),
            player_deck_count=player_deck_count,
            opponent_deck_count=opponent_deck_count,
        )


# Quiet "unused import" warnings for symbols we want re-exported via type hints.
_ = GameEntity
