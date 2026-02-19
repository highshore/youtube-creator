from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.system import check_media_dependencies


def main() -> int:
    report = check_media_dependencies()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["overall"] in {"ok", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
