"""Replay loader: HSReplay XML file -> ReplayState (Slice #13, depends on D-10).

Turns a saved ``.hsreplay`` document into a :class:`ReplayState` — the ordered
sequence of :class:`GameState` snapshots that drives the Replay viewer. It
reuses the EXACT same translation + engine pipeline the live tracker uses
(:func:`stonereader.services._hslog_translator.translate_packet_tree` +
:class:`stonereader.services._engine.GameEngine`), so a replayed game produces
the same snapshots — and therefore the same diff-derived ``GameEvent`` stream —
as it did live.

Pipeline
--------
1. ``HSReplayDocument.from_xml_file`` -> ``to_packet_tree()`` -> first tree.
2. Friendly player from ``FriendlyPlayerExporter`` (authoritative replay
   metadata — the recorded local side).
3. ``translate_packet_tree`` -> canonical internal ``Packet`` list.
4. Feed packets through a ``GameEngine``; immediately after the CREATE_GAME
   packet, ``force_friendly_player`` pins the recorded friendly side (CREATE_GAME
   resets + re-runs the live heuristic, which can disagree) so ``player_*`` /
   ``opponent_*`` zones orient correctly. ``active_player_id`` is normalised to
   the 1=friendly / 2=opponent contract.
5. Capture ``current_state`` after each packet, collapsing only consecutive
   identical snapshots. Deterministic.

Round-trip enum re-resolution (loader boundary adapter)
-------------------------------------------------------
When an hslog ``PacketTree`` is round-tripped through HSReplay XML
(``from_packet_tree`` -> ``to_xml`` -> ``from_xml_file`` -> ``to_packet_tree``),
the resulting ``TagChange.tag`` and ``FullEntity``/``ShowEntity``/``CreateGame``
``.tags`` come back as plain ``int`` GameTag identifiers rather than the
``hearthstone.enums.GameTag`` enums the LIVE parse yields. The shared
translator stringifies a bare ``int`` tag to its decimal text (``"17"``) instead
of the enum name (``"PLAYSTATE"``), which the engine's string-keyed handlers
(``"ZONE"``, ``"CONTROLLER"``, ``"PLAYSTATE"``, ...) do not recognise — the
whole reduction silently no-ops (empty zones, game never completes).

So before translation the loader re-resolves int tags back to ``GameTag``
enums, making the replayed tree byte-for-byte equivalent (in tag shape) to a
freshly-parsed live tree. This is a translation-boundary concern owned by the
loader; the translator and engine stay untouched.

Imports hslog/hsreplay (it is the file-parsing edge), but no wx, no clock,
no real speech — keeping it reusable and unit-testable.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Dict, List, Optional

from hearthstone.enums import BlockType, GameTag
from hslog import packets as hslog_packets
from hslog.export import FriendlyPlayerExporter
from hsreplay.document import HSReplayDocument

from stonereader.models.game_state import GameState
from stonereader.models.replay import ReplayState
from stonereader.services._engine import GameEngine
from stonereader.services._hslog_translator import translate_packet_tree
from stonereader.services._packets import CreateGamePacket


class ReplayLoadError(Exception):
    """Raised when a ``.hsreplay`` file cannot be parsed into a usable game.

    Wraps the underlying XML / packet-tree failure so callers get a controlled
    error instead of a raw library traceback (invalid XML, empty document,
    corrupt or game-less packet tree).
    """


def load_replay(path: Path, card_db: Any = None) -> ReplayState:
    """Load an HSReplay XML file into a :class:`ReplayState`.

    Parses the document, replays it through the shared translation + engine
    pipeline, and returns the ordered sequence of ``GameState`` snapshots with
    the recorded friendly player id.

    ``card_db`` (a ``CardDatabase``) is threaded into the ``GameEngine`` so the
    reconstructed states carry resolved card names, costs, types and hero data —
    without it the viewer would speak bare card ids and ``?`` heroes.

    Raises :class:`ReplayLoadError` for invalid XML or an empty / corrupt
    packet tree.
    """
    tree = _load_first_tree(path)

    # Re-resolve round-trip artefacts (int GameTag AND int BlockType identifiers)
    # back to enums so the shared translator produces the same enum-NAME-keyed
    # tags and block-type names the engine + diff seam expect. This MUST run
    # before friendly-player export: FriendlyPlayerExporter inspects
    # GameTag.CONTROLLER / GameTag.ZONE, which are still ints until resolved.
    _resolve_enums(tree)

    friendly_player_id = _export_friendly_player(tree)

    packets = translate_packet_tree(tree)
    if not packets:
        raise ReplayLoadError(f"no packets translated from replay: {path}")

    # Map each player ENTITY id -> its server player_id (1/2), recovered from the
    # CREATE_GAME packet. Used to normalize active_player_id to the documented
    # 1=friendly / 2=opponent contract (see services/_events.py).
    entity_to_pid = _player_entity_pids(packets)

    engine = GameEngine(card_db=card_db)
    states: List[GameState] = []
    for pkt in packets:
        engine.apply(pkt)
        if isinstance(pkt, CreateGamePacket):
            # CREATE_GAME just reset the engine and re-ran the live AI heuristic;
            # override it with the authoritative recorded friendly side so
            # player_* / opponent_* zones orient correctly (incl. Player-2 replays).
            engine.force_friendly_player(friendly_player_id)
        current = engine.current_state
        if current is None:
            continue
        current = _normalize_active_player(current, entity_to_pid, friendly_player_id)
        # Dedupe only CONSECUTIVE identical snapshots (deterministic).
        if states and states[-1] == current:
            continue
        states.append(current)

    if not states:
        raise ReplayLoadError(f"replay produced no game states: {path}")

    return ReplayState(states=tuple(states), friendly_player_id=friendly_player_id)


def _load_first_tree(path: Path) -> Any:
    """Parse the file into its first hslog packet tree, or raise ReplayLoadError.

    Wraps every XML / serialization failure mode (malformed XML, wrong schema,
    empty document, no games) in a controlled :class:`ReplayLoadError`.
    """
    try:
        with open(path, "rb") as f:
            doc = HSReplayDocument.from_xml_file(f)
        trees = doc.to_packet_tree()
    except ReplayLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 — controlled re-raise below.
        raise ReplayLoadError(f"failed to parse replay XML: {path}") from exc

    if not trees:
        raise ReplayLoadError(f"replay contains no games: {path}")
    tree = trees[0]
    if tree is None or not getattr(tree, "packets", None):
        raise ReplayLoadError(f"replay packet tree is empty or corrupt: {path}")
    return tree


def _export_friendly_player(tree: Any) -> int:
    """Resolve the recorded friendly player id, defaulting to 1 on failure.

    FriendlyPlayerExporter returns 1 or 2 for a normal game. If the export
    raises or yields nothing usable (degenerate replay), fall back to 1 — the
    same default the live engine uses — rather than failing the whole load.
    """
    try:
        exported = FriendlyPlayerExporter(tree).export()
    except Exception:  # noqa: BLE001 — degenerate replay: use the safe default.
        return 1
    if exported in (1, 2):
        return int(exported)
    return 1


def _resolve_enums(tree: Any) -> None:
    """Convert round-tripped int identifiers back to enums, in place.

    After a HSReplay XML round-trip, hslog yields raw ints where the live parse
    yields enums, in TWO places that the engine + diff seam are sensitive to:

    1. ``TagChange.tag`` and the ``(tag, value)`` pairs inside
       ``CreateGame``/``FullEntity``/``ShowEntity``/``ChangeEntity`` ``.tags``
       come back as int ``GameTag`` ids. The translator names tags via
       ``GameTag.name``; a bare int stringifies to its decimal text, so the
       engine's string-keyed handlers (``"ZONE"``/``"CONTROLLER"``/...) no-op.
    2. ``Block.type`` comes back as an int ``BlockType`` id. The translator
       names it via ``BlockType.name``; a bare int stringifies to e.g. ``"7"``
       instead of ``"PLAY"``, so the engine/diff checks for ``"PLAY"``,
       ``"POWER"`` and ``"ATTACK"`` never match — replay event drilldown then
       silently drops card-play, attack and damage events.

    Re-resolving both restores parity with a freshly-parsed live tree. Unknown
    int identifiers are left as-is (idempotent and lossless).
    """
    _walk_resolve(getattr(tree, "packets", []) or [])


def _walk_resolve(nodes: Any) -> None:
    for node in nodes:
        if isinstance(node, hslog_packets.Block):
            node.type = _to_blocktype(getattr(node, "type", None))
            _walk_resolve(getattr(node, "packets", []) or [])
        elif isinstance(node, hslog_packets.TagChange):
            node.tag = _to_gametag(node.tag)
        elif isinstance(
            node,
            (
                hslog_packets.CreateGame,
                hslog_packets.FullEntity,
                hslog_packets.ShowEntity,
                hslog_packets.ChangeEntity,
            ),
        ):
            node.tags = _resolve_tag_pairs(getattr(node, "tags", None))


def _resolve_tag_pairs(tags: Any) -> Any:
    """Return tags with each tag key coerced to a GameTag enum where possible."""
    if not tags:
        return tags
    resolved = []
    for item in tags:
        try:
            tag, value = item
        except (TypeError, ValueError):
            resolved.append(item)
            continue
        resolved.append((_to_gametag(tag), value))
    return resolved


def _to_gametag(tag: Any) -> Any:
    """Coerce an int tag identifier to a GameTag enum; pass through otherwise.

    Already-resolved GameTag enums and unknown identifiers are returned
    unchanged so this is idempotent and lossless.
    """
    if isinstance(tag, GameTag):
        return tag
    try:
        return GameTag(int(tag))
    except (ValueError, TypeError):
        return tag


def _to_blocktype(value: Any) -> Any:
    """Coerce an int BlockType identifier to a BlockType enum; pass through else.

    Already-resolved enums and unknown identifiers are returned unchanged
    (idempotent and lossless), mirroring :func:`_to_gametag`.
    """
    if value is None or isinstance(value, BlockType):
        return value
    try:
        return BlockType(int(value))
    except (ValueError, TypeError):
        return value


def _player_entity_pids(packets: List[Any]) -> Dict[int, int]:
    """Map each player ENTITY id -> its server player_id from CREATE_GAME.

    The translated ``CreateGamePacket.players`` are ``(entity_id, player_id,
    name, hi, lo)`` tuples (same shape the engine's friendly heuristic unpacks).
    """
    mapping: Dict[int, int] = {}
    for pkt in packets:
        if isinstance(pkt, CreateGamePacket):
            for player in pkt.players:
                try:
                    entity_id, player_id = player[0], player[1]
                except (IndexError, TypeError):
                    continue
                mapping[int(entity_id)] = int(player_id)
            break
    return mapping


def _normalize_active_player(
    state: GameState, entity_to_pid: Dict[int, int], friendly_player_id: int
) -> GameState:
    """Remap ``active_player_id`` to the 1=friendly / 2=opponent contract.

    The engine records ``active_player_id`` as the active player's ENTITY id
    (2/3), but the documented contract (services/_events.py) and the viewer/diff
    consumers expect 1 = friendly, 2 = opponent. Translate via the recorded
    player-entity -> player_id map. Non-player active ids (e.g. the pre-turn
    default) are left untouched.
    """
    pid = entity_to_pid.get(state.active_player_id)
    if pid is None:
        return state
    relative = 1 if pid == friendly_player_id else 2
    if relative == state.active_player_id:
        return state
    return dataclasses.replace(state, active_player_id=relative)


# Quiet "unused import" warnings for symbols referenced only in type hints.
_: Optional[GameState] = None
