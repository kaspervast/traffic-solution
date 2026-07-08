export type ScenarioType =
  | "road_closure"
  | "lane_block"
  | "one_way_conversion"
  | "signal_timing_change"
  | "event_demand_surge"
  | "rain_slowdown"
  | "combined";

export interface RunMetrics {
  total_arrived?: number | null;
  average_duration_sec?: number | null;
  average_travel_time_sec?: number | null;
  average_waiting_time_sec?: number | null;
  average_time_loss_sec?: number | null;
  total_time_loss_sec?: number | null;
  total_teleports?: number | null;
}

export interface RunResult {
  run_id: string;
  status: "queued" | "preparing" | "running" | "completed" | "failed" | "cancelled";
  run_dir?: string;
  metrics?: RunMetrics;
  error?: string | null;
}

export interface ScenarioEdgeChange {
  sumo_edge_id: string;
  action: "close" | "reduce_speed" | "reduce_lanes" | "reverse_direction" | "capacity_factor";
  value?: number | string | null;
  start_second: number;
  end_second: number;
}

export interface ScenarioSignalChange {
  traffic_light_id: string;
  phase_index: number;
  new_duration_sec: number;
}

export interface ScenarioDemandChange {
  demand_type: "increase_global" | "increase_zone" | "add_event_arrivals";
  factor: number;
  target_lat?: number | null;
  target_lon?: number | null;
  radius_m?: number | null;
  start_second: number;
  end_second: number;
}

/** Mirrors app/schemas/sumo.py::SumoScenarioRequest -- the shape returned
 * by POST /api/sumo/scenarios/draft and accepted by POST /api/sumo/scenarios. */
export interface ScenarioDraft {
  name: string;
  scenario_type: ScenarioType;
  aoi_id: string;
  network_id: string;
  simulation_start_second: number;
  simulation_end_second: number;
  random_seed: number;
  edge_changes: ScenarioEdgeChange[];
  signal_changes: ScenarioSignalChange[];
  demand_changes: ScenarioDemandChange[];
  description?: string | null;
  created_by?: string | null;
}
