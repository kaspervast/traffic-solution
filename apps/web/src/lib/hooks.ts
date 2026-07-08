"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AOI, Anomaly, FlowObservation, Incident, ProbePoint } from "@/types";

const REFRESH_MS = 30_000; // spec 12.1: auto-refresh every 30-60 seconds

export function useAOI() {
  return useQuery({
    queryKey: ["aoi"],
    queryFn: () => api.get<AOI>("/api/aoi/current"),
    retry: false,
  });
}

export function useProbePoints() {
  return useQuery({
    queryKey: ["probe-points"],
    queryFn: () => api.get<ProbePoint[]>("/api/probe-points"),
    refetchInterval: REFRESH_MS,
  });
}

export function useTrafficLive() {
  return useQuery({
    queryKey: ["traffic-live"],
    queryFn: () => api.get<FlowObservation[]>("/api/traffic/live"),
    refetchInterval: REFRESH_MS,
  });
}

export function useIncidentsLive() {
  return useQuery({
    queryKey: ["incidents-live"],
    queryFn: () => api.get<Incident[]>("/api/incidents/live"),
    refetchInterval: REFRESH_MS,
  });
}

export function useAnomaliesOpen(severity?: string) {
  return useQuery({
    queryKey: ["anomalies-open", severity ?? "all"],
    queryFn: () =>
      api.get<Anomaly[]>(`/api/anomalies/open${severity ? `?severity=${severity}` : ""}`),
    refetchInterval: REFRESH_MS,
  });
}
