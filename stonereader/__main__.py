"""StoneReader entry point.

configure_logging() is called HERE — exactly once before StoneReaderApp() —
to satisfy Pitfall 10 (avoid duplicate handlers on the root logger). Do NOT
call configure_logging() inside app.py; the integration test in 02-07
asserts the call exists in __main__.py only.
"""

from stonereader.app import StoneReaderApp
from stonereader.services._logging_config import configure_logging


def main() -> None:
    configure_logging()
    app = StoneReaderApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
