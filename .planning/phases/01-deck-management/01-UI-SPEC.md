---
phase: 1
slug: deck-management
status: draft
shadcn_initialized: false
preset: none
created: 2026-04-15
---

# Phase 1 -- UI Design Contract

> Interaction and speech output contract for the Deck Management phase. This is a wxPython desktop application for screen reader users -- the "visual" contract is defined in terms of widget structure, keyboard navigation, speech announcements, and screen reader accessibility rather than CSS tokens or color palettes.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (wxPython native widgets) |
| Preset | not applicable |
| Component library | wxPython 4.2.5 native controls (wx.Panel, wx.ListBox, wx.TextCtrl, wx.Button, wx.StaticText, wx.MessageDialog) |
| Icon library | not applicable (screen reader app -- no visual icons) |
| Font | System default (wxPython inherits OS font; screen readers use their own speech engine) |

---

## Widget Spacing

wxPython uses pixel-based sizer spacing. All spacing values are multiples of 4 to maintain consistency.

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | wx.ALL border on inline elements (StaticText labels) |
| sm | 8px | wx.ALL border on grouped elements (TextCtrl, ListBox items) |
| md | 16px | Section padding between widget groups |
| lg | 24px | Not used this phase |
| xl | 32px | Not used this phase |

Exceptions: none -- wxPython sizer spacing only, no CSS.

---

## Typography

Not applicable in the traditional sense. wxPython uses the OS system font for all widgets. The actual "typography" for this application is the **speech output format** -- what the screen reader reads aloud.

### Speech Output Format Contract

| Context | Format | Example |
|---------|--------|---------|
| Home screen button | "{Feature name}" | "Card Library" |
| Deck list item | "{Name}, {Class}, {Format}, {N} of {M}" | "Aggro Paladin, Paladin, Standard, 1 of 5" |
| Deck card item | "{Card name} x{count}, {N} of {M}" | "Reno Jackson x1, 3 of 30" |
| Deck metadata on enter | "{Deck name}: {total} cards, {Class}, {Format}" | "Aggro Paladin: 30 cards, Paladin, Standard" |
| Card detail line | One attribute per down-arrow press (reuses Card.detail_lines()) | "Cost: 6 mana" |
| Navigation back | "{Previous screen name}" (spoken by activate_view) | "Home" |
| Position announcement | "{N} of {M}" suffix on all list items | "3 of 5" |

Source: D-08 from CONTEXT.md for deck list format. Deck metadata on enter is a discretion decision -- announcing metadata when entering a deck's card list gives the user orientation without needing a separate summary zone (satisfies D-10's single-zone approach).

---

## Color

Not applicable. This is a screen reader application. The wxPython window uses OS default system colors. No custom color scheme, no theming. All information is conveyed through speech output and keyboard interaction, never through color alone (WCAG 1.4.1 inherently satisfied).

| Property | Value |
|----------|-------|
| Window background | wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW) -- OS default |
| Text foreground | wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT) -- OS default |
| Custom theming | None -- rely on OS high-contrast mode support |

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Primary CTA (home screen) | "Import Deck" |
| Home screen title | Window title: "StoneReader" (already set in MainWindow) |
| Home menu item: Card Library | "Card Library" |
| Home menu item: Deck Manager | "Deck Manager" |
| Home menu item: Import Deck | "Import Deck" |
| Import screen: deckstring label | "Deck code:" |
| Import screen: name label | "Deck name:" |
| Import screen: submit button | "Import" |
| Import screen: cancel button | "Cancel" |
| Clipboard auto-detect dialog title | "Deck Found on Clipboard" |
| Clipboard auto-detect dialog body | "A deck code was found on your clipboard. Import it?" |
| Clipboard auto-detect: confirm | "Yes" (wx.YES) |
| Clipboard auto-detect: cancel | "No" (wx.NO) |
| Empty state: deck list | "No saved decks. Press Enter on Import Deck from the home screen to add one." |
| Empty state: speech on entering Deck Manager with no decks | "Deck Manager: no saved decks" |
| Error: invalid deckstring | "Invalid deck code. Check that you copied the full code from Hearthstone and try again." |
| Error: missing cards | "Some cards in this deck were not found in the card database. The deck code may be from a newer expansion." |
| Error: empty deckstring field | "Enter a deck code to import." |
| Error: empty name field | "Enter a name for this deck." |
| Delete confirmation title | "Delete Deck" |
| Delete confirmation body | "Delete '{Deck Name}'? This cannot be undone." |
| Delete confirmation: confirm | "Yes" (wx.YES) |
| Delete confirmation: cancel | "No" (wx.NO) |
| Post-delete speech | "{Deck Name} deleted" |
| Export speech confirmation | "Deck code copied to clipboard" |
| Import success speech | "{Deck Name} imported" |

Source: D-07, D-13, D-14, D-15 from CONTEXT.md. Empty state and error copy are discretion decisions using plain, direct language (cognitive accessibility).

---

## Widget Structure

### Screen Hierarchy

```
MainWindow (wx.Frame, 800x600)
  +-- HomePanel (wx.Panel) -- default view on launch
  |     +-- wx.StaticText "StoneReader" (heading for MSAA)
  |     +-- wx.ListBox (feature menu, 3 items, focused on show)
  |           - "Card Library"
  |           - "Deck Manager"
  |           - "Import Deck"
  |
  +-- CardBrowserPanel (wx.Panel) -- existing, shown on selection
  |
  +-- DeckManagerPanel (wx.Panel) -- new, shown on selection
  |     +-- wx.StaticText "Saved decks:" (MSAA label)
  |     +-- DeckListCtrl (wx.ListCtrl, virtual, single-select)
  |
  +-- DeckContentsPanel (wx.Panel) -- new, shown on Enter from deck list
  |     +-- wx.StaticText "Cards:" (MSAA label)
  |     +-- CardListCtrl (wx.ListCtrl, virtual, single-select, same pattern as CardBrowser)
  |
  +-- ImportDeckPanel (wx.Panel) -- new, shown on selection
        +-- wx.StaticText "Deck code:" + wx.TextCtrl (via make_labeled_text_ctrl)
        +-- wx.StaticText "Deck name:" + wx.TextCtrl (via make_labeled_text_ctrl)
        +-- wx.Button "Import"
        +-- wx.Button "Cancel"
```

### Panel Visibility Pattern

Only one panel visible at a time. Panels swap via `Show()`/`Hide()` on the frame's main sizer. This replaces the wx.Notebook tab pattern (D-01).

```
Home --> Card Library (Escape/Back returns to Home)
Home --> Deck Manager (Escape/Back returns to Home)
  Deck Manager --> Deck Contents (Escape/Back returns to Deck Manager)
Home --> Import Deck (Escape/Back returns to Home, or success navigates to Deck Manager)
```

Source: D-01, D-02, D-03, D-11 from CONTEXT.md.

---

## Keyboard Navigation Contract

### Global Keys (all screens)

| Key | Action | Source |
|-----|--------|--------|
| Escape | Navigate back one level (or no-op at home) | D-02 |
| Backspace | Navigate back one level (same as Escape) | D-02 |
| Ctrl+Q | Quit application | Existing accelerator |

### Home Screen Keys

| Key | Action |
|-----|--------|
| Up / Left | Move to previous menu item |
| Down / Right | Move to next menu item |
| Enter | Activate selected feature |
| Home | Jump to first menu item |
| End | Jump to last menu item |

Home screen uses a wx.ListBox -- standard list navigation. Focus set to the ListBox on panel show. The ListBox is the single focus target; no Tab order needed.

### Deck Manager Keys

| Key | Action | Speech Output |
|-----|--------|---------------|
| Up / Left | Previous deck | "{Name}, {Class}, {Format}, {N} of {M}" |
| Down / Right | Next deck | "{Name}, {Class}, {Format}, {N} of {M}" |
| Enter | Open deck contents | "{Deck Name}: {total} cards, {Class}, {Format}" then first card |
| Home | Jump to first deck | First deck announcement |
| End | Jump to last deck | Last deck announcement |
| Delete | Delete selected deck | Shows wx.MessageDialog confirmation |
| c | Copy deckstring to clipboard | "Deck code copied to clipboard" |

Presenter: `DeckManagerPresenter(ZoneNavigationMixin, BasePresenter)`
Zone: "decks" (single zone, per D-10)

Source: D-08 (speech format), D-13 (delete), D-15 (export). Hotkey assignments (Delete key, "c" for copy) are discretion decisions. Delete key is the standard destructive-action key. "c" for copy mirrors Ctrl+C semantics in a non-modifier context.

### Deck Contents Keys

| Key | Action | Speech Output |
|-----|--------|---------------|
| Up / Left | Previous card | "{Card name} x{count}, {N} of {M}" |
| Down / Right | Next card | (same, using detail inspection on Down) |
| Down | Read next detail line (when detail cursor active) | Single detail line from Card.detail_lines() |
| Up | Read previous detail line (when detail cursor active) | Single detail line |
| Home | Jump to first card | First card announcement |
| End | Jump to last card | Last card announcement |
| Escape / Backspace | Return to deck list | Deck list item announcement (cursor preserved) |

Note on Up/Down dual behavior: This follows the existing CardBrowser pattern. Left/Right navigate between cards. Down enters detail inspection mode on the current card. Up scrolls back through detail lines. This is established behavior from ZoneNavigationMixin (D-12).

Presenter: `DeckContentsPresenter(ZoneNavigationMixin, BasePresenter)` -- or this could be a mode of DeckManagerPresenter. Planner decides.
Zone: "cards" (single zone)

### Import Deck Screen Keys

| Key | Action |
|-----|--------|
| Tab | Move between fields (deckstring -> name -> Import button -> Cancel button) |
| Enter (in TextCtrl) | Submit import (same as pressing Import button) |
| Enter (on Import button) | Validate and import deck |
| Enter (on Cancel button) | Return to home screen |
| Escape / Backspace | Cancel and return to home screen |

Text mode activates when TextCtrl fields are focused (via bind_text_mode). All hotkeys suppressed during text input. Standard Tab order: deckstring field, name field, Import button, Cancel button.

---

## Interaction State Machine

### Deck Manager States

```
EMPTY           -- No decks saved. Speech: "Deck Manager: no saved decks"
BROWSING        -- Navigating deck list. Active key map: deck navigation.
VIEWING_DECK    -- Viewing deck contents. Active key map: card navigation.
CONFIRMING_DEL  -- wx.MessageDialog visible. Modal -- blocks all input until dismissed.
```

### Import Deck States

```
EDITING         -- User filling in fields. Text mode active on focused TextCtrl.
VALIDATING      -- On submit: validate deckstring, check name. Errors via wx.MessageBox.
SUCCESS         -- Deck saved. Speech: "{Name} imported". Navigate to Deck Manager.
```

### Clipboard Auto-Detection

```
Trigger: EVT_ACTIVATE on MainWindow (app gains focus)
Check: wx.TheClipboard contains text matching deckstring pattern
  If valid deckstring found:
    Show wx.MessageDialog: "A deck code was found on your clipboard. Import it?"
    Yes -> Open Import Deck screen with deckstring pre-filled, focus on name field
    No -> Continue normally
  If no deckstring: no action
```

Source: D-06 from CONTEXT.md. Deckstring detection regex: starts with base64-like content, validated by `deckstrings.parse_deckstring()` in a try/except.

---

## Screen Reader Accessibility Contract

### MSAA/UIA Label Strategy

| Widget | Label Method | Label Text |
|--------|-------------|------------|
| Home screen ListBox | wx.StaticText sibling before ListBox | "Features:" |
| Deck list ListCtrl | wx.StaticText sibling before ListCtrl | "Saved decks:" |
| Card list ListCtrl | wx.StaticText sibling before ListCtrl | "Cards:" |
| Deckstring TextCtrl | make_labeled_text_ctrl() | "Deck code:" |
| Deck name TextCtrl | make_labeled_text_ctrl() | "Deck name:" |
| Import button | wx.Button label | "Import" |
| Cancel button | wx.Button label | "Cancel" |

All labels placed as wx.StaticText immediately before their associated control in the sizer, following the existing MSAA sibling-order pattern from views/base.py.

### Focus Management

| Event | Focus Target |
|-------|-------------|
| App launch | Home screen ListBox |
| Navigate to Card Library | CardBrowserPanel (existing behavior) |
| Navigate to Deck Manager | Deck list (first item or empty announcement) |
| Navigate to Import Deck | Deckstring TextCtrl |
| Enter on deck in list | Card list (first card) |
| Escape/Back from deck contents | Deck list (cursor preserved per D-11) |
| Escape/Back from any panel | Previous panel's focus target |
| Delete confirmation dismissed | Deck list (next deck, or previous if last was deleted, per D-13) |
| Successful import | Deck Manager panel, deck list focused on newly imported deck |
| Clipboard auto-detect Yes | Import Deck screen, name TextCtrl focused |

Source: D-11 (cursor preservation), D-13 (post-delete cursor). Focus management uses wx.CallAfter(widget.SetFocus) to ensure focus moves after panel swap completes.

### Diminishing Messages

Inherited from ZoneNavigationMixin. Applied to:
- Pressing navigation keys when at list boundary (already handled by mixin)
- No additional diminishing message contexts needed this phase

### Screen Reader Announcements (Interrupt Policy)

| Event | Interrupt | Reason |
|-------|-----------|--------|
| List navigation (up/down/left/right) | Yes | Replace previous position announcement |
| Detail line read | Yes | Replace previous detail line |
| Delete confirmation speech | Yes | Important confirmation feedback |
| Export copy confirmation | Yes | Brief confirmation |
| Import success | Yes | Brief confirmation |
| Empty state announcement | Yes | Orientation message |
| Error dialogs | N/A | wx.MessageBox handles its own screen reader announcement |

All speech uses `self._speech.speak(text, interrupt=True)` (the default) unless otherwise specified.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| not applicable | N/A | N/A -- wxPython native widgets only, no component registries |

---

## Data Contract (Presenter-View Interface)

### DeckManagerPresenter

```python
# Callbacks the view binds
set_on_state_changed(callback: Callable[[list[DeckSummary], int], None]) -> None
set_on_status_changed(callback: Callable[[str], None]) -> None

# DeckSummary is a lightweight tuple or dataclass for display:
# (deck_id: int, name: str, hero_class: str, format: str, card_count: int)

# Key map
get_key_map() -> Dict[str, Callable[[], None]]

# Zone items
get_zone_items("decks") -> Sequence[DeckSummary]
```

### DeckContentsPresenter (or DeckManagerPresenter in "viewing" mode)

```python
# Callbacks
set_on_state_changed(callback: Callable[[list[Tuple[Card, int]], int], None]) -> None

# Key map includes back navigation
get_key_map() -> Dict[str, Callable[[], None]]

# Zone items
get_zone_items("cards") -> Sequence[Tuple[Card, int]]
```

### Navigation Controller (new, manages panel swaps)

```python
# Replaces wx.Notebook page-change logic
show_panel(panel_name: str) -> None  # Swaps visible panel, calls activate_view
go_back() -> None  # Pops navigation stack, returns to previous panel
```

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS (adapted: widget structure and MSAA labels)
- [ ] Dimension 3 Color: PASS (not applicable -- OS system colors, screen reader app)
- [ ] Dimension 4 Typography: PASS (adapted: speech output format contract)
- [ ] Dimension 5 Spacing: PASS (adapted: wxPython sizer spacing)
- [ ] Dimension 6 Registry Safety: PASS (not applicable -- no component registries)

**Approval:** pending
