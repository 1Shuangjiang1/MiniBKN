"""Policy-file authentication and authorization for the local enterprise MVP."""

import hashlib
import json
import secrets
from pathlib import Path

from minibkn.api.errors import MiniBKNError
from minibkn.domain.access_control import SYSTEM_PRINCIPAL, Permission, Principal
from minibkn.domain.models import DataSource, KnowledgeNetwork, ObjectInstance, RelationInstance


class AccessControlService:
    def __init__(self, enabled: bool, policy_file: Path | None, admin_api_key: str = "") -> None:
        self.enabled = enabled
        self._admin_api_key = admin_api_key
        self._principals: dict[str, Principal] = {}
        self._token_hashes: dict[str, str] = {}
        if enabled:
            if policy_file is None:
                raise ValueError(
                    "authorization policy file is required when authorization is enabled"
                )
            self._load(policy_file)

    def authenticate(self, supplied_key: str) -> Principal:
        if not self.enabled:
            return SYSTEM_PRINCIPAL
        if not supplied_key:
            raise MiniBKNError("UNAUTHORIZED", "A valid x-api-key header is required", 401)
        if self._admin_api_key and secrets.compare_digest(supplied_key, self._admin_api_key):
            return SYSTEM_PRINCIPAL
        digest = hashlib.sha256(supplied_key.encode("utf-8")).hexdigest()
        for principal_id, expected in self._token_hashes.items():
            if secrets.compare_digest(digest, expected):
                return self._principals[principal_id]
        raise MiniBKNError("UNAUTHORIZED", "A valid x-api-key header is required", 401)

    @staticmethod
    def require(principal: Principal, permission: Permission, network_id: str = "") -> None:
        if not principal.allows(permission) or (
            network_id and not principal.allows_network(network_id)
        ):
            raise MiniBKNError(
                "FORBIDDEN",
                f"principal '{principal.id}' is not allowed to {permission.value} this resource",
                403,
            )

    @staticmethod
    def require_action(principal: Principal, network_id: str, action_id: str) -> None:
        AccessControlService.require(principal, Permission.EXECUTE, network_id)
        if not principal.allows_action(action_id):
            raise MiniBKNError("FORBIDDEN", f"action '{action_id}' is not permitted", 403)

    @staticmethod
    def filter_networks(
        principal: Principal, networks: list[KnowledgeNetwork]
    ) -> list[KnowledgeNetwork]:
        return [item for item in networks if principal.allows_network(item.id)]

    @staticmethod
    def filter_sources(principal: Principal, sources: list[DataSource]) -> list[DataSource]:
        if principal.is_admin or "*" in principal.resources:
            return sources
        result = []
        for source in sources:
            resources = [item for item in source.resources if principal.allows_resource(item.id)]
            if resources:
                result.append(source.model_copy(update={"resources": resources}))
        return result

    @staticmethod
    def filter_objects(principal: Principal, objects: list[ObjectInstance]) -> list[ObjectInstance]:
        return [item for item in objects if principal.allows_resource(item.resource_id)]

    @staticmethod
    def filter_relations(
        relations: list[RelationInstance], objects: list[ObjectInstance]
    ) -> list[RelationInstance]:
        visible = {(item.object_type_id, item.instance_id) for item in objects}
        return [
            item
            for item in relations
            if (item.source_object_type_id, item.source_instance_id) in visible
            and (item.target_object_type_id, item.target_instance_id) in visible
        ]

    def _load(self, policy_file: Path) -> None:
        payload = json.loads(policy_file.read_text(encoding="utf-8-sig"))
        roles = payload.get("roles", {})
        for raw in payload.get("principals", []):
            merged: dict[str, set[str]] = {
                key: set(raw.get(key, []))
                for key in (
                    "permissions",
                    "networks",
                    "resources",
                    "document_collections",
                    "actions",
                )
            }
            for role_name in raw.get("roles", []):
                role = roles.get(role_name)
                if role is None:
                    raise ValueError(f"unknown authorization role: {role_name}")
                for key in merged:
                    merged[key].update(role.get(key, []))
            principal = Principal(
                id=raw["id"],
                roles=frozenset(raw.get("roles", [])),
                **{key: frozenset(value) for key, value in merged.items()},
            )
            token_hash = str(raw.get("api_key_sha256", "")).lower()
            if len(token_hash) != 64 or any(char not in "0123456789abcdef" for char in token_hash):
                raise ValueError(f"principal '{principal.id}' requires a SHA-256 API key hash")
            self._principals[principal.id] = principal
            if token_hash in self._token_hashes.values():
                raise ValueError("authorization API key hashes must be unique")
            self._token_hashes[principal.id] = token_hash
