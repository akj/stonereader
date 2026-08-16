"""Tests for the replay store (Slice #11): replay files + SQLite metadata."""

from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import pytest

from stonereader.db import get_connection, init_db
from stonereader.models.card import Card, CardDatabase
from stonereader.models.game_state import GameState, Hero
from stonereader.services._replay_recorder import ReplayRecorder
from stonereader.services._replay_store import (
    ReplayImportError,
    ReplayMeta,
    ReplaySaveResult,
    ReplayStore,
)

_XML = "<HSReplay><Game>opaque content</Game></HSReplay>"


def _store(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    replay_dir = tmp_path / "replays"
    return ReplayStore(conn, replay_dir), conn, replay_dir


def _save(store, xml=_XML, **overrides):
    meta = dict(
        source="live_auto",
        friendly_class="MAGE",
        opponent_class="WARRIOR",
        result="WON",
        turns=10,
        played_at="2026-06-20 14:30:00",
    )
    meta.update(overrides)
    return store.save_xml(xml, **meta)


def _hsreplay_files(replay_dir):
    return list(replay_dir.rglob("*.hsreplay"))


def _hdtreplay_files(replay_dir):
    return list(replay_dir.rglob("*.hdtreplay"))


def test_save_xml_writes_one_file_and_one_row(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    saved = _save(store)

    assert isinstance(saved, ReplaySaveResult)
    assert saved.created is True
    assert isinstance(saved.meta, ReplayMeta)
    files = _hsreplay_files(replay_dir)
    assert len(files) == 1
    assert files[0].exists()
    assert files[0].read_text(encoding="utf-8") == _XML

    rows = conn.execute("SELECT COUNT(*) FROM replays").fetchone()
    assert rows[0] == 1
    # file_path on the record points at the written file
    assert saved.meta.file_path == str(files[0])
    conn.close()


def test_save_xml_dedupes_identical_content(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    first = _save(store)
    second = _save(store)  # identical xml -> same checksum

    assert first.created is True
    assert second.created is False
    assert second.meta.id == first.meta.id
    assert len(_hsreplay_files(replay_dir)) == 1
    assert conn.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 1
    conn.close()


def test_save_xml_writes_raw_log_sidecar_on_fresh_save(tmp_path):
    store, conn, replay_dir = _store(tmp_path)

    _save(store, raw_log="line one\nline two\n")

    sidecars = _hdtreplay_files(replay_dir)
    assert len(sidecars) == 1
    with ZipFile(sidecars[0]) as archive:
        assert archive.namelist() == ["output_log.txt"]
        assert archive.read("output_log.txt").decode("utf-8") == (
            "line one\nline two\n"
        )
    conn.close()


def test_save_xml_dedupe_does_not_rewrite_raw_log_sidecar(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    first = _save(store, raw_log="original\n")

    second = _save(store, raw_log="replacement\n")

    assert second.meta.id == first.meta.id
    sidecars = _hdtreplay_files(replay_dir)
    assert len(sidecars) == 1
    with ZipFile(sidecars[0]) as archive:
        assert archive.read("output_log.txt").decode("utf-8") == "original\n"
    conn.close()


def test_save_xml_without_raw_log_writes_no_sidecar(tmp_path):
    store, conn, replay_dir = _store(tmp_path)

    meta = _save(store, raw_log=None).meta

    assert Path(meta.file_path).exists()
    assert _hdtreplay_files(replay_dir) == []
    conn.close()


def test_all_replays_newest_played_at_first(tmp_path):
    store, conn, _ = _store(tmp_path)
    _save(store, xml="<r>old</r>", played_at="2026-06-18 09:00:00")
    _save(store, xml="<r>new</r>", played_at="2026-06-20 21:00:00")

    replays = store.all_replays()
    assert len(replays) == 2
    assert replays[0].played_at == "2026-06-20 21:00:00"
    assert replays[1].played_at == "2026-06-18 09:00:00"
    conn.close()


def test_delete_removes_row_file_and_raw_log_sidecar(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    meta = _save(store, raw_log="source line\n").meta
    file_path = _hsreplay_files(replay_dir)[0]
    sidecar_path = file_path.with_suffix(".hdtreplay")
    assert file_path.exists()
    assert sidecar_path.exists()

    store.delete(meta.id)

    assert conn.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 0
    assert not file_path.exists()
    assert not sidecar_path.exists()
    conn.close()


def test_delete_tolerates_missing_file(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    meta = _save(store).meta
    # remove the file out from under the store
    _hsreplay_files(replay_dir)[0].unlink()

    store.delete(meta.id)  # should not raise

    assert conn.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 0
    conn.close()


def test_import_file_copies_valid_file(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    src = tmp_path / "external.hsreplay"
    src.write_text(_XML, encoding="utf-8")

    imported = store.import_file(
        src,
        source="manual_import",
        friendly_class="MAGE",
        opponent_class="WARRIOR",
        result="LOST",
        turns=7,
        played_at="2026-06-19 12:00:00",
    )

    managed = _hsreplay_files(replay_dir)
    assert len(managed) == 1
    assert managed[0] != src  # copied into managed storage
    assert managed[0].read_text(encoding="utf-8") == _XML
    assert imported.created is True
    assert imported.meta.source == "manual_import"
    assert imported.meta.result == "LOST"
    conn.close()


def test_import_file_dedupes_same_content(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    # seed via save_xml, then import a file with identical content
    first = _save(store)
    src = tmp_path / "external.hsreplay"
    src.write_text(_XML, encoding="utf-8")

    second = store.import_file(
        src,
        source="manual_import",
        friendly_class="MAGE",
        opponent_class="WARRIOR",
        result="WON",
        turns=10,
        played_at="2026-06-20 14:30:00",
    )

    assert second.created is False
    assert second.meta.id == first.meta.id
    assert len(_hsreplay_files(replay_dir)) == 1
    assert conn.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 1
    conn.close()


def test_import_file_prunes_oldest_on_write(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    replay_dir = tmp_path / "replays"
    store = ReplayStore(conn, replay_dir, retention_provider=lambda: 2)
    oldest = _save(
        store,
        xml="<r>oldest</r>",
        played_at="2026-06-18T09:00:00",
    ).meta
    middle = _save(
        store,
        xml="<r>middle</r>",
        played_at="2026-06-19T09:00:00",
    ).meta
    source = tmp_path / "newest.hsreplay"
    source.write_text("<r>newest</r>", encoding="utf-8")

    newest = store.import_file(
        source,
        friendly_class="MAGE",
        opponent_class="WARRIOR",
        result="WON",
        turns=10,
        played_at="2026-06-20T09:00:00",
    ).meta

    assert [replay.id for replay in store.all_replays()] == [newest.id, middle.id]
    assert not Path(oldest.file_path).exists()
    conn.close()


def test_in_stats_write_and_toggle(tmp_path):
    store, conn, _ = _store(tmp_path)
    saved = _save(store, in_stats=True)

    assert saved.meta.in_stats is True

    store.set_in_stats(saved.meta.id, False)
    assert store.all_replays()[0].in_stats is False
    conn.close()


def test_prune_deletes_oldest_rows_and_files_via_delete_path(tmp_path):
    store, conn, _ = _store(tmp_path)
    oldest = _save(
        store,
        xml="<r>oldest</r>",
        played_at="2026-06-18T09:00:00",
        raw_log="oldest\n",
    ).meta
    middle = _save(
        store,
        xml="<r>middle</r>",
        played_at="2026-06-19T09:00:00",
    ).meta
    newest = _save(
        store,
        xml="<r>newest</r>",
        played_at="2026-06-20T09:00:00",
    ).meta

    store.prune(2)

    assert [replay.id for replay in store.all_replays()] == [newest.id, middle.id]
    assert not Path(oldest.file_path).exists()
    assert not Path(oldest.file_path).with_suffix(".hdtreplay").exists()
    conn.close()


def test_prune_none_is_noop(tmp_path):
    store, conn, _ = _store(tmp_path)
    saved = _save(store).meta

    store.prune(None)

    assert [replay.id for replay in store.all_replays()] == [saved.id]
    assert Path(saved.file_path).exists()
    conn.close()


def test_import_file_missing_source_raises(tmp_path):
    store, conn, _ = _store(tmp_path)
    missing = tmp_path / "does_not_exist.hsreplay"

    with pytest.raises(ReplayImportError):
        store.import_file(
            missing,
            source="manual_import",
            friendly_class="MAGE",
            opponent_class="WARRIOR",
            result="WON",
            turns=10,
            played_at="2026-06-20 14:30:00",
        )
    conn.close()


def test_import_file_derives_result_classes_and_turns_from_replay(tmp_path):
    (tmp_path / "source").mkdir()
    source_store, source_conn, _ = _store(tmp_path / "source")
    hero = Hero("?", "?", 30, 0, "")
    running = GameState(
        turn=0,
        active_player_id=1,
        player_board=(),
        opponent_board=(),
        player_hand=(),
        opponent_hand=(),
        player_hero=hero,
        opponent_hero=hero,
        game_state="RUNNING",
    )
    completed = GameState(
        **{
            **running.__dict__,
            "game_state": "COMPLETE",
        }
    )
    recorder = ReplayRecorder(
        source_store,
        now=lambda: datetime(2026, 8, 16, 9, 30, tzinfo=timezone.utc),
    )
    lines = (Path(__file__).parent / "fixtures" / "log" / "game_end.log").read_text(
        encoding="utf-8"
    )
    recorder.on_lines(lines.splitlines())
    recorder.on_state(running, completed)
    source = Path(source_store.all_replays()[0].file_path)

    card_db = CardDatabase()
    for card_id, hero_class in (
        ("HERO_01c", "WARRIOR"),
        ("HERO_11", "DEATHKNIGHT"),
    ):
        card_db.cards_by_id[card_id] = Card(
            id=card_id,
            dbf_id=0,
            name=card_id,
            cost=0,
            attack=None,
            health=None,
            text="",
            rarity="FREE",
            card_class=hero_class,
            card_type="HERO",
            card_set="TEST",
        )
    imported_conn = get_connection(str(tmp_path / "imported.db"))
    init_db(imported_conn)
    imported_store = ReplayStore(imported_conn, tmp_path / "imported", card_db)

    result = imported_store.import_file(source, in_stats=True)

    assert result.created is True
    assert result.meta.source == "manual_import"
    assert result.meta.result == "LOST"
    assert result.meta.friendly_class == "WARRIOR"
    assert result.meta.opponent_class == "DEATHKNIGHT"
    assert result.meta.turns == 2
    assert result.meta.in_stats is True
    source_conn.close()
    imported_conn.close()
