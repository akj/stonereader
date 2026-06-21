"""Game engine: pure Packet → GameState reducer (D-05/D-06/D-07).

Issue #5: the engine no longer constructs GameEvent instances. Subscribers
receive `(prev, curr)` GameState pairs from the tracker and call `diff()`
when they want event-typed information. Engine output is the next
`current_state` only.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from hearthstone.enums import CardType, FormatType, GameType, Zone

from stonereader.models.card import Card, CardDatabase
from stonereader.models.game_state import (
    AttackInProgress,
    GameEntity,
    GameState,
    Hero,
    PlayedCard,
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
    """Pure Packet → GameState reducer.

    Engine NEVER imports hslog (D-10) and NEVER imports wx (kept reusable for Phase 4 replays).
    Subscribers see frozen snapshots only — internal bookkeeping (dicts, lists) is hidden.
    Issue #5: apply() returns None; subscribers diff successive snapshots themselves.
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
        self._game_started: bool = False
        self._game_ended: bool = False
        self._mulligan_complete: bool = False
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
        self._game_started = False
        self._game_ended = False
        self._mulligan_complete = False
        # WR-02: clear friendly-player resolution so a new CREATE_GAME (e.g.
        # reconnect to a different server-assigned slot) re-resolves cleanly.
        self._friendly_player_resolved = False
        self._friendly_player_id = 1

    def force_friendly_player(self, player_id: int) -> None:
        """Authoritatively pin the friendly player_id (used by replay loading).

        A replay's friendly side is known from metadata (FriendlyPlayerExporter),
        not heuristics. CREATE_GAME calls reset() and re-runs the live AI
        heuristic, which can disagree with the recorded side (e.g. a Player-2
        replay). The replay loader calls this AFTER the CREATE_GAME packet to
        override that result and mark resolution final so the SHOW_ENTITY
        fallback cannot change it. Re-buckets already-recorded rows when the id
        actually changes. No-op for an out-of-range player_id.
        """
        if player_id not in (1, 2):
            return
        if player_id != self._friendly_player_id:
            self._friendly_player_id = player_id
            self._rebucket_from_entities()
        self._friendly_player_resolved = True

    def apply(self, packet: Packet) -> None:
        """Apply a packet, mutating internal state and republishing current_state.

        Returns None — subscribers derive events from successive GameState pairs
        via stonereader.services._diff.diff (issue #5).
        """
        try:
            if isinstance(packet, CreateGamePacket):
                self._on_create_game(packet)
            elif isinstance(packet, TagChangePacket):
                self._on_tag_change(packet)
            elif isinstance(packet, BlockStartPacket):
                self._on_block_start(packet)
            elif isinstance(packet, BlockEndPacket):
                self._on_block_end(packet)
            elif isinstance(packet, FullEntityPacket):
                self._record_entity(packet.entity_id, packet.card_id, packet.tags)
            elif isinstance(packet, ShowEntityPacket):
                self._on_show_entity(packet)
            elif isinstance(packet, HideEntityPacket):
                self._on_hide_entity(packet)
            elif isinstance(packet, ChangeEntityPacket):
                self._record_entity(packet.entity_id, packet.card_id, packet.tags)
        except Exception:
            # D-04 / Pitfall 3: never let one packet kill the engine
            logger.exception("engine apply failed for %s", type(packet).__name__)

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

    def _on_create_game(self, p: CreateGamePacket) -> None:
        if self._game_started:
            # A second CREATE_GAME arrived before game ended (e.g. reconnect to
            # an in-progress game).  Log a warning so it is detectable, then
            # fall through to reset.
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
        # gap-closure 03-07 (WR-03): defensive — handles the rare case where
        # a hero entity was recorded into _entities during the loop above
        # (e.g. via a future hslog version that inlines hero FULL_ENTITY rows
        # under CreateGame.entities). In the current hslog version this is a
        # no-op because hero FullEntities arrive on subsequent apply() calls,
        # where _record_entity re-runs _resolve_heroes (line 184). Keep the
        # call so the rare inlined-entities path still benefits.
        self._resolve_heroes()
        self._game_started = True

    def _on_tag_change(self, p: TagChangePacket) -> None:
        ent = self._entities.setdefault(p.entity_id, {})
        prev = ent.get(p.tag)
        ent[p.tag] = p.value

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
        elif p.tag == "ZONE":
            self._handle_zone_change(p.entity_id, prev, p.value)
        elif p.tag == "PLAYSTATE":
            self._handle_playstate(p.entity_id, p.value)
        elif p.tag == "MULLIGAN_STATE" and p.value == _MULLIGAN_DONE:
            if not self._mulligan_complete:
                self._mulligan_complete = True
                if self._current_state is not None:
                    self._current_state = dataclasses.replace(
                        self._current_state, mulligan_complete=True
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

    def _handle_zone_change(self, eid: int, prev: Any, new_zone: int) -> None:
        ent = self._entities.get(eid, {})
        controller = ent.get("CONTROLLER", 0)
        card_id = ent.get("card_id", "")
        base = self._lookup_card(card_id)
        name = base.name if base else card_id
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
        self._refresh_state()

    def _handle_playstate(self, eid: int, value: int) -> None:
        name = _PLAYSTATE_NAMES.get(value, "")
        if (
            value in (4, 5, 8)
            and self._current_state is not None
            and not self._game_ended
        ):
            self._game_ended = True
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

    def _on_block_start(self, p: BlockStartPacket) -> None:
        self._block_stack.append(p.block_type)
        self._block_subjects.append(p.entity_id)
        self._mirror_block_stack()
        if p.block_type == "ATTACK":
            ent = self._entities.get(p.entity_id, {})
            attacker_controller = ent.get("CONTROLLER", 0)
            defender_entity_id = p.target_id or 0
            if self._current_state is not None:
                self._current_state = dataclasses.replace(
                    self._current_state,
                    attack_in_progress=AttackInProgress(
                        attacker_entity_id=p.entity_id,
                        defender_entity_id=defender_entity_id,
                        attacker_controller=attacker_controller,
                    ),
                )

    def _on_block_end(self, p: BlockEndPacket) -> None:
        if self._block_stack:
            self._block_stack.pop()
        if self._block_subjects:
            self._block_subjects.pop()
        self._mirror_block_stack()
        if p.block_type == "ATTACK" and self._current_state is not None:
            self._current_state = dataclasses.replace(
                self._current_state, attack_in_progress=None
            )

    def _mirror_block_stack(self) -> None:
        """Issue #3: keep GameState.block_stack in lockstep with self._block_stack."""
        if self._current_state is None:
            return
        self._current_state = dataclasses.replace(
            self._current_state, block_stack=tuple(self._block_stack)
        )

    def _on_show_entity(self, p: ShowEntityPacket) -> None:
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

    def _on_hide_entity(self, p: HideEntityPacket) -> None:
        # HIDE_ENTITY currently has no GameState side effect: the engine relies
        # on companion TAG_CHANGE/SHOW_ENTITY packets to update zones. Kept as
        # a no-op for future zone-bookkeeping if needed.
        return

    def _entity_view(
        self, eid: int, ent: Dict[str, Any], zone_name: str, controller_int: int
    ) -> GameEntity:
        """Build a published GameEntity from internal bookkeeping for `eid`.

        Carries the int GameTag map (ATK/HEALTH/DAMAGE/...) through as ``tags``
        so the pure diff seam can recover DamageDealt etc. from board entities.
        """
        card_id = ent.get("card_id", "") or ""
        base = self._lookup_card(card_id) if card_id else None
        drawn_turn_raw = ent.get("drawn_turn", -1)
        drawn_turn = drawn_turn_raw if isinstance(drawn_turn_raw, int) else -1
        tags = {k: v for k, v in ent.items() if isinstance(v, int)}
        return GameEntity(
            entity_id=eid,
            card_id=card_id,
            base_card=base,
            name=base.name if base else "",
            cost=base.cost if base else 0,
            current_attack=ent.get("ATK", 0) or 0,
            current_health=ent.get("HEALTH", 0) or 0,
            card_type=base.card_type if base else "",
            zone=zone_name,
            zone_position=ent.get("ZONE_POSITION", 0) or 0,
            controller=controller_int,
            drawn_turn=drawn_turn,
            tags=tags,
            creation_lineage=ent.get("creation_lineage", "") or "",
        )

    def _refresh_state(self) -> None:
        """Rebuild the published snapshot from internal bookkeeping.

        Projects every navigable Zone from self._entities onto GameState so the
        Live surface AND the Replay viewer (PRD #7) can inspect them:
          - PLAY-zone MINIONs  -> player_board / opponent_board
          - PLAY-zone WEAPONs  -> player_weapon / opponent_weapon (0-or-1)
          - HAND               -> player_hand / opponent_hand
          - SECRET             -> player_secrets / opponent_secrets
          - DECK               -> player_deck (friendly) + per-side deck counts
        Heroes are refined separately (CARDTYPE==HERO pass). Iteration over the
        entity dict (keyed by entity_id) implicitly dedupes — exactly one
        bookkeeping entry per entity. NUM_CARDS_IN_DECK is not a GameTag, so the
        deck counts are computed here.
        """
        if self._current_state is None:
            return
        player_board: List[GameEntity] = []
        opponent_board: List[GameEntity] = []
        player_hand: List[GameEntity] = []
        opponent_hand: List[GameEntity] = []
        player_secrets: List[GameEntity] = []
        opponent_secrets: List[GameEntity] = []
        player_weapons: List[GameEntity] = []
        opponent_weapons: List[GameEntity] = []
        player_deck_entities: List[GameEntity] = []
        player_deck_count = 0
        opponent_deck_count = 0
        play_zone = int(Zone.PLAY)
        deck_zone = int(Zone.DECK)
        hand_zone = int(Zone.HAND)
        secret_zone = int(Zone.SECRET)
        minion_type = int(CardType.MINION)
        weapon_type = int(CardType.WEAPON)
        for eid, ent in self._entities.items():
            zone = ent.get("ZONE")
            controller = ent.get("CONTROLLER")
            if controller is None:
                continue
            controller_int = int(controller)
            is_friendly = controller_int == self._friendly_player_id
            if zone == deck_zone:
                if is_friendly:
                    player_deck_count += 1
                    player_deck_entities.append(
                        self._entity_view(eid, ent, "DECK", controller_int)
                    )
                else:
                    opponent_deck_count += 1
            elif zone == hand_zone:
                target = player_hand if is_friendly else opponent_hand
                target.append(self._entity_view(eid, ent, "HAND", controller_int))
            elif zone == secret_zone:
                target = player_secrets if is_friendly else opponent_secrets
                target.append(self._entity_view(eid, ent, "SECRET", controller_int))
            elif zone == play_zone:
                ctype = ent.get("CARDTYPE")
                if ctype == minion_type:
                    target = player_board if is_friendly else opponent_board
                    target.append(self._entity_view(eid, ent, "PLAY", controller_int))
                elif ctype == weapon_type:
                    target = player_weapons if is_friendly else opponent_weapons
                    target.append(self._entity_view(eid, ent, "PLAY", controller_int))
        for lst in (
            player_board,
            opponent_board,
            player_hand,
            opponent_hand,
            player_secrets,
            opponent_secrets,
            player_deck_entities,
        ):
            lst.sort(key=lambda e: e.zone_position)
        self._current_state = dataclasses.replace(
            self._current_state,
            player_board=tuple(player_board),
            opponent_board=tuple(opponent_board),
            player_hand=tuple(player_hand),
            opponent_hand=tuple(opponent_hand),
            player_secrets=tuple(player_secrets),
            opponent_secrets=tuple(opponent_secrets),
            player_weapon=player_weapons[0] if player_weapons else None,
            opponent_weapon=opponent_weapons[0] if opponent_weapons else None,
            player_played=tuple(self._player_played),
            opponent_played=tuple(self._opponent_played),
            player_drawn=tuple(self._player_drawn),
            opponent_drawn=tuple(self._opponent_drawn),
            player_deck=tuple(player_deck_entities),
            player_deck_count=player_deck_count,
            opponent_deck_count=opponent_deck_count,
        )


# Quiet "unused import" warnings for symbols we want re-exported via type hints.
_ = GameEntity
