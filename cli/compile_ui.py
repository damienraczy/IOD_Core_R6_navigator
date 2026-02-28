"""Compile all Qt Designer .ui files to Python modules using pyside6-uic.

Run after editing any .ui file in Qt Designer:
    python cli/compile_ui.py
"""

import subprocess
import sys
from pathlib import Path

FORMS_DIR = Path(__file__).parent.parent / "r6_navigator" / "ui" / "qt" / "forms"


def main() -> None:
    ui_files = sorted(FORMS_DIR.glob("*.ui"))
    if not ui_files:
        print("No .ui files found.")
        return

    errors = []
    for ui_file in ui_files:
        output = FORMS_DIR / f"ui_{ui_file.stem}.py"
        result = subprocess.run(
            ["pyside6-uic", str(ui_file), "-o", str(output)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  OK  {ui_file.name} → {output.name}")
        else:
            print(f"  FAIL {ui_file.name}: {result.stderr.strip()}")
            errors.append(ui_file.name)

    if errors:
        print(f"\n{len(errors)} error(s). Fix the .ui files above.")
        sys.exit(1)
    else:
        print(f"\n{len(ui_files)} file(s) compiled successfully.")


if __name__ == "__main__":
    main()
