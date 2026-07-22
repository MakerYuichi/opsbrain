"""
ORM models for Industrial Knowledge Intelligence Platform.
All tables created via init_db() in database.py.
"""
import json
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Float, DateTime, Integer,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database import Base


class Asset(Base):
    __tablename__ = "assets"

    asset_id  = Column(String, primary_key=True)   # e.g. "ST-11"
    name      = Column(String, nullable=False)
    type      = Column(String, nullable=False)      # tank, pump, sensor, ladle, …
    location  = Column(String)
    _aliases  = Column("aliases", Text, default="[]")   # JSON list

    @property
    def aliases(self):
        return json.loads(self._aliases or "[]")

    @aliases.setter
    def aliases(self, v):
        self._aliases = json.dumps(v)

    facts = relationship("Fact", back_populates="asset", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    doc_id      = Column(String, primary_key=True)
    type        = Column(String)          # maintenance_log, shift_log, permit, oem_manual, …
    source_path = Column(String)
    upload_date = Column(DateTime, default=datetime.utcnow)
    raw_text    = Column(Text)

    facts = relationship("Fact", back_populates="document", cascade="all, delete-orphan")


class Fact(Base):
    __tablename__ = "facts"

    fact_id     = Column(String, primary_key=True)
    doc_id      = Column(String, ForeignKey("documents.doc_id"), nullable=False)
    asset_id    = Column(String, ForeignKey("assets.asset_id"), nullable=True)
    fact_type   = Column(String, nullable=False)   # TEMPERATURE_READING, MAINTENANCE_ACTION, …
    timestamp   = Column(DateTime, nullable=True)
    content     = Column(Text, nullable=False)
    source_span = Column(Text)        # JSON {"start": int, "end": int, "text": str}
    confidence  = Column(Float, default=1.0)

    document = relationship("Document", back_populates="facts")
    asset    = relationship("Asset",    back_populates="facts")

    __table_args__ = (
        Index("ix_facts_asset_ts", "asset_id", "timestamp"),
        Index("ix_facts_doc",      "doc_id"),
        Index("ix_facts_type",     "fact_type"),
    )


class Edge(Base):
    __tablename__ = "edges"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    from_id      = Column(String, nullable=False)   # asset_id or doc_id
    to_id        = Column(String, nullable=False)
    relation_type = Column(String, nullable=False)  # SHARES_ASSET, TEMPORAL_OVERLAP, …
    source_fact_id = Column(String, ForeignKey("facts.fact_id"), nullable=True)
    weight       = Column(Float, default=1.0)

    __table_args__ = (
        Index("ix_edges_from", "from_id"),
        Index("ix_edges_to",   "to_id"),
        UniqueConstraint("from_id", "to_id", "relation_type", name="uq_edge"),
    )


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    asset_id  = Column(String, ForeignKey("assets.asset_id"), nullable=False)
    sensor_id = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    metric    = Column(String, nullable=False)   # temperature, argon_flow, …
    value     = Column(Float, nullable=True)     # NULL when FAULT
    unit      = Column(String)
    status    = Column(String)                   # OK / FAULT / MANUAL_READ / WARN / …
    notes     = Column(Text)

    __table_args__ = (
        Index("ix_sr_asset_ts", "asset_id", "timestamp"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    alert_id        = Column(String, primary_key=True)
    asset_id        = Column(String, ForeignKey("assets.asset_id"), nullable=True)
    pattern_type    = Column(String, nullable=False)
    description     = Column(Text)
    confidence      = Column(Float, default=1.0)
    _source_fact_ids = Column("source_fact_ids", Text, default="[]")  # JSON list
    created_at      = Column(DateTime, default=datetime.utcnow)

    @property
    def source_fact_ids(self):
        return json.loads(self._source_fact_ids or "[]")

    @source_fact_ids.setter
    def source_fact_ids(self, v):
        self._source_fact_ids = json.dumps(v)
