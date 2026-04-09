"""StoneReader entry point."""

from stonereader.app import StoneReaderApp


def main() -> None:
    app = StoneReaderApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
