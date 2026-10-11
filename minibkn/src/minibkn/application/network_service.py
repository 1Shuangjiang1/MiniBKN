"""Knowledge network import and query use cases."""

from pathlib import Path

from minibkn.adapters.bkn_lang import BknLangParser
from minibkn.api.errors import ResourceNotFoundError
from minibkn.domain.models import KnowledgeNetwork
from minibkn.ports.repository import KnowledgeNetworkRepository


class KnowledgeNetworkService:
    def __init__(
        self,
        repository: KnowledgeNetworkRepository,
        parser: BknLangParser | None = None,
    ) -> None:
        self._repository = repository
        self._parser = parser or BknLangParser()

    async def import_directory(self, path: Path) -> KnowledgeNetwork:
        network = self._parser.parse_directory(path)
        return await self._repository.save(network)

    async def list_networks(self) -> list[KnowledgeNetwork]:
        return await self._repository.list_all()

    async def get_network(self, network_id: str) -> KnowledgeNetwork:
        network = await self._repository.get(network_id)
        if network is None:
            raise ResourceNotFoundError("knowledge network", network_id)
        return network
