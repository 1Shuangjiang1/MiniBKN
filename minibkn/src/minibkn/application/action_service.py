"""Controlled action execution with parameter binding, risk gates, and trace events."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from minibkn.adapters.tools import ToolRegistry
from minibkn.api.errors import MiniBKNError, ResourceNotFoundError
from minibkn.domain.access_control import current_principal
from minibkn.domain.models import (
    ActionExecution,
    ActionExecutionStatus,
    ActionType,
    KnowledgeNetwork,
    ObjectInstance,
    RiskDecision,
    RiskSimulationResult,
    RiskType,
    TraceEvent,
)
from minibkn.domain.policy import PolicyEvaluationError, PolicyEvaluator
from minibkn.observability.trace import current_trace_id
from minibkn.ports.repository import (
    ExecutionRepository,
    KnowledgeGraphRepository,
    KnowledgeNetworkRepository,
)


class ActionService:
    def __init__(
        self,
        networks: KnowledgeNetworkRepository,
        graph: KnowledgeGraphRepository,
        executions: ExecutionRepository,
        tools: ToolRegistry,
    ) -> None:
        self._networks = networks
        self._graph = graph
        self._executions = executions
        self._tools = tools
        self._policies = PolicyEvaluator()

    async def execute(
        self,
        network_id: str,
        action_type_id: str,
        object_type_id: str,
        instance_id: str,
        overrides: dict[str, Any],
        idempotency_key: str = "",
    ) -> ActionExecution:
        if idempotency_key:
            existing = await self._executions.find_execution_by_idempotency_key(
                network_id, action_type_id, idempotency_key
            )
            if existing is not None:
                return existing
        network = await self._get_network(network_id)
        action = self._get_action(network, action_type_id)
        if action.bound_object_type != object_type_id:
            raise MiniBKNError(
                error_code="ACTION_OBJECT_TYPE_MISMATCH",
                message=f"action '{action.id}' is bound to '{action.bound_object_type}'",
            )
        instance = await self._get_instance(network_id, object_type_id, instance_id)
        parameters = self._bind_parameters(action, instance, overrides)
        decisions = self._evaluate_risks(
            network, action, instance, parameters, self._trusted_subject({})
        )
        status = self._initial_status(decisions)
        now = datetime.now(UTC)
        execution = ActionExecution(
            id=f"exec-{uuid4().hex}",
            network_id=network_id,
            action_type_id=action.id,
            object_type_id=object_type_id,
            instance_id=instance_id,
            status=status,
            parameters=parameters,
            risk_decisions=decisions,
            trace_id=current_trace_id(),
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        await self._executions.save_execution(execution)
        await self._event(execution, "action.requested", {"parameters": parameters})
        await self._event(
            execution,
            "risk.evaluated",
            {"decisions": [item.model_dump(mode="json") for item in decisions]},
        )
        if status == ActionExecutionStatus.DENIED:
            await self._event(execution, "action.denied", {})
            return execution
        if status == ActionExecutionStatus.PENDING_CONFIRMATION:
            await self._event(execution, "action.awaiting_confirmation", {})
            return execution
        return await self._run_tool(execution, action)

    async def confirm(self, execution_id: str, approved: bool) -> ActionExecution:
        execution = await self.get_execution(execution_id)
        if execution.status != ActionExecutionStatus.PENDING_CONFIRMATION:
            raise MiniBKNError(
                error_code="INVALID_EXECUTION_STATE",
                message=f"execution '{execution_id}' is in state '{execution.status}'",
                status_code=409,
            )
        if not approved:
            denied = execution.model_copy(
                update={"status": ActionExecutionStatus.DENIED, "updated_at": datetime.now(UTC)}
            )
            await self._executions.save_execution(denied)
            await self._event(denied, "action.confirmation_rejected", {})
            return denied
        network = await self._get_network(execution.network_id)
        action = self._get_action(network, execution.action_type_id)
        await self._event(execution, "action.confirmation_approved", {})
        return await self._run_tool(execution, action)

    async def get_execution(self, execution_id: str) -> ActionExecution:
        execution = await self._executions.get_execution(execution_id)
        if execution is None:
            raise ResourceNotFoundError("action execution", execution_id)
        return execution

    async def list_trace(self, trace_id: str) -> list[TraceEvent]:
        return await self._executions.list_trace_events(trace_id)

    async def simulate_risks(
        self,
        network_id: str,
        action_type_id: str,
        object_type_id: str,
        instance_id: str,
        overrides: dict[str, Any],
        subject: dict[str, Any],
    ) -> RiskSimulationResult:
        network = await self._get_network(network_id)
        action = self._get_action(network, action_type_id)
        if action.bound_object_type != object_type_id:
            raise MiniBKNError(
                error_code="ACTION_OBJECT_TYPE_MISMATCH",
                message=f"action '{action.id}' is bound to '{action.bound_object_type}'",
            )
        instance = await self._get_instance(network_id, object_type_id, instance_id)
        parameters = self._bind_parameters(action, instance, overrides)
        decisions = self._evaluate_risks(
            network, action, instance, parameters, self._trusted_subject(subject)
        )
        status = self._initial_status(decisions)
        return RiskSimulationResult(
            network_id=network_id,
            action_type_id=action_type_id,
            object_type_id=object_type_id,
            instance_id=instance_id,
            decision={
                ActionExecutionStatus.DENIED: "deny",
                ActionExecutionStatus.PENDING_CONFIRMATION: "confirm",
            }.get(status, "allow"),
            risk_decisions=decisions,
        )

    async def _run_tool(self, execution: ActionExecution, action: ActionType) -> ActionExecution:
        running = execution.model_copy(
            update={"status": ActionExecutionStatus.RUNNING, "updated_at": datetime.now(UTC)}
        )
        await self._executions.save_execution(running)
        await self._event(running, "tool.started", {"tool_id": action.tool.tool_id})
        tool = self._tools.get(action.tool.toolbox_id, action.tool.tool_id)
        try:
            result = await tool.execute(running.parameters)
        except Exception as exc:
            failed = running.model_copy(
                update={
                    "status": ActionExecutionStatus.FAILED,
                    "error": str(exc),
                    "updated_at": datetime.now(UTC),
                }
            )
            await self._executions.save_execution(failed)
            await self._event(failed, "tool.failed", {"error": str(exc)})
            return failed
        succeeded = running.model_copy(
            update={
                "status": ActionExecutionStatus.SUCCEEDED,
                "result": result,
                "updated_at": datetime.now(UTC),
            }
        )
        await self._executions.save_execution(succeeded)
        await self._event(succeeded, "tool.succeeded", {"result": result})
        return succeeded

    async def _get_network(self, network_id: str) -> KnowledgeNetwork:
        network = await self._networks.get(network_id)
        if network is None:
            raise ResourceNotFoundError("knowledge network", network_id)
        return network

    async def _get_instance(
        self, network_id: str, object_type_id: str, instance_id: str
    ) -> ObjectInstance:
        principal = current_principal()
        instances = [
            item
            for item in await self._graph.list_objects(network_id, object_type_id)
            if principal.allows_resource(item.resource_id)
        ]
        instance = next((item for item in instances if item.instance_id == instance_id), None)
        if instance is None:
            raise ResourceNotFoundError("object instance", f"{object_type_id}/{instance_id}")
        return instance

    @staticmethod
    def _get_action(network: KnowledgeNetwork, action_type_id: str) -> ActionType:
        action = next((item for item in network.action_types if item.id == action_type_id), None)
        if action is None or not action.enabled:
            raise ResourceNotFoundError("enabled action type", action_type_id)
        return action

    @staticmethod
    def _bind_parameters(
        action: ActionType, instance: ObjectInstance, overrides: dict[str, Any]
    ) -> dict[str, Any]:
        parameters: dict[str, Any] = {}
        for binding in action.parameters:
            if binding.parameter in overrides:
                value = overrides[binding.parameter]
            elif binding.source == "property":
                value = instance.properties.get(binding.binding)
            else:
                value = None
            if value is None:
                raise MiniBKNError(
                    error_code="ACTION_PARAMETER_MISSING",
                    message=f"required action parameter '{binding.parameter}' is missing",
                )
            parameters[binding.parameter] = value
        unknown = sorted(set(overrides) - {item.parameter for item in action.parameters})
        if unknown:
            raise MiniBKNError(
                error_code="ACTION_PARAMETER_UNKNOWN",
                message=f"unknown action parameters: {', '.join(unknown)}",
            )
        return parameters

    def _evaluate_risks(
        self,
        network: KnowledgeNetwork,
        action: ActionType,
        instance: ObjectInstance,
        parameters: dict[str, Any],
        subject: dict[str, Any],
    ) -> list[RiskDecision]:
        decisions = [
            self._risk_decision(risk, instance, parameters, subject)
            for risk in network.risk_types
            if action.id in risk.applies_to_actions
        ]
        if action.requires_approval:
            decisions.append(
                RiskDecision(
                    risk_type_id=f"action:{action.id}:requires_approval",
                    policy="confirm",
                    matched=True,
                    reason="action type requires explicit approval",
                )
            )
        return decisions

    def _risk_decision(
        self,
        risk: RiskType,
        instance: ObjectInstance,
        parameters: dict[str, Any],
        subject: dict[str, Any],
    ) -> RiskDecision:
        try:
            matched = self._policies.evaluate(
                risk.condition,
                {"object": instance.properties, "action": parameters, "subject": subject},
            )
        except PolicyEvaluationError as exc:
            return RiskDecision(
                risk_type_id=risk.id,
                policy="deny",
                matched=True,
                reason=f"policy evaluation failed closed: {exc}",
            )
        return RiskDecision(
            risk_type_id=risk.id,
            policy=risk.policy,
            matched=matched,
            reason=f"policy expression {'matched' if matched else 'did not match'}",
        )

    @staticmethod
    def _initial_status(decisions: list[RiskDecision]) -> ActionExecutionStatus:
        matched_policies = {item.policy for item in decisions if item.matched}
        if "deny" in matched_policies:
            return ActionExecutionStatus.DENIED
        if "confirm" in matched_policies:
            return ActionExecutionStatus.PENDING_CONFIRMATION
        return ActionExecutionStatus.RUNNING

    @staticmethod
    def _trusted_subject(submitted: dict[str, Any]) -> dict[str, Any]:
        principal = current_principal()
        if principal.id == "system":
            return submitted
        trusted = dict(submitted)
        trusted.update(
            {
                "id": principal.id,
                "roles": sorted(principal.roles),
                "role": sorted(principal.roles)[0] if principal.roles else "",
            }
        )
        return trusted

    async def _event(
        self, execution: ActionExecution, event_type: str, payload: dict[str, Any]
    ) -> None:
        await self._executions.append_trace_event(
            TraceEvent(
                id=f"event-{uuid4().hex}",
                trace_id=execution.trace_id,
                event_type=event_type,
                payload={"execution_id": execution.id, **payload},
            )
        )
