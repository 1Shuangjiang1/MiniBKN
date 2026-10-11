import json
from pathlib import Path

import httpx
import pytest

from minibkn.config import Settings
from minibkn.main import create_app


@pytest.mark.asyncio
async def test_latest_evaluation_api_reads_only_completed_report(tmp_path: Path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    app = create_app(
        Settings(
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'db.sqlite').as_posix()}",
            data_dir=tmp_path / "runtime",
            evaluation_results_dir=results,
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            missing = await client.get("/api/v1/evaluations/latest")
            assert missing.status_code == 404
            assert missing.json()["error_code"] == "EVALUATION_NOT_AVAILABLE"

            report = {
                "report_version": "1.0",
                "dataset": {"name": "crm_200", "questions": 200},
                "ragas": {"faithfulness": None, "status": "skipped_no_llm"},
            }
            (results / "latest.json").write_text(
                json.dumps(report, ensure_ascii=False), encoding="utf-8"
            )
            response = await client.get("/api/v1/evaluations/latest")
            assert response.status_code == 200
            assert response.json() == report
