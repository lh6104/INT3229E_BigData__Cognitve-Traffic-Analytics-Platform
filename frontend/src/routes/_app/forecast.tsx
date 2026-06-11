import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import { useEffect, useMemo } from "react";
import useSWR from "swr";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
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
});

export const Route = createFileRoute("/_app/forecast")({
  validateSearch: zodValidator(searchSchema),
  component: ForecastPage,
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
  model_source: string;
  data_source: string;
  input_source: string;
  is_fallback: boolean;
  required_feature_count: number;
  available_feature_count: number;
  filled_feature_count: number;
  feature_fill_strategy?: string | null;
  missing_features: string[];
  latest_timestamp?: string | null;
  warning?: string | null;
};

function formatSpeed(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)} km/h` : "n/a";
}

function ForecastPage() {
  const search = Route.useSearch() as { city: CityKey; segment: string };
  const { city, segment } = search;
  const navigate = useNavigate({ from: "/forecast" });
  const setSelectedCity = useAppStore((s) => s.setSelectedCity);
  const setSelectedSegment = useAppStore((s) => s.setSelectedSegment);

  const { data: segments, error: segmentsError, isLoading: segmentsLoading } = useSWR<TrafficSegment[]>(
    `/traffic/segments?city=${city}&limit=100`,
    apiGet,
    { refreshInterval: 60_000 }
  );

  const selectedSegmentId = segment || segments?.[0]?.segment_id || "";
  const selectedSegment = segments?.find((item) => item.segment_id === selectedSegmentId);

  const { data: prediction15, error: prediction15Error, isLoading: loading15 } = useSWR<Prediction>(
    selectedSegmentId ? `/traffic/predict/${encodeURIComponent(selectedSegmentId)}?horizon=15m` : null,
    apiGet,
    { refreshInterval: 60_000 }
  );
  const { data: prediction60, error: prediction60Error, isLoading: loading60 } = useSWR<Prediction>(
    selectedSegmentId ? `/traffic/predict/${encodeURIComponent(selectedSegmentId)}?horizon=60m` : null,
    apiGet,
    { refreshInterval: 60_000 }
  );

  useEffect(() => {
    setSelectedCity(city);
    setSelectedSegment(selectedSegmentId || null);
  }, [city, selectedSegmentId, setSelectedCity, setSelectedSegment]);

  const predictions = [prediction15, prediction60].filter(Boolean) as Prediction[];
  const primaryPrediction = prediction15 ?? prediction60;
  const apiError = segmentsError || prediction15Error || prediction60Error;
  const isLoading = segmentsLoading || loading15 || loading60;

  const chartData = useMemo(() => {
    const current = prediction15?.current_speed ?? prediction60?.current_speed ?? selectedSegment?.current_speed ?? null;
    return [
      { t: "Now", current, predicted: current },
      { t: "+15 min", current: null, predicted: prediction15?.predicted_speed ?? null },
      { t: "+60 min", current: null, predicted: prediction60?.predicted_speed ?? null },
    ];
  }, [prediction15, prediction60, selectedSegment]);

  const selectCity = (next: CityKey) => navigate({ search: { city: next, segment: "" } });
  const selectSegment = (next: string) => navigate({ search: { city, segment: next } });

  const title = selectedSegmentId ? `Forecast · ${selectedSegmentId}` : "Forecast";
  const subtitle = selectedSegment
    ? `${selectedSegment.city} · ${selectedSegment.road_class} · live model inference`
    : "Live LightGBM speed forecasts from local traffic data";

  return (
    <PlaceholderPage title={title} subtitle={subtitle}>
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-wrap items-center gap-2">
          {CITIES.map((c) => (
            <button
              key={c.key}
              onClick={() => selectCity(c.key)}
              className={`rounded-full px-4 py-2 text-xs font-semibold ${c.key === city ? "bg-primary text-primary-foreground" : "bg-card text-muted-foreground"}`}
            >
              {c.label}
            </button>
          ))}
          <select
            value={selectedSegmentId}
            onChange={(event) => selectSegment(event.target.value)}
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
          <span className="rounded-full bg-secondary px-3 py-2 text-[11px] text-muted-foreground">
            Data source: API model inference
          </span>
        </div>

        {(apiError || isLoading || !segments?.length) && (
          <div className="col-span-12 rounded-2xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
            {apiError
              ? `Forecast API unavailable: ${apiError.message}`
              : isLoading
                ? "Loading live forecast data..."
                : "No traffic segments returned for this city."}
          </div>
        )}

        <div className="col-span-12 grid grid-cols-1 gap-4 md:grid-cols-3">
          <ForecastCard
            label="Current"
            value={formatSpeed(primaryPrediction?.current_speed ?? selectedSegment?.current_speed)}
            detail={primaryPrediction?.latest_timestamp ? new Date(primaryPrediction.latest_timestamp).toLocaleString() : "Latest local gold row"}
          />
          <PredictionCard label="+15 min" prediction={prediction15} />
          <PredictionCard label="+60 min" prediction={prediction60} />
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6">
          <h3 className="text-base font-semibold">
            Current vs Predicted Speed
            {selectedSegmentId && <span className="ml-2 text-xs font-normal text-muted-foreground">· {selectedSegmentId}</span>}
          </h3>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid stroke="oklch(0.92 0.01 280)" vertical={false} />
                <XAxis dataKey="t" stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "white", border: "1px solid oklch(0.92 0.01 280)", borderRadius: 12, fontSize: 12 }} />
                <Line type="linear" dataKey="current" stroke="oklch(0.5 0.02 270)" strokeWidth={2} dot={{ r: 5, fill: "oklch(0.5 0.02 270)" }} />
                <Line type="linear" dataKey="predicted" stroke="oklch(0.58 0.21 285)" strokeWidth={2} strokeDasharray="6 4" dot={{ r: 6, fill: "oklch(0.58 0.21 285)", stroke: "white", strokeWidth: 2 }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </PlaceholderPage>
  );
}

function ForecastCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-3xl bg-card p-6">
      <div className="text-xs font-semibold tracking-widest text-muted-foreground">{label.toUpperCase()}</div>
      <div className="mt-3 text-3xl font-semibold">{value}</div>
      <div className="mt-4 rounded-xl bg-secondary px-3 py-2 text-xs text-muted-foreground">{detail}</div>
    </div>
  );
}

function PredictionCard({ label, prediction }: { label: string; prediction?: Prediction }) {
  const filled = prediction?.filled_feature_count ?? 0;
  return (
    <div className="rounded-3xl bg-card p-6">
      <div className="text-xs font-semibold tracking-widest text-muted-foreground">{label.toUpperCase()}</div>
      <div className="mt-3 flex items-baseline gap-2">
        <div className="text-3xl font-semibold">{formatSpeed(prediction?.predicted_speed)}</div>
        <div className="text-sm text-muted-foreground">{prediction?.model_name ?? "model"}</div>
      </div>
      <div className="mt-4 grid gap-2 rounded-xl bg-secondary px-3 py-2 text-xs">
        <div className="flex justify-between gap-2">
          <span className="text-muted-foreground">Feature coverage</span>
          <span className="font-semibold">{prediction ? `${prediction.available_feature_count}/${prediction.required_feature_count}` : "n/a"}</span>
        </div>
        <div className="truncate text-[11px] text-muted-foreground">
          {prediction?.model_artifact ?? "Waiting for API"}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {filled > 0 && <span className="rounded-full bg-primary-soft px-2 py-1 text-[10px] font-semibold text-accent-foreground">Partial feature fill</span>}
        {prediction?.is_fallback && <span className="rounded-full bg-destructive/10 px-2 py-1 text-[10px] font-semibold text-destructive">Model fallback</span>}
      </div>
    </div>
  );
}
