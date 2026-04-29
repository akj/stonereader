---
phase: 03-live-game-tracking
reviewed: 2026-04-29T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - stonereader/services/_engine.py
  - stonereader/services/_parser.py
  - tests/test_services/test_engine_live_state.py
findings:
  blocker: 1
  warning: 5
  total: 6
status: issues_found
---

# Phase 3 (plan 03-07): Code Review Report

**Reviewed:** 2026-04-29
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found
**Scope note:** This review supersedes routing decisions for plan 03-07 changes
only. Findings unrelated to the 03-07 diff (e.g., the pre-existing
`_handle_playstate` `eid == self._friendly_player_id` entity-id-vs-player-id
mismatch on `_engine.py:568,573` carried over from `e953836`) are out of scope
and not re-flagged here.

## Summary

Plan 03-07 closes the engine-publication gap surfaced by UAT: heroes,
RESOURCES/RESOURCES_USED, friendly-deck rebuild, and per-controller deck counts
were never reflected on `engine.current_state`. The fix has the right shape
— `_resolve_heroes` runs at CREATE_GAME and on every late-arriving HERO entity;
RESOURCES branches share the player-entity row; `_refresh_state` rebuilds
`player_deck` from authoritative ZONE==DECK entries — and the captured-fixture
test added in `test_engine_live_state.py` is a strong regression gate.

However, the changes introduce one BLOCKER (heroes are NOT rebucketed when the
multiplayer SHOW_ENTITY-into-HAND fallback flips `_friendly_player_id`),
plus several WARNINGs around partial rebucket coverage, false-zero clamping in
the hero HEALTH/ARMOR fallback, sequencing of hero resolution before
friendly-player resolution, the parser's continued use of hslog private state,
and direct private-state coupling in the new captured-fixture tests.

## Blockers

### BL-01: Heroes are never re-attributed when the multiplayer fallback flips `_friendly_player_id`

**File:** `stonereader/services/_engine.py:271-295` (fallback) and
`stonereader/services/_engine.py:195-239` (`_resolve_heroes`)
**Issue:** In a multiplayer (PvP) game where both players have `lo != 0`,
`_resolve_friendly_player_ai_heuristic` cannot disambiguate at CREATE_GAME, so
`_friendly_player_resolved` stays False and `_friendly_player_id` keeps the
default `1`. Any HERO entity recorded via `FULL_ENTITY` between CREATE_GAME and
the first `SHOW_ENTITY` into HAND triggers `_resolve_heroes` (via
`_record_entity` line 183-184), which classifies the heroes against the
*default* `_friendly_player_id == 1`. When the friendly is actually player 2,
`new_player_hero` and `new_opponent_hero` get swapped on the published
GameState.

When the SHOW_ENTITY-into-HAND fallback subsequently fires
(`_resolve_friendly_player_show_entity_fallback`), it flips
`_friendly_player_id` and calls `_rebucket_from_entities`. That helper only
rebuckets `_player_drawn` / `_opponent_drawn` / `_player_played` /
`_opponent_played` — it does **not** re-resolve heroes, RESOURCES-derived mana
fields, or the deck rebuild in `_refresh_state`. Result: in PvP captures, the
LiveGame panel announces the OPPONENT'S hero class as the user's hero (and vice
versa) for the rest of the match, even though `_rebucket_from_entities`
appears to "fix everything."

This is data-integrity-level wrong (LIVE-08 hero-class announcement) and is not
covered by the captured fixtures (the four `tests/fixtures/log/*.log`
fixtures appear to be vs-AI captures, where the AI heuristic resolves friendly
at CREATE_GAME and the codepath is never exercised).

**Fix:** Have `_rebucket_from_entities` (or the fallback resolver itself) call
`_resolve_heroes` and re-run the RESOURCES classification after flipping
`_friendly_player_id`. Concretely, in `_rebucket_from_entities`:

```python
def _rebucket_from_entities(self) -> None:
    # ...existing drawn/played rebucket...
    self._player_played = new_player_played
    self._opponent_played = new_opponent_played

    # gap-closure 03-07 follow-up: heroes were classified at FULL_ENTITY/
    # CREATE_GAME time using the previous _friendly_player_id. Re-run the
    # full hero pass so player_hero / opponent_hero swap when friendly
    # flips from default 1 → real friendly player_id (multiplayer path).
    self._resolve_heroes()

    # RESOURCES rows on the player entities still carry the correct
    # PLAYER_ID, so re-derive mana for both sides from authoritative state.
    self._reapply_mana_from_entities()

    self._refresh_state()
```

Add a captured-fixture test using a PvP log (or a synthetic one with both
players' `lo != 0`) that asserts `state.player_hero.hero_class` is the friendly
class after the fallback resolves. Without that test, this regression class
will recur on the next refactor.

## Warnings

### WR-01: RESOURCES/RESOURCES_USED updates pre-fallback-resolution stick to the wrong side

**File:** `stonereader/services/_engine.py:454-484` (RESOURCES branch) and
`stonereader/services/_engine.py:297-341` (`_rebucket_from_entities`)
**Issue:** Same root cause as BL-01 but for mana. Any RESOURCES /
RESOURCES_USED TAG_CHANGE that arrives BEFORE the SHOW_ENTITY-into-HAND
fallback resolves friendly_player_id is classified using the default
`_friendly_player_id == 1`, so the mana update may write to
`player_mana`/`player_max_mana` when it should have written to
`opponent_mana`/`opponent_max_mana`. `_rebucket_from_entities` does not replay
the mana derivation, so the stale field values persist.

In practice the fallback usually fires before significant turn-1
RESOURCES_USED activity (mulligan happens before turn 1), so this is
narrower than the hero issue — but the failure mode is identical and any test
that races a RESOURCES update before the first opponent SHOW_ENTITY-into-HAND
will see swapped mana for one snapshot.

**Fix:** Add a `_reapply_mana_from_entities()` helper invoked from
`_rebucket_from_entities`:

```python
def _reapply_mana_from_entities(self) -> None:
    if self._current_state is None:
        return
    replacements = {}
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
```

### WR-02: `_resolve_heroes` clamps HEALTH/ARMOR with `or 30` / `or 0`, masking real zero values

**File:** `stonereader/services/_engine.py:223-224`
**Issue:** Lines 223-224 compute the Hero fields as

```python
health=ent.get("HEALTH", 30) or 30,
armor=ent.get("ARMOR", 0) or 0,
```

The `or 30` / `or 0` form short-circuits when the tag is present but falsy (0).
For `HEALTH=0` this overrides a legitimate value with 30 and hides a hero
that has been read at 0 health (e.g., late SHOW_ENTITY rebroadcast that
includes `HEALTH=0` after lethal). For `armor`, `0 or 0` is always 0, so the
expression is harmless but obscures intent. Use `if ... is None` instead of
the short-circuit so a zero in the log is preserved:

```python
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
```

Same pattern recurs throughout `_refresh_state` (lines 701-705, 726-730 — the
`ent.get("ATK", 0) or 0` and `ent.get("HEALTH", 0) or 0` forms — but those
were not introduced by 03-07 and are out of scope here).

### WR-03: `_resolve_heroes` ordering during CREATE_GAME ignores future late-arriving FULL_ENTITY hero packets without card_id resolution

**File:** `stonereader/services/_engine.py:386-393`
**Issue:** `_on_create_game` calls `_resolve_heroes` at line 393 — but only
records the GameEntity and player rows beforehand (lines 356-360). Hero
entities arrive as `FullEntity` packets *after* CREATE_GAME's own packet block
in the log; those FullEntities are emitted to the engine on subsequent
`apply()` calls, where each one's `_record_entity` re-invokes
`_resolve_heroes` (line 184). So the line 393 call usually finds zero
HERO entities in `_entities` and is a no-op — the work is done later when the
FullEntity for the hero card is consumed.

That's correct behavior, but the comment on lines 388-392 ("hero entities for
both players are typically recorded inside the CREATE_GAME block via
FullEntity packets BEFORE the GameState is constructed above") is misleading:
each FullEntity is a separate top-level hslog packet that arrives in a separate
`apply()` call, not a sub-row appended inside the CreateGame packet. The first
call to `_resolve_heroes` at line 393 is therefore typically a no-op, and the
real resolution happens via `_record_entity` after CREATE_GAME returns.

This is not a correctness bug — `_resolve_heroes` is idempotent — but the
misleading comment will lead future readers to delete the line-393 call as
"clearly redundant," which would break the case where hero entities ARE
included in CREATE_GAME's `initial_tags` parse path (rare, but conceivable).

**Fix:** Either remove the line-393 call (it's a no-op in practice and
`_record_entity` handles every real case), or update the comment:

```python
# gap-closure 03-07: defensive — handles the rare case where a hero
# entity was recorded into _entities during the loop above (e.g. via a
# future hslog version that inlines hero FULL_ENTITY rows under
# CreateGame.entities). In the current hslog version this is a no-op
# because hero FullEntities arrive on subsequent apply() calls, where
# _record_entity re-runs _resolve_heroes.
self._resolve_heroes()
```

### WR-04: `_normalize_entity_id` duplicates `_player_entity_id` logic, drifting on PlayerReference handling

**File:** `stonereader/services/_parser.py:289-309` and
`stonereader/services/_parser.py:319-334`
**Issue:** `_normalize_entity_id` (new, line 289-309) and `_player_entity_id`
(pre-existing, line 319-334) both coerce a possibly-PlayerReference value to a
plain int. They are nearly identical except `_player_entity_id` falls back to
`p.player_id` while `_normalize_entity_id` falls back to `int(entity)` then
`0`. CreateGame translation uses `_player_entity_id` (line 227) and then
populates a tuple where the same row's `player_id` is the second column — a
future refactor that consolidates these two helpers risks flipping the
fallback semantics and silently making `_entities` keying inconsistent between
CREATE_GAME and TAG_CHANGE.

**Fix:** Have `_player_entity_id` delegate to `_normalize_entity_id` and only
fall back to `p.player_id` if normalization yields 0:

```python
@staticmethod
def _player_entity_id(p: Any) -> int:
    ent = getattr(p, "entity", None)
    eid = Parser._normalize_entity_id(ent) if ent is not None else 0
    if eid:
        return eid
    return int(getattr(p, "player_id", 0) or 0)
```

### WR-05: Captured-fixture tests reach into engine private state (`_entities`, `_friendly_player_id`)

**File:** `tests/test_services/test_engine_live_state.py:88, 178-187`
**Issue:** Two tests read engine-internal state directly:
- Line 88: `e.controller == engine._friendly_player_id` in
  `test_player_deck_rebuilt_from_entities`
- Line 178-187: iterates `engine._entities.values()` to compute the
  expected per-controller ZONE==DECK count in `test_deck_counts_track_zone`,
  using the same private `_friendly_player_id`

This is the same coupling pattern flagged as IN-03 in the prior review (direct
private state access in tests). For the new tests it's worse because
`_entities` is the engine's primary internal data structure: any future
refactor that moves bookkeeping out of a `Dict[int, dict]` (e.g., into a
typed `EntityRecord` class) will break these tests for reasons unrelated to
the contract being verified.

**Fix:** Either (a) add a public, test-only readonly accessor on the engine —
e.g., `engine.snapshot_for_test()` returning a copy or a typed view — and
have the tests use it; or (b) drop the cross-check against `_entities` in
`test_deck_counts_track_zone` and rely on the existing assertion that
`state.player_deck_count > 0` plus the bound `<= 60` (the equality check
against `_entities` adds little signal beyond the published-state assertions
and tightly couples the test to internal storage).

If retaining the private-state checks, add an explicit comment matching the
"this is one of the rare tests that DOES read internal state" style flagged in
the prior review's IN-03, so future readers know the coupling is intentional.

---

_Reviewed: 2026-04-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
