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
  Bar,
  BarChart,
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

const demoTrend = Array.from({ length: 24 }, (_, i) => ({
  hour: `${i}:00`,
  speed: 28 + Math.sin(i / 3) * 12 + (i > 7 && i < 10 ? -8 : 0) + (i > 16 && i < 20 ? -10 : 0),
  jam: 4 + Math.cos(i / 3) * 1.5 + (i > 7 && i < 10 ? 2 : 0) + (i > 16 && i < 20 ? 3 : 0),
}));

const segments = [
  { name: "Mon", value: 38 },
  { name: "Tue", value: 45 },
  { name: "Wed", value: 32 },
  { name: "Thu", value: 58 },
  { name: "Fri", value: 72 },
  { name: "Sat", value: 41 },
  { name: "Sun", value: 29 },
];

type DashboardSummary = {
  city: string;
  monitored_segments: number;
  active_alerts: number;
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

const demoSummary: DashboardSummary = {
  city: "hanoi",
  monitored_segments: 2481,
  active_alerts: 17,
  free_flow_segments: 1842,
  slow_segments: 412,
  congested_segments: 227,
  avg_speed: 34,
  avg_jam_factor: 5.4,
  latest_timestamp: null,
  data_source: "demo_fallback",
  is_demo: true,
};

const emptySummary: DashboardSummary = {
  city: "hanoi",
  monitored_segments: 0,
  active_alerts: 0,
  free_flow_segments: 0,
  slow_segments: 0,
  congested_segments: 0,
  avg_speed: null,
  avg_jam_factor: null,
  latest_timestamp: null,
  data_source: "gold_local",
  is_demo: false,
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

  const usingDemoFallback = Boolean(summaryError || trendsError);
  const summaryView = summaryError ? demoSummary : summary ?? { ...emptySummary, city };
  const summarySourceLabel = summaryError ? "Demo fallback" : "API";
  const trendSourceLabel = trendsError ? "Demo fallback" : "API";
  const trendData = useMemo(() => {
    if (trendsError) return demoTrend;
    return (trends?.points ?? []).map((point) => ({
      hour: new Date(point.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      speed: point.avg_speed,
      jam: point.avg_jam_factor,
    }));
  }, [trends, trendsError]);
  const hasLimitedCoverage = !usingDemoFallback && summaryView.monitored_segments > 0 && summaryView.monitored_segments < 50;

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* HERO */}
      <div className="col-span-12 xl:col-span-9">
        {usingDemoFallback && (
          <div className="mb-4 rounded-2xl border border-orange-200 bg-orange-50 px-4 py-3 text-sm font-medium text-orange-800">
            Dashboard API unavailable. Showing demo fallback.
          </div>
        )}
        {!usingDemoFallback && (summary?.message || trends?.message || hasLimitedCoverage) && (
          <div className="mb-4 rounded-2xl border border-primary/20 bg-primary-soft px-4 py-3 text-sm font-medium text-accent-foreground">
            {summary?.message || trends?.message || "Limited local data coverage"}
          </div>
        )}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary to-[oklch(0.45_0.22_290)] p-8 text-primary-foreground">
          <div className="absolute -right-10 -top-10 h-60 w-60 rounded-full bg-white/10 blur-3xl" />
          <div className="absolute right-20 top-10 text-white/20">
            <Sparkle />
          </div>
          <div className="relative">
            <div className="text-[11px] font-semibold tracking-widest text-white/70">REAL-TIME ANALYTICS</div>
            <h2 className="mt-3 max-w-xl text-3xl font-semibold leading-tight">
              Cognitive Traffic Intelligence for a Smarter City
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
            label="Monitored segments"
            value={summaryLoading && !summary ? "..." : summaryView.monitored_segments.toLocaleString()}
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
            label="Avg city speed"
            value={summaryLoading && !summary ? "..." : summaryView.avg_speed == null ? "N/A" : `${summaryView.avg_speed.toFixed(1)} km/h`}
            delta={summarySourceLabel}
            tone="warning"
          />
          <StatCard
            icon={Activity}
            label="Avg jam factor"
            value={summaryLoading && !summary ? "..." : summaryView.avg_jam_factor == null ? "N/A" : summaryView.avg_jam_factor.toFixed(1)}
            delta={summarySourceLabel}
            tone="success"
          />
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



        {/* recent alerts table */}
        <div className="mt-4 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">Recent Alerts</h3>
            <span className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">Demo</span>
          </div>
          <div className="mt-4 overflow-x-auto">
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
                {[
                  { loc: "Cau Giay, Hanoi", sev: "High", cause: "Peak hour + rain", t: "2m ago" },
                  { loc: "District 1, HCMC", sev: "Critical", cause: "Accident reported", t: "8m ago" },
                  { loc: "Dong Da, Hanoi", sev: "Medium", cause: "Public event", t: "21m ago" },
                ].map((r) => (
                  <tr key={r.loc} className="border-t border-border">
                    <td className="py-3 font-medium">{r.loc}</td>
                    <td>
                      <SeverityBadge level={r.sev} />
                    </td>
                    <td className="text-muted-foreground">{r.cause}</td>
                    <td className="text-muted-foreground">{r.t}</td>
                    <td>
                      <button className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-muted-foreground hover:bg-secondary">
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* RIGHT SIDEBAR */}
      <div className="col-span-12 xl:col-span-3">
        <div className="rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">System Health</h3>
            <span className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">Demo</span>
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
                  strokeDashoffset="76"
                  strokeLinecap="round"
                  transform="rotate(-90 80 80)"
                />
              </svg>
              <div className="absolute inset-3 flex items-center justify-center rounded-full bg-primary-soft">
                <Cpu className="h-12 w-12 text-accent-foreground" />
              </div>
              <div className="absolute right-0 top-3 rounded-full bg-primary px-2.5 py-0.5 text-xs font-semibold text-primary-foreground">
                82%
              </div>
            </div>
            <div className="mt-4 text-center">
              <div className="text-lg font-semibold">All Systems Healthy ⚡</div>
              <div className="mt-1 text-xs text-muted-foreground">
                Kafka, Spark & API operating within thresholds.
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-2xl bg-secondary p-4">
            <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
              <span>Predictions / day</span>
              <span className="font-semibold">Demo</span>
            </div>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={segments}>
                  <XAxis dataKey="name" stroke="oklch(0.5 0.02 270)" fontSize={10} tickLine={false} axisLine={false} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {segments.map((_, i) => (
                      <Bar key={i} dataKey="value" fill={i === 4 ? "oklch(0.58 0.21 285)" : "oklch(0.85 0.08 285)"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">Model Performance</h3>
            <span className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">Demo</span>
          </div>
          <div className="mt-4 flex flex-col gap-3">
            {[
              { name: "MAE", v: "3.21", sub: "v2024.11" },
              { name: "RMSE", v: "5.07", sub: "v2024.11" },
              { name: "Latency", v: "184 ms", sub: "p95" },
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

function Sparkle() {
  return (
    <svg width="120" height="120" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l1.5 6.5L20 10l-6.5 1.5L12 18l-1.5-6.5L4 10l6.5-1.5z" />
    </svg>
  );
}

// Default segment ids representing the most congested currently active corridors.
const CONGESTED_DEFAULTS = [
  "HN_001",
  "HN_002",
  "HN_003",
];

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
  const [segmentId, setSegmentId] = useSWRSafeState(CONGESTED_DEFAULTS[0]);
  const { data, error, isLoading, isValidating } = useSWR<UpstreamResponse>(
    `/segments/${segmentId}/upstream`,
    fetcher,
    { refreshInterval: 60_000, revalidateOnFocus: false }
  );

  return (
    <div className="rounded-3xl bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">Live Corridor Tracking</h3>
          <p className="text-xs text-muted-foreground">
            Upstream chain for the most congested active segment · auto-refresh 60s
            {isValidating && !isLoading ? " · refreshing…" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={segmentId}
            onChange={(e) => setSegmentId(e.target.value)}
            className="rounded-full border border-border bg-background px-3 py-1.5 text-xs"
          >
            {CONGESTED_DEFAULTS.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        {error ? (
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

// Local hook to avoid pulling extra imports at the top of the file.
function useSWRSafeState<T>(initial: T) {
  return useState<T>(initial);
}
