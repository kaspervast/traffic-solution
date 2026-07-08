"""Unit tests for TomTom response normalization (spec sections 4, 15).

These test pure normalization functions against realistic fixture payloads
-- no network calls (live API verification was done manually against the
real TOMTOM_API_KEY during development, see project report).
"""

from __future__ import annotations

from app.services.tomtom_client import _redact_url, normalize_flow_segment, normalize_incidents


FLOW_FIXTURE = {
    "flowSegmentData": {
        "frc": "FRC0",
        "currentSpeed": 12,
        "freeFlowSpeed": 42,
        "currentTravelTime": 780,
        "freeFlowTravelTime": 300,
        "confidence": 0.95,
        "roadClosure": False,
        "coordinates": {
            "coordinate": [
                {"latitude": 22.329, "longitude": 70.7695},
                {"latitude": 22.3291, "longitude": 70.7696},
            ]
        },
    }
}


CLOSED_ROAD_FIXTURE = {
    "flowSegmentData": {
        "frc": "FRC2",
        "currentSpeed": 0,
        "freeFlowSpeed": 35,
        "currentTravelTime": 0,
        "freeFlowTravelTime": 200,
        "confidence": 0.8,
        "roadClosure": True,
        "coordinates": {"coordinate": []},
    }
}


INCIDENTS_FIXTURE = {
    "incidents": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [70.77, 22.33]},
            "properties": {
                "id": "abc123",
                "iconCategory": 6,
                "magnitudeOfDelay": 2,
                "events": [{"description": "Traffic jam", "code": 401, "iconCategory": 6}],
                "startTime": "2026-07-08T10:00:00Z",
                "endTime": "2026-07-08T12:00:00Z",
                "from": "Kalawad Road",
                "to": "150 Feet Ring Road",
                "length": 450.0,
                "delay": 300,
                "roadNumbers": ["SH-24"],
                "timeValidity": "present",
                "probabilityOfOccurrence": "certain",
                "numberOfReports": 3,
            },
        }
    ]
}


def test_normalize_flow_segment_basic_fields():
    norm = normalize_flow_segment(FLOW_FIXTURE)
    assert norm["current_speed_kmph"] == 12
    assert norm["free_flow_speed_kmph"] == 42
    assert norm["current_travel_time_sec"] == 780
    assert norm["free_flow_travel_time_sec"] == 300
    assert norm["confidence"] == 0.95
    assert norm["road_closure"] is False
    assert len(norm["coordinates"]) == 2
    assert norm["raw"] == FLOW_FIXTURE


def test_normalize_flow_segment_computes_speed_ratio_and_delay():
    norm = normalize_flow_segment(FLOW_FIXTURE)
    assert norm["speed_ratio"] == 12 / 42
    assert norm["delay_sec"] == 780 - 300


def test_normalize_flow_segment_handles_road_closure():
    norm = normalize_flow_segment(CLOSED_ROAD_FIXTURE)
    assert norm["road_closure"] is True
    assert norm["current_speed_kmph"] == 0


def test_normalize_flow_segment_missing_data_never_fabricated():
    norm = normalize_flow_segment({"flowSegmentData": {}})
    assert norm["current_speed_kmph"] is None
    assert norm["free_flow_speed_kmph"] is None
    assert norm["speed_ratio"] is None
    assert norm["delay_sec"] is None
    assert norm["road_closure"] is False  # explicit spec default


def test_normalize_flow_segment_empty_response():
    norm = normalize_flow_segment({})
    assert norm["current_speed_kmph"] is None
    assert norm["coordinates"] == []


def test_normalize_incidents_extracts_expected_fields():
    result = normalize_incidents(INCIDENTS_FIXTURE)
    assert len(result) == 1
    incident = result[0]
    assert incident["provider_incident_id"] == "abc123"
    assert incident["magnitude_of_delay"] == 2
    assert incident["from_text"] == "Kalawad Road"
    assert incident["to_text"] == "150 Feet Ring Road"
    assert incident["delay_sec"] == 300
    assert incident["road_numbers"] == ["SH-24"]
    assert incident["description"] == "Traffic jam"
    assert incident["raw"] == INCIDENTS_FIXTURE["incidents"][0]


def test_normalize_incidents_empty_list():
    assert normalize_incidents({"incidents": []}) == []
    assert normalize_incidents({}) == []


def test_normalize_incidents_never_fabricates_road_names():
    fixture = {
        "incidents": [
            {
                "properties": {"id": "no-name-1", "events": []},
                "geometry": {"type": "Point", "coordinates": [70.77, 22.33]},
            }
        ]
    }
    result = normalize_incidents(fixture)
    assert result[0]["from_text"] is None
    assert result[0]["to_text"] is None
    assert result[0]["description"] is None


def test_redact_url_hides_api_key():
    url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?key=SECRET123&point=22.3,70.7"
    redacted = _redact_url(url)
    assert "SECRET123" not in redacted
    assert "point=22.3,70.7" in redacted
    assert "***REDACTED***" in redacted


def test_redact_url_noop_when_no_key():
    url = "https://api.tomtom.com/health"
    assert _redact_url(url) == url
