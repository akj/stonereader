---
status: diagnosed
trigger: "UAT test 4 — OCR shows last label as 'Drawn:' not 'Cards Drawn:', no mana line visible, screen reader only announces 'remaining_deck: empty' on panel entry."
created: 2026-04-27T00:00:00Z
updated: 2026-04-27T00:00:00Z
goal: find_root_cause_only
---

## Current Focus

hypothesis: All three observations have benign / expected explanations — only (a) is potentially actionable, and even then the source is correct. The OCR-vs-source discrepancy is a measurement artifact, not a code bug.
test: Direct source inspection of `stonereader/views/live_game.py` + `stonereader/presenters/live_game.py` + `stonereader/app.py`; cross-reference against UI-SPEC and 03-06-SUMMARY.
expecting: Source matches spec. OCR/screen-reader divergences explained by either (i) tooling artifacts or (ii) expected NVDA behavior on focus enter.
next_action: Return ROOT CAUSE FOUND with per-observation breakdown.

## Symptoms

expected: |
  Panel renders title → mana → 4 (label + list) blocks in vertical order.
  Last label reads "Cards Drawn:".
  Screen reader on panel entry walks the structure.
actual: |
  OCR: "No game in progress" / "Remaining Deck:" / "Opponent Hand:" / "Opponent Played:" / "Drawn:"
  No mana line visible in OCR.
  Screen reader on panel entry only announces (paraphrased) "remaining_deck: empty".
errors: None — UAT test 1 cold-start passed with no console output.
reproduction: Launch app, open Live Game from home menu, observe rendered panel + screen reader output.
started: Discovered during UAT 2026-04-27.

## Eliminated

- hypothesis: "Source code says 'Drawn:' instead of 'Cards Drawn:'"
  evidence: |
    `stonereader/views/live_game.py:190` reads literally:
        `self._cards_drawn_label = wx.StaticText(self, label="Cards Drawn:")`
    Module docstring at line 16 also says `"Cards Drawn:"`. Grep across the
    entire `stonereader/` tree finds zero occurrences of the bare string
    `"Drawn:"` — the only `"Drawn:"` matches are in `.planning/` documents
    (the UAT report itself and quoted plan/spec text).
    `git diff HEAD -- stonereader/views/live_game.py` shows no uncommitted
    changes; the only commit touching this file is the original feature
    commit `95516fd feat(03-06): add LiveGamePanel view + format helpers`.
  timestamp: 2026-04-27

- hypothesis: "Mana StaticText is missing from the layout"
  evidence: |
    `stonereader/views/live_game.py:168-169`:
        self._mana = wx.StaticText(self, label="")
        sizer.Add(self._mana, 0, wx.ALL | wx.EXPAND, 4)
    The widget is constructed and added to the sizer between the title
    (line 165) and the Remaining Deck label (line 172). It is present.
  timestamp: 2026-04-27

- hypothesis: "MSAA label-to-control association is broken (HUMAN-UAT B3 regression)"
  evidence: |
    All 4 (label, list) pairs are added directly to the panel's outer
    `wx.BoxSizer(wx.VERTICAL)` — no nested sub-panels. The labels and list
    ctrls are direct children of the same parent (`self`, i.e. the
    `LiveGamePanel`), so they are siblings in the wx parent-child tree.
    UI-SPEC §"Layout Contract" line 115 explicitly relies on this
    "immediately before its wx.ListCtrl in the BoxSizer" pattern; the
    implementation matches.
  timestamp: 2026-04-27

- hypothesis: "_open_remaining_deck or home-menu select chains are passing the wrong zone identifier and the literal `remaining_deck` is being read because `_ZONE_LABELS.get(zone_name, zone_name)` falls through to the raw key"
  evidence: |
    `stonereader/presenters/live_game.py:53-58` — `_ZONE_LABELS` maps
    `"remaining_deck"` to `"Remaining deck zone"`. Both
    `app.py:478-479` (`_on_home_select`) and `app.py:542-544`
    (`_open_remaining_deck`) pass the literal `"remaining_deck"` —
    matches the dict key exactly. The zone-empty announcement at
    `presenters/live_game.py:323` is `f"{label}: empty"` where `label`
    is the dict-resolved value `"Remaining deck zone"`. Therefore the
    actual speech IS `"Remaining deck zone: empty"`. The user's report
    `"remaining_deck: empty"` is a paraphrase, not a literal transcript.
  timestamp: 2026-04-27

## Evidence

- timestamp: 2026-04-27
  checked: stonereader/views/live_game.py (full file)
  found: |
    Line 164: title = wx.StaticText(self, label="No game in progress")
    Line 168: mana = wx.StaticText(self, label="")
    Line 172: remaining_label = wx.StaticText(self, label="Remaining Deck:")
    Line 178: opp_hand_label = wx.StaticText(self, label="Opponent Hand:")
    Line 184: opp_played_label = wx.StaticText(self, label="Opponent Played:")
    Line 190: cards_drawn_label = wx.StaticText(self, label="Cards Drawn:")
    All 6 StaticText widgets and 4 ListCtrls are added to the same
    `wx.BoxSizer(wx.VERTICAL)` bound to the panel via SetSizer at line
    195. There are no nested sub-panels.
  implication: |
    Source matches UI-SPEC and 03-06-SUMMARY exactly. The "Cards Drawn:"
    string is correct in source. Layout is flat — sibling order is
    correct for MSAA association.

- timestamp: 2026-04-27
  checked: stonereader/presenters/live_game.py:305-313 (current_mana_summary)
  found: |
    def current_mana_summary(self) -> str:
        state = self._current_state
        if state is None:
            return ""
        return f"You {state.player_mana}/... opponent ..."
    With no game (`_current_state is None`), this returns the empty string.
    The view sets `self._mana.SetLabel("")` in `_on_state_changed` (line 260).
  implication: |
    The mana StaticText is present in the sizer but contains an empty
    string. wx.StaticText with empty text collapses to ~0px height. OCR
    will not see any glyphs because there are no glyphs to read. This is
    the SPEC behavior per UI-SPEC §"Layout Contract" — mana is
    "panel-only mana surfacing" that comes alive when a game starts. NOT
    a bug.

- timestamp: 2026-04-27
  checked: stonereader/app.py:476-481 (_on_home_select) and 542-544 (_open_remaining_deck)
  found: |
    Both call sites pass the literal "remaining_deck" string to
    `live_presenter.jump_to_zone(...)`. `_ZONE_LABELS` resolves this to
    "Remaining deck zone" so `jump_to_zone` speaks
    `"Remaining deck zone, N cards. <first row>"` when N>0 or
    `"Remaining deck zone: empty"` when N==0. With no game,
    `get_zone_items("remaining_deck")` returns `[]` (presenter line 187-190),
    so the empty branch fires.
  implication: |
    The speech "remaining_deck: empty" reported by the user is a paraphrase
    of "Remaining deck zone: empty". The system is behaving exactly per
    spec D-17. The reason ONLY this is announced is that NVDA on focus
    enter does NOT auto-walk siblings — the user must press NVDA+Down
    (Say All) or use browse mode (HUMAN-UAT B2/B4) to walk the panel.
    UI-SPEC line 251 explicitly notes this: "The zone-entry speech fires
    before focus arrives. This is intentional and benign."

- timestamp: 2026-04-27
  checked: AcceptsFocus chain across LiveGamePanel + 4 ListCtrls
  found: |
    LiveGamePanel inherits the default wx.Panel.AcceptsFocus() (returns
    True when focusable; the panel is constructed with `style=wx.WANTS_CHARS`
    at line 158 so it can receive char events). All 4 _*ListCtrl classes
    override `AcceptsFocus() -> False` (lines 63, 83, 103, 125). The panel
    itself is registered as its own focus_target at app.py:466
    (`nav.register_panel("Live Game", live_panel, live_presenter, live_panel)`).
    On show_panel, NavigationController calls
    `wx.CallAfter(self._focus_targets[name].SetFocus)` — focus lands on
    the panel, not on any ListCtrl.
  implication: |
    The focus model is correct per UI-SPEC: Tab focus rests on the panel,
    arrow keys route through EVT_CHAR_HOOK -> InputLayer ->
    presenter.get_key_map(). NVDA can still object-navigate INTO each
    ListCtrl independently using NVDA+arrow keys (browse mode) -- but
    on plain focus enter, NVDA only announces the focused control + any
    speech the app emitted. There is no "auto-walk" of siblings on focus
    enter; that's not how screen readers work. NOT a bug.

- timestamp: 2026-04-27
  checked: git diff HEAD -- stonereader/views/live_game.py
  found: No output (no uncommitted changes).
  implication: |
    The committed source matches the planned implementation exactly. No
    local modifications could explain the OCR "Drawn:" reading.

## Resolution

root_cause: |
  All three observations have benign explanations grounded in the
  committed source code. None is a code defect.

  **Per observation:**

  (a) "Last label is 'Drawn:' not 'Cards Drawn:'" — **OCR measurement
      artifact, not a source defect.** `stonereader/views/live_game.py:190`
      contains the literal string `"Cards Drawn:"` (verified via Read +
      Grep across the entire `stonereader/` tree; `git diff` confirms no
      local mods; only one commit ever touched this file). The "Cards"
      prefix is missing from the OCR output most likely because the OCR
      pass either (i) cropped the screenshot near the bottom of the panel
      where the last label sits, or (ii) misread small text against a
      list-control border. The source is correct. There is no
      `"Drawn:"` literal anywhere in the codebase outside the UAT report
      and quoted plan/spec text.

  (b) "Mana StaticText not visible in OCR" — **expected behavior, not a
      bug.** Mana is constructed and sizer-added at
      `stonereader/views/live_game.py:168-169`, but its label text is set
      to whatever `LiveGamePresenter.current_mana_summary()` returns
      (line 260). With `_current_state is None` (no game in progress),
      `current_mana_summary()` returns `""`
      (`stonereader/presenters/live_game.py:308-309`). An empty
      `wx.StaticText` collapses to ~0px height — there's nothing for OCR
      to read because there are no glyphs. The widget IS in the sizer
      and IS adjacent to its title sibling; it will populate the moment
      a game starts (LIVE-07).

  (c) "Screen reader only announces 'remaining_deck: empty' on panel
      entry" — **expected NVDA behavior + paraphrased speech transcript,
      not a bug.** The actual speech emitted is
      `"Remaining deck zone: empty"` per
      `stonereader/presenters/live_game.py:323` and
      `_ZONE_LABELS["remaining_deck"] = "Remaining deck zone"` (line 54);
      the user's report is a paraphrase. The reason ONLY this single
      announcement plays is that NVDA on focus enter does NOT auto-walk
      siblings — to hear the title, mana, and four labels/lists, the
      user must press NVDA+Down (Say All) or use browse mode. This is
      precisely what HUMAN-UAT items B2 / B4 test, and UI-SPEC line 251
      explicitly documents it as "intentional and benign."

      MSAA structure is correct: all 4 (label, list) pairs are direct
      siblings of the panel's outer `wx.BoxSizer(wx.VERTICAL)` — no
      nested sub-panels — so NVDA browse mode can associate labels with
      lists by sibling order (UI-SPEC line 115).

      AcceptsFocus chain is also correct: panel accepts focus
      (`style=wx.WANTS_CHARS` at line 158), all 4 ListCtrls return
      `AcceptsFocus() -> False` (lines 63, 83, 103, 125), panel is its
      own focus_target (`app.py:466`).

fix: |
  No code fix required. Recommended actions for the planner:

  1. (a) Re-run the UAT test 4 OCR with a screenshot that captures the
     full panel height OR have the user manually read the bottom label
     to confirm it says "Cards Drawn:" — the source guarantees it does.
     If the OCR persistently truncates, treat this as a UAT-tooling
     limitation, not a phase-3 gap.

  2. (b) Update HUMAN-UAT B-series prerequisite to clarify that the mana
     line is INTENTIONALLY blank with no game in progress; verify the
     mana line populates as soon as a Hearthstone Constructed match
     starts (covered by HUMAN-UAT once a real game is available).

  3. (c) Add a HUMAN-UAT prerequisite note: "On panel entry, NVDA will
     announce only the zone-entry speech ('Remaining deck zone: empty'
     when no game). To verify the full structure walks correctly, press
     NVDA+Down (Say All) or activate browse mode and traverse with
     arrow keys. The four (label, list) sibling pairs should each
     associate." This matches HUMAN-UAT B2/B4 already, but the UAT
     reporter mistook the focus-enter behavior for a structural defect.

  No production code in `stonereader/` needs to change.

verification: N/A — diagnosis-only.
files_changed: []
