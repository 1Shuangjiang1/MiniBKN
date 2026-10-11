# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Deterministic, domain-neutral answer generation from normalized evidence."""

from minibkn.domain.evidence import EvidenceItem, EvidenceKind


class EvidenceAnswerGenerator:
    """Build a readable fallback answer without assuming any business domain."""

    def generate(self, evidence: list[EvidenceItem]) -> str:
        instances = [item for item in evidence if item.kind == EvidenceKind.INSTANCE]
        relations = [item for item in evidence if item.kind == EvidenceKind.RELATION]
        computed = [item for item in evidence if item.kind == EvidenceKind.COMPUTED]
        if not instances:
            if computed:
                return "查询计划计算结果：" + "；".join(item.content for item in computed) + "。"
            return "当前索引中没有找到足够的实例证据来回答该问题。"

        summaries = [self._instance_summary(item) for item in instances[:8]]
        answer = "检索到的相关业务对象包括：" + "；".join(summaries) + "。"
        if relations:
            relation_text = "；".join(item.content for item in relations[:8])
            answer += " 相关业务关系：" + relation_text + "。"
        if computed:
            answer += " 计算结果：" + "；".join(item.content for item in computed) + "。"
        answer += "结果来自当前分层检索证据，请结合引用核验。"
        return answer

    @staticmethod
    def _instance_summary(item: EvidenceItem) -> str:
        properties = item.attributes.get("properties", {})
        details = "，".join(f"{key}={value}" for key, value in list(properties.items())[:6])
        identity = f"{item.entity_type}/{item.entity_id}"
        return f"{item.title}（{identity}{'：' + details if details else ''}）"
