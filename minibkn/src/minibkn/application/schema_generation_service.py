"""Generate an initial knowledge network from discovered structured resources."""

import re
from typing import Any

from minibkn.api.errors import MiniBKNError, ResourceNotFoundError
from minibkn.domain.models import (
    DataProperty,
    DataSourceBinding,
    KnowledgeNetwork,
    ObjectType,
    RelationEndpoint,
    RelationMapping,
    RelationType,
    Resource,
)
from minibkn.ports.repository import KnowledgeGraphRepository, KnowledgeNetworkRepository
from minibkn.ports.schema_ai import SchemaEnhancer


class SchemaGenerationService:
    def __init__(
        self,
        networks: KnowledgeNetworkRepository,
        graph: KnowledgeGraphRepository,
        enhancer: SchemaEnhancer | None = None,
    ) -> None:
        self._networks = networks
        self._graph = graph
        self._enhancer = enhancer

    async def generate(
        self, source_id: str, network_id: str, name: str, use_ai: bool
    ) -> KnowledgeNetwork:
        network, _ = await self.draft(source_id, network_id, name, use_ai)
        return await self._networks.save(network)

    async def draft(
        self,
        source_id: str,
        network_id: str,
        name: str,
        use_ai: bool,
        instruction: str = "",
    ) -> tuple[KnowledgeNetwork, dict[str, Any]]:
        source = await self._graph.get_source(source_id)
        if source is None:
            raise ResourceNotFoundError("data source", source_id)
        if not source.resources:
            raise MiniBKNError(
                error_code="SOURCE_NOT_DISCOVERED",
                message=f"data source '{source_id}' has no discovered resources",
                status_code=409,
            )
        objects = [self._object_type(resource) for resource in source.resources]
        relations = self._relations(objects, source.resources)
        enrichment: dict[str, Any] = {}
        if use_ai:
            if self._enhancer is None:
                raise MiniBKNError(
                    error_code="AI_SCHEMA_NOT_CONFIGURED",
                    message=(
                        "AI Schema enrichment requires LLM provider, base URL, model, and API key"
                    ),
                    status_code=409,
                )
            enrichment = await self._enhancer.enhance(
                {
                    "instruction": instruction,
                    "objects": [item.model_dump(mode="json") for item in objects],
                    "relations": [item.model_dump(mode="json") for item in relations],
                }
            )
            objects, relations = self._apply_enrichment(objects, relations, enrichment)
        network = KnowledgeNetwork(
            id=network_id,
            name=name,
            description=f"Generated from discovered source {source.name}",
            business_domain="generated",
            source_path=f"generated://source/{source.id}",
            object_types=objects,
            relation_types=relations,
        )
        return network, enrichment

    @staticmethod
    def _object_type(resource: Resource) -> ObjectType:
        object_id = _object_id(resource)
        recommended = [item for item in resource.primary_key_candidates if item.recommended]
        primary_fields = (
            recommended[0].fields
            if recommended
            else [field.name for field in resource.fields if field.primary_key]
        )
        if not primary_fields and resource.fields:
            primary_fields = [resource.fields[0].name]
        field_names = {field.name for field in resource.fields}
        display_key = "name" if "name" in field_names else primary_fields[0]
        return ObjectType(
            id=object_id,
            name=_display_name(object_id),
            description=f"Generated from resource {resource.name}",
            properties=[
                DataProperty(
                    name=field.name,
                    display_name=_display_name(field.name),
                    value_type=field.value_type,
                    mapped_field=field.name,
                )
                for field in resource.fields
            ],
            primary_keys=primary_fields,
            display_key=display_key,
            data_source=DataSourceBinding(
                source_type="resource", source_id=resource.id, name=resource.name
            ),
            source_path=f"generated://resource/{resource.id}",
        )

    @staticmethod
    def _relations(objects: list[ObjectType], resources: list[Resource]) -> list[RelationType]:
        relations: list[RelationType] = []
        objects_by_resource = {
            item.data_source.source_id: item for item in objects if item.data_source is not None
        }
        for resource in resources:
            source = objects_by_resource.get(resource.id)
            if source is None:
                continue
            for candidate in resource.foreign_key_candidates:
                if not candidate.recommended:
                    continue
                target = objects_by_resource.get(candidate.target_resource_id)
                if target is None:
                    continue
                relation_id = f"{source.id}_to_{target.id}"
                relations.append(
                    RelationType(
                        id=relation_id,
                        name=f"{source.name} to {target.name}",
                        description=(
                            "Generated from profiled foreign-key candidate "
                            f"(confidence {candidate.confidence:.2f})"
                        ),
                        endpoint=RelationEndpoint(
                            source_object_type=source.id,
                            target_object_type=target.id,
                        ),
                        mappings=[
                            RelationMapping(source_property=left, target_property=right)
                            for left, right in zip(
                                candidate.fields, candidate.target_fields, strict=True
                            )
                        ],
                        source_path=f"generated://relation/{relation_id}",
                    )
                )
        relation_ids = {item.id for item in relations}
        for source in objects:
            for prop in source.properties:
                if not prop.name.endswith("_id"):
                    continue
                target = next(
                    (
                        item
                        for item in objects
                        if item.id != source.id and prop.name in item.primary_keys
                    ),
                    None,
                )
                if target is None:
                    continue
                relation_id = f"{source.id}_to_{target.id}"
                if relation_id in relation_ids:
                    continue
                relations.append(
                    RelationType(
                        id=relation_id,
                        name=f"{source.name} to {target.name}",
                        description=f"Generated by matching foreign key {prop.name}",
                        endpoint=RelationEndpoint(
                            source_object_type=source.id,
                            target_object_type=target.id,
                        ),
                        mappings=[
                            RelationMapping(source_property=prop.name, target_property=prop.name)
                        ],
                        source_path=f"generated://relation/{relation_id}",
                    )
                )
        return relations

    @staticmethod
    def _apply_enrichment(
        objects: list[ObjectType], relations: list[RelationType], value: dict[str, Any]
    ) -> tuple[list[ObjectType], list[RelationType]]:
        object_descriptions = value.get("object_descriptions", {})
        relation_descriptions = value.get("relation_descriptions", {})
        if not isinstance(object_descriptions, dict):
            object_descriptions = {}
        if not isinstance(relation_descriptions, dict):
            relation_descriptions = {}
        return (
            [
                item.model_copy(
                    update={"description": str(object_descriptions.get(item.id, item.description))}
                )
                for item in objects
            ],
            [
                item.model_copy(
                    update={
                        "description": str(relation_descriptions.get(item.id, item.description))
                    }
                )
                for item in relations
            ],
        )


def _object_id(resource: Resource) -> str:
    value = re.sub(r"_csv$", "", resource.id.lower())
    if value.endswith("ies"):
        value = f"{value[:-3]}y"
    elif value.endswith("s") and not value.endswith("ss"):
        value = value[:-1]
    return re.sub(r"[^a-z0-9_]+", "_", value).strip("_")


def _display_name(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_"))
