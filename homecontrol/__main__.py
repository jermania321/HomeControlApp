"""Run the HomeControl desktop application with ``python -m homecontrol``."""

import os
import traceback
from pathlib import Path


def main():
    try:
        from .gui import main as gui_main
        gui_main()
    except BaseException:
        log = Path(os.environ.get("APPDATA", Path.home())) / "HomeControlApp" / "app.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as stream:
                traceback.print_exc(file=stream)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
