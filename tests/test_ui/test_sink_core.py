from __future__ import annotations

from stonereader.ui._sink_core import _SinkCore
from stonereader.ui.announcer import Announcer
from stonereader.ui.chords import Chord
from stonereader.ui.registry import Command, CommandRegistry, Layer
from stonereader.ui.text_mode import TextSession

from .conftest import FakeSpeech


def core(speech: FakeSpeech, stops: list[str]) -> _SinkCore:
    return _SinkCore(Announcer(speech), lambda: stops.append("stop"))


def test_dispatches_commands_and_routes_announced_noops() -> None:
    speech = FakeSpeech()
    calls: list[str] = []
    sink = core(speech, [])
    registry = CommandRegistry()
    registry.register(
        Layer.SURFACE,
        Chord("z"),
        Command("z", "Z: act", lambda: calls.append("z")),
    )
    sink.set_active(registry)

    assert sink.handle_chord(Chord("z")) is True
    assert sink.handle_chord(Chord("enter")) is True
    assert calls == ["z"]
    assert speech.calls == [("Nothing to do here", True)]


def test_ctrl_combos_are_dispatched_and_unhandled_keys_are_not_consumed() -> None:
    calls: list[str] = []
    sink = core(FakeSpeech(), [])
    registry = CommandRegistry()
    registry.register(
        Layer.UNIVERSAL,
        Chord("q", ctrl=True),
        Command("quit", "Ctrl+Q: quit", lambda: calls.append("quit")),
    )
    sink.set_active(registry)
    assert sink.handle_chord(Chord("q", ctrl=True)) is True
    assert sink.handle_chord(Chord("x", ctrl=True)) is False
    assert calls == ["quit"]


def test_bare_ctrl_tap_stops_audio() -> None:
    stops: list[str] = []
    sink = core(FakeSpeech(), stops)
    sink.control_down()
    assert sink.control_up() is True
    assert stops == ["stop"]


def test_intervening_chord_cancels_bare_ctrl_tap() -> None:
    stops: list[str] = []
    sink = core(FakeSpeech(), stops)
    sink.set_active(CommandRegistry())
    sink.control_down()
    sink.handle_chord(Chord("x"))
    assert sink.control_up() is False
    assert stops == []


def test_intervening_modifier_cancels_bare_ctrl_tap() -> None:
    stops: list[str] = []
    sink = core(FakeSpeech(), stops)
    sink.control_down()
    sink.cancel_control_tap()
    assert sink.control_up() is False
    assert stops == []


def test_offer_accepts_once_per_subject() -> None:
    accepted: list[str] = []
    sink = core(FakeSpeech(), [])
    sink.set_active(CommandRegistry())
    assert sink.arm_offer("code", lambda: accepted.append("accepted")) is True
    assert sink.handle_chord(Chord("enter", ctrl=True)) is True
    assert sink.arm_offer("code", lambda: accepted.append("again")) is False
    assert sink.handle_chord(Chord("enter", ctrl=True)) is False
    assert accepted == ["accepted"]


def test_mark_offer_subject_seen_prevents_arming_without_accepting() -> None:
    accepted: list[str] = []
    sink = core(FakeSpeech(), [])
    sink.set_active(CommandRegistry())
    sink.mark_offer_subject_seen("own-copy")

    assert sink.arm_offer("own-copy", lambda: accepted.append("accepted")) is False
    assert sink.handle_chord(Chord("enter", ctrl=True)) is False
    assert accepted == []


def test_nonaccept_key_disarms_offer_silently_and_processes_normally() -> None:
    speech = FakeSpeech()
    calls: list[str] = []
    sink = core(speech, [])
    registry = CommandRegistry()
    registry.register(
        Layer.SURFACE,
        Chord("a"),
        Command("act", "A: act", lambda: calls.append("act")),
    )
    sink.set_active(registry)
    sink.arm_offer("code", lambda: calls.append("accept"))
    assert sink.handle_chord(Chord("a")) is True
    assert calls == ["act"]
    assert speech.calls == []


def test_text_mode_owns_routing_and_drops_offers() -> None:
    speech = FakeSpeech()
    commits: list[str] = []
    accepted: list[str] = []
    sink = core(speech, [])
    sink.set_active(CommandRegistry())
    session = TextSession("Code", "", Announcer(speech), commits.append, lambda: None)
    sink.enter_text_mode(session)
    assert sink.arm_offer("code", lambda: accepted.append("accepted")) is False

    assert sink.handle_chord(Chord("a")) is True
    assert session.text == "a"
    assert sink.handle_chord(Chord("enter")) is True
    assert commits == ["a"]
    assert accepted == []
    sink.exit_text_mode()
    assert sink.text_mode_active is False
