"""Tests for stonereader.services._exceptions and stonereader.services._packets."""
from __future__ import annotations

import dataclasses
import pytest


# --- _exceptions tests ---


def test_services_error_is_base_exception():
    from stonereader.services._exceptions import ServicesError

    with pytest.raises(ServicesError):
        raise ServicesError("base error")


def test_parser_error_is_services_error():
    from stonereader.services._exceptions import ParserError, ServicesError

    err = ParserError("parser failed")
    assert isinstance(err, ServicesError)
    assert isinstance(err, Exception)


def test_engine_error_is_services_error():
    from stonereader.services._exceptions import EngineError, ServicesError

    err = EngineError("engine failed")
    assert isinstance(err, ServicesError)
    assert isinstance(err, Exception)


def test_no_hslog_import_in_exceptions():
    """D-10: _exceptions.py must not import hslog."""
    import importlib.util
    import pathlib

    src = pathlib.Path("stonereader/services/_exceptions.py").read_text()
    assert "import hslog" not in src
    assert "from hslog" not in src


# --- _packets tests ---


def test_all_packet_classes_are_frozen_dataclasses():
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

    classes = [
        Packet,
        CreateGamePacket,
        TagChangePacket,
        BlockStartPacket,
        BlockEndPacket,
        FullEntityPacket,
        ShowEntityPacket,
        HideEntityPacket,
        ChangeEntityPacket,
    ]
    for cls in classes:
        assert dataclasses.is_dataclass(cls), f"{cls.__name__} should be a dataclass"
        assert cls.__dataclass_params__.frozen, f"{cls.__name__} should be frozen"


def test_create_game_packet_is_packet():
    from stonereader.services._packets import CreateGamePacket, Packet

    pkt = CreateGamePacket(packet_id=0, game_entity_id=1)
    assert isinstance(pkt, Packet)
    assert pkt.packet_id == 0
    assert pkt.game_entity_id == 1
    assert pkt.players == ()
    assert pkt.initial_tags == {}


def test_create_game_packet_immutable():
    from stonereader.services._packets import CreateGamePacket

    pkt = CreateGamePacket(packet_id=0, game_entity_id=1)
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        pkt.packet_id = 99  # type: ignore[misc]


def test_tag_change_packet_fields():
    from stonereader.services._packets import TagChangePacket

    pkt = TagChangePacket(packet_id=1, entity_id=2, tag="ZONE", value=3)
    assert pkt.entity_id == 2
    assert pkt.tag == "ZONE"
    assert pkt.value == 3
    assert pkt.source_id is None


def test_block_start_packet_fields():
    from stonereader.services._packets import BlockStartPacket

    pkt = BlockStartPacket(packet_id=2, block_type="ATTACK", entity_id=5)
    assert pkt.block_type == "ATTACK"
    assert pkt.entity_id == 5
    assert pkt.target_id is None
    assert pkt.sub_option is None


def test_block_end_packet_fields():
    from stonereader.services._packets import BlockEndPacket

    pkt = BlockEndPacket(packet_id=3, block_type="ATTACK", entity_id=5)
    assert pkt.block_type == "ATTACK"
    assert pkt.entity_id == 5


def test_full_entity_packet_fields():
    from stonereader.services._packets import FullEntityPacket

    pkt = FullEntityPacket(packet_id=4, entity_id=10, card_id="EX1_001")
    assert pkt.entity_id == 10
    assert pkt.card_id == "EX1_001"
    assert pkt.tags == {}


def test_show_entity_packet_fields():
    from stonereader.services._packets import ShowEntityPacket

    pkt = ShowEntityPacket(packet_id=5, entity_id=11, card_id="EX1_002")
    assert pkt.entity_id == 11
    assert pkt.card_id == "EX1_002"
    assert pkt.tags == {}


def test_hide_entity_packet_fields():
    from stonereader.services._packets import HideEntityPacket

    pkt = HideEntityPacket(packet_id=6, entity_id=12, zone=2)
    assert pkt.entity_id == 12
    assert pkt.zone == 2


def test_change_entity_packet_fields():
    from stonereader.services._packets import ChangeEntityPacket

    pkt = ChangeEntityPacket(packet_id=7, entity_id=13, card_id="NEW_CARD")
    assert pkt.entity_id == 13
    assert pkt.card_id == "NEW_CARD"
    assert pkt.tags == {}


def test_no_list_type_hints_in_packets():
    """Per plan constraint: no List[ in _packets.py — use Tuple instead."""
    import pathlib

    src = pathlib.Path("stonereader/services/_packets.py").read_text()
    assert "List[" not in src, "_packets.py must not use List[ type hints"


def test_no_hslog_import_in_packets():
    """D-10: _packets.py must not import hslog."""
    import pathlib

    src = pathlib.Path("stonereader/services/_packets.py").read_text()
    assert "import hslog" not in src
    assert "from hslog" not in src
