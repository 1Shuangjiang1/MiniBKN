"""Data source discovery, object materialization, and graph traversal use cases."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from minibkn.api.errors import MiniBKNError, ResourceNotFoundError
from minibkn.domain.access_control import current_principal
from minibkn.domain.build import ChangeSet, RecordChange
from minibkn.domain.models import (
    DataSource,
    DataSourceKind,
    KnowledgeNetwork,
    ObjectInstance,
    ObjectType,
    RelationInstance,
    Resource,
    Subgraph,
)
from minibkn.ports.datasource import DataSourceAdapter
from minibkn.ports.repository import KnowledgeGraphRepository, KnowledgeNetworkRepository


class KnowledgeGraphService:
    def __init__(
        self,
        networks: KnowledgeNetworkRepository,
        graph: KnowledgeGraphRepository,
        adapters: dict[DataSourceKind, DataSourceAdapter],
    ) -> None:
        self._networks = networks
        self._graph = graph
        self._adapters = adapters

    async def register_source(
        self, source_id: str, name: str, kind: DataSourceKind, path: str
    ) -> DataSource:
        source = DataSource(id=source_id, name=name, kind=kind, path=path)
        return await self._graph.save_source(source)

    async def discover_source(self, source_id: str) -> DataSource:
        source = await self.get_source(source_id)
        resources = self._adapters[source.kind].discover(source)
        discovered = source.model_copy(
            update={"resources": resources, "updated_at": datetime.now(UTC)}
        )
        return await self._graph.save_source(discovered)

    async def get_source(self, source_id: str) -> DataSource:
        source = await self._graph.get_source(source_id)
        if source is None:
            raise ResourceNotFoundError("data source", source_id)
        return source

    async def list_sources(self) -> list[DataSource]:
        return await self._graph.list_sources()

    async def materialize(self, network_id: str) -> tuple[int, int]:
        network = await self._get_network(network_id)
        objects, relations = await self._desired_graph(network)
        await self._graph.replace_graph(network_id, objects, relations)
        return len(objects), len(relations)

    async def materialize_incremental(self, network_id: str) -> tuple[ChangeSet, int, int]:
        network = await self._get_network(network_id)
        desired_objects, desired_relations = await self._desired_graph(network)
        current_objects = await self._graph.list_objects(network_id)
        current_relations = await self._graph.list_relations(network_id)
        current_map = {(item.object_type_id, item.instance_id): item for item in current_objects}
        desired_map = {(item.object_type_id, item.instance_id): item for item in desired_objects}
        inserted_keys = sorted(set(desired_map) - set(current_map))
        deleted_keys = sorted(set(current_map) - set(desired_map))
        updated_keys = sorted(
            key
            for key in set(current_map) & set(desired_map)
            if self._object_hash(current_map[key]) != self._object_hash(desired_map[key])
        )
        current_edges = {self._relation_key(item): item for item in current_relations}
        desired_edges = {self._relation_key(item): item for item in desired_relations}
        inserted_edges = sorted(set(desired_edges) - set(current_edges))
        deleted_edges = sorted(set(current_edges) - set(desired_edges))
        await self._graph.apply_graph_changes(
            network_id,
            [desired_map[key] for key in inserted_keys + updated_keys],
            deleted_keys,
            [desired_edges[key] for key in inserted_edges],
            deleted_edges,
        )
        return (
            ChangeSet(
                inserted=[self._record_change(desired_map[key]) for key in inserted_keys],
                updated=[self._record_change(desired_map[key]) for key in updated_keys],
                deleted=[self._record_change(current_map[key]) for key in deleted_keys],
            ),
            len(inserted_edges),
            len(deleted_edges),
        )

    async def _desired_graph(
        self, network: KnowledgeNetwork
    ) -> tuple[list[ObjectInstance], list[RelationInstance]]:
        resources = await self._resources_by_id()
        objects: list[ObjectInstance] = []
        for object_type in network.object_types:
            resource = self._bound_resource(object_type, resources)
            source = await self.get_source(resource.source_id)
            rows = self._adapters[source.kind].read_rows(resource)
            objects.extend(
                self._map_object(network, object_type, resource, row, index)
                for index, row in enumerate(rows, start=2)
            )
        relations = self._map_relations(network, objects)
        return objects, relations

    async def list_instances(self, network_id: str, object_type_id: str) -> list[ObjectInstance]:
        await self._get_network(network_id)
        principal = current_principal()
        return [
            item
            for item in await self._graph.list_objects(network_id, object_type_id)
            if principal.allows_resource(item.resource_id)
        ]

    async def subgraph(
        self, network_id: str, object_type_id: str, instance_id: str, depth: int
    ) -> Subgraph:
        await self._get_network(network_id)
        principal = current_principal()
        objects = [
            item
            for item in await self._graph.list_objects(network_id)
            if principal.allows_resource(item.resource_id)
        ]
        relations = await self._graph.list_relations(network_id)
        object_map = {(item.object_type_id, item.instance_id): item for item in objects}
        start = (object_type_id, instance_id)
        if start not in object_map:
            raise ResourceNotFoundError("object instance", f"{object_type_id}/{instance_id}")

        visited = {start}
        frontier = {start}
        selected_edges: list[RelationInstance] = []
        for _ in range(depth):
            next_frontier: set[tuple[str, str]] = set()
            for edge in relations:
                source = (edge.source_object_type_id, edge.source_instance_id)
                target = (edge.target_object_type_id, edge.target_instance_id)
                if source in frontier or target in frontier:
                    if edge not in selected_edges:
                        selected_edges.append(edge)
                    if source not in visited:
                        next_frontier.add(source)
                    if target not in visited:
                        next_frontier.add(target)
            visited.update(next_frontier)
            frontier = next_frontier
        return Subgraph(
            nodes=[object_map[key] for key in sorted(visited)],
            edges=selected_edges,
        )

    async def _get_network(self, network_id: str) -> KnowledgeNetwork:
        network = await self._networks.get(network_id)
        if network is None:
            raise ResourceNotFoundError("knowledge network", network_id)
        return network

    async def _resources_by_id(self) -> dict[str, Resource]:
        resources: dict[str, Resource] = {}
        for source in await self._graph.list_sources():
            for resource in source.resources:
                if resource.id in resources:
                    raise MiniBKNError(
                        error_code="AMBIGUOUS_RESOURCE",
                        message=f"resource id '{resource.id}' exists in multiple sources",
                    )
                resources[resource.id] = resource
        return resources

    @staticmethod
    def _bound_resource(object_type: ObjectType, resources: dict[str, Resource]) -> Resource:
        if object_type.data_source is None:
            raise MiniBKNError(
                error_code="OBJECT_TYPE_NOT_BOUND",
                message=f"object type '{object_type.id}' has no data source binding",
            )
        resource = resources.get(object_type.data_source.source_id)
        if resource is None:
            raise ResourceNotFoundError("resource", object_type.data_source.source_id)
        return resource

    @staticmethod
    def _map_object(
        network: KnowledgeNetwork,
        object_type: ObjectType,
        resource: Resource,
        row: dict[str, Any],
        row_number: int,
    ) -> ObjectInstance:
        properties = {
            prop.name: _convert_value(row.get(prop.mapped_field), prop.value_type)
            for prop in object_type.properties
        }
        instance_id = "|".join(str(properties[key]) for key in object_type.primary_keys)
        display_name = str(properties.get(object_type.display_key) or instance_id)
        return ObjectInstance(
            network_id=network.id,
            object_type_id=object_type.id,
            instance_id=instance_id,
            display_name=display_name,
            resource_id=resource.id,
            row_number=row_number,
            properties=properties,
        )

    @staticmethod
    def _map_relations(
        network: KnowledgeNetwork, objects: list[ObjectInstance]
    ) -> list[RelationInstance]:
        by_type: dict[str, list[ObjectInstance]] = {}
        for item in objects:
            by_type.setdefault(item.object_type_id, []).append(item)
        result: list[RelationInstance] = []
        for relation in network.relation_types:
            sources = by_type.get(relation.endpoint.source_object_type, [])
            targets = by_type.get(relation.endpoint.target_object_type, [])
            for source in sources:
                for target in targets:
                    if all(
                        source.properties.get(mapping.source_property)
                        == target.properties.get(mapping.target_property)
                        for mapping in relation.mappings
                    ):
                        result.append(
                            RelationInstance(
                                network_id=network.id,
                                relation_type_id=relation.id,
                                source_object_type_id=source.object_type_id,
                                source_instance_id=source.instance_id,
                                target_object_type_id=target.object_type_id,
                                target_instance_id=target.instance_id,
                            )
                        )
        return result

    @staticmethod
    def _object_hash(item: ObjectInstance) -> str:
        payload = {
            "display_name": item.display_name,
            "resource_id": item.resource_id,
            "row_number": item.row_number,
            "properties": item.properties,
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    @classmethod
    def _record_change(cls, item: ObjectInstance) -> RecordChange:
        return RecordChange(
            object_type_id=item.object_type_id,
            instance_id=item.instance_id,
            content_hash=cls._object_hash(item),
        )

    @staticmethod
    def _relation_key(item: RelationInstance) -> tuple[str, str, str]:
        return item.relation_type_id, item.source_instance_id, item.target_instance_id


def _convert_value(value: Any, value_type: str) -> Any:
    if value is None or value == "":
        return None
    if value_type == "integer":
        return int(value)
    if value_type in {"number", "float", "double"}:
        return float(value)
    if value_type == "boolean":
        return str(value).lower() in {"1", "true", "yes"}
    if value_type == "decimal":
        try:
            return format(Decimal(str(value)), "f")
        except InvalidOperation as exc:
            raise ValueError(f"invalid decimal value: {value}") from exc
    if value_type == "date":
        return datetime.fromisoformat(str(value)).date().isoformat()
    if value_type == "datetime":
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
    if value_type == "json":
        return value if isinstance(value, (dict, list)) else json.loads(str(value))
    return str(value)
