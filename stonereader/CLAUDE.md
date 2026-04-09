# stonereader/

## Files

| File                | What                                                  | When to read                                     |
| ------------------- | ----------------------------------------------------- | ------------------------------------------------ |
| `README.md`         | Architecture, design decisions, invariants            | Understanding why the code is structured this way |
| `speech_service.py` | SpeechService: accessible_output2 wrapper             | Modifying speech output, debugging screen reader |
| `input_layer.py`    | InputLayer: EVT_CHAR_HOOK key routing, text mode      | Changing key routing, debugging text mode         |
| `app.py`            | MainWindow, StoneReaderApp, Notebook shell            | Adding tabs, modifying app structure              |
| `__main__.py`       | App entry point                                       | Changing startup behavior                         |
| `db.py`             | SQLite connection, schema, migrations                 | Adding tables, changing persistence               |

## Subdirectories

| Directory     | What                                             | When to read                          |
| ------------- | ------------------------------------------------ | ------------------------------------- |
| `models/`     | Domain models: Card, Deck, GameState, etc.       | Changing data structures              |
| `presenters/` | Presenters: ZoneNavigationMixin, BasePresenter   | Implementing feature presenters       |
| `views/`      | View helpers: text mode binding, labeled widgets | Building feature panels               |
