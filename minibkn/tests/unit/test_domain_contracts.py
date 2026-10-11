from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from minibkn.domain.build import BuildJob, ChangeSet, RecordChange
from minibkn.domain.evidence import EvidenceItem, EvidenceKind
from minibkn.domain.modeling import (
    BknLifecycleStatus,
    BknVersion,
    ProposalKind,
    SchemaProposal,
)
from minibkn.domain.query import (
    ActionRequest,
    AggregateFunction,
    AggregateSpec,
    FilterCondition,
    FilterOperator,
    QueryIntent,
    QueryPlan,
    TraversalStep,
)


def test_evidence_contract_is_provider_neutral_and_frozen() -> None:
    evidence = EvidenceItem(
        id="instance:customer:CUST-001",
        network_id="crm",
        kind=EvidenceKind.INSTANCE,
        title="星河科技",
        content="customer_id CUST-001 segment enterprise",
        citation="resource://customers_csv#row=2",
        entity_type="customer",
        entity_id="CUST-001",
        attributes={"segment": "enterprise"},
    )

    assert evidence.kind == EvidenceKind.INSTANCE
    with pytest.raises(ValidationError):
        EvidenceItem.model_validate({**evidence.model_dump(), "unknown": True})


def test_query_plan_supports_traversal_filter_and_aggregation() -> None:
    plan = QueryPlan(
        intent=QueryIntent.AGGREGATE,
        object_types=["customer", "order"],
        filters=[FilterCondition(field="order.status", operator=FilterOperator.EQ, value="paid")],
        traversals=[TraversalStep(relation="placed_by")],
        aggregates=[
            AggregateSpec(function=AggregateFunction.SUM, field="order.amount", alias="revenue")
        ],
        group_by=["customer.customer_id"],
        answer_mode="table",
    )

    assert plan.version == "1.0"
    assert plan.aggregates[0].alias == "revenue"


def test_query_plan_rejects_unsafe_or_incomplete_shapes() -> None:
    with pytest.raises(ValidationError):
        QueryPlan.model_validate(
            {
                "intent": "search",
                "raw_sql": "DROP TABLE customers",
            }
        )
    with pytest.raises(ValidationError):
        QueryPlan(intent=QueryIntent.ACTION)
    with pytest.raises(ValidationError):
        AggregateSpec(function=AggregateFunction.SUM, alias="total")
    with pytest.raises(ValidationError, match="list value"):
        FilterCondition(field="status", operator=FilterOperator.IN, value="open paid")
    with pytest.raises(ValidationError, match="traverse intent"):
        QueryPlan(
            intent=QueryIntent.LOOKUP,
            object_types=["order"],
            traversals=[TraversalStep(relation="placed_by")],
        )
    action_plan = QueryPlan(
        intent=QueryIntent.ACTION,
        action_request=ActionRequest(
            action_type_id="approve_order",
            object_type_id="order",
            instance_id="ORD-001",
        ),
    )
    assert action_plan.action_request is not None


def test_modeling_and_build_contracts_keep_review_and_change_state() -> None:
    proposal = SchemaProposal(
        id="proposal-1",
        session_id="session-1",
        kind=ProposalKind.RELATION,
        target_id="placed_by",
        payload={"source": "order", "target": "customer"},
        confidence=0.94,
        evidence=["customer_id inclusion=1.0"],
    )
    version = BknVersion(
        network_id="crm",
        version=1,
        status=BknLifecycleStatus.PUBLISHED,
        content_hash="sha256:example",
        created_by="system",
        published_at=datetime.now(UTC),
    )
    changes = ChangeSet(
        inserted=[RecordChange(object_type_id="order", instance_id="ORD-005")],
        updated=[RecordChange(object_type_id="customer", instance_id="CUST-001")],
    )
    job = BuildJob(id="build-1", network_id="crm", target_version=2, change_set=changes)

    assert proposal.status == "pending"
    assert version.status == BknLifecycleStatus.PUBLISHED
    assert job.change_set.total == 2
