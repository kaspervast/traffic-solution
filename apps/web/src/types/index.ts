export type Severity = "low" | "medium" | "high" | "critical";
export type Priority = "high" | "medium" | "low";

export interface AOI {
  id: string;
  name: string;
  radius_m: number;
  bbox_min_lat: number;
  bbox_min_lon: number;
  bbox_max_lat: number;
  bbox_max_lon: number;
  center_lat: number;
  center_lon: number;
  created_at: string;
}

export interface ProbePoint {
  id: string;
  name: string;
  lat: number;
  lon: number;
  priority: Priority;
  polling_interval_seconds: number;
  is_active: boolean;
  notes: string | null;
  road_segment_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface FlowObservation {
  id: string;
  probe_point_id: string | null;
  observed_at: string;
  current_speed_kmph: number | null;
  free_flow_speed_kmph: number | null;
  current_travel_time_sec: number | null;
  free_flow_travel_time_sec: number | null;
  speed_ratio: number | null;
  delay_sec: number | null;
  confidence: number | null;
  road_closure: boolean;
}

export interface Incident {
  id: string;
  provider_incident_id: string;
  category: string | null;
  icon_category: number | null;
  magnitude_of_delay: number | null;
  from_text: string | null;
  to_text: string | null;
  description: string | null;
  delay_sec: number | null;
  length_m: number | null;
  start_time: string | null;
  end_time: string | null;
  is_active: boolean;
  last_seen_at: string;
  lat: number | null;
  lon: number | null;
}

export interface Anomaly {
  id: string;
  probe_point_id: string | null;
  road_segment_id: string | null;
  detected_at: string;
  anomaly_type: string;
  severity: Severity;
  score: number;
  baseline_speed_kmph: number | null;
  observed_speed_kmph: number | null;
  delay_sec: number | null;
  evidence: Record<string, unknown>;
  status: "open" | "acknowledged" | "resolved" | "dismissed";
}

export interface IngestionRunResult {
  started_at: string;
  finished_at: string;
  probe_points_polled: number;
  flow_observations_stored: number;
  incidents_upserted: number;
  anomalies_detected: number;
  errors: string[];
}

export interface CommandAnswer {
  intent: string;
  answer: string;
  evidence: { label: string; value: string; source: string }[];
  confidence: number;
  assumptions: string[];
  missing_data: string[];
  suggested_advisory: string | null;
  ai_insight_id: string | null;
}

export interface SumoEdgeOut {
  id: string;
  sumo_edge_id: string;
  road_name: string | null;
  num_lanes: number | null;
  speed_mps: number | null;
  length_m: number | null;
  coordinates: [number, number][];
}

export interface ScenarioComparison {
  scenario_id: string;
  baseline_run_id: string;
  scenario_run_id: string;
  overall_delta: {
    average_travel_time_change_percent: number | null;
    average_waiting_time_change_percent: number | null;
    completed_ratio_change_percent: number | null;
    teleport_delta: number | null;
  };
  edge_impacts: {
    sumo_edge_id: string;
    road_name: string | null;
    speed_change_percent: number | null;
    waiting_time_change_sec: number | null;
    impact: "better" | "worse" | "unchanged";
  }[];
  recommendation: "approve_for_field_review" | "reject" | "needs_more_data";
}

export interface BboxSummary {
  bbox: [number, number, number, number];
  incident_count: number;
  by_magnitude_of_delay: Record<string, number>;
}

export interface ImportOsmResult {
  network_id: string;
  network_name: string;
  edges_created: number;
  edges_skipped_no_shape: number;
  vehicle_count: number | null;
  junction_count: number | null;
  validated: boolean | null;
}

export const SEVERITY_COLORS: Record<Severity, string> = {
  critical: "#dc2626",
  high: "#ea580c",
  medium: "#d97706",
  low: "#65a30d",
};
