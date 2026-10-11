"""Parser for the intentionally small BKN Lang subset used by MiniBKN."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from minibkn.adapters.bkn_lang.validator import validate_network
from minibkn.domain.errors import BknParseError, ValidationIssue
from minibkn.domain.models import (
    ActionType,
    DataProperty,
    DataSourceBinding,
    DocumentType,
    KnowledgeNetwork,
    ObjectType,
    ParameterBinding,
    RelationEndpoint,
    RelationMapping,
    RelationType,
    RiskType,
    ToolBinding,
)

_FRONTMATTER = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|\Z)", re.DOTALL)
_HEADING_3 = re.compile(r"^###\s+.+$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    metadata: dict[str, Any]
    body: str
    source_path: str


class BknLangParser:
    """Load a BKN directory and return a validated aggregate."""

    def parse_directory(self, root: Path) -> KnowledgeNetwork:
        root = root.resolve()
        if not root.is_dir():
            raise BknParseError(f"BKN directory does not exist: {root}")

        files = sorted(root.rglob("*.bkn"))
        if not files:
            raise BknParseError(f"No .bkn documents found in {root}")

        documents = [self._read_document(path, root) for path in files]
        network_documents = [
            document
            for document in documents
            if document.metadata["type"] == DocumentType.KNOWLEDGE_NETWORK
        ]
        if len(network_documents) != 1:
            raise BknParseError(
                "A BKN directory must contain exactly one knowledge_network document",
                [
                    ValidationIssue(
                        path=str(root),
                        message=f"found {len(network_documents)} knowledge_network documents",
                    )
                ],
            )

        network_document = network_documents[0]
        object_types: list[ObjectType] = []
        relation_types: list[RelationType] = []
        action_types: list[ActionType] = []
        risk_types: list[RiskType] = []

        for document in documents:
            document_type = document.metadata["type"]
            if document_type == DocumentType.KNOWLEDGE_NETWORK:
                continue
            try:
                if document_type == DocumentType.OBJECT_TYPE:
                    object_types.append(self._parse_object_type(document))
                elif document_type == DocumentType.RELATION_TYPE:
                    relation_types.append(self._parse_relation_type(document))
                elif document_type == DocumentType.ACTION_TYPE:
                    action_types.append(self._parse_action_type(document))
                elif document_type == DocumentType.RISK_TYPE:
                    risk_types.append(self._parse_risk_type(document))
                else:  # pragma: no cover - guarded while reading frontmatter
                    raise BknParseError(f"Unsupported document type: {document_type}")
            except PydanticValidationError as exc:
                raise self._domain_model_error(document.source_path, exc) from exc

        metadata = network_document.metadata
        try:
            network = KnowledgeNetwork(
                id=self._required_text(metadata, "id", network_document.source_path),
                name=self._required_text(metadata, "name", network_document.source_path),
                description=self._description(network_document.body),
                tags=self._tags(metadata),
                business_domain=str(metadata.get("business_domain") or "default"),
                version=int(metadata.get("version") or 1),
                source_path=network_document.source_path,
                object_types=object_types,
                relation_types=relation_types,
                action_types=action_types,
                risk_types=risk_types,
            )
        except (PydanticValidationError, TypeError, ValueError) as exc:
            if isinstance(exc, PydanticValidationError):
                raise self._domain_model_error(network_document.source_path, exc) from exc
            raise BknParseError(
                f"Invalid knowledge_network metadata in {network_document.source_path}",
                [ValidationIssue(network_document.source_path, str(exc))],
            ) from exc
        validate_network(network)
        return network

    def _read_document(self, path: Path, root: Path) -> ParsedDocument:
        source_path = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8-sig")
        match = _FRONTMATTER.match(text)
        if not match:
            raise BknParseError(
                f"Missing or malformed YAML frontmatter in {source_path}",
                [ValidationIssue(path=source_path, message="expected a leading --- block")],
            )
        try:
            metadata = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            raise BknParseError(
                f"Invalid YAML frontmatter in {source_path}",
                [ValidationIssue(path=source_path, message=str(exc))],
            ) from exc
        if not isinstance(metadata, dict):
            raise BknParseError(f"Frontmatter must be an object in {source_path}")

        raw_type = self._required_text(metadata, "type", source_path)
        try:
            metadata["type"] = DocumentType(raw_type)
        except ValueError as exc:
            supported = ", ".join(item.value for item in DocumentType)
            raise BknParseError(
                f"Unsupported BKN document type '{raw_type}' in {source_path}",
                [ValidationIssue(path=source_path, message=f"supported types: {supported}")],
            ) from exc
        self._required_text(metadata, "id", source_path)
        self._required_text(metadata, "name", source_path)
        return ParsedDocument(metadata, text[match.end() :].strip(), source_path)

    def _parse_object_type(self, document: ParsedDocument) -> ObjectType:
        rows = self._table(document, "Data Properties", required=True)
        properties = [
            DataProperty(
                name=self._cell(row, "name", document.source_path),
                display_name=self._cell(row, "display name", document.source_path),
                value_type=self._cell(row, "type", document.source_path),
                description=row.get("description", ""),
                mapped_field=self._cell(row, "mapped field", document.source_path),
            )
            for row in rows
        ]

        keys_section = self._section(document.body, "Keys")
        primary_keys = self._key_values(keys_section, "Primary Keys")
        display_keys = self._key_values(keys_section, "Display Key")
        incremental_keys = self._key_values(keys_section, "Incremental Key")

        source_rows = self._table(document, "Data Source", required=False)
        data_source = None
        if source_rows:
            row = source_rows[0]
            data_source = DataSourceBinding(
                source_type=self._cell(row, "type", document.source_path),
                source_id=self._cell(row, "id", document.source_path),
                name=row.get("name", ""),
            )

        metadata = document.metadata
        return ObjectType(
            id=str(metadata["id"]),
            name=str(metadata["name"]),
            description=self._description(document.body),
            tags=self._tags(metadata),
            properties=properties,
            primary_keys=primary_keys,
            display_key=display_keys[0] if display_keys else "",
            incremental_key=incremental_keys[0] if incremental_keys else "",
            data_source=data_source,
            source_path=document.source_path,
        )

    def _parse_relation_type(self, document: ParsedDocument) -> RelationType:
        endpoint_rows = self._table(document, "Endpoint", required=True)
        endpoint_row = endpoint_rows[0]
        mapping_rows = self._table(document, "Mapping Rules", required=True)
        metadata = document.metadata
        return RelationType(
            id=str(metadata["id"]),
            name=str(metadata["name"]),
            description=self._description(document.body),
            tags=self._tags(metadata),
            endpoint=RelationEndpoint(
                source_object_type=self._cell(endpoint_row, "source", document.source_path),
                target_object_type=self._cell(endpoint_row, "target", document.source_path),
                relation_kind=endpoint_row.get("type", "direct") or "direct",
            ),
            mappings=[
                RelationMapping(
                    source_property=self._cell(row, "source property", document.source_path),
                    target_property=self._cell(row, "target property", document.source_path),
                )
                for row in mapping_rows
            ],
            source_path=document.source_path,
        )

    def _parse_action_type(self, document: ParsedDocument) -> ActionType:
        bound_rows = self._table(document, "Bound Object", required=True)
        tool_rows = self._table(document, "Tool Configuration", required=True)
        parameter_rows = self._table(document, "Parameter Binding", required=False)
        bound_row = bound_rows[0]
        tool_row = tool_rows[0]
        metadata = document.metadata
        trigger = self._yaml_code_block(document, "Trigger Condition")
        if isinstance(trigger.get("condition"), dict):
            trigger = trigger["condition"]
        return ActionType(
            id=str(metadata["id"]),
            name=str(metadata["name"]),
            description=self._description(document.body),
            tags=self._tags(metadata),
            action_kind=str(
                metadata.get("action_type") or bound_row.get("action type") or "modify"
            ),
            enabled=bool(metadata.get("enabled", True)),
            risk_level=str(metadata.get("risk_level") or "low"),
            requires_approval=bool(metadata.get("requires_approval", False)),
            bound_object_type=self._cell(bound_row, "bound object", document.source_path),
            trigger_condition=trigger,
            tool=ToolBinding(
                binding_type=self._cell(tool_row, "type", document.source_path),
                toolbox_id=self._cell(tool_row, "toolbox id", document.source_path),
                tool_id=self._cell(tool_row, "tool id", document.source_path),
            ),
            parameters=[
                ParameterBinding(
                    parameter=self._cell(row, "parameter", document.source_path),
                    source=self._cell(row, "source", document.source_path),
                    binding=self._cell(row, "binding", document.source_path),
                    description=row.get("description", ""),
                )
                for row in parameter_rows
            ],
            source_path=document.source_path,
        )

    def _parse_risk_type(self, document: ParsedDocument) -> RiskType:
        metadata = document.metadata
        raw_actions = metadata.get("applies_to_actions") or []
        if isinstance(raw_actions, str):
            raw_actions = [raw_actions]
        return RiskType(
            id=str(metadata["id"]),
            name=str(metadata["name"]),
            description=self._description(document.body),
            tags=self._tags(metadata),
            level=str(metadata.get("level") or "high"),
            policy=str(metadata.get("policy") or "confirm"),
            applies_to_actions=[str(value) for value in raw_actions],
            condition=self._risk_condition(metadata),
            source_path=document.source_path,
        )

    @staticmethod
    def _risk_condition(metadata: dict[str, Any]) -> dict[str, Any]:
        condition = metadata.get("condition")
        if isinstance(condition, dict):
            return condition
        if "value_threshold" in metadata:
            threshold = float(metadata["value_threshold"])
            return {
                "gte": [
                    {
                        "mul": [
                            {
                                "max": [
                                    0,
                                    {
                                        "sub": [
                                            {"ref": "object.safety_stock"},
                                            {"ref": "object.current_stock"},
                                        ]
                                    },
                                ]
                            },
                            {"ref": "object.unit_cost"},
                        ]
                    },
                    threshold,
                ]
            }
        return {"eq": [1, 1]}

    def _table(
        self, document: ParsedDocument, heading: str, *, required: bool
    ) -> list[dict[str, str]]:
        section = self._section(document.body, heading)
        lines = [line.strip() for line in section.splitlines() if line.strip()]
        table_start = next((index for index, line in enumerate(lines) if line.startswith("|")), -1)
        if table_start < 0 or table_start + 1 >= len(lines):
            if required:
                raise BknParseError(
                    f"Missing '{heading}' table in {document.source_path}",
                    [ValidationIssue(path=document.source_path, message=f"missing {heading}")],
                )
            return []

        headers = self._split_row(lines[table_start])
        separator = self._split_row(lines[table_start + 1])
        if len(separator) != len(headers) or not all(
            re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in separator
        ):
            raise BknParseError(f"Malformed '{heading}' table in {document.source_path}")

        rows: list[dict[str, str]] = []
        for line in lines[table_start + 2 :]:
            if not line.startswith("|"):
                break
            values = self._split_row(line)
            if len(values) != len(headers):
                raise BknParseError(
                    f"Column count mismatch in '{heading}' table in {document.source_path}"
                )
            rows.append(
                {
                    header.strip().lower(): value.strip()
                    for header, value in zip(headers, values, strict=True)
                }
            )
        if required and not rows:
            raise BknParseError(f"'{heading}' table is empty in {document.source_path}")
        return rows

    @staticmethod
    def _split_row(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    @staticmethod
    def _section(body: str, heading: str) -> str:
        match = re.search(rf"^###\s+{re.escape(heading)}\s*$", body, re.MULTILINE)
        if not match:
            return ""
        next_heading = _HEADING_3.search(body, match.end())
        end = next_heading.start() if next_heading else len(body)
        return body[match.end() : end].strip()

    def _yaml_code_block(self, document: ParsedDocument, heading: str) -> dict[str, Any]:
        section = self._section(document.body, heading)
        match = re.search(r"```ya?ml\s*(.*?)```", section, re.DOTALL | re.IGNORECASE)
        if not match:
            return {}
        try:
            value = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as exc:
            raise BknParseError(
                f"Invalid YAML block under '{heading}' in {document.source_path}"
            ) from exc
        if not isinstance(value, dict):
            raise BknParseError(
                f"YAML block under '{heading}' must be an object in {document.source_path}"
            )
        return value

    @staticmethod
    def _description(body: str) -> str:
        first_section = re.split(r"^###\s+", body, maxsplit=1, flags=re.MULTILINE)[0]
        lines = []
        for line in first_section.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append(stripped)
        return " ".join(lines)

    @staticmethod
    def _domain_model_error(source_path: str, exc: PydanticValidationError) -> BknParseError:
        issues = [
            ValidationIssue(
                path=f"{source_path}:{'.'.join(str(part) for part in error['loc'])}",
                message=error["msg"],
            )
            for error in exc.errors()
        ]
        return BknParseError(f"Invalid BKN document in {source_path}", issues)

    @staticmethod
    def _key_values(section: str, label: str) -> list[str]:
        match = re.search(rf"^{re.escape(label)}:\s*(.*)$", section, re.MULTILINE)
        if not match or not match.group(1).strip():
            return []
        return [value.strip() for value in match.group(1).split(",") if value.strip()]

    @staticmethod
    def _required_text(metadata: dict[str, Any], key: str, source_path: str) -> str:
        value = metadata.get(key)
        if value is None or not str(value).strip():
            raise BknParseError(
                f"Missing required frontmatter field '{key}' in {source_path}",
                [ValidationIssue(path=source_path, message=f"missing frontmatter.{key}")],
            )
        return str(value).strip()

    @staticmethod
    def _tags(metadata: dict[str, Any]) -> list[str]:
        tags = metadata.get("tags") or []
        if isinstance(tags, str):
            return [tags]
        return [str(tag) for tag in tags]

    @staticmethod
    def _cell(row: dict[str, str], column: str, source_path: str) -> str:
        value = row.get(column, "").strip()
        if not value:
            raise BknParseError(
                f"Required column '{column}' is empty in {source_path}",
                [ValidationIssue(path=source_path, message=f"empty column: {column}")],
            )
        return value
