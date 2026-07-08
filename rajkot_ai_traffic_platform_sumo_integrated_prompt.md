# Build Prompt: AI-Native Traffic Intelligence & Urban Mobility Platform — SUMO Integrated

> This is the SUMO-integrated version. It includes the original Rajkot/TomTom/Gemini prompt plus mandatory SUMO integration requirements. Where sections conflict, the SUMO-integrated override sections at the end take priority.

# Build Prompt: AI-Native Traffic Intelligence & Urban Mobility Platform

## Project Name
**Rajkot AI Traffic Command Center — MVP**

## Target Area
Build the MVP for a small pilot zone in **Rajkot City, Gujarat, India**.

- Center latitude: `22.329077`
- Center longitude: `70.769564`
- Pilot radius: `1 km`
- Approximate MVP bounding box:
  - `minLat = 22.320094`
  - `maxLat = 22.338060`
  - `minLon = 70.759854`
  - `maxLon = 70.779274`
- TomTom incident bbox format: `minLon,minLat,maxLon,maxLat`
  - `70.759854,22.320094,70.779274,22.338060`

Do not claim city-wide coverage. This is a 1 km-radius pilot only.

---

# 1. Role for the AI Builder

Act as a **Senior AI Architect, Urban Mobility Specialist, GIS Engineer, Backend Engineer, Frontend Engineer, and DevOps Lead**.

Design and build a cloud-ready but locally runnable MVP for a next-generation traffic intelligence platform. The system must be better than simple tools that only poll map APIs and display heatmaps. It must include baseline traffic analytics plus an **AI-first command center** using Gemini models.

The build must be practical for a solo/beginner developer but designed so it can later scale to a full city.

---

# 2. Core Objective

Create a working MVP that ingests live traffic data from **TomTom APIs**, stores spatial/time-series data in **PostgreSQL + PostGIS**, detects congestion anomalies, generates AI-assisted root-cause explanations, drafts mitigation actions, and provides a dashboard for city officials.

The platform must initially work without physical sensors or cameras.

---

# 3. Non-Negotiable Requirements

1. Use **TomTom API** as the primary traffic data source.
2. Use a **1 km pilot radius** around `22.329077,70.769564`.
3. Poll traffic data approximately every **2 minutes**, but implement adaptive polling to control cost.
4. Use **FastAPI** for backend APIs.
5. Use **PostgreSQL + PostGIS** for geospatial data.
6. Use **Redis** for cache, rate-limit coordination, and job state.
7. Use **Next.js** for frontend dashboard.
8. Use **Gemini API** for AI-generated explanations, predictive alerts, and mitigation drafts.
9. Do not let Gemini directly control signals or dispatch. Gemini only drafts recommendations. Human approval is mandatory.
10. All AI responses must include confidence score, evidence, assumptions, and recommended human review steps.
11. Store both normalized traffic data and raw API responses for audit/debugging.
12. The MVP must run locally using Docker Compose.

---

# 4. TomTom API Usage

## 4.1 APIs to Use

### A. Traffic Flow Segment Data
Use for speed/current travel time/free-flow travel time at selected probe points.

Endpoint pattern:

```text
GET https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?key={TOMTOM_API_KEY}&point={lat},{lon}&unit=kmph&openLr=false
```

Expected data to normalize:

- `currentSpeed`
- `freeFlowSpeed`
- `currentTravelTime`
- `freeFlowTravelTime`
- `confidence`
- `roadClosure`
- `coordinates`

### B. Traffic Incident Details v5
Use for jams, accidents, lane closures, road works, flooding, broken-down vehicles, and future/present incidents within the pilot bounding box.

Endpoint pattern:

```text
GET https://api.tomtom.com/traffic/services/5/incidentDetails?key={TOMTOM_API_KEY}&bbox=70.759854,22.320094,70.779274,22.338060&fields={incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,events{description,code,iconCategory},startTime,endTime,from,to,length,delay,roadNumbers,timeValidity,probabilityOfOccurrence,numberOfReports,lastReportTime}}}&language=en-GB&timeValidityFilter=present,future
```

### C. Optional Later APIs
Use only after MVP works:

- TomTom Routing API for reroute suggestions.
- TomTom Search/Reverse Geocoding for road names and POI context.
- TomTom Matrix Routing for route impact comparisons.
- TomTom Traffic Stats / historical services if account supports them.

---

# 5. Data Ingestion Strategy

## 5.1 Important Cost Rule
Do **not** poll a dense grid. Poll only selected road probe points.

For a 1 km radius MVP:

- Start with `15–30` active probe points.
- Each probe point should sit close to an important road segment or junction.
- Poll every 2 minutes during active traffic hours.
- Poll every 5–10 minutes late night if traffic is stable.
- Poll incident bbox every 2 minutes.
- Cache duplicate responses.
- Deduplicate same road segment results where multiple probe points map to the same road fragment.

Daily call estimate:

```text
Flow calls/day = active_probe_points × polls_per_day
If 20 probe points and 2-minute polling:
20 × 720 = 14,400 flow calls/day

Incident calls/day:
1 bbox × 720 = 720 incident calls/day
```

Before production, compare this estimate with your TomTom account quota/pricing.

## 5.2 Probe Point Strategy

Build an admin UI where the operator can add/edit/delete probe points.

Each probe point should have:

- Name
- Latitude
- Longitude
- Priority: `high`, `medium`, `low`
- Polling interval override
- Nearby junction/road label
- Active/inactive status

Initial seed generation:

1. Create the 1 km radius polygon in PostGIS.
2. Add 15–30 manual probe points through admin UI.
3. Call TomTom Flow Segment Data for each point.
4. Store returned road coordinates.
5. Deduplicate points that resolve to the same TomTom road segment.
6. Keep the most useful points based on road coverage.

## 5.3 Adaptive Polling Rules

Default intervals:

| Condition | Poll Interval |
|---|---:|
| Severe congestion active | 1–2 min |
| Normal daytime | 2 min |
| Stable/no anomaly for 30 min | 5 min |
| Night low-traffic period | 10 min |
| TomTom rate-limit warning/error | exponential backoff |

Never hammer the API after failure. Apply retry with jitter.

## 5.4 External Data Sources

MVP phase:

- Weather: Open-Meteo, OpenWeather, IMD source, or any selected weather API.
- Events: Manual local event calendar table first.
- Citizen reports: Manual image/text upload first.

Later phase:

- X/Twitter API or official city social feed.
- Police/citizen app reports.
- Roadwork permits.
- School/college timing data.
- Emergency incident feeds.

---

# 6. Architecture

## 6.1 High-Level Components

```text
[TomTom APIs]           [Weather API]        [Manual Events]
      |                      |                    |
      v                      v                    v
[Ingestion Worker] ---> [Redis Queue/Cache] ---> [FastAPI Backend]
      |                                           |
      v                                           v
[PostgreSQL + PostGIS + Timescale-style tables]  [Gemini AI Service]
      |                                           |
      v                                           v
[Analytics/Forecast Engine] ----------------> [AI Insights]
      |
      v
[Next.js Dashboard + Map + Command Center]
      |
      v
[WhatsApp/SMS/Email Alert Integrations]
```

## 6.2 Recommended Tech Stack

### Frontend

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui or MUI
- Leaflet, MapLibre GL, or TomTom Maps SDK
- TanStack Query for API state
- Recharts or ECharts for charts
- WebSocket/SSE for live updates

### Backend

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2 or SQLModel
- Alembic migrations
- asyncpg / psycopg
- APScheduler, Celery, Dramatiq, or RQ for polling jobs
- Redis for cache and queues
- httpx for async API calls
- tenacity for retry/backoff

### Database

- PostgreSQL 16+
- PostGIS extension
- Optional: TimescaleDB for time-series optimization

### AI Layer

- Gemini API via `google-genai`
- Recommended model routing:
  - `gemini-3.5-flash` for fast structured alerts, summaries, report generation, command center answers.
  - `gemini-3.1-pro-preview` or latest available Gemini Pro model for complex what-if planning, long reasoning, and multi-step urban planning analysis.
  - Use the latest stable Gemini embedding model available in the account for retrieval over reports/incidents.

### Cloud-Ready Deployment Later

- Google Cloud Run for FastAPI and worker containers.
- Cloud SQL PostgreSQL + PostGIS.
- Memorystore Redis.
- Cloud Scheduler for periodic jobs.
- Pub/Sub for event-driven ingestion.
- Secret Manager for API keys.
- Cloud Storage for report PDFs/images.

For MVP, Docker Compose is enough.

---

# 7. Monorepo Structure

Create this repository structure:

```text
rajkot-ai-traffic/
  README.md
  .env.example
  docker-compose.yml
  apps/
    web/
      package.json
      next.config.js
      src/
        app/
        components/
        lib/
        types/
  services/
    api/
      pyproject.toml
      alembic.ini
      app/
        main.py
        core/
          config.py
          security.py
          logging.py
        db/
          session.py
          models.py
          migrations/
        routers/
          health.py
          aoi.py
          traffic.py
          incidents.py
          anomalies.py
          ai.py
          reports.py
          alerts.py
        services/
          tomtom_client.py
          weather_client.py
          ingestion_service.py
          anomaly_service.py
          forecast_service.py
          gemini_service.py
          alert_service.py
          report_service.py
        schemas/
          traffic.py
          ai.py
          reports.py
        jobs/
          poll_tomtom.py
          daily_report.py
        tests/
    worker/
      app/
        worker.py
        tasks.py
  infra/
    nginx/
    postgres/
  docs/
    architecture.md
    api_contract.md
    data_dictionary.md
    ai_prompting.md
```

---

# 8. Database Schema

Use migrations. The following is the core schema.

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE areas_of_interest (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    center GEOGRAPHY(Point, 4326) NOT NULL,
    radius_m INTEGER NOT NULL DEFAULT 1000,
    bbox_min_lat DOUBLE PRECISION NOT NULL,
    bbox_min_lon DOUBLE PRECISION NOT NULL,
    bbox_max_lat DOUBLE PRECISION NOT NULL,
    bbox_max_lon DOUBLE PRECISION NOT NULL,
    polygon GEOGRAPHY(Polygon, 4326),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE road_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id UUID REFERENCES areas_of_interest(id),
    provider TEXT NOT NULL DEFAULT 'tomtom',
    provider_segment_key TEXT,
    road_name TEXT,
    road_class TEXT,
    direction TEXT,
    length_m DOUBLE PRECISION,
    geom GEOGRAPHY(LineString, 4326),
    raw JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_road_segments_geom ON road_segments USING GIST (geom);
CREATE INDEX idx_road_segments_provider_key ON road_segments(provider, provider_segment_key);

CREATE TABLE probe_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id UUID REFERENCES areas_of_interest(id),
    road_segment_id UUID REFERENCES road_segments(id),
    name TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('high','medium','low')),
    geom GEOGRAPHY(Point, 4326) NOT NULL,
    polling_interval_seconds INTEGER NOT NULL DEFAULT 120,
    is_active BOOLEAN NOT NULL DEFAULT true,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_probe_points_geom ON probe_points USING GIST (geom);
CREATE INDEX idx_probe_points_active ON probe_points(is_active, priority);

CREATE TABLE traffic_flow_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    probe_point_id UUID REFERENCES probe_points(id),
    road_segment_id UUID REFERENCES road_segments(id),
    observed_at TIMESTAMPTZ NOT NULL,
    provider TEXT NOT NULL DEFAULT 'tomtom',
    current_speed_kmph DOUBLE PRECISION,
    free_flow_speed_kmph DOUBLE PRECISION,
    current_travel_time_sec INTEGER,
    free_flow_travel_time_sec INTEGER,
    speed_ratio DOUBLE PRECISION,
    delay_sec INTEGER,
    confidence DOUBLE PRECISION,
    road_closure BOOLEAN DEFAULT false,
    geom GEOGRAPHY(LineString, 4326),
    raw JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_flow_observed_at ON traffic_flow_observations(observed_at DESC);
CREATE INDEX idx_flow_probe_time ON traffic_flow_observations(probe_point_id, observed_at DESC);
CREATE INDEX idx_flow_geom ON traffic_flow_observations USING GIST (geom);

CREATE TABLE traffic_incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL DEFAULT 'tomtom',
    provider_incident_id TEXT NOT NULL,
    aoi_id UUID REFERENCES areas_of_interest(id),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    time_validity TEXT,
    category TEXT,
    icon_category INTEGER,
    magnitude_of_delay INTEGER,
    probability_of_occurrence TEXT,
    number_of_reports INTEGER,
    from_text TEXT,
    to_text TEXT,
    road_numbers TEXT[],
    length_m DOUBLE PRECISION,
    delay_sec INTEGER,
    description TEXT,
    geom GEOGRAPHY(Geometry, 4326),
    raw JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(provider, provider_incident_id)
);

CREATE INDEX idx_incidents_active ON traffic_incidents(is_active, last_seen_at DESC);
CREATE INDEX idx_incidents_geom ON traffic_incidents USING GIST (geom);

CREATE TABLE weather_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id UUID REFERENCES areas_of_interest(id),
    observed_at TIMESTAMPTZ NOT NULL,
    temperature_c DOUBLE PRECISION,
    humidity_percent DOUBLE PRECISION,
    rainfall_mm DOUBLE PRECISION,
    wind_speed_kmph DOUBLE PRECISION,
    visibility_m DOUBLE PRECISION,
    condition_text TEXT,
    raw JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_weather_time ON weather_snapshots(observed_at DESC);

CREATE TABLE local_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id UUID REFERENCES areas_of_interest(id),
    title TEXT NOT NULL,
    venue TEXT,
    expected_crowd INTEGER,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ,
    geom GEOGRAPHY(Point, 4326),
    event_type TEXT,
    source TEXT DEFAULT 'manual',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_events_time ON local_events(starts_at, ends_at);
CREATE INDEX idx_events_geom ON local_events USING GIST (geom);

CREATE TABLE traffic_anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id UUID REFERENCES areas_of_interest(id),
    road_segment_id UUID REFERENCES road_segments(id),
    probe_point_id UUID REFERENCES probe_points(id),
    detected_at TIMESTAMPTZ NOT NULL,
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    score DOUBLE PRECISION NOT NULL,
    baseline_speed_kmph DOUBLE PRECISION,
    observed_speed_kmph DOUBLE PRECISION,
    delay_sec INTEGER,
    evidence JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','resolved','dismissed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_anomalies_time ON traffic_anomalies(detected_at DESC);
CREATE INDEX idx_anomalies_status ON traffic_anomalies(status, severity);

CREATE TABLE ai_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id UUID REFERENCES areas_of_interest(id),
    anomaly_id UUID REFERENCES traffic_anomalies(id),
    insight_type TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    input_payload JSONB NOT NULL,
    output_payload JSONB NOT NULL,
    confidence DOUBLE PRECISION,
    human_review_status TEXT NOT NULL DEFAULT 'pending' CHECK (human_review_status IN ('pending','approved','rejected','needs_revision')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_insights_type_time ON ai_insights(insight_type, created_at DESC);

CREATE TABLE alert_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    channel_type TEXT NOT NULL CHECK (channel_type IN ('email','sms','whatsapp','webhook')),
    config JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id UUID REFERENCES areas_of_interest(id),
    anomaly_id UUID REFERENCES traffic_anomalies(id),
    ai_insight_id UUID REFERENCES ai_insights(id),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','sent','failed','cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ
);

CREATE TABLE citizen_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id UUID REFERENCES areas_of_interest(id),
    source TEXT NOT NULL DEFAULT 'manual',
    report_type TEXT,
    description TEXT,
    image_url TEXT,
    geom GEOGRAPHY(Point, 4326),
    reported_at TIMESTAMPTZ,
    ai_vision_payload JSONB,
    verification_status TEXT NOT NULL DEFAULT 'unverified' CHECK (verification_status IN ('unverified','likely_valid','verified','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_citizen_reports_geom ON citizen_reports USING GIST (geom);
```

---

# 9. Anomaly Detection Logic

Do not rely only on Gemini for anomaly detection. Use deterministic logic first.

Calculate:

```text
speed_ratio = current_speed_kmph / free_flow_speed_kmph
travel_time_delay_sec = current_travel_time_sec - free_flow_travel_time_sec
```

Severity rules:

| Rule | Severity |
|---|---|
| roadClosure = true | critical |
| speed_ratio <= 0.25 and delay >= 600 sec | critical |
| speed_ratio <= 0.40 and delay >= 300 sec | high |
| speed_ratio <= 0.60 and delay >= 120 sec | medium |
| speed_ratio <= 0.75 | low |
| otherwise | normal |

Also compare against historical baseline for the same road/time/day once enough data exists.

Minimum anomaly evidence:

```json
{
  "probe_point_id": "uuid",
  "observed_at": "ISO timestamp",
  "current_speed_kmph": 11.5,
  "free_flow_speed_kmph": 42.0,
  "speed_ratio": 0.27,
  "delay_sec": 480,
  "confidence": 0.91,
  "nearby_incidents": [],
  "weather": {},
  "local_events": []
}
```

---

# 10. AI Features

## 10.1 Conversational Command Center

Officials can ask:

- “What is causing delay in this area right now?”
- “Summarize yesterday evening peak congestion.”
- “Which road segment has repeated bottlenecks?”
- “Draft an advisory for citizens.”
- “What should police deployment focus on for the next 2 hours?”

Implementation rule:

Gemini must not answer directly from memory. The backend must first retrieve relevant database facts, then pass only factual context to Gemini.

Command workflow:

1. User asks question.
2. Backend classifies intent.
3. Backend runs SQL/PostGIS query.
4. Backend builds grounded context packet.
5. Gemini generates answer with evidence.
6. Store prompt/input/output in `ai_insights`.

## 10.2 Predictive Congestion Forecasting

MVP forecasting approach:

1. Use rolling traffic history from last 30/60/120 minutes.
2. Add same-time historical averages when enough data exists.
3. Add current weather.
4. Add event proximity and expected crowd.
5. Detect rising delay trend.
6. Ask Gemini to generate structured prediction and mitigation plan.

Do not claim accurate ML prediction until enough historical data is collected. In the first 2–4 weeks, call it **risk forecasting**, not a trained traffic model.

## 10.3 Automated Incident Mitigation Drafts

Gemini should draft:

- Problem summary
- Likely root cause
- Impacted roads/segments
- Recommended police deployment points
- Suggested citizen advisory
- Suggested reroutes if routing API data is available
- Suggested signal timing change as a draft only
- Escalation priority

Never auto-publish. Human approval required.

## 10.4 Generative Urban Planning / What-If Analysis

MVP version:

- Not a real microscopic simulation.
- Use heuristic scenario analysis based on observed speed/delay and road importance.
- Output assumptions clearly.

Phase 2:

- Integrate SUMO.
- Build or import road network.
- Simulate road closure, one-way conversion, signal timing changes.
- Compare baseline vs scenario travel time, queue length, throughput.

## 10.5 Multi-Modal Citizen Feedback

MVP version:

- Manual citizen report upload: image + description + location.
- Gemini Vision classifies issue type: accident, pothole, flooding, obstruction, roadwork, crowding, other.
- Correlate report location with nearby flow slowdown within 200–500 meters and 30 minutes.

Phase 2:

- X/Twitter ingestion if API/legal access exists.
- WhatsApp citizen bot.
- Mobile app.

---

# 11. Backend API Contract

Build these endpoints.

```text
GET  /health
GET  /api/aoi/current
POST /api/probe-points
GET  /api/probe-points
PATCH /api/probe-points/{id}
DELETE /api/probe-points/{id}

POST /api/ingestion/run-now
GET  /api/traffic/live
GET  /api/traffic/history?probe_point_id=&from=&to=
GET  /api/incidents/live
GET  /api/anomalies/open
PATCH /api/anomalies/{id}/status

POST /api/ai/predictive-alert
POST /api/ai/command
POST /api/ai/mitigation-draft
POST /api/ai/citizen-report-vision

GET  /api/reports/daily?date=YYYY-MM-DD
GET  /api/reports/weekly?week_start=YYYY-MM-DD
POST /api/alerts/{id}/approve
POST /api/alerts/{id}/send
```

---

# 12. Frontend Requirements

Build dashboard pages:

## 12.1 Live Map

- Show 1 km pilot area circle/polygon.
- Show probe points.
- Show traffic segment color by severity.
- Show incident markers.
- Show active anomaly cards.
- Auto-refresh every 30–60 seconds.

## 12.2 Command Center

- Natural language query box.
- Suggested questions.
- AI answer with evidence table.
- Confidence score.
- “Copy advisory” button.
- “Create alert draft” button.

## 12.3 Anomaly Monitor

- Open anomalies table.
- Severity filters.
- Timeline chart.
- Acknowledge/resolve buttons.

## 12.4 Reports

- Daily summary.
- Weekly summary.
- Peak hour bottlenecks.
- Top repeated congestion locations.
- Export to PDF/CSV.

## 12.5 Admin

- Manage probe points.
- Manage local events.
- Manage alert channels.
- API polling status.
- Last successful TomTom poll.

---

# 13. Core AI Python Script

Create a file:

```text
services/api/app/services/gemini_predictive_alert.py
```

Use this production-ready base script.

```python
"""
Gemini predictive traffic alert service.

Install:
    pip install google-genai pydantic tenacity

Environment:
    export GEMINI_API_KEY="your_key"
    export GEMINI_MODEL="gemini-3.5-flash"

Purpose:
    Takes normalized traffic anomalies, weather, and local events.
    Returns a structured predictive alert and mitigation strategy.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Literal

from google import genai
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

logger = logging.getLogger(__name__)


Severity = Literal["low", "medium", "high", "critical"]
RiskLevel = Literal["low", "medium", "high", "critical"]


class TrafficAnomaly(BaseModel):
    anomaly_id: str | None = None
    road_name: str | None = None
    probe_name: str | None = None
    lat: float | None = None
    lon: float | None = None
    detected_at: datetime
    anomaly_type: str
    severity: Severity
    current_speed_kmph: float | None = None
    free_flow_speed_kmph: float | None = None
    speed_ratio: float | None = None
    delay_sec: int | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    nearby_incidents: list[dict[str, Any]] = Field(default_factory=list)


class WeatherSnapshot(BaseModel):
    observed_at: datetime
    condition_text: str | None = None
    temperature_c: float | None = None
    rainfall_mm: float | None = None
    humidity_percent: float | None = None
    wind_speed_kmph: float | None = None
    visibility_m: float | None = None


class LocalEvent(BaseModel):
    title: str
    venue: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    expected_crowd: int | None = None
    distance_from_anomaly_m: float | None = None
    event_type: str | None = None


class PredictiveAlertInput(BaseModel):
    generated_at: datetime
    aoi_name: str = "Rajkot 1 km pilot zone"
    center_lat: float = 22.329077
    center_lon: float = 70.769564
    forecast_horizon_minutes: int = Field(default=120, ge=15, le=360)
    anomalies: list[TrafficAnomaly]
    weather: WeatherSnapshot | None = None
    local_events: list[LocalEvent] = Field(default_factory=list)
    operator_notes: str | None = None


class MitigationAction(BaseModel):
    action_type: Literal[
        "police_deployment",
        "citizen_advisory",
        "reroute_suggestion",
        "signal_timing_review",
        "field_verification",
        "monitor_only",
        "other",
    ]
    priority: Literal["low", "medium", "high", "urgent"]
    action: str
    location_hint: str | None = None
    reason: str
    requires_human_approval: bool = True


class PredictiveAlertOutput(BaseModel):
    alert_title: str
    risk_level: RiskLevel
    forecast_window: str
    predicted_impact_summary: str
    likely_root_causes: list[str]
    affected_locations: list[str]
    evidence: list[str]
    mitigation_actions: list[MitigationAction]
    citizen_message_draft: str
    police_control_room_summary: str
    confidence_score: float = Field(ge=0, le=1)
    assumptions: list[str]
    missing_data: list[str]
    human_review_required: bool = True


SYSTEM_INSTRUCTION = """
You are an AI traffic operations analyst for a city traffic command center.
You must produce operationally useful but conservative recommendations.
Use only the provided JSON facts. Do not invent incidents, road names, weather, events, or official actions.
Signal timing, route diversion, police deployment, and public advisories are recommendations only and require human approval.
If evidence is weak, lower the confidence score and list missing data.
Return valid JSON matching the required schema.
""".strip()


class GeminiPredictiveAlertService:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        self.client = genai.Client(api_key=self.api_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def generate_alert(self, payload: dict[str, Any]) -> PredictiveAlertOutput:
        try:
            validated_input = PredictiveAlertInput.model_validate(payload)
        except ValidationError as exc:
            logger.exception("Invalid predictive alert input")
            raise ValueError(f"Invalid predictive alert input: {exc}") from exc

        prompt = self._build_prompt(validated_input)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "system_instruction": SYSTEM_INSTRUCTION,
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "response_json_schema": PredictiveAlertOutput.model_json_schema(),
            },
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty response")

        try:
            parsed = json.loads(response.text)
            return PredictiveAlertOutput.model_validate(parsed)
        except Exception as exc:
            logger.error("Raw Gemini response: %s", response.text)
            raise RuntimeError("Failed to parse Gemini structured output") from exc

    def _build_prompt(self, data: PredictiveAlertInput) -> str:
        compact_json = data.model_dump_json(indent=2)
        return f"""
Analyze the following live traffic operations packet for the Rajkot 1 km pilot zone.

Tasks:
1. Predict congestion risk for the next {data.forecast_horizon_minutes} minutes.
2. Identify likely root causes using only supplied anomalies, incidents, weather, and events.
3. Draft mitigation actions suitable for traffic police/city officials.
4. Draft a short citizen advisory.
5. State confidence, assumptions, and missing data.

Input JSON:
{compact_json}
""".strip()


if __name__ == "__main__":
    sample_payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "forecast_horizon_minutes": 120,
        "anomalies": [
            {
                "anomaly_id": "demo-001",
                "road_name": "Unknown road segment - probe A",
                "probe_name": "Probe A",
                "lat": 22.329077,
                "lon": 70.769564,
                "detected_at": datetime.utcnow().isoformat() + "Z",
                "anomaly_type": "slowdown",
                "severity": "high",
                "current_speed_kmph": 12.0,
                "free_flow_speed_kmph": 42.0,
                "speed_ratio": 0.28,
                "delay_sec": 420,
                "confidence": 0.88,
                "nearby_incidents": [],
            }
        ],
        "weather": {
            "observed_at": datetime.utcnow().isoformat() + "Z",
            "condition_text": "clear",
            "temperature_c": 31.0,
            "rainfall_mm": 0.0,
            "humidity_percent": 50,
            "wind_speed_kmph": 8,
        },
        "local_events": [],
        "operator_notes": "Demo run. Road name not yet verified.",
    }

    service = GeminiPredictiveAlertService()
    alert = service.generate_alert(sample_payload)
    print(alert.model_dump_json(indent=2))
```

---

# 14. FastAPI Gemini Service Integration

Create route:

```python
from fastapi import APIRouter, HTTPException
from app.services.gemini_predictive_alert import GeminiPredictiveAlertService

router = APIRouter(prefix="/api/ai", tags=["AI"])

@router.post("/predictive-alert")
def predictive_alert(payload: dict):
    try:
        service = GeminiPredictiveAlertService()
        result = service.generate_alert(payload)
        return result.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

Before calling this route from frontend, backend should build the payload from database queries, not from user-provided free text.

---

# 15. TomTom Client Requirements

Create `tomtom_client.py` with:

- async `httpx.AsyncClient`
- retry/backoff
- timeout
- request logging without exposing API key
- normalized response models
- raw response preservation
- rate limit handling

Required methods:

```python
async def get_flow_segment(lat: float, lon: float) -> dict: ...
async def get_incidents_for_bbox(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict: ...
```

Normalization must convert TomTom fields into internal fields:

```python
normalized = {
    "current_speed_kmph": raw.get("flowSegmentData", {}).get("currentSpeed"),
    "free_flow_speed_kmph": raw.get("flowSegmentData", {}).get("freeFlowSpeed"),
    "current_travel_time_sec": raw.get("flowSegmentData", {}).get("currentTravelTime"),
    "free_flow_travel_time_sec": raw.get("flowSegmentData", {}).get("freeFlowTravelTime"),
    "confidence": raw.get("flowSegmentData", {}).get("confidence"),
    "road_closure": raw.get("flowSegmentData", {}).get("roadClosure", False),
    "coordinates": raw.get("flowSegmentData", {}).get("coordinates", {}).get("coordinate", []),
    "raw": raw,
}
```

---

# 16. Alerting

MVP alert channels:

1. Email first.
2. WhatsApp/SMS later via approved provider.
3. Web dashboard alert always.

Alert workflow:

```text
Anomaly detected
  -> AI mitigation draft created
  -> Alert saved as draft
  -> Operator reviews
  -> Operator approves
  -> System sends alert
  -> Delivery status stored
```

Do not auto-send public alerts in MVP.

---

# 17. Reports

Generate:

## Daily Report

- Date
- Total anomalies
- Critical/high/medium/low count
- Worst 5 locations
- Peak congestion windows
- Incident summary
- Weather/events correlation
- AI executive summary
- Suggested follow-up actions

## Weekly Report

- Repeated bottlenecks
- Average speed trend
- Delay trend
- Incident types
- Recommendations for enforcement/engineering review

---

# 18. Security and Audit

Implement:

- `.env` secrets only; never commit API keys.
- Request logging with API key redaction.
- Admin login.
- RBAC roles:
  - `admin`
  - `operator`
  - `viewer`
- Store AI input/output in `ai_insights`.
- Store alert approvals.
- Store ingestion job status.
- Add rate limiting to public endpoints.

---

# 19. Docker Compose MVP

Create services:

```yaml
services:
  postgres:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: trafficdb
      POSTGRES_USER: traffic
      POSTGRES_PASSWORD: trafficpass
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  api:
    build: ./services/api
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  worker:
    build: ./services/api
    command: python -m app.jobs.poll_tomtom
    env_file: .env
    depends_on:
      - postgres
      - redis

  web:
    build: ./apps/web
    env_file: .env
    ports:
      - "3000:3000"
    depends_on:
      - api

volumes:
  pgdata:
```

---

# 20. Environment Variables

Create `.env.example`:

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://traffic:trafficpass@postgres:5432/trafficdb
REDIS_URL=redis://redis:6379/0

TOMTOM_API_KEY=replace_me
TOMTOM_BASE_URL=https://api.tomtom.com
TOMTOM_FLOW_ZOOM=10
TOMTOM_FLOW_STYLE=absolute
TOMTOM_FLOW_UNIT=kmph

GEMINI_API_KEY=replace_me
GEMINI_MODEL=gemini-3.5-flash

AOI_NAME=Rajkot 1 km Pilot Zone
AOI_CENTER_LAT=22.329077
AOI_CENTER_LON=70.769564
AOI_RADIUS_M=1000
AOI_BBOX=70.759854,22.320094,70.779274,22.338060

WEATHER_API_KEY=replace_me_if_required
EMAIL_SMTP_HOST=
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=
EMAIL_SMTP_PASSWORD=
```

---

# 21. 4-Week MVP Roadmap

## Week 1 — Foundation + Data Ingestion

Deliverables:

- Monorepo setup.
- Docker Compose running PostGIS, Redis, FastAPI, Next.js.
- Database migrations.
- AOI seeded for Rajkot 1 km pilot zone.
- Probe point CRUD.
- TomTom Flow Segment Data client.
- TomTom Incident Details client.
- Manual ingestion run button.
- Scheduled polling worker.
- Raw + normalized data storage.

Acceptance criteria:

- User can add probe points.
- Worker polls active probe points.
- Incidents are fetched for the Rajkot bbox.
- Data appears in database.
- API health endpoint works.

## Week 2 — Dashboard + Anomaly Detection

Deliverables:

- Live map page.
- Probe point markers.
- Traffic severity colors.
- Active incidents layer.
- Anomaly detection service.
- Open anomalies page.
- Basic charts: speed trend, delay trend.
- Admin panel for polling status.

Acceptance criteria:

- Dashboard shows current traffic state.
- Slowdowns generate anomalies.
- Operator can acknowledge/resolve anomalies.
- Historical chart works for selected probe point.

## Week 3 — Gemini AI Command Center + Predictive Alerts

Deliverables:

- Gemini predictive alert service.
- `/api/ai/predictive-alert` endpoint.
- Command center query UI.
- Grounded context builder from database.
- AI root-cause summary.
- AI mitigation draft.
- AI citizen advisory draft.
- Store AI insights in database.

Acceptance criteria:

- Operator can ask a traffic question.
- Gemini answer includes evidence and confidence.
- AI output is structured JSON.
- AI mitigation draft is saved for review.

## Week 4 — Reports + Alerting + Polish

Deliverables:

- Daily report generator.
- Weekly report generator.
- Email alert draft and approval workflow.
- CSV/PDF export.
- Error handling and logs.
- Basic authentication/RBAC.
- Deployment documentation.
- Seed demo data for offline demo.

Acceptance criteria:

- Daily report can be generated.
- Alert draft can be approved and sent by email.
- Dashboard has no hardcoded fake data.
- README explains setup from zero.

---

# 22. MVP Acceptance Checklist

The project is acceptable only if all items below work:

- [ ] Docker Compose starts all services.
- [ ] PostGIS database initializes successfully.
- [ ] AOI is seeded with Rajkot pilot area.
- [ ] Probe points can be created from UI.
- [ ] TomTom flow data is fetched and stored.
- [ ] TomTom incident data is fetched and stored.
- [ ] Live dashboard shows current traffic state.
- [ ] Anomalies are detected by deterministic rules.
- [ ] Gemini generates structured predictive alert JSON.
- [ ] AI answer includes confidence, assumptions, and missing data.
- [ ] Alerts are draft-first and require human approval.
- [ ] Daily report is generated from real stored data.
- [ ] API keys are not exposed in frontend or logs.

---

# 23. Explicit Warnings for the Builder

Do not build a fake dashboard with static sample values. If demo data is needed, keep it clearly marked as seed/demo data.

Do not send all raw traffic records to Gemini. Summarize and compress context first.

Do not use Gemini as a database. Store all facts in PostgreSQL/PostGIS.

Do not auto-publish citizen alerts.

Do not claim real signal-control capability in MVP.

Do not implement X/Twitter scraping unless API/legal access is available.

Do not assume road names if TomTom does not return them. Mark as unknown and allow manual naming.

---

# 24. Future Phase 2 Features

After MVP:

1. SUMO simulation integration for true what-if traffic simulation.
2. Route impact analysis using TomTom Routing/Matrix APIs.
3. Citizen mobile app and WhatsApp bot.
4. Gemini Vision-based citizen report classification.
5. Historical ML model using LightGBM/XGBoost.
6. Automatic probe point optimization.
7. City-wide expansion by wards/zones.
8. SLA dashboard for incident response.
9. Multi-agency command room mode.
10. Hindi/Gujarati citizen advisory generation.

---

# 25. Build Order for Coding Agent

Follow this exact order:

1. Create repo structure.
2. Create Docker Compose.
3. Create FastAPI base app.
4. Create database models and migrations.
5. Seed AOI.
6. Build probe point CRUD.
7. Build TomTom client.
8. Build ingestion worker.
9. Build anomaly detector.
10. Build frontend map/dashboard.
11. Build Gemini predictive alert service.
12. Build command center.
13. Build reports.
14. Build alert approval workflow.
15. Add tests.
16. Write README.

At each step, provide working code, file paths, and run commands.

---

# 26. Source Notes to Respect

- TomTom Traffic API provides Traffic Incidents and Traffic Flow services based on TomTom Traffic.
- TomTom Flow Segment Data v4 returns speed and travel-time information for the road fragment closest to supplied coordinates.
- TomTom Incident Details v5 supports incident lookup inside a bounding box and includes fields such as category, magnitude of delay, length, delay, location, and time validity.
- Gemini structured output should be used so AI responses are valid JSON matching the application schema.


---

# SUMO-INTEGRATED VERSION — OVERRIDE NOTES

This file updates the original MVP prompt. If any old section says SUMO is a future Phase 2 item, ignore that statement. In this version, **Eclipse SUMO is mandatory in the MVP**.

Use this product split:

```text
TomTom = live real-world traffic observation
SUMO = simulation / what-if planning engine
Gemini = explanation, scenario authoring, result summarization, mitigation drafting
PostGIS = spatial source of truth
Next.js = operational dashboard and SUMO What-If Lab
```

Do not let Gemini invent traffic metrics. Numeric impact must come from TomTom observations, deterministic calculations, database queries, or SUMO outputs.

---

# A. Updated Core Objective With SUMO

Create a working MVP for the Rajkot 1 km pilot area that:

1. Polls TomTom Flow Segment Data and Traffic Incident APIs.
2. Stores live traffic observations in PostgreSQL/PostGIS.
3. Detects anomalies using deterministic logic.
4. Uses Gemini for grounded explanations and mitigation drafts.
5. Builds/imports a SUMO road network for the Rajkot pilot area.
6. Runs SUMO baseline simulation.
7. Runs SUMO what-if scenarios.
8. Compares baseline vs scenario metrics.
9. Shows live traffic + simulation results in the dashboard.
10. Clearly labels simulation results as estimates requiring engineering/field review.

The MVP must remain software-only. No physical sensors or cameras are required.

---

# B. Updated Non-Negotiable Requirements

Add these to the original non-negotiable requirements:

1. Integrate **Eclipse SUMO** in the MVP, not in a later phase.
2. Build or import a SUMO network for the Rajkot 1 km pilot zone using OpenStreetMap.
3. Use left-hand traffic settings appropriate for India when generating the SUMO network.
4. Use Python TraCI/libsumo or headless `sumo` subprocess runs for scenario execution.
5. Store SUMO network metadata, edges, scenarios, runs, metrics, and comparisons in PostgreSQL/PostGIS.
6. Build a dashboard page called **SUMO What-If Lab**.
7. Every scenario must compare a baseline run against a scenario run using the same network, demand, duration, and random seed.
8. Gemini may draft scenario configs and summarize results, but SUMO must compute the simulation metrics.
9. Do not present SUMO as an official engineering-certified model unless calibrated and validated with real traffic counts/signal plans.
10. Do not let any simulated mitigation auto-publish to citizens or trigger dispatch. Human approval is mandatory.

---

# C. Updated Architecture With SUMO

```text
[TomTom Flow + Incidents]     [Weather API]     [Manual Events]
          |                       |                  |
          v                       v                  v
   [Ingestion Worker] -----> [Redis Queue/Cache] ---> [FastAPI Backend]
          |                                          /       \
          v                                         /         \
[PostgreSQL + PostGIS] <---------------------------           \
    |   |   |                                                  \
    |   |   +--> live observations / incidents / anomalies       \
    |   +------> SUMO networks / edges / scenarios / runs         \
    |                                                            v
    |                                                   [Gemini AI Service]
    |                                                            |
    v                                                            v
[Analytics + Forecast Engine] ----------------------> [AI Insights + Drafts]
    |
    v
[SUMO Simulation Service]
    |
    v
[Baseline vs Scenario Metrics]
    |
    v
[Next.js Dashboard + Live Map + Command Center + SUMO What-If Lab]
```

Service responsibilities:

| Service | Responsibility |
|---|---|
| FastAPI API | Auth, CRUD, query APIs, orchestration |
| Worker | TomTom/weather/event polling and anomaly detection |
| Simulation service | SUMO network import, scenario execution, output parsing |
| Gemini service | Structured explanations, scenario drafts, result summaries |
| PostGIS | AOI, road geometry, observations, SUMO edges, scenario results |
| Redis | cache, queue, job status, API rate-limit coordination |
| Next.js | dashboard, map, command center, what-if lab |

---

# D. Updated Monorepo Structure

Add these folders/files to the original repository structure:

```text
rajkot-ai-traffic/
  services/
    simulation/
      Dockerfile
      pyproject.toml
      app/
        main.py
        config.py
        network_builder.py
        scenario_runner.py
        traci_runner.py
        metrics_parser.py
        scenario_templates.py
        queue_worker.py
      scenarios/
        rajkot_pilot/
          README.md
          network/
            rajkot_pilot.osm.xml
            rajkot_pilot.net.xml
            rajkot_pilot.poly.xml
          demand/
            baseline.trips.xml
            baseline.rou.xml
          runs/
  apps/
    web/
      src/
        app/
          sumo-lab/
            page.tsx
        components/
          sumo/
            SumoMapLayer.tsx
            ScenarioBuilder.tsx
            ScenarioRunStatus.tsx
            ScenarioComparison.tsx
            EdgeImpactTable.tsx
```

---

# E. SUMO Network Generation for Rajkot Pilot

Target area:

```text
center_lat = 22.329077
center_lon = 70.769564
radius_m = 1000
bbox = 70.759854,22.320094,70.779274,22.338060
bbox format = minLon,minLat,maxLon,maxLat
```

Preferred workflow:

```text
1. Download OSM extract for bbox.
2. Convert OSM to SUMO network with netconvert.
3. Use left-hand traffic.
4. Guess traffic lights if OSM has signal data.
5. Validate in sumo-gui or netedit.
6. Save the generated network as a stable asset.
7. Extract SUMO edges into PostGIS.
8. Build TomTom road segment <-> SUMO edge mapping.
```

Recommended command:

```bash
netconvert \
  --osm-files rajkot_pilot.osm.xml \
  -o rajkot_pilot.net.xml \
  --geometry.remove \
  --junctions.join \
  --tls.guess-signals \
  --tls.discard-simple \
  --tls.join \
  --tls.default-type actuated \
  --lefthand true
```

If OSM signal data is incomplete, allow signal-timing scenarios only where traffic-light IDs exist in the SUMO network. Otherwise, mark signal recommendations as advisory only.

---

# F. SUMO Demand Generation and Calibration

For MVP, start with synthetic demand. Do not claim certified forecast accuracy.

Baseline demand generation:

```bash
python $SUMO_HOME/tools/randomTrips.py \
  -n network/rajkot_pilot.net.xml \
  -r demand/baseline.rou.xml \
  -b 0 \
  -e 3600 \
  -p 3.0 \
  --validate \
  --fringe-factor 5 \
  --seed 42
```

Tuning rules:

| Parameter | Meaning | MVP Use |
|---|---|---|
| `-p` | average seconds between vehicle insertions | lower = more traffic |
| `--fringe-factor` | more boundary-to-boundary trips | useful for clipped 1 km area |
| `--seed` | repeatability | keep same seed for baseline/scenario comparison |
| vehicle speed factor | driver speed variation | tune to match observed traffic |
| vehicle sigma | driver imperfection | increase for rain/congested scenarios |

Calibration loop:

```text
1. Run baseline with fixed seed.
2. Parse tripinfo/summary/edgeData outputs.
3. Match SUMO edges to TomTom road segments.
4. Compare SUMO edge speed with TomTom observed speed ratio.
5. Adjust demand insertion period and vehicle parameters.
6. Save calibration version.
```

Store calibration configuration in DB as JSON. Do not keep it only in XML files.

---

# G. TomTom-to-SUMO Edge Mapping

Create a mapping table between real-world live data and simulation edges.

Algorithm:

```text
1. Convert SUMO edge shapes into WGS84 LineStrings.
2. Store them in `sumo_edges.geom`.
3. Store TomTom flow segment coordinates in `road_segments.geom`.
4. Use PostGIS nearest-neighbor matching.
5. Reject matches where distance > 30 meters.
6. Expose manual review in Admin UI.
```

SQL idea:

```sql
SELECT
  rs.id AS tomtom_road_segment_id,
  se.id AS sumo_edge_db_id,
  ST_Distance(rs.geom::geography, se.geom::geography) AS distance_m
FROM road_segments rs
JOIN LATERAL (
  SELECT *
  FROM sumo_edges se
  WHERE se.network_id = :network_id
  ORDER BY se.geom <-> rs.geom
  LIMIT 1
) se ON true
WHERE ST_Distance(rs.geom::geography, se.geom::geography) <= 30;
```

Admin review UI:

- Show TomTom segment and SUMO edge overlay.
- Show distance and confidence.
- Approve/reject mapping.
- Allow manual override.

---

# H. SUMO Database Schema Additions

Add these tables to the original database schema.

```sql
CREATE TABLE sumo_networks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id UUID REFERENCES areas_of_interest(id),
    name TEXT NOT NULL,
    sumo_version TEXT,
    source TEXT NOT NULL DEFAULT 'osm',
    bbox_min_lat DOUBLE PRECISION NOT NULL,
    bbox_min_lon DOUBLE PRECISION NOT NULL,
    bbox_max_lat DOUBLE PRECISION NOT NULL,
    bbox_max_lon DOUBLE PRECISION NOT NULL,
    net_file_path TEXT NOT NULL,
    osm_file_path TEXT,
    config_file_path TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sumo_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    network_id UUID REFERENCES sumo_networks(id),
    sumo_edge_id TEXT NOT NULL,
    from_node TEXT,
    to_node TEXT,
    road_name TEXT,
    priority INTEGER,
    num_lanes INTEGER,
    speed_mps DOUBLE PRECISION,
    length_m DOUBLE PRECISION,
    geom GEOGRAPHY(LineString, 4326),
    raw JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(network_id, sumo_edge_id)
);

CREATE INDEX idx_sumo_edges_geom ON sumo_edges USING GIST (geom);
CREATE INDEX idx_sumo_edges_network_edge ON sumo_edges(network_id, sumo_edge_id);

CREATE TABLE tomtom_sumo_edge_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    road_segment_id UUID REFERENCES road_segments(id),
    sumo_edge_db_id UUID REFERENCES sumo_edges(id),
    match_method TEXT NOT NULL DEFAULT 'spatial_nearest',
    distance_m DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    review_status TEXT NOT NULL DEFAULT 'pending'
      CHECK (review_status IN ('pending','approved','rejected','manual_override')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sumo_scenarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aoi_id UUID REFERENCES areas_of_interest(id),
    network_id UUID REFERENCES sumo_networks(id),
    name TEXT NOT NULL,
    scenario_type TEXT NOT NULL,
    description TEXT,
    scenario_payload JSONB NOT NULL,
    created_by TEXT,
    human_review_status TEXT NOT NULL DEFAULT 'draft'
      CHECK (human_review_status IN ('draft','approved','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sumo_simulation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id UUID REFERENCES sumo_scenarios(id),
    baseline_run_id UUID REFERENCES sumo_simulation_runs(id),
    run_type TEXT NOT NULL CHECK (run_type IN ('baseline','scenario')),
    status TEXT NOT NULL DEFAULT 'queued'
      CHECK (status IN ('queued','preparing','running','completed','failed','cancelled')),
    run_dir TEXT,
    sumocfg_path TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sumo_run_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES sumo_simulation_runs(id),
    total_departed INTEGER,
    total_arrived INTEGER,
    total_loaded INTEGER,
    completed_ratio DOUBLE PRECISION,
    average_travel_time_sec DOUBLE PRECISION,
    average_waiting_time_sec DOUBLE PRECISION,
    average_time_loss_sec DOUBLE PRECISION,
    total_time_loss_sec DOUBLE PRECISION,
    average_speed_mps DOUBLE PRECISION,
    total_teleports INTEGER,
    metrics_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sumo_edge_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES sumo_simulation_runs(id),
    sumo_edge_db_id UUID REFERENCES sumo_edges(id),
    begin_second INTEGER,
    end_second INTEGER,
    mean_speed_mps DOUBLE PRECISION,
    density DOUBLE PRECISION,
    occupancy DOUBLE PRECISION,
    waiting_time_sec DOUBLE PRECISION,
    time_loss_sec DOUBLE PRECISION,
    departed INTEGER,
    arrived INTEGER,
    raw JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sumo_edge_metrics_run ON sumo_edge_metrics(run_id);
CREATE INDEX idx_sumo_edge_metrics_edge ON sumo_edge_metrics(sumo_edge_db_id);

CREATE TABLE sumo_scenario_comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    baseline_run_id UUID REFERENCES sumo_simulation_runs(id),
    scenario_run_id UUID REFERENCES sumo_simulation_runs(id),
    comparison_payload JSONB NOT NULL,
    gemini_summary_insight_id UUID REFERENCES ai_insights(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

# I. SUMO Scenario Schema

Create this schema in:

```text
services/api/app/schemas/sumo.py
```

```python
from typing import Literal
from pydantic import BaseModel, Field

ScenarioType = Literal[
    "road_closure",
    "lane_block",
    "one_way_conversion",
    "signal_timing_change",
    "event_demand_surge",
    "rain_slowdown",
    "combined",
]

class SumoEdgeChange(BaseModel):
    sumo_edge_id: str
    action: Literal["close", "reduce_speed", "reduce_lanes", "reverse_direction", "capacity_factor"]
    value: float | str | None = None
    start_second: int = 0
    end_second: int = 3600

class SignalTimingChange(BaseModel):
    traffic_light_id: str
    phase_index: int
    new_duration_sec: int = Field(ge=5, le=180)

class DemandChange(BaseModel):
    demand_type: Literal["increase_global", "increase_zone", "add_event_arrivals"]
    factor: float = Field(default=1.0, ge=0.1, le=5.0)
    target_lat: float | None = None
    target_lon: float | None = None
    radius_m: int | None = None
    start_second: int = 0
    end_second: int = 3600

class SumoScenarioRequest(BaseModel):
    name: str
    scenario_type: ScenarioType
    aoi_id: str
    network_id: str
    simulation_start_second: int = 0
    simulation_end_second: int = 3600
    random_seed: int = 42
    edge_changes: list[SumoEdgeChange] = []
    signal_changes: list[SignalTimingChange] = []
    demand_changes: list[DemandChange] = []
    description: str | None = None
    created_by: str | None = None
```

---

# J. SUMO API Endpoints

Add these endpoints to the main FastAPI backend:

```text
GET  /api/sumo/networks
POST /api/sumo/networks/import-osm
GET  /api/sumo/networks/{network_id}
GET  /api/sumo/networks/{network_id}/edges
POST /api/sumo/networks/{network_id}/match-tomtom-segments
PATCH /api/sumo/edge-mappings/{mapping_id}

POST /api/sumo/scenarios
GET  /api/sumo/scenarios
GET  /api/sumo/scenarios/{scenario_id}
POST /api/sumo/scenarios/{scenario_id}/run
GET  /api/sumo/runs/{run_id}
GET  /api/sumo/runs/{run_id}/metrics
GET  /api/sumo/runs/{run_id}/files
POST /api/sumo/runs/{run_id}/summarize-with-gemini
```

Rules:

- `POST /api/sumo/scenarios` creates a draft scenario.
- `POST /api/sumo/scenarios/{id}/run` enqueues a job.
- The simulation service executes SUMO.
- Main API stores metrics and exposes results.
- Gemini summary only runs after SUMO metrics exist.

---

# K. SUMO Simulation Metrics

Capture these metrics:

| Metric | Description |
|---|---|
| total_departed | Vehicles inserted |
| total_arrived | Vehicles completed trip |
| completed_ratio | arrived / departed |
| average_travel_time_sec | mean trip duration |
| average_waiting_time_sec | mean waiting time |
| average_time_loss_sec | mean time loss |
| total_time_loss_sec | total network time loss |
| average_speed_mps | average speed |
| total_teleports | teleports/gridlock indicator |
| edge_mean_speed | per-edge speed |
| edge_waiting_time | per-edge waiting time |
| edge_density | per-edge density if available |
| queue_length | queue estimate if configured |

Every run directory must contain:

```text
runs/{run_id}/
  scenario.sumocfg
  scenario.rou.xml
  tripinfo.xml
  summary.xml
  edgeData.xml
  run.log
```

---

# L. Baseline vs Scenario Comparison

Every SUMO scenario requires baseline comparison.

```json
{
  "scenario_id": "uuid",
  "baseline_run_id": "uuid",
  "scenario_run_id": "uuid",
  "overall_delta": {
    "average_travel_time_change_percent": 12.4,
    "average_waiting_time_change_percent": -8.2,
    "completed_ratio_change_percent": 1.1,
    "teleport_delta": 0
  },
  "edge_impacts": [
    {
      "sumo_edge_id": "edge123",
      "road_name": "manual or OSM name",
      "speed_change_percent": -15.0,
      "waiting_time_change_sec": 42.5,
      "impact": "worse"
    }
  ],
  "recommendation": "approve_for_field_review | reject | needs_more_data"
}
```

Use the same seed for baseline and scenario. Otherwise, comparison noise will be high.

---

# M. Simulation Service Dockerfile

Create:

```text
services/simulation/Dockerfile
```

```dockerfile
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV SUMO_HOME=/usr/share/sumo

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    sumo \
    sumo-tools \
    sumo-doc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && pip install fastapi uvicorn pydantic redis sqlalchemy psycopg[binary]

COPY app /app/app
COPY scenarios /app/scenarios

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
```

---

# N. Docker Compose Addition

Add this service to `docker-compose.yml`:

```yaml
  simulation:
    build: ./services/simulation
    env_file: .env
    environment:
      SUMO_HOME: /usr/share/sumo
      DATABASE_URL: postgresql+psycopg://traffic:trafficpass@postgres:5432/trafficdb
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./services/simulation/scenarios:/app/scenarios
      - ./services/simulation/runs:/app/runs
    ports:
      - "8100:8100"
    depends_on:
      - postgres
      - redis
```

Add to `.env.example`:

```env
SUMO_HOME=/usr/share/sumo
SUMO_SERVICE_URL=http://simulation:8100
SUMO_SCENARIO_DIR=/app/scenarios/rajkot_pilot
SUMO_RUNS_DIR=/app/runs
SUMO_DEFAULT_DURATION_SECONDS=3600
SUMO_DEFAULT_SEED=42
```

---

# O. Simulation Service FastAPI

Create:

```text
services/simulation/app/main.py
```

```python
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.scenario_runner import SumoScenarioRunner

app = FastAPI(title="Rajkot SUMO Simulation Service")

class RunScenarioRequest(BaseModel):
    scenario_config: dict

@app.get("/health")
def health():
    return {"status": "ok", "service": "sumo-simulation"}

@app.post("/run-scenario")
def run_scenario(req: RunScenarioRequest):
    try:
        runner = SumoScenarioRunner(
            base_scenario_dir="/app/scenarios/rajkot_pilot",
            runs_dir="/app/runs",
            sumo_binary="sumo",
        )
        result = runner.run_scenario(req.scenario_config)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

For a quick local MVP this synchronous endpoint is acceptable for short simulations. For production, use Redis queue + worker and return job status.

---

# P. Scenario Runner Base Code

Create:

```text
services/simulation/app/scenario_runner.py
```

```python
from __future__ import annotations

import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

@dataclass
class SumoRunResult:
    run_id: str
    status: str
    run_dir: str
    metrics: dict[str, Any]
    error: str | None = None

class SumoScenarioRunner:
    def __init__(self, base_scenario_dir: str, runs_dir: str, sumo_binary: str = "sumo") -> None:
        self.base_scenario_dir = Path(base_scenario_dir)
        self.runs_dir = Path(runs_dir)
        self.sumo_binary = sumo_binary
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def run_scenario(self, scenario_config: dict[str, Any]) -> dict[str, Any]:
        run_id = scenario_config.get("run_id") or str(uuid.uuid4())
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._copy_base_files(run_dir)
            self._write_additional_file(run_dir, scenario_config)
            sumocfg = self._write_sumocfg(run_dir, scenario_config)
            ok = self._execute_sumo(run_dir, sumocfg)
            metrics = self._parse_tripinfo(run_dir / "tripinfo.xml")
            return asdict(SumoRunResult(
                run_id=run_id,
                status="completed" if ok else "failed",
                run_dir=str(run_dir),
                metrics=metrics,
                error=None if ok else "SUMO exited with non-zero status",
            ))
        except Exception as exc:
            return asdict(SumoRunResult(
                run_id=run_id,
                status="failed",
                run_dir=str(run_dir),
                metrics={},
                error=str(exc),
            ))

    def _copy_base_files(self, run_dir: Path) -> None:
        for item in self.base_scenario_dir.iterdir():
            if item.name == "runs":
                continue
            target = run_dir / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

    def _write_additional_file(self, run_dir: Path, scenario_config: dict[str, Any]) -> None:
        root = ET.Element("additional")
        for change in scenario_config.get("edge_changes", []):
            edge_id = change["sumo_edge_id"]
            action = change["action"]
            start = str(change.get("start_second", 0))
            end = str(change.get("end_second", 3600))
            if action == "close":
                rerouter = ET.SubElement(root, "rerouter", id=f"rr_{edge_id}", edges=edge_id)
                interval = ET.SubElement(rerouter, "interval", begin=start, end=end)
                ET.SubElement(interval, "closingReroute", id=edge_id)
        ET.ElementTree(root).write(run_dir / "scenario.additional.xml", encoding="utf-8", xml_declaration=True)

    def _write_sumocfg(self, run_dir: Path, scenario_config: dict[str, Any]) -> Path:
        begin = scenario_config.get("simulation_start_second", 0)
        end = scenario_config.get("simulation_end_second", 3600)
        content = f'''<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <input>
    <net-file value="network/rajkot_pilot.net.xml"/>
    <route-files value="demand/baseline.rou.xml"/>
    <additional-files value="scenario.additional.xml"/>
  </input>
  <time>
    <begin value="{begin}"/>
    <end value="{end}"/>
    <step-length value="1"/>
  </time>
  <output>
    <tripinfo-output value="tripinfo.xml"/>
    <summary-output value="summary.xml"/>
  </output>
  <processing>
    <ignore-route-errors value="true"/>
    <time-to-teleport value="300"/>
  </processing>
</configuration>
'''
        path = run_dir / "scenario.sumocfg"
        path.write_text(content, encoding="utf-8")
        return path

    def _execute_sumo(self, run_dir: Path, sumocfg: Path) -> bool:
        cmd = [
            self.sumo_binary,
            "-c", str(sumocfg),
            "--edgedata-output", str(run_dir / "edgeData.xml"),
            "--no-step-log", "true",
            "--duration-log.statistics", "true",
        ]
        with (run_dir / "run.log").open("w", encoding="utf-8") as log:
            proc = subprocess.run(cmd, cwd=str(run_dir), stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False)
        return proc.returncode == 0

    def _parse_tripinfo(self, tripinfo_path: Path) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "total_arrived": 0,
            "average_duration_sec": None,
            "average_waiting_time_sec": None,
            "average_time_loss_sec": None,
            "total_time_loss_sec": 0.0,
        }
        if not tripinfo_path.exists():
            return metrics
        durations, waits, losses = [], [], []
        for _, elem in ET.iterparse(tripinfo_path, events=("end",)):
            if elem.tag == "tripinfo":
                metrics["total_arrived"] += 1
                durations.append(float(elem.attrib.get("duration", 0)))
                waits.append(float(elem.attrib.get("waitingTime", 0)))
                losses.append(float(elem.attrib.get("timeLoss", 0)))
                elem.clear()
        if durations:
            metrics["average_duration_sec"] = sum(durations) / len(durations)
            metrics["average_waiting_time_sec"] = sum(waits) / len(waits)
            metrics["average_time_loss_sec"] = sum(losses) / len(losses)
            metrics["total_time_loss_sec"] = sum(losses)
        return metrics
```

---

# Q. Optional TraCI Runtime Runner

Create:

```text
services/simulation/app/traci_runner.py
```

```python
from __future__ import annotations

import os
import sys
from typing import Any

if "SUMO_HOME" in os.environ:
    sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))

import traci  # type: ignore

class TraciScenarioRunner:
    def __init__(self, sumo_binary: str = "sumo") -> None:
        self.sumo_binary = sumo_binary

    def run_with_runtime_changes(self, sumocfg_path: str, scenario_config: dict[str, Any]) -> dict[str, Any]:
        traci.start([self.sumo_binary, "-c", sumocfg_path, "--no-step-log", "true"])
        try:
            begin = int(scenario_config.get("simulation_start_second", 0))
            end = int(scenario_config.get("simulation_end_second", 3600))
            for t in range(begin, end):
                for change in scenario_config.get("edge_changes", []):
                    if int(change.get("start_second", 0)) <= t <= int(change.get("end_second", 3600)):
                        if change["action"] == "reduce_speed":
                            traci.edge.setMaxSpeed(change["sumo_edge_id"], float(change.get("value", 5.0)))
                for sig in scenario_config.get("signal_changes", []):
                    if t == 0:
                        traci.trafficlight.setPhase(sig["traffic_light_id"], int(sig["phase_index"]))
                        traci.trafficlight.setPhaseDuration(sig["traffic_light_id"], int(sig["new_duration_sec"]))
                traci.simulationStep()
            return {
                "status": "completed",
                "arrived": traci.simulation.getArrivedNumber(),
                "departed": traci.simulation.getDepartedNumber(),
                "teleports_starting": traci.simulation.getStartingTeleportNumber(),
            }
        finally:
            traci.close()
```

---

# R. SUMO What-If Lab Frontend

Create page:

```text
apps/web/src/app/sumo-lab/page.tsx
```

Required UI blocks:

1. Rajkot AOI map.
2. SUMO edge layer.
3. TomTom live segment overlay.
4. Edge selection tool.
5. Scenario builder form.
6. Baseline run status.
7. Scenario run status.
8. Comparison cards.
9. Edge impact table.
10. Gemini result summary.
11. PDF/CSV export.

Scenario builder fields:

```text
Scenario name
Scenario type
Selected SUMO edge
Start second
End second
Demand factor
Signal timing change, if available
Run baseline toggle
Run scenario button
```

Display warning on page:

```text
SUMO simulation is a planning estimate. It depends on OSM network quality and synthetic/calibrated demand. Field validation is required before operational changes.
```

---

# S. Gemini + SUMO Flow

Use Gemini in two stages only.

## Stage 1: Scenario Authoring

User asks:

```text
Simulate if we close this road for 30 minutes during evening peak.
```

Backend flow:

```text
1. Identify selected SUMO edge from map.
2. Pull TomTom live speed/delay for mapped road segment.
3. Pull recent anomalies and incidents.
4. Ask Gemini to draft SumoScenarioRequest JSON.
5. Validate JSON strictly with Pydantic.
6. Human approves.
7. Enqueue SUMO run.
```

## Stage 2: Result Summarization

After SUMO finishes:

```text
1. Backend computes comparison metrics.
2. Send compact metrics packet to Gemini.
3. Gemini produces summary, limitations, and next actions.
4. Store output in ai_insights.
```

Strict rule:

```text
Gemini must not invent numbers, roads, signals, or scenario outputs.
```

---

# T. Updated 4-Week MVP Roadmap With SUMO

## Week 1 — Foundation + SUMO Network

Deliverables:

- Docker Compose: PostGIS, Redis, FastAPI, worker, Next.js, simulation service.
- Database schema with original + SUMO tables.
- Rajkot AOI seed.
- SUMO installed in simulation container.
- Rajkot OSM extract converted to SUMO network.
- SUMO edges imported into PostGIS.
- Simulation service `/health` works.

Acceptance:

- `docker compose up -d` starts all services.
- `sumo --version` works in simulation container.
- `rajkot_pilot.net.xml` loads.
- PostGIS has SUMO edge records.

## Week 2 — TomTom + Mapping + Baseline Simulation

Deliverables:

- TomTom Flow and Incident client.
- Probe point CRUD.
- Live traffic ingestion.
- TomTom-to-SUMO edge matching.
- Baseline demand generation.
- Baseline SUMO run.
- Dashboard map with TomTom + SUMO layers.

Acceptance:

- TomTom observations are stored.
- SUMO baseline produces `tripinfo.xml`, `summary.xml`, and `edgeData.xml`.
- Admin can review edge mappings.

## Week 3 — SUMO What-If Lab + Gemini

Deliverables:

- Scenario schema.
- Scenario CRUD.
- Road closure scenario.
- Lane/speed reduction scenario.
- Baseline vs scenario comparison.
- SUMO What-If Lab UI.
- Gemini scenario-draft endpoint.
- Gemini result-summary endpoint.

Acceptance:

- Operator selects an edge and runs a road-closure scenario.
- Dashboard shows whether metrics improved or worsened.
- Gemini summary uses only actual metrics.

## Week 4 — Reports + Alerts + Polish

Deliverables:

- Daily/weekly reports.
- SUMO scenario report export.
- Alert draft workflow.
- RBAC/auth.
- Clear limitations and source labels.
- Seed demo data.
- README setup guide.

Acceptance:

- Report contains live observations + anomaly summary + SUMO scenario summary.
- Alerts remain draft-first and human-approved.
- No fake hardcoded dashboard values.

---

# U. Updated Build Order

Follow this exact build order:

1. Create repo structure.
2. Create Docker Compose with SUMO simulation service.
3. Create FastAPI base app.
4. Create simulation service base app.
5. Create DB models/migrations including SUMO tables.
6. Seed Rajkot AOI.
7. Build/import Rajkot SUMO network from OSM.
8. Import SUMO edges into PostGIS.
9. Build TomTom client.
10. Build probe point CRUD.
11. Build TomTom-to-SUMO edge mapping.
12. Build ingestion worker.
13. Build anomaly detector.
14. Build baseline SUMO run.
15. Build SUMO scenario runner.
16. Build SUMO comparison metrics.
17. Build live dashboard.
18. Build SUMO What-If Lab.
19. Build Gemini predictive alert service.
20. Build Gemini scenario authoring and SUMO result summary.
21. Build command center.
22. Build reports.
23. Build alert approval workflow.
24. Add tests.
25. Write README.

---

# V. Updated Acceptance Checklist

The MVP is acceptable only if these work:

- [ ] Docker Compose starts all services.
- [ ] SUMO simulation service starts.
- [ ] `sumo --version` works inside simulation container.
- [ ] Rajkot pilot SUMO network exists and loads.
- [ ] PostGIS stores SUMO edges.
- [ ] TomTom flow observations are stored.
- [ ] TomTom incidents are stored.
- [ ] TomTom road segments can be mapped to SUMO edges.
- [ ] Baseline SUMO simulation runs.
- [ ] Road-closure scenario runs.
- [ ] Baseline vs scenario metrics are stored.
- [ ] Dashboard shows SUMO scenario results.
- [ ] Gemini summarizes SUMO metrics without inventing numbers.
- [ ] UI labels SUMO results as simulation estimates.
- [ ] Alerts require human approval.

---

# W. Explicit Warnings

- Do not treat SUMO synthetic demand as real traffic count data.
- Do not claim city-wide accuracy from a 1 km pilot.
- Do not auto-publish public advisories.
- Do not let Gemini control signals, dispatch, or field operations.
- Do not hide OSM/SUMO limitations.
- Do not compare baseline and scenario using different random seeds unless explicitly testing randomness.
- Do not run long simulations in the request thread in production.
- Do not mix TomTom live values and SUMO simulated values in one chart without source labels.

---

# X. SUMO Source Notes to Respect

- Eclipse SUMO is an open-source, microscopic traffic simulator for road networks and multiple transport modes.
- OSM Web Wizard can create SUMO scenarios from OpenStreetMap excerpts with randomized demand.
- `netconvert --osm-files` converts OSM files into SUMO `.net.xml` network files.
- `duarouter` builds vehicle route files from demand definitions.
- Python TraCI can start and step SUMO simulations and change runtime behavior such as signals or edge speeds.
