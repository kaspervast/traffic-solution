"""SQLAlchemy 2.0 models for the Rajkot AI Traffic Command Center.

Covers both the original schema (build spec section 8) and the SUMO
integration schema additions (build spec section H, SUMO-integrated
override). One models module is kept (rather than splitting original vs
SUMO) because they are heavily cross-referenced (e.g.
tomtom_sumo_edge_mappings joins road_segments <-> sumo_edges) and Alembic
autogenerate works more reliably against a single MetaData.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


def _created_at() -> Mapped[dt.datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# ---------------------------------------------------------------------------
# Original schema (spec section 8)
# ---------------------------------------------------------------------------


class AreaOfInterest(Base):
    __tablename__ = "areas_of_interest"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    center = mapped_column(Geography("POINT", srid=4326), nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    bbox_min_lat: Mapped[float] = mapped_column(Double, nullable=False)
    bbox_min_lon: Mapped[float] = mapped_column(Double, nullable=False)
    bbox_max_lat: Mapped[float] = mapped_column(Double, nullable=False)
    bbox_max_lon: Mapped[float] = mapped_column(Double, nullable=False)
    polygon = mapped_column(Geography("POLYGON", srid=4326), nullable=True)
    created_at: Mapped[dt.datetime] = _created_at()


class RoadSegment(Base):
    __tablename__ = "road_segments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="tomtom")
    provider_segment_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    road_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    road_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    direction: Mapped[str | None] = mapped_column(Text, nullable=True)
    length_m: Mapped[float | None] = mapped_column(Double, nullable=True)
    geom = mapped_column(Geography("LINESTRING", srid=4326), nullable=True)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[dt.datetime] = _created_at()
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProbePoint(Base):
    __tablename__ = "probe_points"
    __table_args__ = (
        CheckConstraint("priority IN ('high','medium','low')", name="ck_probe_points_priority"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    road_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("road_segments.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False, default="medium")
    geom = mapped_column(Geography("POINT", srid=4326), nullable=False)
    polling_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = _created_at()
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class TrafficFlowObservation(Base):
    __tablename__ = "traffic_flow_observations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    probe_point_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("probe_points.id"), nullable=True
    )
    road_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("road_segments.id"), nullable=True
    )
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="tomtom")
    current_speed_kmph: Mapped[float | None] = mapped_column(Double, nullable=True)
    free_flow_speed_kmph: Mapped[float | None] = mapped_column(Double, nullable=True)
    current_travel_time_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    free_flow_travel_time_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    speed_ratio: Mapped[float | None] = mapped_column(Double, nullable=True)
    delay_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Double, nullable=True)
    road_closure: Mapped[bool] = mapped_column(Boolean, default=False)
    geom = mapped_column(Geography("LINESTRING", srid=4326), nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[dt.datetime] = _created_at()


class TrafficIncident(Base):
    __tablename__ = "traffic_incidents"
    __table_args__ = (UniqueConstraint("provider", "provider_incident_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="tomtom")
    provider_incident_id: Mapped[str] = mapped_column(Text, nullable=False)
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    start_time: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_validity: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_category: Mapped[int | None] = mapped_column(Integer, nullable=True)
    magnitude_of_delay: Mapped[int | None] = mapped_column(Integer, nullable=True)
    probability_of_occurrence: Mapped[str | None] = mapped_column(Text, nullable=True)
    number_of_reports: Mapped[int | None] = mapped_column(Integer, nullable=True)
    from_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    road_numbers: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    length_m: Mapped[float | None] = mapped_column(Double, nullable=True)
    delay_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    geom = mapped_column(Geography(srid=4326), nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = _created_at()
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id: Mapped[uuid.UUID] = _uuid_pk()
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature_c: Mapped[float | None] = mapped_column(Double, nullable=True)
    humidity_percent: Mapped[float | None] = mapped_column(Double, nullable=True)
    rainfall_mm: Mapped[float | None] = mapped_column(Double, nullable=True)
    wind_speed_kmph: Mapped[float | None] = mapped_column(Double, nullable=True)
    visibility_m: Mapped[float | None] = mapped_column(Double, nullable=True)
    condition_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[dt.datetime] = _created_at()


class LocalEvent(Base):
    __tablename__ = "local_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    venue: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_crowd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    geom = mapped_column(Geography("POINT", srid=4326), nullable=True)
    event_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, default="manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = _created_at()


class TrafficAnomaly(Base):
    __tablename__ = "traffic_anomalies"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low','medium','high','critical')", name="ck_anomalies_severity"
        ),
        CheckConstraint(
            "status IN ('open','acknowledged','resolved','dismissed')",
            name="ck_anomalies_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    road_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("road_segments.id"), nullable=True
    )
    probe_point_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("probe_points.id"), nullable=True
    )
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Double, nullable=False)
    baseline_speed_kmph: Mapped[float | None] = mapped_column(Double, nullable=True)
    observed_speed_kmph: Mapped[float | None] = mapped_column(Double, nullable=True)
    delay_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    created_at: Mapped[dt.datetime] = _created_at()
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AIInsight(Base):
    __tablename__ = "ai_insights"
    __table_args__ = (
        CheckConstraint(
            "human_review_status IN ('pending','approved','rejected','needs_revision')",
            name="ck_ai_insights_review_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    anomaly_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("traffic_anomalies.id"), nullable=True
    )
    insight_type: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Double, nullable=True)
    human_review_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[dt.datetime] = _created_at()


class AlertChannel(Base):
    __tablename__ = "alert_channels"
    __table_args__ = (
        CheckConstraint(
            "channel_type IN ('email','sms','whatsapp','webhook')",
            name="ck_alert_channels_type",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    channel_type: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = _created_at()


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','approved','sent','failed','cancelled')",
            name="ck_alerts_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    anomaly_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("traffic_anomalies.id"), nullable=True
    )
    ai_insight_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_insights.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_at: Mapped[dt.datetime] = _created_at()
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(Text, nullable=True)


class CitizenReport(Base):
    __tablename__ = "citizen_reports"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('unverified','likely_valid','verified','rejected')",
            name="ck_citizen_reports_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    report_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    geom = mapped_column(Geography("POINT", srid=4326), nullable=True)
    reported_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_vision_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    verification_status: Mapped[str] = mapped_column(Text, nullable=False, default="unverified")
    created_at: Mapped[dt.datetime] = _created_at()


class AppUser(Base):
    """Minimal user table backing RBAC login (spec section 18: admin login,
    admin/operator/viewer roles). Not present as an explicit table in the
    spec's SQL listing, but required to make "Admin login" real rather than
    a stub with no persistence."""

    __tablename__ = "app_users"
    __table_args__ = (
        CheckConstraint("role IN ('admin','operator','viewer')", name="ck_app_users_role"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = _created_at()


# ---------------------------------------------------------------------------
# SUMO schema additions (spec section H)
# ---------------------------------------------------------------------------


class SumoNetwork(Base):
    __tablename__ = "sumo_networks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sumo_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="osm")
    bbox_min_lat: Mapped[float] = mapped_column(Double, nullable=False)
    bbox_min_lon: Mapped[float] = mapped_column(Double, nullable=False)
    bbox_max_lat: Mapped[float] = mapped_column(Double, nullable=False)
    bbox_max_lon: Mapped[float] = mapped_column(Double, nullable=False)
    net_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    osm_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[dt.datetime] = _created_at()


class SumoEdge(Base):
    __tablename__ = "sumo_edges"
    __table_args__ = (UniqueConstraint("network_id", "sumo_edge_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    network_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sumo_networks.id"), nullable=True
    )
    sumo_edge_id: Mapped[str] = mapped_column(Text, nullable=False)
    from_node: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_node: Mapped[str | None] = mapped_column(Text, nullable=True)
    road_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_lanes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    speed_mps: Mapped[float | None] = mapped_column(Double, nullable=True)
    length_m: Mapped[float | None] = mapped_column(Double, nullable=True)
    geom = mapped_column(Geography("LINESTRING", srid=4326), nullable=True)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[dt.datetime] = _created_at()


class TomTomSumoEdgeMapping(Base):
    __tablename__ = "tomtom_sumo_edge_mappings"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending','approved','rejected','manual_override')",
            name="ck_edge_mapping_review_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    road_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("road_segments.id"), nullable=True
    )
    sumo_edge_db_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sumo_edges.id"), nullable=True
    )
    match_method: Mapped[str] = mapped_column(Text, nullable=False, default="spatial_nearest")
    distance_m: Mapped[float | None] = mapped_column(Double, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Double, nullable=True)
    review_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[dt.datetime] = _created_at()
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SumoScenario(Base):
    __tablename__ = "sumo_scenarios"
    __table_args__ = (
        CheckConstraint(
            "human_review_status IN ('draft','approved','rejected')",
            name="ck_sumo_scenarios_review_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    aoi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas_of_interest.id"), nullable=True
    )
    network_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sumo_networks.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_review_status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_at: Mapped[dt.datetime] = _created_at()
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SumoSimulationRun(Base):
    __tablename__ = "sumo_simulation_runs"
    __table_args__ = (
        CheckConstraint("run_type IN ('baseline','scenario')", name="ck_sumo_run_type"),
        CheckConstraint(
            "status IN ('queued','preparing','running','completed','failed','cancelled')",
            name="ck_sumo_run_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sumo_scenarios.id"), nullable=True
    )
    baseline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sumo_simulation_runs.id"), nullable=True
    )
    run_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    run_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    sumocfg_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[dt.datetime] = _created_at()


class SumoRunMetrics(Base):
    __tablename__ = "sumo_run_metrics"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sumo_simulation_runs.id"), nullable=True
    )
    total_departed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_arrived: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_loaded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_ratio: Mapped[float | None] = mapped_column(Double, nullable=True)
    average_travel_time_sec: Mapped[float | None] = mapped_column(Double, nullable=True)
    average_waiting_time_sec: Mapped[float | None] = mapped_column(Double, nullable=True)
    average_time_loss_sec: Mapped[float | None] = mapped_column(Double, nullable=True)
    total_time_loss_sec: Mapped[float | None] = mapped_column(Double, nullable=True)
    average_speed_mps: Mapped[float | None] = mapped_column(Double, nullable=True)
    total_teleports: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metrics_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[dt.datetime] = _created_at()


class SumoEdgeMetrics(Base):
    __tablename__ = "sumo_edge_metrics"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sumo_simulation_runs.id"), nullable=True
    )
    sumo_edge_db_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sumo_edges.id"), nullable=True
    )
    begin_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mean_speed_mps: Mapped[float | None] = mapped_column(Double, nullable=True)
    density: Mapped[float | None] = mapped_column(Double, nullable=True)
    occupancy: Mapped[float | None] = mapped_column(Double, nullable=True)
    waiting_time_sec: Mapped[float | None] = mapped_column(Double, nullable=True)
    time_loss_sec: Mapped[float | None] = mapped_column(Double, nullable=True)
    departed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    arrived: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[dt.datetime] = _created_at()


class SumoScenarioComparison(Base):
    __tablename__ = "sumo_scenario_comparisons"

    id: Mapped[uuid.UUID] = _uuid_pk()
    baseline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sumo_simulation_runs.id"), nullable=True
    )
    scenario_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sumo_simulation_runs.id"), nullable=True
    )
    comparison_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    gemini_summary_insight_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_insights.id"), nullable=True
    )
    created_at: Mapped[dt.datetime] = _created_at()
