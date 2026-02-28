from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from r6_navigator.db.database import get_engine, get_session_factory, init_db
from r6_navigator.ui.qt.app import R6NavigatorApp

_DB_PATH = Path(__file__).parent.parent / "r6_navigator.db"


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("R6 Navigator")

    engine = get_engine(_DB_PATH)
    init_db(engine, seed_capacities=True)
    session_factory = get_session_factory(engine)

    window = R6NavigatorApp(session_factory, db_path=_DB_PATH)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
