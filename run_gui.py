"""
Launch the NL2 Track Designer GUI.

Run with:   python run_gui.py
(requires PySide6:  pip install PySide6)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gui.main import main

if __name__ == "__main__":
    main()
