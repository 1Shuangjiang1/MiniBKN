"""Request identity and least-privilege access-control contracts."""

from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import StrEnum


class Permission(StrEnum):
    READ = "read"
    MODEL = "model"
    EXECUTE = "execute"
    APPROVE = "approve"
    AUDIT = "audit"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class Principal:
    id: str
    roles: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    networks: frozenset[str] = frozenset()
    resources: frozenset[str] = frozenset()
    document_collections: frozenset[str] = frozenset()
    actions: frozenset[str] = frozenset()

    @property
    def is_admin(self) -> bool:
        return "*" in self.permissions or Permission.ADMIN in self.permissions

    def allows(self, permission: Permission) -> bool:
        return self.is_admin or permission in self.permissions

    def allows_network(self, network_id: str) -> bool:
        return self.is_admin or "*" in self.networks or network_id in self.networks

    def allows_resource(self, resource_id: str) -> bool:
        return self.is_admin or "*" in self.resources or resource_id in self.resources

    def allows_collection(self, collection: str) -> bool:
        return (
            self.is_admin
            or "*" in self.document_collections
            or collection in self.document_collections
        )

    def allows_action(self, action_id: str) -> bool:
        return self.is_admin or "*" in self.actions or action_id in self.actions


SYSTEM_PRINCIPAL = Principal(
    id="system",
    roles=frozenset({"system"}),
    permissions=frozenset({"*"}),
    networks=frozenset({"*"}),
    resources=frozenset({"*"}),
    document_collections=frozenset({"*"}),
    actions=frozenset({"*"}),
)

_principal: ContextVar[Principal] = ContextVar("minibkn_principal", default=SYSTEM_PRINCIPAL)


def current_principal() -> Principal:
    return _principal.get()


def set_principal(principal: Principal) -> Token[Principal]:
    return _principal.set(principal)


def reset_principal(token: Token[Principal]) -> None:
    _principal.reset(token)
