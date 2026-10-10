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
1. ``ElementTree.parse`` -> ``HSReplayDocument.from_xml`` -> ``to_packet_tree()``
   -> first tree, plus the game type and format from its ``<Game>`` element.
2. Friendly player from ``FriendlyPlayerExporter`` (authoritative replay
   metadata — the recorded local side).
3. ``translate_packet_tree`` -> canonical internal ``Packet`` list.
4. Feed packets through a ``GameEngine``; immediately after the CREATE_GAME
   packet, ``force_friendly_player`` pins the recorded friendly side (CREATE_GAME
   resets + re-runs the live heuristic, which can disagree) so ``player_*`` /
   ``opponent_*`` zones orient correctly, and a ``GameMetaPacket`` carries the
   type and format.
5. Capture ``current_state`` after each packet, collapsing only consecutive
   identical snapshots, from the first snapshot with both heroes on the board.
   Deterministic.

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

from pathlib import Path
from typing import Any, List, Optional
from xml.etree import ElementTree

from hearthstone.enums import BlockType, GameTag
from hslog import packets as hslog_packets
from hslog.export import FriendlyPlayerExporter
from hsreplay.document import HSReplayDocument

from stonereader.models.game_state import GameState
from stonereader.models.replay import ReplayState
from stonereader.services._engine import GameEngine
from stonereader.services._hslog_translator import is_sub_spell, translate_packet_tree
from stonereader.services._packets import CreateGamePacket, GameMetaPacket


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
    tree, game_type, format_type = _load_first_game(path)

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

    engine = GameEngine(card_db=card_db)
    states: List[GameState] = []
    for pkt in packets:
        engine.apply(pkt)
        if isinstance(pkt, CreateGamePacket):
            # CREATE_GAME just reset the engine and re-ran the live AI heuristic;
            # override it with the authoritative recorded friendly side so
            # player_* / opponent_* zones orient correctly (incl. Player-2 replays).
            engine.force_friendly_player(friendly_player_id)
            # The live log carries type and format as metadata lines after
            # CREATE_GAME; the file keeps them on its <Game> element instead.
            engine.apply(
                GameMetaPacket(
                    packet_id=pkt.packet_id,
                    game_type=game_type,
                    format_type=format_type,
                )
            )
        current = engine.current_state
        if current is None:
            continue
        # Dedupe only CONSECUTIVE identical snapshots (deterministic).
        if states and states[-1] == current:
            continue
        states.append(current)

    if not states:
        raise ReplayLoadError(f"replay produced no game states: {path}")

    # Hearthstone creates both heroes right after the decks, before any card is
    # dealt. Earlier setup snapshots carry no events, and starting at the first
    # one would make the opening GameStarted name two unknown heroes.
    start = next(
        (
            index
            for index, state in enumerate(states)
            if state.player_hero_entity is not None
            and state.opponent_hero_entity is not None
        ),
        0,
    )
    return ReplayState(
        states=tuple(states[start:]), friendly_player_id=friendly_player_id
    )


def _load_first_game(path: Path) -> tuple[Any, Optional[int], Optional[int]]:
    """Parse the file's first game into a packet tree, game type, and format.

    Wraps every XML / serialization failure mode (malformed XML, wrong schema,
    empty document, no games) in a controlled :class:`ReplayLoadError`. Type
    and format are ``None`` when the ``<Game>`` element omits them.
    """
    try:
        with open(path, "rb") as f:
            xml = ElementTree.parse(f)
        trees = HSReplayDocument.from_xml(xml).to_packet_tree()
    except ReplayLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 — controlled re-raise below.
        raise ReplayLoadError(f"failed to parse replay XML: {path}") from exc

    if not trees:
        raise ReplayLoadError(f"replay contains no games: {path}")
    tree = trees[0]
    if tree is None or not getattr(tree, "packets", None):
        raise ReplayLoadError(f"replay packet tree is empty or corrupt: {path}")
    # hsreplay's GameNode does not read its own attributes back from XML.
    game = xml.getroot().find("Game")
    attrib = game.attrib if game is not None else {}
    return (
        tree,
        _optional_int(attrib.get("type")),
        _optional_int(attrib.get("format")),
    )


def _optional_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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

    Re-resolving both restores parity with a freshly-parsed live tree. The
    walk descends into Block and SubSpell children alike. Unknown int
    identifiers are left as-is (idempotent and lossless).
    """
    _walk_resolve(getattr(tree, "packets", []) or [])


def _walk_resolve(nodes: Any) -> None:
    for node in nodes:
        if isinstance(node, hslog_packets.Block):
            node.type = _to_blocktype(getattr(node, "type", None))
            _walk_resolve(getattr(node, "packets", []) or [])
        elif is_sub_spell(node):
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


# Quiet "unused import" warnings for symbols referenced only in type hints.
_: Optional[GameState] = None
