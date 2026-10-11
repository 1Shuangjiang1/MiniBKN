"""Relational persistence schema for phase A metadata."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class KnowledgeNetworkRow(Base):
    __tablename__ = "knowledge_networks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_domain: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    documents: Mapped[list["BknDocumentRow"]] = relationship(
        back_populates="network", cascade="all, delete-orphan"
    )


class BknDocumentRow(Base):
    __tablename__ = "bkn_documents"
    __table_args__ = (UniqueConstraint("network_id", "document_type", "document_id"),)

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    network_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_networks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    document_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    network: Mapped[KnowledgeNetworkRow] = relationship(back_populates="documents")


class DataSourceRow(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ObjectInstanceRow(Base):
    __tablename__ = "object_instances"
    __table_args__ = (UniqueConstraint("network_id", "object_type_id", "instance_id"),)

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    network_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    object_type_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(512), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class RelationInstanceRow(Base):
    __tablename__ = "relation_instances"
    __table_args__ = (
        UniqueConstraint(
            "network_id", "relation_type_id", "source_instance_id", "target_instance_id"
        ),
    )

    row_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    network_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    relation_type_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_object_type_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_instance_id: Mapped[str] = mapped_column(String(512), nullable=False)
    target_object_type_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_instance_id: Mapped[str] = mapped_column(String(512), nullable=False)


class SearchDocumentRow(Base):
    __tablename__ = "search_documents"

    id: Mapped[str] = mapped_column(String(512), primary_key=True)
    network_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    citation: Mapped[str] = mapped_column(String(1024), nullable=False)
    vector: Mapped[list[float]] = mapped_column(JSON, nullable=False)


class SearchIndexManifestRow(Base):
    __tablename__ = "search_index_manifests"

    network_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    embedding_version: Mapped[str] = mapped_column(String(512), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BuildJobRow(Base):
    __tablename__ = "build_jobs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    network_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelingSessionRow(Base):
    __tablename__ = "modeling_sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    network_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ActionExecutionRow(Base):
    __tablename__ = "action_executions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    network_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action_type_id: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type_id: Mapped[str] = mapped_column(String(128), nullable=False)
    instance_id: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TraceEventRow(Base):
    __tablename__ = "trace_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
