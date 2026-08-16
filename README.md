# StoneReader - AN Accessible Hearthstone Replay Viewer

## Purpose

StoneReader offers an accessible way to view cards, deckstrings, and Hearthstone replays in a simple WX GUI.

## Key Features

- Search for cards by name or card id, or by reviewing cards grouped by set.
- Given a deckstring, return an accessible view of the deck's contents.
- Given a Hearthstone replay log or file, return an accessible view of the game including cards played, a view of each player's hand after each turn, and other relevant information.

## Audio integration smoke test

The real-install audio extraction smoke test is excluded from the default test
run. On a Windows machine with Hearthstone installed, run it explicitly with:

```powershell
uv run pytest -q -m slow_audio tests/test_services/test_audio_integration.py
```
