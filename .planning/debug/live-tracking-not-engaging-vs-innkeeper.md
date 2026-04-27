---
status: diagnosed
trigger: "this isn't working vs the innkeeper"
created: 2026-04-27T00:00:00Z
updated: 2026-04-27T00:00:00Z
---

## Current Focus

hypothesis: GameEngine._refresh_state() never populates state.player_deck / player_deck_count / opponent_deck_count / player_mana / player_max_mana / opponent_mana / opponent_max_mana / player_hero / opponent_hero from internal _entities bookkeeping; the engine only publishes player_played, opponent_played, player_drawn, opponent_drawn, opponent_hand. The presenter and view are correctly wired and would render correctly IF those fields were ever non-empty.
test: Read engine.py and grep for any code that ever assigns those fields after the empty-Hero initialization in _on_create_game.
expecting: No assignments anywhere outside _on_create_game's initial empty values. → confirms structural gap.
next_action: Diagnosis complete. Return ROOT CAUSE FOUND.

## Symptoms

expected: With a Hearthstone match running (vs Innkeeper or otherwise), the LiveGamePanel reflects game state — title shows "<Class> vs <Class>", Remaining Deck count decrements as cards are drawn, Opponent Hand zone populates, Cards Drawn zone populates per draw event.
actual: User reported "this isn't working vs the innkeeper". UAT test 8 marked failed.
errors: None reported by user. Console output during the failed match was not captured.
reproduction: UAT test 8 in .planning/phases/03-live-game-tracking/03-UAT.md. Hearthstone open, match started vs Innkeeper, StoneReader running with Live Game panel open.
started: Discovered during UAT 2026-04-27.

## Eliminated

- hypothesis: Tracker not started in OnInit
  evidence: app.py:573 calls self._tracker.start(parent=self._frame) inside try/except after frame.Show(). Wiring is correct.
  timestamp: 2026-04-27

- hypothesis: Presenter not subscribed to tracker
  evidence: presenters/live_game.py:105 calls self._tracker.subscribe(self._on_game_event) in __init__. App constructs presenter at app.py:464 (live_presenter = LiveGamePresenter(speech, db_conn, self._tracker, card_db)) using the same self._tracker that gets started later.
  timestamp: 2026-04-27

- hypothesis: View not wired to presenter state-change callback
  evidence: views/live_game.py:198-199 wires presenter.set_on_state_changed(self._on_state_changed) and set_on_title_changed in LiveGamePanel.__init__. Presenter._notify_view fires both callbacks (live_game.py:274-278). View's _on_state_changed re-fetches all 4 zones and calls SetLabel on title/mana.
  timestamp: 2026-04-27

- hypothesis: Practice mode (vs Innkeeper) is gated out of tracking
  evidence: presenters/live_game.py:61 _NON_CONSTRUCTED_GAME_TYPES = {"BATTLEGROUNDS", "ARENA"}. GT_VS_AI is NOT in this set; Innkeeper match would not be skipped. Tracker dispatch path doesn't filter by game_type either.
  timestamp: 2026-04-27

- hypothesis: Watcher not tailing right path / log.config not enabled
  evidence: app.py:402 calls ensure_log_config() at app start which idempotently writes [Power] section to %LOCALAPPDATA%\Blizzard\Hearthstone\log.config (services/_log_config.py:43-81). discover_power_log_path falls back to registry HKLM\SOFTWARE\Blizzard\Hearthstone\InstallPath when install_dir is unknown (services/_log_path.py:35-65). Path resolution is best-effort but robust. Even if user-setup were the issue, that would not explain why the user did not report ANY title or zone activity at all (the panel would still render "No game in progress" before tracking ever fires — and that DOES match what they see). User-setup remains a possible additional concern but is downstream of the structural gap below.
  timestamp: 2026-04-27

## Evidence

- timestamp: 2026-04-27
  checked: services/_engine.py: every call site that constructs or replaces self._current_state.
  found: _on_create_game (line 311-334) constructs GameState with empty_hero (hero_class=""), player_deck=() (default), player_deck_count=0 (default), player_mana=0 (default). _refresh_state (line 562-609) reconstructs ONLY player_played, opponent_played, player_drawn, opponent_drawn, opponent_hand. NO code path ever populates state.player_deck, state.player_deck_count, state.opponent_deck_count, state.player_mana, state.player_max_mana, state.opponent_mana, state.opponent_max_mana, state.player_hero, or state.opponent_hero after the initial empty construction.
  implication: GameState fields the LiveGamePresenter and LiveGamePanel render are permanently stuck at their dataclass defaults (0 / "" / ()) for the entire game.

- timestamp: 2026-04-27
  checked: presenters/live_game.py: data flow from state.player_deck → auto-detection trigger → _compute_remaining_deck.
  found: Line 134-138 gates auto-detection on revealed_count = sum(1 for e in state.player_deck if e.card_id) >= 30. Since state.player_deck is permanently (), revealed_count is permanently 0; auto-detection NEVER fires. Line 187-210 _compute_remaining_deck iterates state.player_deck for the no-detected-deck branch — iterating over () produces no rows. The Remaining Deck zone is therefore always empty.
  implication: Remaining Deck zone (UAT test 8 user-visible deliverable LIVE-02) cannot populate regardless of in-game activity.

- timestamp: 2026-04-27
  checked: presenters/live_game.py current_title() (line 282-291).
  found: player_class = (state.player_hero.hero_class or "").strip(); opponent_class = (state.opponent_hero.hero_class or "").strip(); matchup = " vs ".join(filter(None, [player_class, opponent_class])) or "Game"; deck_name = self._detected_deck_name or "Unknown deck"; returns f"{matchup} — {deck_name}". With both heroes' hero_class empty, matchup becomes "Game"; with detection never firing, deck_name is "Unknown deck"; title becomes "Game — Unknown deck" once a game starts. (User reported NOT seeing "<Class> vs <Class>" — consistent with this.)
  implication: Title cannot show real matchup (LIVE-08 user-visible deliverable) because hero_class is never set on either Hero.

- timestamp: 2026-04-27
  checked: presenters/live_game.py current_mana_summary() (line 305-313).
  found: Returns f"You {state.player_mana}/{state.player_max_mana}, opponent {state.opponent_mana}/{state.opponent_max_mana}". With all four mana fields permanently 0, mana line would always read "You 0/0, opponent 0/0".
  implication: Mana StaticText (LIVE-07) cannot show real values. UAT test 4 already separately reports the mana line is missing/blank from OCR — consistent.

- timestamp: 2026-04-27
  checked: presenters/live_game.py announce_deck_counts() (line 331-340), used by Ctrl+Shift+D.
  found: Speaks f"{state.player_deck_count} left, opponent {state.opponent_deck_count}." Both fields are permanently 0. Hotkey would always announce "0 left, opponent 0." (UAT test 6 explicitly accepts this as passing because the test was run with no Hearthstone game — but it would also be wrong DURING a real game.)
  implication: Ctrl+Shift+D speak-only hotkey (LIVE-06 user-visible deliverable) cannot reflect real deck counts.

- timestamp: 2026-04-27
  checked: tests/test_live_game_presenter.py _make_state helper (lines 87-127).
  found: All 19 presenter tests construct GameState manually via _make_state(player_deck=..., player_deck_count=..., player_hero_class="MAGE", player_mana=..., ...). The tests SET these fields directly, then dispatch synthetic events through MockGameTracker. The tests therefore verify presenter behavior given a populated GameState — they do NOT verify that the production GameEngine actually populates that GameState from real Power.log data.
  implication: There is a missing integration test layer between Phase 2 (engine) and Phase 3 (presenter). The presenter is well-tested and correct; the engine has a structural gap; no test catches the gap because each side is unit-tested with synthetic data on the other side of the boundary.

- timestamp: 2026-04-27
  checked: Cards Drawn zone (state.player_drawn) and Opponent Hand zone (state.opponent_hand) — the two zones the engine DOES populate.
  found: _refresh_state DOES rebuild player_drawn (engine.py:606), opponent_drawn (607), opponent_hand (608) from authoritative bookkeeping. _handle_zone_change (397-467) appends to _player_drawn / _opponent_drawn on ZONE→HAND transitions. _record_entity (145-178) feeds opponent_hand reconstruction. So: (a) Cards Drawn zone WOULD populate during a real game (good news — the chain is end-to-end alive on those zones); (b) Opponent Hand zone WOULD populate. UAT test 8's "isn't working" is dominated by the visible failure of Title and Remaining Deck — both directly affected by the missing fields.
  implication: The engine is partially-correct. The user's report is consistent with seeing a working app where the title and Remaining Deck zone are inert while other zones might or might not show activity (the user did not test individual zones — they saw the most prominent visible elements failing and reported the whole thing as broken).

## Resolution

root_cause: |
  GameEngine._refresh_state() does not populate the GameState fields that the LiveGamePresenter renders to the user as the most-visible deliverables — specifically: player_deck (drives Remaining Deck zone + auto-deck-detection), player_deck_count / opponent_deck_count (drive Ctrl+Shift+D speech), player_mana / player_max_mana / opponent_mana / opponent_max_mana (drive mana StaticText), and player_hero.hero_class / opponent_hero.hero_class (drive panel title matchup).

  All these fields are initialized to empty/zero defaults in _on_create_game (engine.py:311-334) and never updated thereafter. _refresh_state only republishes player_played, opponent_played, player_drawn, opponent_drawn, and opponent_hand — leaving the rest stale at construction-time defaults.

  Because of this:
  - Panel title reads "Game — Unknown deck" instead of "<Class> vs <Class> — <DeckName>" (LIVE-08 broken).
  - Remaining Deck zone is permanently empty, irrespective of how many cards Hearthstone reveals via FullEntity packets at CREATE_GAME (LIVE-02 broken).
  - Auto-deck-detection (LIVE-08) never triggers because revealed_count = sum(1 for e in state.player_deck if e.card_id) is permanently 0.
  - Mana StaticText reads "You 0/0, opponent 0/0" instead of real mana (LIVE-07 broken).
  - Ctrl+Shift+D speaks "0 left, opponent 0." instead of real counts (LIVE-06 broken).

  Cards Drawn and Opponent Hand zones DO populate from real packets (because _refresh_state does rebuild player_drawn and opponent_hand), but with the most-visible deliverables broken, the user reasonably reports the whole feature as "not working".

  This is a structural gap in Phase 02's engine that Phase 03 inherited without an integration test bridging the two layers. The presenter is correctly wired against the engine; the engine is correctly wired against the parser/watcher; but the engine fails to publish the deck/mana/hero state to GameState. There is NO UAT-distinguishing factor for "vs Innkeeper" specifically — the same failure would manifest in any game type because the missing engine code is independent of game type.
fix: Diagnosis only — to be addressed by gsd-planner gap-closure plan.
verification: ""
files_changed: []
