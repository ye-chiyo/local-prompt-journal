from __future__ import annotations

import sys
from pathlib import Path

repository = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repository))

from prompt_journal.__main__ import main


raise SystemExit(main([*sys.argv[1:], "monitor"]))
