import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import { useEffect, useMemo } from "react";
import useSWR from "swr";
import { Activity, Brain, CloudRain, Database, History, MapPin, TrendingDown, TrendingUp } from "lucide-react";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { apiGet } from "@/lib/api/client";
import { useAppStore, type CityKey } from "@/lib/store/useAppStore";

const CITIES: { key: CityKey; label: string }[] = [
  { key: "hanoi", label: "Hanoi" },
  { key: "hcmc", label: "HCMC" },
];

const searchSchema = z.object({
  city: fallback(z.enum(["hanoi", "hcmc"]), "hanoi").default("hanoi"),
  segment: fallback(z.string(), "").default(""),
  horizon: fallback(z.enum(["15m", "60m"]), "15m").default("15m"),
});

export const Route = createFileRoute("/_app/explanations")({
  validateSearch: zodValidator(searchSchema),
  component: ExplanationsPage,
});

type TrafficSegment = {
  segment_id: string;
  city: CityKey;
  current_speed: number;
  free_flow_speed: number;
  jam_factor: number;
  timestamp: string;
  road_class: string;
  district: string;
};

type Prediction = {
  segment_id: string;
  horizon: "15m" | "60m";
  predicted_speed: number | null;
  current_speed: number | null;
  current_jam_factor: number | null;
  model_name: string;
  model_artifact: string;
  data_source: string;
  filled_feature_count: number;
  required_feature_count: number;
  available_feature_count: number;
  latest_timestamp?: string | null;
};

type ExplanationFeature = {
  name: string;
  value: number | string | boolean | null;
  baseline_value: number | string | boolean | null;
  shap_value: number;
  direction: "raises_speed" | "lowers_speed";
};

type Explanation = {
  prediction_id: string;
  segment_id: string;
  horizon: "15m" | "60m";
  predicted_speed: number;
  current_speed: number | null;
  current_jam_factor: number | null;
  model_name: string;
  model_artifact: string;
  data_source: string;
  attribution_method: string;
  required_feature_count: number;
  available_feature_count: number;
  filled_feature_count: number;
  missing_features: string[];
  top_features: ExplanationFeature[];
  weather_context: Record<string, number>;
  baseline_context: Record<string, number | string>;
};

function formatSpeed(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)} km/h` : "n/a";
}

function formatValue(value: ExplanationFeature["value"]) {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === "boolean") return value ? "true" : "false";
  return value ?? "n/a";
}

function featureLabel(name: string) {
  return name.replaceAll("_", " ");
}

function ExplanationsPage() {
  const search = Route.useSearch() as { city: CityKey; segment: string; horizon: "15m" | "60m" };
  const { city, segment, horizon } = search;
  const navigate = useNavigate({ from: "/explanations" });
  const setSelectedCity = useAppStore((s) => s.setSelectedCity);
  const setSelectedSegment = useAppStore((s) => s.setSelectedSegment);

  const { data: segments, error: segmentsError, isLoading: segmentsLoading } = useSWR<TrafficSegment[]>(
    `/traffic/segments?city=${city}&limit=100`,
    apiGet,
    { refreshInterval: 60_000 }
  );

  const selectedSegmentId = segment || segments?.[0]?.segment_id || "";
  const selectedSegment = segments?.find((item) => item.segment_id === selectedSegmentId);

  const { data: prediction, error: predictionError, isLoading: predictionLoading } = useSWR<Prediction>(
    selectedSegmentId ? `/traffic/predict/${encodeURIComponent(selectedSegmentId)}?horizon=${horizon}` : null,
    apiGet,
    { refreshInterval: 60_000 }
  );
  const { data: explanation, error: explanationError, isLoading: explanationLoading } = useSWR<Explanation>(
    selectedSegmentId ? `/predictions/${encodeURIComponent(selectedSegmentId)}/explain?horizon=${horizon}&top_n=10` : null,
    apiGet,
    { refreshInterval: 60_000 }
  );

  useEffect(() => {
    setSelectedCity(city);
    setSelectedSegment(selectedSegmentId || null);
  }, [city, selectedSegmentId, setSelectedCity, setSelectedSegment]);

  const apiError = segmentsError || predictionError || explanationError;
  const loading = segmentsLoading || predictionLoading || explanationLoading;
  const maxImpact = useMemo(
    () => Math.max(1, ...((explanation?.top_features ?? []).map((feature) => Math.abs(feature.shap_value)))),
    [explanation]
  );

  const setCity = (next: CityKey) => navigate({ search: { city: next, segment: "", horizon } });
  const setSegment = (next: string) => navigate({ search: { city, segment: next, horizon } });
  const setHorizon = (next: "15m" | "60m") => navigate({ search: { city, segment: selectedSegmentId, horizon: next } });

  return (
    <PlaceholderPage title="Explanations" subtitle="Model-derived feature attribution for local traffic forecasts">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-wrap items-center gap-2">
          {CITIES.map((item) => (
            <button
              key={item.key}
              onClick={() => setCity(item.key)}
              className={`rounded-full px-4 py-2 text-xs font-semibold ${item.key === city ? "bg-primary text-primary-foreground" : "bg-card text-muted-foreground"}`}
            >
              {item.label}
            </button>
          ))}
          <select
            value={selectedSegmentId}
            onChange={(event) => setSegment(event.target.value)}
            className="h-9 min-w-64 rounded-full border border-border bg-card px-3 text-xs font-semibold text-foreground outline-none"
            disabled={!segments?.length}
          >
            {!segments?.length && <option value="">No segments</option>}
            {segments?.map((item) => (
              <option key={item.segment_id} value={item.segment_id}>
                {item.segment_id} · {formatSpeed(item.current_speed)}
              </option>
            ))}
          </select>
          <div className="flex rounded-full bg-card p-1">
            {(["15m", "60m"] as const).map((item) => (
              <button
                key={item}
                onClick={() => setHorizon(item)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold ${item === horizon ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        {(apiError || loading || !selectedSegmentId) && (
          <div className="col-span-12 rounded-2xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
            {apiError
              ? `Explanation API unavailable: ${apiError.message}`
              : loading
                ? "Loading model explanation..."
                : "Select a segment to explain."}
          </div>
        )}

        <div className="col-span-12 grid grid-cols-1 gap-4 md:grid-cols-4">
          <MetricCard icon={Brain} label="Predicted" value={formatSpeed(explanation?.predicted_speed ?? prediction?.predicted_speed)} detail={`${horizon} forecast`} />
          <MetricCard icon={Activity} label="Current" value={formatSpeed(explanation?.current_speed ?? prediction?.current_speed ?? selectedSegment?.current_speed)} detail={`Jam ${explanation?.current_jam_factor ?? prediction?.current_jam_factor ?? selectedSegment?.jam_factor ?? "n/a"}`} />
          <MetricCard icon={Database} label="Model" value={explanation?.model_name ?? prediction?.model_name ?? "n/a"} detail={explanation?.model_artifact ?? prediction?.model_artifact ?? "Waiting for API"} />
          <MetricCard icon={MapPin} label="Segment" value={selectedSegmentId || "n/a"} detail={selectedSegment?.district ?? city} />
        </div>

        <div className="col-span-12 lg:col-span-8 rounded-3xl bg-card p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">Top Feature Contributions</h3>
              <p className="text-xs text-muted-foreground">Values are computed from the active forecast model by replacing one feature at a time with its training baseline.</p>
            </div>
            <span className="rounded-full bg-secondary px-3 py-1 text-[11px] text-muted-foreground">
              {explanation?.available_feature_count ?? prediction?.available_feature_count ?? 0}/{explanation?.required_feature_count ?? prediction?.required_feature_count ?? 0} features
            </span>
          </div>
          <div className="mt-5 space-y-3">
            {(explanation?.top_features ?? []).map((feature) => {
              const lowersSpeed = feature.shap_value < 0;
              const width = `${Math.max(6, (Math.abs(feature.shap_value) / maxImpact) * 100)}%`;
              const Icon = lowersSpeed ? TrendingDown : TrendingUp;
              return (
                <div key={feature.name} className="flex items-center gap-3">
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${lowersSpeed ? "bg-destructive/10 text-destructive" : "bg-success/10 text-success"}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="truncate text-sm font-medium">{featureLabel(feature.name)}</span>
                      <span className={`text-xs font-semibold ${lowersSpeed ? "text-destructive" : "text-success"}`}>
                        {feature.shap_value > 0 ? "+" : ""}{feature.shap_value.toFixed(2)} km/h
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
                        <div className={`h-full rounded-full ${lowersSpeed ? "bg-destructive" : "bg-success"}`} style={{ width }} />
                      </div>
                      <span className="w-40 truncate text-right text-[11px] text-muted-foreground">
                        {formatValue(feature.value)} vs {formatValue(feature.baseline_value)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            {explanation && !explanation.top_features.length && (
              <div className="rounded-2xl bg-secondary px-4 py-3 text-sm text-muted-foreground">
                The model returned no non-zero single-feature contributions for this segment.
              </div>
            )}
          </div>
        </div>

        <div className="col-span-12 space-y-4 lg:col-span-4">
          <ContextPanel icon={CloudRain} title="Weather Context">
            <ContextRow label="Temperature" value={`${(explanation?.weather_context.temperature ?? 0).toFixed(1)} C`} />
            <ContextRow label="Humidity" value={`${(explanation?.weather_context.humidity ?? 0).toFixed(0)}%`} />
            <ContextRow label="Rain 1h" value={`${(explanation?.weather_context.rain_1h ?? 0).toFixed(1)} mm`} />
            <ContextRow label="Visibility" value={`${(explanation?.weather_context.visibility ?? 0).toFixed(0)} m`} />
          </ContextPanel>
          <ContextPanel icon={History} title="Baseline Context">
            <ContextRow label="P15" value={formatSpeed(Number(explanation?.baseline_context.p15 ?? 0))} />
            <ContextRow label="P50" value={formatSpeed(Number(explanation?.baseline_context.p50 ?? 0))} />
            <ContextRow label="P85" value={formatSpeed(Number(explanation?.baseline_context.p85 ?? 0))} />
            <ContextRow label="Typical hour" value={formatSpeed(Number(explanation?.baseline_context.typical_hour_avg ?? 0))} />
          </ContextPanel>
          <ContextPanel icon={Database} title="Attribution">
            <ContextRow label="Method" value={explanation?.attribution_method?.replaceAll("_", " ") ?? "n/a"} />
            <ContextRow label="Source" value={explanation?.data_source ?? prediction?.data_source ?? "n/a"} />
            <ContextRow label="Filled features" value={`${explanation?.filled_feature_count ?? prediction?.filled_feature_count ?? 0}`} />
          </ContextPanel>
        </div>
      </div>
    </PlaceholderPage>
  );
}

function MetricCard({ icon: Icon, label, value, detail }: { icon: typeof Brain; label: string; value: string; detail: string }) {
  return (
    <div className="rounded-3xl bg-card p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] font-semibold tracking-widest text-muted-foreground">{label.toUpperCase()}</div>
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <div className="mt-3 truncate text-2xl font-semibold">{value}</div>
      <div className="mt-3 truncate rounded-xl bg-secondary px-3 py-2 text-xs text-muted-foreground">{detail}</div>
    </div>
  );
}

function ContextPanel({ icon: Icon, title, children }: { icon: typeof Brain; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-3xl bg-card p-6">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Icon className="h-4 w-4 text-primary" />
        {title}
      </div>
      <div className="mt-3 space-y-2 text-xs">{children}</div>
    </div>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate text-right font-semibold">{value}</span>
    </div>
  );
}
