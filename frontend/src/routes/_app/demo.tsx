import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle, Brain, CheckCircle2, Flame, Gauge, Map, Route as RouteIcon, Sparkles, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { apiGet } from "@/lib/api/client";

export const Route = createFileRoute("/_app/demo")({
  component: DemoFlowPage,
});

type DashboardSummary = {
  city: string;
  monitored_segments: number;
  active_alerts: number;
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
  points: Array<{ timestamp: string; avg_speed: number; avg_jam_factor: number }>;
  available_points: number;
  min_timestamp: string | null;
  max_timestamp: string | null;
  data_source: string;
};

type TrafficSegment = {
  segment_id: string;
  city: string;
  current_speed: number;
  free_flow_speed: number;
  jam_factor: number;
  timestamp: string;
  road_class: string;
};

type Hotspot = {
  hotspot_id: string;
  cluster_id: number;
  city: string;
  num_segments: number;
  avg_congestion: number;
  avg_jam_factor: number;
  severity: string;
  detected_at: string;
};

type Prediction = {
  segment_id: string;
  horizon: "15m" | "60m";
  predicted_speed: number | null;
  current_speed: number | null;
  current_jam_factor: number | null;
  model_name: string;
  model_artifact: string;
  is_fallback: boolean;
  required_feature_count: number;
  available_feature_count: number;
  filled_feature_count: number;
  latest_timestamp?: string | null;
};

type PredictedHotspot = {
  segment_id: string;
  road_name: string;
  city: string;
  current_speed: number;
  predicted_speed: number;
  free_flow_speed: number;
  horizon: string;
  risk_level: string;
  reason: string;
  latest_timestamp?: string | null;
  model_name: string;
  filled_feature_count: number;
  is_fallback: boolean;
};

function DemoFlowPage() {
  const [selectedSegmentId, setSelectedSegmentId] = useState("");
  const { data: summary, error: summaryError, isLoading: summaryLoading } = useSWR<DashboardSummary>(
    "/dashboard/summary?city=hanoi",
    apiGet,
    { revalidateOnFocus: false }
  );
  const { data: trends, error: trendsError } = useSWR<DashboardTrends>(
    "/dashboard/trends?city=hanoi&hours=24",
    apiGet,
    { revalidateOnFocus: false }
  );
  const { data: segments, error: segmentsError, isLoading: segmentsLoading } = useSWR<TrafficSegment[]>(
    "/traffic/segments?city=hanoi&limit=100",
    apiGet,
    { revalidateOnFocus: false }
  );
  const { data: hotspots, error: hotspotsError } = useSWR<Hotspot[]>(
    "/hotspots?city=hanoi",
    apiGet,
    { revalidateOnFocus: false }
  );
  const { data: predictedHotspots, error: predictedHotspotsError } = useSWR<PredictedHotspot[]>(
    "/hotspots/predicted?city=hanoi&horizon=15m",
    apiGet,
    { revalidateOnFocus: false }
  );

  const segmentId = selectedSegmentId || segments?.[0]?.segment_id || "";
  const selectedSegment = segments?.find((segment) => segment.segment_id === segmentId);
  const { data: prediction15, error: prediction15Error } = useSWR<Prediction>(
    segmentId ? `/traffic/predict/${encodeURIComponent(segmentId)}?horizon=15m` : null,
    apiGet,
    { revalidateOnFocus: false }
  );
  const { data: prediction60, error: prediction60Error } = useSWR<Prediction>(
    segmentId ? `/traffic/predict/${encodeURIComponent(segmentId)}?horizon=60m` : null,
    apiGet,
    { revalidateOnFocus: false }
  );

  const latestTimestamp = summary?.latest_timestamp ?? segments?.[0]?.timestamp ?? null;
  const topSegments = useMemo(() => (segments ?? []).slice(0, 5), [segments]);
  const topHotspots = useMemo(() => (hotspots ?? []).slice(0, 4), [hotspots]);
  const topPredictedHotspots = useMemo(() => (predictedHotspots ?? []).slice(0, 4), [predictedHotspots]);
  const apiErrors = [
    summaryError && "/dashboard/summary",
    trendsError && "/dashboard/trends",
    segmentsError && "/traffic/segments",
    hotspotsError && "/hotspots",
    predictedHotspotsError && "/hotspots/predicted",
    prediction15Error && "/traffic/predict 15m",
    prediction60Error && "/traffic/predict 60m",
  ].filter(Boolean);

  return (
    <div className="space-y-4">
      <section className="rounded-3xl bg-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              <Sparkles className="h-4 w-4 text-primary" />
              Demo Flow
            </div>
            <h1 className="mt-2 text-2xl font-semibold">Cognitive Traffic Analytics Platform</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              A focused walkthrough of the real demo path: TomTom traffic snapshots, local Silver/Gold data,
              geospatial segments, current congestion analytics, LightGBM speed forecasts, and predicted hotspot signals.
            </p>
          </div>
          <div className="rounded-2xl bg-secondary px-4 py-3 text-xs text-muted-foreground">
            <div className="font-semibold text-foreground">Demo city: Hanoi</div>
            <div>Backend API: FastAPI · Data source: local gold traffic data</div>
          </div>
        </div>
        {apiErrors.length > 0 && (
          <div className="mt-4 rounded-2xl border border-orange-200 bg-orange-50 px-4 py-3 text-sm font-medium text-orange-800">
            API unavailable for: {apiErrors.join(", ")}. Start the backend with make docker-api and keep VITE_API_BASE_URL=http://localhost:8000.
          </div>
        )}
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <MetricCard icon={RouteIcon} label="Monitored segments" value={loadingValue(summaryLoading, summary?.monitored_segments)} source="/dashboard/summary" />
        <MetricCard icon={AlertTriangle} label="Active alerts" value={loadingValue(summaryLoading, summary?.active_alerts)} source="/dashboard/summary" />
        <MetricCard icon={Gauge} label="Avg speed" value={formatSpeed(summary?.avg_speed)} source="Gold latest rows" />
        <MetricCard icon={TrendingUp} label="Avg jam factor" value={formatNumber(summary?.avg_jam_factor)} source="Gold latest rows" />
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <DemoSection
          title="1. Local Data Coverage"
          icon={CheckCircle2}
          source="/dashboard/summary · /traffic/segments"
          note="This section uses local gold traffic data generated from TomTom Flow Segment snapshots."
        >
          <div className="grid gap-3 text-sm">
            <KeyValue label="City" value={summary?.city?.toUpperCase() ?? "HANOI"} />
            <KeyValue label="Segments in current demo" value={loadingValue(segmentsLoading, segments?.length ?? summary?.monitored_segments)} />
            <KeyValue label="Latest timestamp" value={formatDate(latestTimestamp)} />
            <KeyValue label="Trend points, last 24h" value={String(trends?.available_points ?? 0)} />
          </div>
        </DemoSection>

        <DemoSection
          title="2. Real-time Traffic"
          icon={Gauge}
          source="/traffic/segments"
          note="Segments are sorted by current jam factor so the demo starts with the most congested corridors."
        >
          <div className="space-y-2">
            {topSegments.length === 0 ? (
              <EmptyState text={segmentsError ? segmentsError.message : "No segments returned yet."} />
            ) : (
              topSegments.map((segment) => (
                <CompactRow
                  key={segment.segment_id}
                  title={segment.segment_id}
                  detail={`Speed ${segment.current_speed.toFixed(1)} km/h · Jam ${segment.jam_factor.toFixed(1)}`}
                  badge={segment.jam_factor >= 6 ? "Congested" : segment.jam_factor >= 3 ? "Slow" : "Free"}
                />
              ))
            )}
          </div>
        </DemoSection>

        <DemoSection
          title="3. Geospatial Map"
          icon={Map}
          source="/segments/geojson"
          note="The full map page renders TomTom segment geometry as GeoJSON polylines."
        >
          <div className="rounded-2xl bg-secondary p-4 text-sm">
            <div className="text-2xl font-semibold">{summary?.monitored_segments ?? segments?.length ?? 0}</div>
            <div className="text-xs text-muted-foreground">GeoJSON-capable Hanoi segments in this local demo dataset.</div>
            <Link to="/live-map" search={{ city: "hanoi" }} className="mt-4 inline-flex rounded-full bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground">
              Open Live Map
            </Link>
          </div>
        </DemoSection>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <DemoSection
          title="4. Current Hotspots"
          icon={Flame}
          source="/hotspots"
          note="Current hotspots are derived from latest congested segments and grouped for operational scanning."
        >
          <div className="space-y-2">
            {topHotspots.length === 0 ? (
              <EmptyState text={hotspotsError ? hotspotsError.message : "No current hotspots returned."} />
            ) : (
              topHotspots.map((hotspot) => (
                <CompactRow
                  key={hotspot.hotspot_id}
                  title={`Cluster ${hotspot.cluster_id}`}
                  detail={`${hotspot.num_segments} segment(s) · avg jam ${hotspot.avg_jam_factor.toFixed(1)}`}
                  badge={hotspot.severity}
                />
              ))
            )}
          </div>
        </DemoSection>

        <DemoSection
          title="5. Forecast"
          icon={Brain}
          source="/traffic/predict/{segment_id}"
          note="Forecasts are produced by LightGBM models for 15-minute and 60-minute horizons."
        >
          <div className="space-y-3">
            <select
              value={segmentId}
              onChange={(event) => setSelectedSegmentId(event.target.value)}
              className="h-10 w-full rounded-2xl border border-border bg-background px-3 text-sm"
              disabled={!segments?.length}
            >
              {!segments?.length && <option value="">No segment available</option>}
              {segments?.map((segment) => (
                <option key={segment.segment_id} value={segment.segment_id}>
                  {segment.segment_id} · {segment.current_speed.toFixed(1)} km/h
                </option>
              ))}
            </select>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <SmallForecast label="Current" value={formatSpeed(selectedSegment?.current_speed ?? prediction15?.current_speed)} detail={segmentId || "No segment"} />
              <SmallForecast label="+15m" value={formatSpeed(prediction15?.predicted_speed)} detail={featureDetail(prediction15)} />
              <SmallForecast label="+60m" value={formatSpeed(prediction60?.predicted_speed)} detail={featureDetail(prediction60)} />
            </div>
            {(prediction15?.filled_feature_count || prediction60?.filled_feature_count) ? (
              <div className="rounded-2xl bg-primary-soft px-3 py-2 text-xs font-medium text-accent-foreground">
                Partial feature fill is present in model inputs. This is acceptable for the demo but should be reduced for production.
              </div>
            ) : null}
          </div>
        </DemoSection>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <DemoSection
          title="6. Predicted Hotspots"
          icon={AlertTriangle}
          source="/hotspots/predicted?city=hanoi&horizon=15m"
          note="Predicted hotspots are rule-based risk signals derived from predicted speed, free-flow speed, and current speed drop."
        >
          <div className="space-y-2">
            {topPredictedHotspots.length === 0 ? (
              <EmptyState text={predictedHotspotsError ? predictedHotspotsError.message : "No predicted hotspots returned for the selected horizon."} />
            ) : (
              topPredictedHotspots.map((hotspot) => (
                <CompactRow
                  key={`${hotspot.segment_id}-${hotspot.horizon}`}
                  title={hotspot.road_name || hotspot.segment_id}
                  detail={`${hotspot.current_speed.toFixed(1)} -> ${hotspot.predicted_speed.toFixed(1)} km/h · ${hotspot.reason}`}
                  badge={hotspot.risk_level}
                />
              ))
            )}
          </div>
        </DemoSection>

        <DemoSection
          title="7. What is Real vs Demo"
          icon={CheckCircle2}
          source="Demo readiness note"
          note="This section is intentionally visible so the presentation stays honest."
        >
          <div className="grid gap-3 md:grid-cols-2">
            <RealityList
              title="Real in this demo"
              items={[
                "Traffic segment data from local gold dataset",
                "TomTom geometry rendered on Live Map",
                "Dashboard summary and trends",
                "Alerts and current hotspots",
                "LightGBM speed forecast API",
              ]}
            />
            <RealityList
              title="Demo or limited"
              items={[
                "Around 75 Hanoi segments, not full city coverage",
                "Some model inputs use feature fill",
                "Predicted hotspots are a rule layer on forecasts",
                "Monitoring and explanations pages are static",
                "Batch snapshots, not production streaming",
              ]}
            />
          </div>
        </DemoSection>
      </section>
    </div>
  );
}

function DemoSection({
  title,
  icon: Icon,
  source,
  note,
  children,
}: {
  title: string;
  icon: typeof Sparkles;
  source: string;
  note: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-3xl bg-card p-6">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-primary" />
            <h2 className="text-base font-semibold">{title}</h2>
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{note}</p>
        </div>
        <span className="shrink-0 rounded-full bg-secondary px-3 py-1 text-[11px] font-semibold text-muted-foreground">
          {source}
        </span>
      </div>
      {children}
    </section>
  );
}

function MetricCard({ icon: Icon, label, value, source }: { icon: typeof Sparkles; label: string; value: string; source: string }) {
  return (
    <div className="rounded-3xl bg-card p-5">
      <div className="flex items-start justify-between gap-2">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-accent-foreground">
          <Icon className="h-5 w-5" />
        </div>
        <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">API</span>
      </div>
      <div className="mt-4 text-2xl font-semibold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-2 text-[10px] text-muted-foreground">{source}</div>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-border px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold">{value}</span>
    </div>
  );
}

function CompactRow({ title, detail, badge }: { title: string; detail: string; badge: string }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-2xl border border-border px-3 py-2.5">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold">{title}</div>
        <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{detail}</div>
      </div>
      <span className="shrink-0 rounded-full bg-secondary px-2.5 py-1 text-[10px] font-semibold capitalize text-muted-foreground">
        {badge}
      </span>
    </div>
  );
}

function SmallForecast({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl bg-secondary p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
      <div className="mt-1 truncate text-[11px] text-muted-foreground">{detail}</div>
    </div>
  );
}

function RealityList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-border p-4">
      <div className="text-sm font-semibold">{title}</div>
      <ul className="mt-3 space-y-2 text-xs leading-5 text-muted-foreground">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-2xl bg-secondary px-3 py-4 text-sm text-muted-foreground">{text}</div>;
}

function formatSpeed(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)} km/h` : "N/A";
}

function formatNumber(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(1) : "N/A";
}

function loadingValue(isLoading: boolean, value?: number | null) {
  if (isLoading) return "...";
  return typeof value === "number" ? value.toLocaleString() : "N/A";
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "N/A";
}

function featureDetail(prediction?: Prediction) {
  if (!prediction) return "Waiting for API";
  const fill = prediction.filled_feature_count ? ` · ${prediction.filled_feature_count} filled` : "";
  return `${prediction.available_feature_count}/${prediction.required_feature_count} features${fill}`;
}
