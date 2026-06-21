"""Tests for the replay store (Slice #11): .hsreplay file + SQLite metadata."""

import pytest

from stonereader.db import get_connection, init_db
from stonereader.services._replay_store import (
    ReplayImportError,
    ReplayMeta,
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


def test_save_xml_writes_one_file_and_one_row(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    meta = _save(store)

    assert isinstance(meta, ReplayMeta)
    files = _hsreplay_files(replay_dir)
    assert len(files) == 1
    assert files[0].exists()
    assert files[0].read_text(encoding="utf-8") == _XML

    rows = conn.execute("SELECT COUNT(*) FROM replays").fetchone()
    assert rows[0] == 1
    # file_path on the record points at the written file
    assert meta.file_path == str(files[0])
    conn.close()


def test_save_xml_dedupes_identical_content(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    first = _save(store)
    second = _save(store)  # identical xml -> same checksum

    assert second.id == first.id
    assert len(_hsreplay_files(replay_dir)) == 1
    assert conn.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 1
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


def test_delete_removes_row_and_file(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    meta = _save(store)
    file_path = _hsreplay_files(replay_dir)[0]
    assert file_path.exists()

    store.delete(meta.id)

    assert conn.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 0
    assert not file_path.exists()
    conn.close()


def test_delete_tolerates_missing_file(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    meta = _save(store)
    # remove the file out from under the store
    _hsreplay_files(replay_dir)[0].unlink()

    store.delete(meta.id)  # should not raise

    assert conn.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 0
    conn.close()


def test_import_file_copies_valid_file(tmp_path):
    store, conn, replay_dir = _store(tmp_path)
    src = tmp_path / "external.hsreplay"
    src.write_text(_XML, encoding="utf-8")

    meta = store.import_file(
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
    assert meta.source == "manual_import"
    assert meta.result == "LOST"
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

    assert second.id == first.id
    assert len(_hsreplay_files(replay_dir)) == 1
    assert conn.execute("SELECT COUNT(*) FROM replays").fetchone()[0] == 1
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
