"""Opt-in live smoke test for local DeepSeek and SiliconFlow credentials."""

import argparse
import asyncio
import json
from pathlib import Path

from minibkn.adapters.bkn_lang import BknLangParser
from minibkn.adapters.llm import OpenAICompatibleQueryPlanner
from minibkn.adapters.search import SiliconFlowEmbedder

PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def verify(args: argparse.Namespace) -> dict[str, object]:
    deepseek_key = args.deepseek_key_file.read_text(encoding="utf-8-sig").strip()
    siliconflow_key = args.siliconflow_key_file.read_text(encoding="utf-8-sig").strip()
    network = BknLangParser().parse_directory(PROJECT_ROOT / "examples" / "crm" / "bkn")
    planner = OpenAICompatibleQueryPlanner(
        "https://api.deepseek.com/v1", deepseek_key, "deepseek-chat"
    )
    clear = await planner.analyze("统计已付款订单的总金额", network)
    ambiguous = await planner.analyze("最近的大客户怎么样", network)
    embedder = SiliconFlowEmbedder(
        api_key=siliconflow_key,
        model="BAAI/bge-m3",
        dimensions=1024,
    )
    vectors = await asyncio.to_thread(embedder.embed_many, ["企业客户", "已付款订单"])
    return {
        "deepseek": {
            "clear_status": clear.status,
            "clear_intent": clear.plan.intent if clear.plan else None,
            "clear_plan": clear.plan.model_dump(mode="json") if clear.plan else None,
            "ambiguous_status": ambiguous.status,
            "ambiguity_ids": [item.id for item in ambiguous.ambiguities],
        },
        "siliconflow": {
            "vectors": len(vectors),
            "dimensions": len(vectors[0]) if vectors else 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deepseek-key-file", type=Path, required=True)
    parser.add_argument("--siliconflow-key-file", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(verify(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
