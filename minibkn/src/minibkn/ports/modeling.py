"""Persistence port for reviewable AI modeling sessions."""

from typing import Protocol

from minibkn.domain.modeling import ModelingSession


class ModelingRepository(Protocol):
    async def save_modeling_session(self, session: ModelingSession) -> ModelingSession: ...

    async def get_modeling_session(self, session_id: str) -> ModelingSession | None: ...

    async def list_modeling_sessions(self) -> list[ModelingSession]: ...
