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
