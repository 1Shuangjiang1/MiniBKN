"""Load a bundled example into a running local MiniBKN server via its public API."""

import argparse
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def load_example(base_url: str, example: str, api_key: str = "") -> dict[str, object]:
    """Stop on errors; never silently replace an existing network or source."""
    folder = ROOT / "examples" / example
    source_id = "supply_chain_files" if example == "supply_chain" else "crm_demo_files"
    headers = {"x-api-key": api_key} if api_key else {}
    with httpx.Client(base_url=base_url, headers=headers, timeout=120) as client:
        networks = client.get("/api/v1/networks")
        networks.raise_for_status()
        sources = client.get("/api/v1/sources")
        sources.raise_for_status()
        if any(item["id"] == example for item in networks.json()["entries"]) or any(
            item["id"] == source_id for item in sources.json()
        ):
            raise RuntimeError("Example network/source already exists; no demo import performed.")
        requests = [
            ("/api/v1/networks/import", {"path": str(folder / "bkn")}),
            (
                "/api/v1/sources",
                {
                    "id": source_id,
                    "name": f"{example} demo CSV",
                    "kind": "csv",
                    "path": str(folder / "data"),
                },
            ),
            (f"/api/v1/sources/{source_id}/discover", {}),
            (f"/api/v1/networks/{example}/builds", {}),
        ]
        result: dict[str, object] = {}
        for endpoint, body in requests:
            response = client.post(endpoint, json=body)
            if response.is_error:
                raise RuntimeError(
                    f"{endpoint}: HTTP {response.status_code}. "
                    "Inspect the server/Swagger for details. Earlier steps may have succeeded; "
                    "do not delete data or repeat imports blindly."
                )
            result[endpoint] = response.json()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", choices=["supply_chain", "crm"], default="supply_chain")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key-file", type=Path)
    args = parser.parse_args()
    key = args.api_key_file.read_text(encoding="utf-8-sig").strip() if args.api_key_file else ""
    print(json.dumps(load_example(args.base_url, args.example, key), ensure_ascii=True, indent=2))
