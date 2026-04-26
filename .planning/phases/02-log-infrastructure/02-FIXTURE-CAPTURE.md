# Phase 2 — Power.log Fixture Capture Procedure

**When to use:** Re-capture fixtures after a Hearthstone patch breaks parser tests, or when adding new test scenarios that need a different in-match state.

**Reference:** Distilled from `02-RESEARCH.md §"Test Fixture Capture Procedure (D-17)"` (lines 632-697) and the inline procedure in `02-08-PLAN.md`.

## Required fixtures

| File | Drives | Approx. size |
|------|--------|--------------|
| `match_start.log` | LOG-01 detect new lines, GameStarted, mulligan | 30-50 KB |
| `mid_game.log` | LOG-01 cards drawn/played, turn changes, full snapshot | 80-150 KB |
| `game_end.log` | GameEnded, PLAYSTATE WON/LOST | 100-200 KB |
| `reconnect.log` | Pitfall 7 — reconnect re-dumps full game state (second CREATE_GAME) | 150-250 KB |
| `battlegrounds.log` | Stress, no-crash assertion (optional v1) | 1-5 MB |

## Prerequisites

- Windows machine with Hearthstone installed (the only OS that produces `Power.log` for a normal user — Mac requires extra setup)
- Permission to edit `%LOCALAPPDATA%\Blizzard\Hearthstone\log.config`
- A text editor that won't insert BOM/CRLF substitutions on save (Notepad++ recommended), OR a WSL/Git Bash shell with `sed`
- The `head` command (Git Bash, WSL, or a built-in PowerShell equivalent) for size truncation

## Step 1: Configure `log.config`

Open or create `%LOCALAPPDATA%\Blizzard\Hearthstone\log.config`:

```ini
[Power]
LogLevel=1
FilePrinting=True
ConsolePrinting=False
ScreenPrinting=False
Verbose=True
```

> **Shortcut:** StoneReader's `ensure_log_config()` writes exactly this section idempotently. If StoneReader has been run on this machine, `log.config` is already correct — skip to Step 2.

## Step 2: Restart Hearthstone

Force a fresh log directory. After Hearthstone launches, confirm:

```
%LOCALAPPDATA%\Blizzard\Hearthstone\Logs\Hearthstone_YYYY_MM_DD_HH_MM_SS\Power.log
```

…exists and is non-empty within ~10 seconds of the title screen appearing.

## Step 3: Capture `match_start.log`

1. Start a Casual match against the AI Innkeeper (Solo Adventures → Practice).
2. Wait for your starting hand to render.
3. Concede immediately (~30 seconds total).
4. Copy `Power.log` → `match_start.log`.

**Size target:** 30-50 KB.

## Step 4: Capture `mid_game.log`

1. Start a fresh Casual match (so the new session writes to a new log directory).
2. Play through the mulligan.
3. Play 5-7 turns (several minion plays, a card draw or two, at least one turn change).
4. **While the match is still ongoing**, use Windows Explorer or `cp` to copy `Power.log` → `mid_game.log`.

**Critical:** the file must NOT contain a final `PLAYSTATE WON/LOST` block — this is the "mid game" state we need.

**Size target:** 80-150 KB.

## Step 5: Capture `game_end.log`

1. Start a fresh Casual match.
2. Play to game completion (win or lose — both produce a PLAYSTATE block).
3. After the victory/defeat screen renders, copy `Power.log` → `game_end.log`.

**Size target:** 100-200 KB.

## Step 6: Capture `reconnect.log`

1. Start a fresh Casual match.
2. Play 2-3 turns.
3. Force-quit Hearthstone via Task Manager (do NOT use the in-game quit menu).
4. Restart Hearthstone. The client should automatically reconnect to the match.
5. Hearthstone re-dumps the full game state on reconnect — this produces a **second** `CREATE_GAME` block in `Power.log`.
6. Wait for the reconnect to settle (your turn or opponent's turn renders normally).
7. Copy `Power.log` → `reconnect.log`.

**Size target:** 150-250 KB. Verify by `grep -c "CREATE_GAME" reconnect.log` ≥ 2.

## Step 7 (optional): Capture `battlegrounds.log`

1. Play one Battlegrounds match to top-4 minimum (~25 minutes).
2. Copy `Power.log` after the match concludes.

**Size target:** 1-5 MB raw; truncate to 2 MB if not using git LFS (see Step 9).

## Step 8: Anonymize

Each `.log` file may contain real BattleTags. Open in Notepad++ (or use `sed`) and replace:

| Find | Replace with |
|------|--------------|
| `PlayerName=<your-tag>` | `PlayerName=Player1` |
| `PlayerName=<opponent-tag>` | `PlayerName=Player2` |
| `BnetID=<hi> <lo>` (your account) | `BnetID=1 1` |
| `BnetID=<hi> <lo>` (opponent) | `BnetID=2 2` |

**Consistency rule:** every occurrence of the same BattleTag must map to the same Player1/Player2 alias within a fixture. Otherwise the parser sees two distinct entities and tests fail confusingly.

`sed` example (WSL/Git Bash):

```bash
sed -i 's/PlayerName=YourTag#1234/PlayerName=Player1/g; \
        s/PlayerName=OpponentTag#5678/PlayerName=Player2/g; \
        s/BnetID=144115205255972392 1234/BnetID=1 1/g; \
        s/BnetID=144115205255972999 5678/BnetID=2 2/g' \
        match_start.log
```

## Step 9: Truncate to size budget

If any file exceeds its size budget (250 KB for the standard fixtures, 2 MB for battlegrounds), truncate at a `\n` boundary:

```bash
# Cap at 250000 bytes:
head -c 250000 game_end.log > game_end_trimmed.log

# Open game_end_trimmed.log in a text editor.
# Delete the partial last line (any line that does not end with a complete tag/value).
# Save, then move:
mv game_end_trimmed.log game_end.log
```

**Why the newline boundary matters:** `Parser.feed_line()` calls `hslog.LogParser` which raises `RegexParsingError` on partial lines. A fixture truncated mid-line will fail loading.

For `battlegrounds.log`: prefer git LFS if available; otherwise truncate to 2 MB at a `\n` boundary using the same procedure.

## Step 10: Place files

Copy all 4-5 captured `.log` files into `tests/fixtures/log/` in this repo. Confirm:

```bash
ls tests/fixtures/log/
# Expected: match_start.log mid_game.log game_end.log reconnect.log [battlegrounds.log]
```

## Step 11: Verify with the test suite

```bash
uv run pytest tests/test_services/test_engine.py -v
```

The previously-skipped fixture-dependent tests should now report PASSED:

- `test_mid_game_fixture_emits_expected_events`
- `test_dual_source_fixture_no_duplicates`
- `test_tick_under_50ms`

If any test fails:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `RegexParsingError` on a specific line | Truncation cut mid-line, or `sed` replaced a numeric ID with a malformed one | Re-truncate at `\n`; use the consistency rule in Step 8 |
| `assert events == expected_event_sequence` mismatch | Captured a different match flow than the test expects (e.g., different starting hand, different turn count) | Re-capture with the script the test expects, or update the test's expected sequence |
| `test_tick_under_50ms` exceeds budget | `card_db` lookup hitting disk on every call, or excessive `dataclasses.replace` | Cache `CardDatabase` once per session in the fixture; batch `replace()` per packet group |

## When to re-capture

Re-run this procedure (and update this doc with the new build number) when:

- Hearthstone patch changes the `Power.log` format (e.g., a new `BLOCK_START` regex variant — `hslog` has 5+ historical variants)
- An `hslog` 1.x upgrade changes parser output that breaks an existing fixture
- A new test requires a scenario not in the current fixtures (e.g., a specific dormant-minion sequence for DIFF-03)

After re-capture, append a row to the table below documenting which build was captured and which tests broke.

## Capture log

| Date (UTC) | Hearthstone build | Captured by | Notes |
|------------|-------------------|-------------|-------|
| _Initial capture (Plan 02-08, Task 1)_ | _to fill in_ | _to fill in_ | _to fill in_ |

## Privacy note

Captured `Power.log` files contain only public game data once anonymized. Hearthstone does not write personally identifying information beyond `PlayerName=` (BattleTag) and `BnetID=` — Step 8 removes both. Committing anonymized fixtures to a public repo is appropriate.
