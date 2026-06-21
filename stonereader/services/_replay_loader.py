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
4. Feed packets through a ``GameEngine`` pre-seeded with the recorded friendly
   player id so ``player_*`` / ``opponent_*`` zones orient to the right side.
5. Capture ``current_state`` after each packet, collapsing only consecutive
   identical snapshots. Deterministic.

GameTag re-resolution (loader boundary adapter)
-----------------------------------------------
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

from pathlib import Path
from typing import Any, List, Optional

from hearthstone.enums import GameTag
from hslog import packets as hslog_packets
from hslog.export import FriendlyPlayerExporter
from hsreplay.document import HSReplayDocument

from stonereader.models.game_state import GameState
from stonereader.models.replay import ReplayState
from stonereader.services._engine import GameEngine
from stonereader.services._hslog_translator import translate_packet_tree


class ReplayLoadError(Exception):
    """Raised when a ``.hsreplay`` file cannot be parsed into a usable game.

    Wraps the underlying XML / packet-tree failure so callers get a controlled
    error instead of a raw library traceback (invalid XML, empty document,
    corrupt or game-less packet tree).
    """


def load_replay(path: Path) -> ReplayState:
    """Load an HSReplay XML file into a :class:`ReplayState`.

    Parses the document, replays it through the shared translation + engine
    pipeline, and returns the ordered sequence of ``GameState`` snapshots with
    the recorded friendly player id.

    Raises :class:`ReplayLoadError` for invalid XML or an empty / corrupt
    packet tree.
    """
    tree = _load_first_tree(path)
    friendly_player_id = _export_friendly_player(tree)

    # Re-resolve int GameTag identifiers (round-trip artefact) to enums so the
    # shared translator produces enum-NAME-keyed tags the engine understands.
    _resolve_gametags(tree)

    packets = translate_packet_tree(tree)
    if not packets:
        raise ReplayLoadError(f"no packets translated from replay: {path}")

    engine = GameEngine()
    # Friendly player is authoritative from the replay metadata: pin it so the
    # engine orients player_* / opponent_* zones to the recorded local side and
    # does not re-run its live heuristics.
    engine._friendly_player_id = friendly_player_id
    engine._friendly_player_resolved = True

    states: List[GameState] = []
    for pkt in packets:
        engine.apply(pkt)
        current = engine.current_state
        if current is None:
            continue
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


def _resolve_gametags(tree: Any) -> None:
    """Convert int GameTag identifiers in a round-tripped tree to GameTag enums.

    Mutates the tree in place. After a HSReplay XML round-trip, hslog yields
    ``TagChange.tag`` and the ``(tag, value)`` pairs inside
    ``CreateGame``/``FullEntity``/``ShowEntity``/``ChangeEntity`` ``.tags`` as
    plain ints. The shared translator names tags via ``GameTag.name``, so bare
    ints stringify to their decimal text and the engine no longer recognises
    them. Re-resolving to enums restores parity with the live parse.

    Unknown int identifiers (tags not in the GameTag enum) are left as-is; the
    translator already tolerates them and the engine ignores tags it does not
    handle.
    """
    _walk_resolve(getattr(tree, "packets", []) or [])


def _walk_resolve(nodes: Any) -> None:
    for node in nodes:
        if isinstance(node, hslog_packets.Block):
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


# Quiet "unused import" warnings for symbols referenced only in type hints.
_: Optional[GameState] = None
