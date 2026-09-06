# Open issue review, 2026-09-06

Reviewed the three open issues against `main` at `2c69cd7` and the local card
library changes. GitHub's `main` matched that commit at review time. This
review did not change GitHub issues or publish comments.

| Issue | Finding | Recommendation |
| --- | --- | --- |
| [#7, local replays](https://github.com/akj/stonereader/issues/7) | The replay feature has merged. Its final comment still says the branch is local and pending merge. | Close the feature umbrella. Two documentation requests remain, listed below. |
| [#8, card library keymap](https://github.com/akj/stonereader/issues/8) | Class cycling, mana toggles, search, and paging already existed. The class menu was absent, sorting was alphabetical, and filter changes did not reset the cursor. | Keep open until the local changes land and Andrew checks the keyboard and speech experience. |
| [#37, dependency dashboard](https://github.com/akj/stonereader/issues/37) | This is Renovate's ongoing dashboard. Its open setuptools update fails CI. | Keep open. Resolve the HSReplay dependency before accepting the setuptools update. |

## Replay umbrella

Commit `55b7a75` merged the replay implementation through PR #16. All seven
constituent issues, #9 through #15, are closed. The current app wires the
recorder, managed replay storage, import, Replays, and Replay Viewer.

The tests exercise completed and abandoned games, concessions, duplicate
checksums, save failures, import failures, deletion, and newest-first history.
`tests/test_replay_e2e.py` feeds captured Power.log lines through the real
recorder, writes XML and metadata to temporary storage, reloads the file, and
builds replay turn data. Surface tests separately exercise keyboard dispatch,
zone inspection, queries, and event scrubbing with captured speech output.
These are automated integration and Surface checks, not a fresh live
Hearthstone recording or an NVDA listening pass.

The issue's original behavior is no longer the entire current contract.
ADR-0012 adds statistics membership and retention. ADR-0015 and commit
`2a1fe4c` start turns at the first event and add F5/F6 event stepping. The
recorder also preserves an unknown result when neither side's result can be
resolved, covered by a regression test, instead of inventing a win or loss.
Those differences should not be treated as missing replay implementation.

Two documentation requests in #7 remain literal gaps. There is no dedicated
ADR declaring HSReplay XML the canonical stored format, and CONTEXT.md still
says "StoneReader-saved game record" without naming that format. Neither is
a missing user flow.

## Card library and decks

The local changes make Home → Cards a vertical class menu. Classes appear
alphabetically, followed by Neutral and All cards. Enter opens Card Browser;
Escape or Backspace returns to the menu at its previous position.

Cards sort by printed mana cost ascending, then case-insensitive name, then
DBF ID for stable ordering of different printings. Tab and Shift+Tab use the
same order as the menu. Mana filters and search persist across class changes.
Selecting a class, changing a mana filter, or committing a search resets the
card and detail cursors and refreshes the rendered results. Cancelling search
keeps the selected card. The existing exact-cost digits and 9-plus bucket
remain in place.

Saved deck contents use the same sort key while preserving counts and the
stored deck code. Live Remaining Deck already sorted by cost and name and
now shares that key. Replay deck contents now sort too, with hidden entries
last. Hands, boards, and played/drawn history retain their existing order.

ADR-0006 and the UI spec now describe the class menu. Generated command help
includes both Cards and Card Browser. The old #8 references to presenters,
`CATEGORY_TO_FILTER`, and a status zone refer to the retired UI architecture.

## Deck viewer references

- [Hearthstone Deck Viewer source](https://github.com/oliverfei/HearthstoneDeckViewer/blob/master/scripts/scripts.js) explicitly sorts by cost, then `localeCompare` on card names. Rows contain cost, name, and copy count.
- [HSGuru's indexed deck lists](https://staging.hsguru.com/) show ascending mana cost and alphabetical names within a cost. Direct requests returned HTTP 403, so this is indexed-page evidence, not an interactive check.
- [HSReplay's published deck lists](https://articles.hsreplay.net/2018/03/02/the-heroes-of-the-brawl/) show ascending mana cost and copy counts. These older exports do not establish a current alphabetical tie-break rule. The current interactive deck viewer was blocked by a browser challenge.
- [Hearthstone Access commands](https://hearthstoneaccess.com/commands.html) remain the keyboard reference. StoneReader's existing 0 through 9 mana filters deliberately extend HSA's 0 through 7 contract.

Browser automation reported that no browser was available. Native screen-reader
validation remains outstanding.

## Dependency dashboard

[PR #36](https://github.com/akj/stonereader/pull/36) changes setuptools from
`>=80.9.0,<81` to `>=84,<85`. Its build job passed, but the
[checks job](https://github.com/akj/stonereader/actions/runs/31992230995/job/95277693371)
failed during test collection with `ModuleNotFoundError: No module named
'pkg_resources'`. The traceback enters HSReplay's import. This verifies why
the current pin cannot be removed as an ordinary dependency refresh.

## Verification

The complete default test suite passes, including real card-database ordering,
menu navigation through the input dispatcher, filter resets, saved deck-code
preservation, and replay deck sorting with hidden entries. Ruff and pyright
pass. The real-install audio test stays excluded by the repository's default
pytest configuration.
