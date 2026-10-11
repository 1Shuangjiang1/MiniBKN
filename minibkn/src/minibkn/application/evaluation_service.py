"""Read machine-readable benchmark reports without inventing missing metrics."""

import json
from pathlib import Path
from typing import Any

from minibkn.api.errors import MiniBKNError


class EvaluationReportService:
    def __init__(self, results_dir: Path) -> None:
        self._results_dir = results_dir

    def latest(self) -> dict[str, Any]:
        path = self._results_dir / "latest.json"
        if not path.is_file():
            raise MiniBKNError(
                error_code="EVALUATION_NOT_AVAILABLE",
                message="No completed evaluation report is available",
                status_code=404,
            )
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise MiniBKNError(
                error_code="INVALID_EVALUATION_REPORT",
                message="The latest evaluation report is not a JSON object",
                status_code=500,
            )
        return value
