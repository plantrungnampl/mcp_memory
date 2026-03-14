from __future__ import annotations

import sys

from viberecall_mcp.deployed_smoke import SmokeFailure, main


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
