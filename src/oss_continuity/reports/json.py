from __future__ import annotations

import json as _json

from ..model import Report


def render_json(report: Report) -> str:
    return _json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n"
