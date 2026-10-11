"""Human-gated AI-assisted modeling workflow."""

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from minibkn.api.errors import MiniBKNError, ResourceNotFoundError
from minibkn.application.schema_generation_service import SchemaGenerationService
from minibkn.domain.modeling import (
    ModelingSession,
    ModelingSessionStatus,
    ProposalKind,
    ProposalStatus,
    SchemaProposal,
)
from minibkn.domain.models import (
    ActionType,
    DataProperty,
    KnowledgeNetwork,
    ObjectType,
    RelationType,
    RiskType,
)
from minibkn.domain.policy import PolicyEvaluationError, PolicyEvaluator
from minibkn.ports.modeling import ModelingRepository
from minibkn.ports.repository import KnowledgeNetworkRepository


class ModelingService:
    def __init__(
        self,
        sessions: ModelingRepository,
        networks: KnowledgeNetworkRepository,
        schema: SchemaGenerationService,
    ) -> None:
        self._sessions = sessions
        self._networks = networks
        self._schema = schema
        self._policies = PolicyEvaluator()

    async def create(
        self,
        source_id: str,
        network_id: str,
        name: str,
        instruction: str,
        use_ai: bool,
    ) -> ModelingSession:
        draft, enrichment = await self._schema.draft(
            source_id, network_id, name, use_ai, instruction
        )
        session_id = f"model-{uuid4().hex}"
        proposals = self._schema_proposals(session_id, draft)
        proposals.extend(self._suggested_actions(session_id, draft, instruction, enrichment))
        now = datetime.now(UTC)
        session = ModelingSession(
            id=session_id,
            source_id=source_id,
            network_id=network_id,
            name=name,
            instruction=instruction,
            use_ai=use_ai,
            status=ModelingSessionStatus.IN_REVIEW,
            proposals=proposals,
            created_at=now,
            updated_at=now,
        )
        return await self._sessions.save_modeling_session(session)

    async def get(self, session_id: str) -> ModelingSession:
        session = await self._sessions.get_modeling_session(session_id)
        if session is None:
            raise ResourceNotFoundError("modeling session", session_id)
        return session

    async def list_all(self) -> list[ModelingSession]:
        return await self._sessions.list_modeling_sessions()

    async def review(
        self,
        session_id: str,
        proposal_id: str,
        status: ProposalStatus,
        reviewed_by: str,
        payload: dict[str, Any] | None,
    ) -> ModelingSession:
        session = await self.get(session_id)
        if session.status == ModelingSessionStatus.PUBLISHED:
            raise MiniBKNError(
                "MODELING_SESSION_PUBLISHED",
                "Published modeling sessions are immutable",
                409,
            )
        found = False
        proposals: list[SchemaProposal] = []
        for proposal in session.proposals:
            if proposal.id != proposal_id:
                proposals.append(proposal)
                continue
            found = True
            if status == ProposalStatus.MODIFIED and payload is None:
                raise MiniBKNError(
                    "MODIFIED_PAYLOAD_REQUIRED",
                    "A modified proposal requires replacement payload",
                    400,
                )
            replacement = payload if payload is not None else proposal.payload
            self._validate_proposal(proposal.kind, replacement)
            proposals.append(
                proposal.model_copy(
                    update={
                        "payload": replacement,
                        "status": status,
                        "reviewed_by": reviewed_by,
                        "reviewed_at": datetime.now(UTC),
                    }
                )
            )
        if not found:
            raise ResourceNotFoundError("schema proposal", proposal_id)
        ready = all(item.status != ProposalStatus.PENDING for item in proposals)
        updated = session.model_copy(
            update={
                "proposals": proposals,
                "status": (
                    ModelingSessionStatus.READY if ready else ModelingSessionStatus.IN_REVIEW
                ),
                "updated_at": datetime.now(UTC),
            }
        )
        return await self._sessions.save_modeling_session(updated)

    async def publish(self, session_id: str, published_by: str) -> KnowledgeNetwork:
        session = await self.get(session_id)
        if session.status != ModelingSessionStatus.READY:
            raise MiniBKNError(
                "MODELING_REVIEW_INCOMPLETE",
                "Every proposal must be accepted, modified, or rejected before publication",
                409,
            )
        network = self._assemble(session, published_by)
        existing = await self._networks.get(session.network_id)
        if existing is not None:
            network = network.model_copy(update={"version": existing.version + 1})
        published = await self._networks.save(network)
        updated = session.model_copy(
            update={
                "status": ModelingSessionStatus.PUBLISHED,
                "published_network_version": published.version,
                "updated_at": datetime.now(UTC),
            }
        )
        await self._sessions.save_modeling_session(updated)
        return published

    @staticmethod
    def _schema_proposals(session_id: str, draft: KnowledgeNetwork) -> list[SchemaProposal]:
        proposals: list[SchemaProposal] = []
        for object_type in draft.object_types:
            object_payload = object_type.model_dump(
                mode="json", exclude={"properties", "primary_keys"}
            )
            proposals.append(
                _proposal(session_id, ProposalKind.OBJECT_TYPE, object_type.id, object_payload, 0.9)
            )
            for prop in object_type.properties:
                proposals.append(
                    _proposal(
                        session_id,
                        ProposalKind.PROPERTY,
                        f"{object_type.id}.{prop.name}",
                        {
                            "object_type_id": object_type.id,
                            "property": prop.model_dump(mode="json"),
                        },
                        0.85,
                    )
                )
            proposals.append(
                _proposal(
                    session_id,
                    ProposalKind.PRIMARY_KEY,
                    object_type.id,
                    {"object_type_id": object_type.id, "fields": object_type.primary_keys},
                    0.8,
                )
            )
        for relation in draft.relation_types:
            proposals.append(
                _proposal(
                    session_id,
                    ProposalKind.RELATION,
                    relation.id,
                    relation.model_dump(mode="json"),
                    0.75,
                )
            )
        return proposals

    def _suggested_actions(
        self,
        session_id: str,
        draft: KnowledgeNetwork,
        instruction: str,
        enrichment: dict[str, Any],
    ) -> list[SchemaProposal]:
        raw_actions = enrichment.get("action_suggestions", [])
        raw_risks = enrichment.get("risk_suggestions", [])
        suggestions: list[SchemaProposal] = []
        if isinstance(raw_actions, list):
            for item in raw_actions:
                if not isinstance(item, dict):
                    continue
                safe = self._safe_action(item, draft)
                if safe is not None:
                    suggestions.append(
                        _proposal(
                            session_id,
                            ProposalKind.ACTION,
                            safe.id,
                            safe.model_dump(mode="json"),
                            0.55,
                        )
                    )
        if isinstance(raw_risks, list):
            for item in raw_risks:
                if not isinstance(item, dict):
                    continue
                try:
                    risk = RiskType.model_validate(item)
                    if risk.policy not in {"confirm", "deny"}:
                        continue
                    self._policies.validate(risk.condition)
                except (ValidationError, PolicyEvaluationError):
                    continue
                suggestions.append(
                    _proposal(
                        session_id, ProposalKind.RISK, risk.id, risk.model_dump(mode="json"), 0.5
                    )
                )
        if (
            suggestions
            or not draft.object_types
            or not re.search(
                r"动作|审批|创建|更新|删除|action|approve|execute", instruction, re.IGNORECASE
            )
        ):
            return suggestions
        target = draft.object_types[0]
        action = ActionType(
            id="suggested_business_action",
            name="Suggested business action",
            description=f"Drafted from instruction: {instruction}",
            enabled=False,
            requires_approval=True,
            risk_level="high",
            bound_object_type=target.id,
            tool={"binding_type": "mcp", "toolbox_id": "unconfigured", "tool_id": "unconfigured"},
            source_path=f"generated://modeling/{session_id}/action",
        )
        risk = RiskType(
            id="review_suggested_business_action",
            name="Human review required",
            policy="confirm",
            applies_to_actions=[action.id],
            condition={"eq": [1, 1]},
            source_path=f"generated://modeling/{session_id}/risk",
        )
        return [
            _proposal(
                session_id, ProposalKind.ACTION, action.id, action.model_dump(mode="json"), 0.4
            ),
            _proposal(session_id, ProposalKind.RISK, risk.id, risk.model_dump(mode="json"), 0.4),
        ]

    @staticmethod
    def _safe_action(value: dict[str, Any], draft: KnowledgeNetwork) -> ActionType | None:
        object_ids = {item.id for item in draft.object_types}
        value = dict(value)
        value["enabled"] = False
        value["requires_approval"] = True
        value["tool"] = {
            "binding_type": "mcp",
            "toolbox_id": "unconfigured",
            "tool_id": "unconfigured",
        }
        try:
            action = ActionType.model_validate(value)
        except ValidationError:
            return None
        return action if action.bound_object_type in object_ids else None

    def _validate_proposal(self, kind: ProposalKind, payload: dict[str, Any]) -> None:
        try:
            if kind == ProposalKind.OBJECT_TYPE:
                required = {"id", "name", "display_key", "data_source", "source_path"}
                if not required.issubset(payload):
                    raise ValueError("object proposal is incomplete")
            elif kind == ProposalKind.PROPERTY:
                DataProperty.model_validate(payload["property"])
            elif kind == ProposalKind.PRIMARY_KEY:
                if not payload.get("object_type_id") or not payload.get("fields"):
                    raise ValueError("primary key proposal is incomplete")
            elif kind == ProposalKind.RELATION:
                RelationType.model_validate(payload)
            elif kind == ProposalKind.ACTION:
                action = ActionType.model_validate(payload)
                if action.enabled or not action.requires_approval:
                    raise ValueError("proposed actions must stay disabled and require approval")
            elif kind == ProposalKind.RISK:
                risk = RiskType.model_validate(payload)
                if risk.policy not in {"confirm", "deny"}:
                    raise ValueError("proposed risk policy must be confirm or deny")
                self._policies.validate(risk.condition)
        except (KeyError, ValidationError, ValueError, PolicyEvaluationError) as exc:
            raise MiniBKNError("INVALID_MODELING_PROPOSAL", str(exc), 400) from exc

    def _assemble(self, session: ModelingSession, published_by: str) -> KnowledgeNetwork:
        selected = [
            item
            for item in session.proposals
            if item.status in {ProposalStatus.ACCEPTED, ProposalStatus.MODIFIED}
        ]
        object_payloads = {
            item.target_id: dict(item.payload)
            for item in selected
            if item.kind == ProposalKind.OBJECT_TYPE
        }
        properties: dict[str, list[DataProperty]] = {key: [] for key in object_payloads}
        primary_keys: dict[str, list[str]] = {}
        for item in selected:
            if item.kind == ProposalKind.PROPERTY:
                object_id = str(item.payload["object_type_id"])
                if object_id in properties:
                    properties[object_id].append(
                        DataProperty.model_validate(item.payload["property"])
                    )
            elif item.kind == ProposalKind.PRIMARY_KEY:
                primary_keys[str(item.payload["object_type_id"])] = [
                    str(value) for value in item.payload["fields"]
                ]
        objects = [
            ObjectType.model_validate(
                {
                    **payload,
                    "properties": [item.model_dump(mode="json") for item in properties[object_id]],
                    "primary_keys": primary_keys.get(object_id, []),
                }
            )
            for object_id, payload in object_payloads.items()
        ]
        if not objects:
            raise MiniBKNError(
                "MODELING_EMPTY_NETWORK", "At least one object must be approved", 409
            )
        object_ids = {item.id for item in objects}
        relations = [
            RelationType.model_validate(item.payload)
            for item in selected
            if item.kind == ProposalKind.RELATION
            and item.payload.get("endpoint", {}).get("source_object_type") in object_ids
            and item.payload.get("endpoint", {}).get("target_object_type") in object_ids
        ]
        actions = [
            ActionType.model_validate(item.payload)
            for item in selected
            if item.kind == ProposalKind.ACTION
            and item.payload.get("bound_object_type") in object_ids
        ]
        action_ids = {item.id for item in actions}
        risks = [
            RiskType.model_validate(item.payload)
            for item in selected
            if item.kind == ProposalKind.RISK
            and set(item.payload.get("applies_to_actions", [])).issubset(action_ids)
        ]
        now = datetime.now(UTC)
        return KnowledgeNetwork(
            id=session.network_id,
            name=session.name,
            description=f"Human-approved modeling session {session.id} by {published_by}",
            business_domain="modeled",
            lifecycle_status="published",
            source_path=f"modeling://session/{session.id}",
            object_types=objects,
            relation_types=relations,
            action_types=actions,
            risk_types=risks,
            created_at=now,
            updated_at=now,
        )


def _proposal(
    session_id: str,
    kind: ProposalKind,
    target_id: str,
    payload: dict[str, Any],
    confidence: float,
) -> SchemaProposal:
    return SchemaProposal(
        id=f"proposal-{uuid4().hex}",
        session_id=session_id,
        kind=kind,
        target_id=target_id,
        payload=payload,
        confidence=confidence,
        evidence=[str(payload.get("source_path", target_id))],
        rationale="Generated from discovered source metadata and the user's instruction",
    )
