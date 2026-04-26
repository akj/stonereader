---
phase: 3
reviewers: [codex]
reviewed_at: 2026-04-26T23:32:44Z
plans_reviewed: [03-01-PLAN.md, 03-02-PLAN.md, 03-03-PLAN.md, 03-04-PLAN.md, 03-05-PLAN.md, 03-06-PLAN.md]
notes: >
  Running inside Claude Code CLI, so the local `claude` reviewer was skipped for
  independence. Of the remaining configured reviewers, only `codex` was
  installed locally — `gemini`, `coderabbit`, `opencode`, `qwen`, and `cursor`
  were missing on PATH. This review therefore reflects a single external AI
  perspective rather than a multi-reviewer consensus.
---

# Cross-AI Plan Review — Phase 3

## Codex Review

## 03-01-PLAN.md

### Summary
This is a solid Wave 0 scaffolding plan with clear scope control: it creates test placeholders and a `MockGameTracker` without touching production code. It sets up later waves well, but it is slightly too rigid about exact test counts and imports from `tests.conftest`, which could create avoidable friction if the repo's test layout differs from assumptions.

### Strengths
- Clear separation: test scaffolding only, no production-code bleed.
- Good requirement traceability from LIVE/WR/D items to named tests.
- `MockGameTracker` mirrors the important tracker contract, including exception isolation.
- `collect-only` verification is the right gate for this wave.
- Explicit anti-false-green stance is correct.

### Concerns
- **MEDIUM**: The plan hardcodes exact file contents and exact test counts, which is brittle if the existing test suite already has overlapping helpers or naming conventions.
- **MEDIUM**: Importing directly from `tests.conftest` can be fragile; pytest fixtures/helpers are often better imported from helper modules to avoid path quirks.
- **LOW**: `dispatch()` swallowing all exceptions with `pass` matches the tracker behavior conceptually, but it hides debugging signal during tests.
- **LOW**: Requiring all stubs to be `xfail` may create noise later when converting tests incrementally; some could be `skip` with a tighter reason.

### Suggestions
- Move `MockGameTracker` to a dedicated test helper module if this repo already uses that pattern.
- Log or comment swallowed exceptions in `MockGameTracker.dispatch()` so failures are easier to debug if reused beyond scaffolding.
- Relax "exactly N tests" style acceptance criteria to "all required named tests exist."
- Confirm whether `tests/conftest.py` is already imported as a normal module in this repo before depending on `from tests.conftest import ...`.

### Risk Assessment
**LOW**. The plan is narrow and reversible. Main risk is test-maintenance friction, not product correctness.

---

## 03-02-PLAN.md

### Summary
This plan addresses a real correctness blocker and is one of the most important in the phase. The overall direction is right, especially the parser shape fix and dual-path friendly-player resolution, but the fallback logic is under-specified relative to actual log timing and may still misattribute pre-resolution events in real multiplayer logs.

### Strengths
- Correctly identifies WR-02 as phase-critical.
- Good decision to carry `player_id` distinctly through parser and packets.
- Good regression coverage for AI heuristic, fallback, and fixture lock.
- Preserves raw `CardDrawn.controller` semantics while fixing derived bucketing.
- Sequential parser → packet → engine update ordering is sound.

### Concerns
- **HIGH**: The SHOW_ENTITY fallback as written uses the first `SHOW_ENTITY` into `HAND` after unresolved create-game, but the plan assumes that event reliably belongs to the friendly player in all relevant cases. If replayed/reconnect/mulligan ordering differs, this can still misresolve.
- **HIGH**: Re-bucketing by simply swapping `player_drawn/opponent_drawn` and `player_played/opponent_played` assumes all pre-resolution rows were inverted uniformly. That may not hold if some rows happened after resolution or if mixed-controller events were already emitted.
- **MEDIUM**: The plan explicitly chooses "default to 1, then fix later," which bakes in a known transient wrong state instead of buffering until resolved.
- **MEDIUM**: Updating packet tuple shape is a breaking internal contract; only some downstream tests are listed. Other code may destructure `CreateGamePacket.players`.
- **LOW**: The captured fixtures are all vs-AI, so the most important branch is still only synthetic-tested.

### Suggestions
- Prefer buffering controller-dependent bucketing until friendly-player resolution is known, at least during the startup window.
- If keeping re-bucketing, recompute from authoritative entity state rather than swapping accumulated lists blindly.
- Add a test for "events before fallback resolution and more events after fallback resolution" to validate mixed timing.
- Search for every `CreateGamePacket.players` consumer, not just known tests.
- Add a reconnect-specific friendly-resolution test if reconnect logs include a second `CREATE_GAME`.

### Risk Assessment
**MEDIUM-HIGH**. This plan targets the right bug, but subtle event-order issues could leave 50/50-style attribution bugs partially fixed rather than eliminated.

---

## 03-03-PLAN.md

### Summary
This plan is well-targeted and fixes a real engine gap: `opponent_hand` reconstruction plus lineage capture. The typed `creation_lineage` field is a good choice. The main risk is that the lineage heuristic is intentionally shallow and may overfit to simple POWER-block cases while missing or mislabeling more complex generation flows.

### Strengths
- Good choice to add a typed `creation_lineage` field instead of hiding data in tag bags.
- Fixes an important state-publication gap, not just the lineage feature.
- Clear five-condition lineage guard reduces false positives.
- Good reconnect-reset thinking.
- Synthetic tests are appropriate for lineage because real fixtures are limited.

### Concerns
- **MEDIUM**: Capturing lineage only from the top POWER block subject may be too naive for nested blocks or intermediary generators.
- **MEDIUM**: `opponent_hand` reconstruction from all `ZONE == HAND` entities assumes the bookkeeping dict is clean and unique; stale/duplicate entity state could leak in if zone transitions are not fully normalized.
- **MEDIUM**: `drawn_turn` remains mostly placeholder state, but the presenter plan later speaks it as if authoritative.
- **LOW**: `creation_lineage` is sticky forever once set. That is probably intended, but a plan note should state that later reveals or transforms do not rewrite lineage.
- **LOW**: Tests do not appear to cover `SHOW_ENTITY` revealing an existing hidden hand entity after lineage was recorded.

### Suggestions
- Add one nested-block synthetic test to verify the chosen subject selection rule.
- Add a test where a hand entity is later revealed via `SHOW_ENTITY` and confirm lineage survives.
- Document explicitly that lineage is best-effort and not guaranteed across reconnects or complex nested generation flows.
- Consider reconstructing `opponent_hand` from authoritative zone-position ordering with dedupe by entity id.

### Risk Assessment
**MEDIUM**. The plan is directionally correct and likely sufficient for v1, but lineage is inherently heuristic and the current approach is intentionally approximate.

---

## 03-04-PLAN.md

### Summary
This is a strong, appropriately scoped service plan. It keeps hotkey registration generic, testable, and isolated from app wiring. The implementation shape is sound. The main weakness is that the tests validate service behavior with monkeypatching but do not exercise enough callback-failure and duplicate-registration edge cases.

### Strengths
- Good separation: service only, no premature app coupling.
- Correct use of `wx.RegisterHotKey` abstraction instead of low-level hooks.
- `MOD_NOREPEAT` default is a good design choice.
- Failure accumulation and idempotent cleanup are both practical.
- Test strategy avoids real OS registration, which is correct for unit scope.

### Concerns
- **MEDIUM**: No explicit test for callback exception isolation in `_on_hotkey`.
- **MEDIUM**: No explicit test for repeated `register()` calls after a failure or partial success.
- **LOW**: `clear_all()` retains `_failed`, which is reasonable, but the lifecycle expectation should be documented so callers do not treat it as current-state only.
- **LOW**: The service binds `EVT_HOTKEY` in constructor and never unbinds; usually fine for frame-lifetime use, but worth noting.

### Suggestions
- Add a fourth unit test for a callback that raises to ensure dispatch isolation and logging.
- Add a test for unknown event ids and duplicate `clear_all()` after failed registration.
- Document that `failed` is cumulative for the service lifetime.
- Consider exposing registered labels/ids for diagnostics if future troubleshooting matters.

### Risk Assessment
**LOW-MEDIUM**. The plan is small, well-bounded, and technically sound. Residual risk is mostly around missing edge-case tests.

---

## 03-05-PLAN.md

### Summary
This is the largest and riskiest plan in the set because it concentrates a lot of policy into one presenter: subscription, deck detection, three zone adapters, speech formatting, and navigation behavior. The overall architecture fits the codebase, but there is some scope creep and a few correctness mismatches, especially around LIVE-03, drawn-turn fidelity, and the assumption that the presenter can safely own all these private cross-layer contracts.

### Strengths
- Good MVP alignment: presenter owns speech and state interpretation.
- Strong requirement mapping and test intent.
- Correct silence-on-event policy for screen reader usability.
- Strict deck-detection policy is the right trust model.
- Keeping the presenter wx-free is a good boundary.

### Concerns
- **HIGH**: The plan claims coverage for LIVE-03 through opponent-hand speech formatting, but LIVE-03 in the phase requirements is "cards drawn this game." The presenter does not actually surface a drawn-cards list; this is a requirements mismatch.
- **HIGH**: The drawn-to-zero test uses a 30x copy deck, which is not a legal Hearthstone deck for normal constructed play and may not be supported by deckstring tooling assumptions.
- **MEDIUM**: Presenter tests depend heavily on private attributes (`_detected_deck_name`, `_format_title`, `_zone_cursors`), making refactors expensive.
- **MEDIUM**: `OpponentHandRow.drawn_turn` is treated as meaningful speech output, but the engine plan does not robustly populate it yet.
- **MEDIUM**: The presenter carries more policy than necessary, including title formatting and hotkey-oriented phrasing, which could complicate view integration.
- **MEDIUM**: Non-constructed skip-list is too narrow if other modes also violate the 30-card invariant.
- **LOW**: The plan mentions cursor-key preservation in prose but the proposed implementation mostly preserves indices, not logical identity.

### Suggestions
- Resolve the LIVE-03 mismatch explicitly: either re-scope the requirement, or add a minimal drawn-cards surface if Phase 3 must claim it.
- Replace the 30x single-card detection test with a legal deck composition.
- Avoid testing presenter internals directly where public behavior can be asserted instead.
- Do not speak `drawn_turn` as authoritative until engine population is verified; consider fallback wording when it is `-1`.
- Reduce presenter responsibility slightly by making title/mana formatting explicit public accessors if the view needs them.
- Add a test for malformed saved deckstrings being skipped without breaking detection.

### Risk Assessment
**MEDIUM-HIGH**. The architecture is workable, but this plan carries the most product-level behavior and currently has one real requirements mismatch plus several "best effort" assumptions.

---

## 03-06-PLAN.md

### Summary
This plan completes the user-facing path, but it is the most integration-sensitive and currently has the highest risk of subtle UX and lifecycle bugs. The general wiring is appropriate, but there are signs of over-coupling between view, presenter, and app frame, and some implementation details conflict with the project's accessibility and layering standards.

### Strengths
- Correctly defers app wiring until services and presenter exist.
- Hotkey mapping choices are coherent and mnemonic.
- Cleanup ordering is explicitly considered, which matters for OS-registered state.
- Manual checkpoint is appropriate here; automated tests cannot fully validate real WM_HOTKEY/NVDA behavior.
- Home-menu and hotkey dual-entry model matches the phase decisions.

### Concerns
- **HIGH**: The browse-open hotkey callback order and focus behavior are still shaky. Speaking before the panel is focused may be acceptable, but the plan does not verify that subsequent keyboard navigation lands in the right place consistently.
- **HIGH**: The view plan reaches into presenter private state (`_zone_cursors`, `_format_title`) and the app plan reaches into presenter private state (`_current_state`) for hand-count speech. That is tight coupling and likely to rot.
- **HIGH**: `LiveGamePanel` using multiple virtual `ListCtrl`s with `AcceptsFocus() -> False` may not give a reliable accessible reading surface for screen-reader users if focus always remains on the outer panel. This needs stronger validation than the plan provides.
- **MEDIUM**: The view text and presenter speech can diverge; there is duplicated formatting logic in two layers.
- **MEDIUM**: Adding a fourth hotkey for opponent hand count is reasonable, but it expands scope beyond what earlier plans tested directly.
- **MEDIUM**: The close-path integration test only checks call order, not failure handling or whether DB close still occurs when cleanup raises.
- **MEDIUM**: `LiveGamePanel` is a UI task, and the plan does not explicitly account for manual accessibility verification of list semantics, label relationships, and keyboard/focus behavior beyond the smoke test.
- **LOW**: Importing new modules inside `OnInit` blocks is fine, but consistency with existing app composition style should be checked.

### Suggestions
- Add small public presenter accessors instead of reading `_current_state`, `_zone_cursors`, and `_format_title` from outside the presenter.
- Add an automated test for `_on_close` continuing cleanup if one step raises.
- Reduce duplicated row-formatting logic by centralizing display-text helpers.
- Reconsider whether three separate non-focusable `ListCtrl`s are the best accessible surface; at minimum, make the manual verification gate stricter on actual NVDA object navigation and keyboard use.
- Add a presenter method `announce_opponent_hand_count()` so app wiring does not bypass presenter ownership of speech/state.
- Verify that the home-menu "Live Game" entry and browse-open hotkeys behave correctly when no game has been seen yet.

### Risk Assessment
**HIGH**. This plan is where architecture, accessibility, and lifecycle all meet. It probably works, but the coupling and focus/accessibility risks are material.

---

# Overall Assessment

## Summary
The phase is well decomposed and mostly follows the codebase's architecture. Plans 03-02, 03-03, and 03-04 are the strongest. The main weaknesses are in the user-facing layers: 03-05 has a requirements mismatch around LIVE-03, and 03-06 introduces tight coupling plus accessibility/focus risks that the automated tests only partially cover.

## Cross-Plan Strengths
- Good wave ordering overall.
- Strong traceability from requirements to tests.
- Correct separation of engine, service, presenter, and app wiring in principle.
- Good attention to silent speech behavior and conflict reporting.
- Reasonable manual-validation checkpoint for Windows/NVDA specifics.

## Cross-Plan Concerns
- **HIGH**: LIVE-03 is not clearly satisfied by the current plan set as written.
- **HIGH**: Friendly-player fallback and rebucketing may still be wrong in edge timing cases.
- **HIGH**: The final UI wiring relies on private presenter internals too heavily.
- **MEDIUM**: Drawn-turn and lineage are spoken with more confidence than the engine can robustly guarantee.
- **MEDIUM**: Accessibility validation is present, but the chosen `ListCtrl` interaction model still needs more skepticism.

## Cross-Plan Suggestions
- Fix the LIVE-03 requirement story before implementation proceeds.
- Strengthen WR-02 handling around pre-resolution event timing.
- Add public presenter APIs for title, hand count, and cursor/selection state to reduce coupling.
- Tighten 03-06 accessibility validation around focus, screen reader reading order, and actual interaction with the panel controls.
- Add a small "integration contract" doc or test for presenter/view/app interactions to avoid private-field creep.

## Overall Risk Assessment
**MEDIUM-HIGH**. The backend and service layers are well planned, but the user-facing integration still has real correctness and accessibility risk, and one requirement is not convincingly met by the current plan set.

---

## Consensus Summary

Only one external reviewer (Codex) was available in this environment, so no
multi-reviewer consensus was synthesized. The full review above represents the
single external perspective.

If multi-AI consensus is desired, install at least one additional CLI from the
following and re-run `/gsd:review --phase 3`:

- `gemini` — https://github.com/google-gemini/gemini-cli
- `coderabbit` — CodeRabbit CLI
- `opencode` — https://opencode.ai
- `qwen` — https://github.com/nicepkg/qwen-code
- `cursor` — https://cursor.com

### Top Concerns (from Codex, ranked HIGH)
1. **LIVE-03 requirements mismatch** — 03-05-PLAN claims LIVE-03 coverage via opponent-hand formatting, but LIVE-03 is "cards drawn this game." Either re-scope the requirement or add a drawn-cards surface.
2. **WR-02 friendly-player edge cases** — Fallback resolution and re-bucketing in 03-02-PLAN may misattribute mixed-timing events around the resolution boundary.
3. **UI coupling to presenter internals** — 03-06-PLAN view/app code reads `_current_state`, `_zone_cursors`, `_format_title` from the presenter; this needs public accessors before implementation.
4. **`LiveGamePanel` accessibility model** — Multiple non-focusable virtual `ListCtrl`s may not provide a reliable screen-reader reading surface; needs stronger validation than the planned smoke test.
