# Phase 1: Deck Management - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 01-deck-management
**Areas discussed:** Import workflow, Deck list display, Deck contents zones, Delete and export, App shell navigation

---

## Import Workflow

| Option | Description | Selected |
|--------|-------------|----------|
| Inside Deck Manager panel | Deckstring and name fields always visible above the deck list | |
| Separate "Import Deck" action | Main menu has dedicated import screen, returns to deck list after | ✓ |
| You decide / research it | Let researcher figure out best pattern | |

**User's choice:** Separate "Import Deck" action, plus clipboard auto-detection
**Notes:** User wants Hearthstone-style clipboard paste: when app gains focus, detect deckstring on clipboard, pop dialog to import, clear clipboard after. This was a user-initiated addition beyond the presented options.

### Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Speak error inline | Announce error through speech, keep focus in field | |
| Error dialog | wx.MessageBox with error message | ✓ |
| You decide | Claude picks | |

**User's choice:** Error dialog (wx.MessageBox)
**Notes:** Screen readers auto-read dialog content.

---

## Deck List Display

### Speech Format

| Option | Description | Selected |
|--------|-------------|----------|
| Name + class | "Aggro Paladin, Paladin, 1 of 5" | |
| Name + class + format | "Aggro Paladin, Paladin, Standard, 1 of 5" | ✓ |
| Name only | "Aggro Paladin, 1 of 5" | |

**User's choice:** Name + class + format
**Notes:** Format (Standard/Wild) matters for users who play both.

### Sort Order

| Option | Description | Selected |
|--------|-------------|----------|
| Most recently added first | Newest at top, uses created_at column | ✓ |
| Alphabetical by name | A-Z by deck name | |
| By class, then name | Grouped by hero class | |

**User's choice:** Most recently added first
**Notes:** None.

---

## Deck Contents Zones

### Zone Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Summary + card list | Two zones: singleton summary and navigable card list | |
| Card list only | Just the card list, metadata available elsewhere | ✓ |
| You decide | Claude picks based on ZoneNavigationMixin patterns | |

**User's choice:** Card list only
**Notes:** Simpler approach — no summary zone.

### Enter/Exit Navigation

| Option | Description | Selected |
|--------|-------------|----------|
| Enter on deck, Escape to go back | Enter opens contents, Escape returns to list, cursor preserved | ✓ |
| Hotkey toggles between list and contents | Specific key switches between list and contents views | |
| You decide | Claude picks | |

**User's choice:** Enter on deck, Escape to go back
**Notes:** Cursor position in deck list preserved across enter/exit.

---

## Delete and Export

### Delete Confirmation

| Option | Description | Selected |
|--------|-------------|----------|
| wx.MessageDialog | Standard Yes/No dialog, screen readers auto-read | ✓ |
| Inline speech confirmation | Double-press to confirm, no dialog | |
| You decide | Claude picks best for screen readers | |

**User's choice:** wx.MessageDialog with Yes/No
**Notes:** After deletion, cursor moves to next deck (or previous if last). Speak "Deck Name deleted."

### Export Feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Speech announcement | "Deckstring copied to clipboard" via screen reader | ✓ |
| MessageBox confirmation | Dialog requiring OK press | |
| You decide | Claude picks | |

**User's choice:** Speech announcement
**Notes:** No dialog to dismiss — simple and fast.

---

## App Shell Navigation (User-Initiated)

The user raised this topic during the Import workflow discussion, requesting migration away from wx.Notebook.

### Menu Pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Menu always visible | Buttons stay at top/side, panel fills rest | |
| Menu is a home screen | Home screen with buttons, panel replaces it entirely | ✓ |
| You decide / research | Researcher investigates best pattern | |

**User's choice:** Menu is a home screen
**Notes:** Like Hearthstone's main menu. Full-window panels when a feature is selected.

### Feature Switching

| Option | Description | Selected |
|--------|-------------|----------|
| Hotkeys per feature | Ctrl+1, Ctrl+2, etc. from anywhere | |
| Always go through menu | Escape to home, then pick next feature | ✓ |
| You decide / research | Researcher determines best approach | |

**User's choice:** Always go through menu
**Notes:** Simple mental model. User also specified Backspace should navigate back up the chain in addition to Escape.

---

## Claude's Discretion

- Specific hotkey assignments for delete, export, and import
- Layout details of import screen
- How home screen buttons are announced to screen readers
- Whether to announce deck metadata when entering card list

## Deferred Ideas

None — discussion stayed within phase scope.
