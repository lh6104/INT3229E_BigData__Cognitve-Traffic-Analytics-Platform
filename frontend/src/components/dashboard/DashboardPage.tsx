import {
  Activity,
  AlertTriangle,
  Gauge,
  Map as MapIcon,
  Cpu,
  Zap,
  ArrowUpRight,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { apiGet } from "@/lib/api/client";
import { useAppStore } from "@/lib/store/useAppStore";

type DashboardSummary = {
  city: string;
  monitored_segments: number;
  active_alerts: number;
  risk_markers?: number;
  total_gold_rows?: number;
  serving_snapshot_rows?: number;
  displayed_segments?: number;
  train_rows?: number;
  free_flow_segments: number;
  slow_segments: number;
  congested_segments: number;
  avg_speed: number | null;
  avg_jam_factor: number | null;
  latest_timestamp: string | null;
  data_source: string;
  is_demo: boolean;
  message?: string | null;
};

type DashboardTrends = {
  city: string;
  hours: number;
  points: Array<{
    timestamp: string;
    avg_speed: number;
    avg_jam_factor: number;
  }>;
  data_source: string;
  available_points: number;
  min_timestamp: string | null;
  max_timestamp: string | null;
  is_demo: boolean;
  message?: string | null;
};

const emptySummary: DashboardSummary = {
  city: "hanoi",
  monitored_segments: 0,
  active_alerts: 0,
  risk_markers: 0,
  total_gold_rows: 0,
  serving_snapshot_rows: 0,
  displayed_segments: 0,
  train_rows: 0,
  free_flow_segments: 0,
  slow_segments: 0,
  congested_segments: 0,
  avg_speed: null,
  avg_jam_factor: null,
  latest_timestamp: null,
  data_source: "gold_local",
  is_demo: false,
};

type ApiAlert = {
  alert_id: string;
  segment_id: string;
  city: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  reason: string;
  predicted_speed: number;
  baseline_p50: number;
  created_at: string;
  acknowledged: boolean;
};

type TrafficSegment = {
  segment_id: string;
  city: string;
  current_speed: number;
  free_flow_speed: number;
  jam_factor: number;
  timestamp: string;
  road_class: string;
  district: string;
};

type MonitoringModel = {
  ready: boolean;
  model_dir: string;
  models: Array<{
    horizon_minutes: number;
    mae: number;
    rmse: number;
    r2_score: number;
    rows: number;
    feature_count: number;
    artifact: string;
  }>;
};

type SystemStatus = {
  api: { status: string; uptime_seconds: number };
  data: {
    status: string;
    gold_row_count: number;
    segment_count: number;
    latest_data_timestamp?: string | null;
  };
  model: {
    loaded: boolean;
    model_name?: string | null;
    average_feature_coverage_ratio?: number | null;
  };
  performance: {
    status: string;
    forecast_p95_ms?: number | null;
    dashboard_summary_p95_ms?: number | null;
    predicted_hotspots_p95_ms?: number | null;
  };
  streaming: { status: string; kafka_enabled: boolean };
};

type SystemEvidence = {
  overall_status: "OK" | "Degraded" | "Unhealthy";
  reasons: string[];
  data_freshness: {
    status: string;
    age_hours?: number | null;
    last_updated?: string | null;
    warning?: string | null;
  };
  dq_report: { status: string; warning_count?: number; critical_failure_count?: number };
  api_benchmark: { status: string; p95_ms?: number | null };
  model: { status: string; artifact_version?: string | null; training_rows?: number | null };
  pipeline_run_manifest: { status: string; end_time_utc?: string | null };
};

type GraphHealth = {
  status: string;
  backend: string;
  segments?: number;
  relationships?: number;
  neo4j?: string;
};

type GraphHotspot = {
  segment_id: string;
  name?: string;
  city?: string;
  jam_factor?: number;
  speed?: number;
  neighbors?: string[];
};

type GraphHotspotsResponse = {
  source: string;
  hotspots: GraphHotspot[];
};

function StatCard({
  icon: Icon,
  label,
  value,
  delta,
  tone = "primary",
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  delta?: string;
  tone?: "primary" | "warning" | "success" | "destructive";
}) {
  const toneMap: Record<string, string> = {
    primary: "bg-primary-soft text-accent-foreground",
    warning: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]",
    success: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]",
    destructive: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]",
  };
  return (
    <div className="rounded-2xl bg-card p-5">
      <div className="flex items-start justify-between">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${toneMap[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
        {delta && <span className="text-xs font-medium text-muted-foreground">{delta}</span>}
      </div>
      <div className="mt-4 text-2xl font-semibold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

export function DashboardPage() {
  const city = useAppStore((state) => state.selectedCity);
  const { data: summary, error: summaryError, isLoading: summaryLoading } = useSWR<DashboardSummary>(
    `/dashboard/summary?city=${city}`,
    apiGet,
    { revalidateOnFocus: false, shouldRetryOnError: false }
  );
  const { data: trends, error: trendsError, isLoading: trendsLoading } = useSWR<DashboardTrends>(
    `/dashboard/trends?city=${city}&hours=24`,
    apiGet,
    { revalidateOnFocus: false, shouldRetryOnError: false }
  );
  const { data: alerts, error: alertsError, isLoading: alertsLoading } = useSWR<ApiAlert[]>(
    `/alerts/active?city=${city}&limit=20`,
    apiGet,
    { refreshInterval: 60_000, revalidateOnFocus: false, shouldRetryOnError: false }
  );
  const { data: modelStatus } = useSWR<MonitoringModel>(
    "/monitoring/model",
    apiGet,
    { refreshInterval: 60_000, revalidateOnFocus: false, shouldRetryOnError: false }
  );
  const { data: systemStatus } = useSWR<SystemStatus>(
    "/system/status",
    apiGet,
    { refreshInterval: 30_000, revalidateOnFocus: false, shouldRetryOnError: false }
  );
  const { data: evidence } = useSWR<SystemEvidence>(
    "/system/evidence",
    apiGet,
    { refreshInterval: 60_000, revalidateOnFocus: false, shouldRetryOnError: false }
  );

  const summaryView = summary ?? { ...emptySummary, city };
  const summarySourceLabel = summaryError ? "Unavailable" : "API";
  const trendSourceLabel = trendsError ? "Unavailable" : "API";
  const trendData = useMemo(() => {
    return (trends?.points ?? []).map((point) => ({
      hour: new Date(point.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      speed: point.avg_speed,
      jam: point.avg_jam_factor,
    }));
  }, [trends]);
  const hasLimitedCoverage = summaryView.monitored_segments > 0 && summaryView.monitored_segments < 50;
  const alertList = alerts ?? [];
  const criticalAlerts = alertList.filter((alert) => alert.severity === "CRITICAL").length;
  const highAlerts = alertList.filter((alert) => alert.severity === "HIGH").length;
  const modelRows = modelStatus?.models.reduce((total, item) => total + item.rows, 0) ?? null;
  const primaryModel = modelStatus?.models[0];
  const warningMessages = [
    evidence?.data_freshness.warning,
    evidence?.overall_status && evidence.overall_status !== "OK" ? `System evidence status: ${evidence.overall_status}` : null,
    evidence?.dq_report.status && evidence.dq_report.status !== "PASS" ? `DQ status: ${evidence.dq_report.status}` : null,
  ].filter(Boolean);

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* HERO */}
      <div className="col-span-12 xl:col-span-9">
        {(summaryError || trendsError || alertsError) && (
          <div className="mb-4 rounded-2xl border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm font-medium text-destructive">
            Some operational endpoints are unavailable. The dashboard is not displaying replacement data.
          </div>
        )}
        {(summary?.message || trends?.message || hasLimitedCoverage) && (
          <div className="mb-4 rounded-2xl border border-primary/20 bg-primary-soft px-4 py-3 text-sm font-medium text-accent-foreground">
            {summary?.message || trends?.message || "Limited local data coverage"}
          </div>
        )}
        {warningMessages.length > 0 && (
          <div className="mb-4 rounded-2xl border border-warning/30 bg-[oklch(0.95_0.08_70)] px-4 py-3 text-sm font-medium text-[oklch(0.45_0.15_70)]">
            {warningMessages.join(" · ")}
          </div>
        )}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary to-[oklch(0.45_0.22_290)] p-8 text-primary-foreground">
          <div className="absolute -right-10 -top-10 h-60 w-60 rounded-full bg-white/10 blur-3xl" />
          <div className="absolute right-20 top-10 text-white/20">
            <Sparkle />
          </div>
          <div className="relative">
            <div className="text-[11px] font-semibold tracking-widest text-white/70">
              LOCAL GOLD SNAPSHOT · {evidence?.data_freshness.status?.toUpperCase() ?? "CHECKING"}
            </div>
            <h2 className="mt-3 max-w-xl text-3xl font-semibold leading-tight">
              Operational Traffic Intelligence from Local Gold Data
            </h2>
            <button className="mt-6 inline-flex items-center gap-2 rounded-full bg-foreground px-5 py-2.5 text-sm font-medium text-background">
              View Live Map
              <ArrowUpRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* metric strip */}
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            icon={MapIcon}
            label="Displayed segments"
            value={summaryLoading && !summary ? "..." : (summaryView.displayed_segments ?? summaryView.monitored_segments).toLocaleString()}
            delta={summarySourceLabel}
          />
          <StatCard
            icon={AlertTriangle}
            label="Active alerts"
            value={summaryLoading && !summary ? "..." : summaryView.active_alerts.toLocaleString()}
            delta={summarySourceLabel}
            tone="destructive"
          />
          <StatCard
            icon={Gauge}
            label="Avg speed"
            value={summaryLoading && !summary ? "..." : summaryView.avg_speed == null ? "N/A" : `${summaryView.avg_speed.toFixed(1)} km/h`}
            delta={summarySourceLabel}
            tone="warning"
          />
          <StatCard
            icon={Activity}
            label="Gold rows"
            value={summaryLoading && !summary ? "..." : (summaryView.total_gold_rows ?? systemStatus?.data.gold_row_count ?? 0).toLocaleString()}
            delta="local data"
            tone="success"
          />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
          <HealthRow label="Serving snapshot rows" value={(summaryView.serving_snapshot_rows ?? 0).toLocaleString()} />
          <HealthRow label="Train rows" value={(summaryView.train_rows ?? evidence?.model.training_rows ?? 0).toLocaleString()} />
          <HealthRow label="DQ status" value={evidence?.dq_report.status ?? "unknown"} />
          <HealthRow label="API benchmark p95" value={formatMs(evidence?.api_benchmark.p95_ms)} />
        </div>

        {/* trend chart */}
        <div className="mt-4 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold">Traffic Trend</h3>
              <p className="text-xs text-muted-foreground">
                Average speed & jam factor — last 24h · Data source: {trendSourceLabel}
              </p>
            </div>
            <div className="flex gap-2 text-xs">
              <span className="flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1.5">
                <span className="h-2 w-2 rounded-full bg-primary" /> Speed
              </span>
              <span className="flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1.5">
                <span className="h-2 w-2 rounded-full bg-warning" /> Jam factor
              </span>
            </div>
          </div>
          <div className="mt-4 h-64">
            {trendsLoading && !trends ? (
              <div className="flex h-full items-center justify-center rounded-2xl bg-secondary text-sm text-muted-foreground">
                Loading dashboard trend...
              </div>
            ) : trendData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData}>
                  <defs>
                    <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="oklch(0.58 0.21 285)" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="oklch(0.58 0.21 285)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="oklch(0.92 0.01 280)" vertical={false} />
                  <XAxis dataKey="hour" stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{
                      background: "white",
                      border: "1px solid oklch(0.92 0.01 280)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                  <Area type="monotone" dataKey="speed" stroke="oklch(0.58 0.21 285)" strokeWidth={2.5} fill="url(#g1)" />
                  <Area type="monotone" dataKey="jam" stroke="oklch(0.78 0.16 70)" strokeWidth={2} fill="transparent" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center rounded-2xl bg-secondary text-sm text-muted-foreground">
                No local trend data available.
              </div>
            )}
          </div>
        </div>

        {/* category cards row */}
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          {[
            { label: "Free Flow", count: `${summaryView.free_flow_segments} / ${summaryView.monitored_segments}`, color: "success" },
            { label: "Slow Traffic", count: `${summaryView.slow_segments} / ${summaryView.monitored_segments}`, color: "warning" },
            { label: "Congested", count: `${summaryView.congested_segments} / ${summaryView.monitored_segments}`, color: "destructive" },
          ].map((c) => (
            <div key={c.label} className="flex items-center justify-between rounded-2xl bg-card p-5">
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-11 w-11 items-center justify-center rounded-xl ${
                    c.color === "success"
                      ? "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]"
                      : c.color === "warning"
                      ? "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]"
                      : "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]"
                  }`}
                >
                  <Zap className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">{c.count}</div>
                  <div className="font-semibold">{c.label}</div>
                </div>
              </div>
              <button className="text-muted-foreground">⋮</button>
            </div>
          ))}
        </div>

        {/* live corridor tracking */}
        <div className="mt-4">
          <LiveCorridorTracking />
        </div>

        <div className="mt-4">
          <GraphHotspotPanel />
        </div>

        {/* recent alerts table */}
        <div className="mt-4 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">Recent Alerts</h3>
            <span className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">API</span>
          </div>
          <div className="mt-4 overflow-x-auto">
            {alertsLoading && !alerts ? (
              <div className="rounded-2xl bg-secondary p-4 text-sm text-muted-foreground">Loading alerts...</div>
            ) : alertsError ? (
              <div className="rounded-2xl bg-secondary p-4 text-sm text-muted-foreground">Alerts API unavailable.</div>
            ) : alertList.length === 0 ? (
              <div className="rounded-2xl bg-secondary p-4 text-sm text-muted-foreground">No active alerts in local Gold data.</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  <tr className="text-left">
                    <th className="pb-3 font-medium">Location</th>
                    <th className="pb-3 font-medium">Severity</th>
                    <th className="pb-3 font-medium">Cause</th>
                    <th className="pb-3 font-medium">Detected</th>
                    <th className="pb-3 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {alertList.slice(0, 5).map((alert) => (
                    <tr key={alert.alert_id} className="border-t border-border">
                      <td className="py-3 font-medium">{alert.segment_id}, {alert.city.toUpperCase()}</td>
                      <td>
                        <SeverityBadge level={formatSeverity(alert.severity)} />
                      </td>
                      <td className="text-muted-foreground">{alert.reason}</td>
                      <td className="text-muted-foreground">{new Date(alert.created_at).toLocaleString()}</td>
                      <td>
                        <button className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-muted-foreground hover:bg-secondary">
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* RIGHT SIDEBAR */}
      <div className="col-span-12 xl:col-span-3">
        <div className="rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">System Health</h3>
            <span className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">/system/status</span>
          </div>
          <div className="mt-5 flex flex-col items-center">
            <div className="relative">
              <svg width="160" height="160" viewBox="0 0 160 160">
                <circle cx="80" cy="80" r="68" fill="none" stroke="oklch(0.93 0.06 285)" strokeWidth="6" />
                <circle
                  cx="80"
                  cy="80"
                  r="68"
                  fill="none"
                  stroke="oklch(0.58 0.21 285)"
                  strokeWidth="6"
                  strokeDasharray="427"
                  strokeDashoffset={systemStatus?.api.status === "ok" ? "76" : "300"}
                  strokeLinecap="round"
                  transform="rotate(-90 80 80)"
                />
              </svg>
              <div className="absolute inset-3 flex items-center justify-center rounded-full bg-primary-soft">
                <Cpu className="h-12 w-12 text-accent-foreground" />
              </div>
              <div className="absolute right-0 top-3 rounded-full bg-primary px-2.5 py-0.5 text-xs font-semibold text-primary-foreground">
                {systemStatus?.api.status === "ok" ? "OK" : "N/A"}
              </div>
            </div>
            <div className="mt-4 text-center">
              <div className="text-lg font-semibold">
                {systemStatus ? `API ${systemStatus.api.status}` : "System status unavailable"}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                Data: {systemStatus?.data.status ?? "not_available"} · Streaming: bounded replay demo ({systemStatus?.streaming.status ?? "not_available"})
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-2xl bg-secondary p-4">
            <div className="grid gap-3 text-sm">
              <HealthRow label="Gold rows" value={systemStatus?.data.gold_row_count?.toLocaleString() ?? "not available"} />
              <HealthRow label="Segments" value={systemStatus?.data.segment_count?.toLocaleString() ?? "not available"} />
              <HealthRow label="Model" value={systemStatus?.model.model_name ?? "not available"} />
              <HealthRow label="Artifact" value={evidence?.model.artifact_version ?? "not available"} />
              <HealthRow label="Forecast p95" value={formatMs(systemStatus?.performance.forecast_p95_ms)} />
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">Model Performance</h3>
            <span className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">API</span>
          </div>
          <div className="mt-4 flex flex-col gap-3">
            {[
              { name: "MAE", v: primaryModel ? primaryModel.mae.toFixed(2) : "not available", sub: primaryModel ? `${primaryModel.horizon_minutes}m horizon` : "model status" },
              { name: "RMSE", v: primaryModel ? primaryModel.rmse.toFixed(2) : "not available", sub: primaryModel ? `${primaryModel.rows.toLocaleString()} rows` : "model status" },
              { name: "Latency", v: formatMs(systemStatus?.performance.forecast_p95_ms), sub: "forecast p95" },
              { name: "Train rows", v: modelRows == null ? "not available" : modelRows.toLocaleString(), sub: "all reported horizons" },
            ].map((m) => (
              <div key={m.name} className="flex items-center justify-between rounded-2xl border border-border p-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary-soft text-accent-foreground">
                    <Activity className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold">{m.name}</div>
                    <div className="text-[11px] text-muted-foreground">{m.sub}</div>
                  </div>
                </div>
                <div className="text-sm font-semibold">{m.v}</div>
              </div>
            ))}
            <button className="rounded-2xl bg-primary-soft py-3 text-sm font-medium text-accent-foreground">
              Open Monitoring
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SeverityBadge({ level }: { level: string }) {
  const map: Record<string, string> = {
    Low: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]",
    Medium: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]",
    High: "bg-primary-soft text-accent-foreground",
    Critical: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]",
  };
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${map[level]}`}>{level}</span>
  );
}

function formatSeverity(severity: ApiAlert["severity"]) {
  return (severity.charAt(0) + severity.slice(1).toLowerCase()) as "Critical" | "High" | "Medium" | "Low";
}

function formatMs(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)} ms` : "not measured";
}

function HealthRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="truncate text-xs font-semibold text-foreground">{value}</span>
    </div>
  );
}

function Sparkle() {
  return (
    <svg width="120" height="120" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l1.5 6.5L20 10l-6.5 1.5L12 18l-1.5-6.5L4 10l6.5-1.5z" />
    </svg>
  );
}

// Default segment ids representing the most congested currently active corridors.
type UpstreamSegment = {
  id: string;
  name: string;
  road_class: string;
  speed_kmh: number;
  status: "free" | "slow" | "congested";
};

type UpstreamResponse = {
  segment_id: string;
  updated_at: string;
  chain: UpstreamSegment[];
};

const fetcher = (url: string) =>
  apiGet<UpstreamResponse>(url);

function StatusBadge({ status }: { status: UpstreamSegment["status"] }) {
  const map = {
    free: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]",
    slow: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]",
    congested: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]",
  } as const;
  const label = { free: "Free", slow: "Slow", congested: "Congested" }[status];
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${map[status]}`}>
      {label}
    </span>
  );
}

function LiveCorridorTracking() {
  const { data: segments } = useSWR<TrafficSegment[]>(
    "/traffic/segments?city=hanoi&limit=10",
    apiGet,
    { refreshInterval: 60_000, revalidateOnFocus: false }
  );
  const segmentIds = (segments ?? []).map((segment) => segment.segment_id);
  const [manualSegmentId, setManualSegmentId] = useSWRSafeState<string | null>(null);
  const segmentId = manualSegmentId ?? segmentIds[0] ?? "";
  const { data, error, isLoading, isValidating } = useSWR<UpstreamResponse>(
    segmentId ? `/segments/${segmentId}/upstream` : null,
    fetcher,
    { refreshInterval: 60_000, revalidateOnFocus: false }
  );

  return (
    <div className="rounded-3xl bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold">Live Corridor Tracking</h3>
            <span className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">API</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Segment chain from local traffic state · auto-refresh 60s
            {isValidating && !isLoading ? " · refreshing…" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={segmentId}
            onChange={(e) => setManualSegmentId(e.target.value)}
            className="rounded-full border border-border bg-background px-3 py-1.5 text-xs"
            disabled={!segmentIds.length}
          >
            {segmentIds.length === 0 && <option value="">No segments</option>}
            {segmentIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        {!segmentId ? (
          <div className="rounded-2xl bg-secondary p-4 text-sm text-muted-foreground">
            No segment data available.
          </div>
        ) : error ? (
          <div className="rounded-2xl bg-secondary p-4 text-sm text-muted-foreground">
            Couldn't load upstream chain.
          </div>
        ) : isLoading || !data ? (
          <div className="space-y-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-xl bg-secondary" />
            ))}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr className="text-left">
                <th className="pb-3 font-medium">#</th>
                <th className="pb-3 font-medium">Segment</th>
                <th className="pb-3 font-medium">Speed</th>
                <th className="pb-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.chain.map((seg, idx) => (
                <tr key={seg.id} className="border-t border-border">
                  <td className="py-3 text-muted-foreground">{idx + 1}</td>
                  <td className="py-3">
                    <div className="font-medium">{seg.name}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {seg.id} · {seg.road_class}
                    </div>
                  </td>
                  <td className="py-3 font-medium">{seg.speed_kmh} km/h</td>
                  <td className="py-3">
                    <StatusBadge status={seg.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function GraphHotspotPanel() {
  const { data: health } = useSWR<GraphHealth>(
    "/graph/health",
    apiGet,
    { refreshInterval: 60_000, revalidateOnFocus: false, shouldRetryOnError: false }
  );
  const { data, error, isLoading } = useSWR<GraphHotspotsResponse>(
    "/graph/hotspots?limit=5",
    apiGet,
    { refreshInterval: 60_000, revalidateOnFocus: false, shouldRetryOnError: false }
  );
  const rows = data?.hotspots ?? [];

  return (
    <div className="rounded-3xl bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold">Graph Hotspots</h3>
            <span className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">
              {health?.backend ?? "graph"}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Neo4j road graph when available · local Gold fallback is labeled by the API
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <MapIcon className="h-4 w-4" />
          {health?.segments != null ? `${health.segments} nodes · ${health.relationships ?? 0} links` : health?.status ?? "checking"}
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        {error ? (
          <div className="rounded-2xl bg-secondary p-4 text-sm text-muted-foreground">Graph API unavailable.</div>
        ) : isLoading && !data ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-xl bg-secondary" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="rounded-2xl bg-secondary p-4 text-sm text-muted-foreground">No graph hotspots available.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr className="text-left">
                <th className="pb-3 font-medium">Segment</th>
                <th className="pb-3 font-medium">Jam</th>
                <th className="pb-3 font-medium">Speed</th>
                <th className="pb-3 font-medium">Neighbors</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.segment_id} className="border-t border-border">
                  <td className="py-3">
                    <div className="font-medium">{row.name || row.segment_id}</div>
                    <div className="text-[11px] text-muted-foreground">{row.segment_id} · {row.city ?? "unknown"}</div>
                  </td>
                  <td className="py-3 font-medium">{row.jam_factor == null ? "N/A" : row.jam_factor.toFixed(1)}</td>
                  <td className="py-3 font-medium">{row.speed == null ? "N/A" : `${row.speed.toFixed(1)} km/h`}</td>
                  <td className="py-3 text-muted-foreground">{row.neighbors?.length ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// Local hook to avoid pulling extra imports at the top of the file.
function useSWRSafeState<T>(initial: T) {
  return useState<T>(initial);
}
