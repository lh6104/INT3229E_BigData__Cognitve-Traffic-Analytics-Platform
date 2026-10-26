import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";
import useSWR from "swr";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { apiGet } from "@/lib/api/client";

const searchSchema = z.object({
  city: z.enum(["hanoi", "hcmc"]).catch("hanoi").default("hanoi"),
  segment: z.string().catch("").default(""),
});

export const Route = createFileRoute("/_app/forecast")({
  validateSearch: (search) => searchSchema.parse(search),
  component: ForecastPage,
});

type Road = { road_id: string; city: string; name: string; category: string };
type CurrentRoad = { road_id: string; speed_kmh: number; event_time: string };
type Forecast = {
  event_id: string;
  road_id: string;
  prediction_time: string;
  target_time: string;
  horizon_minutes: number;
  model_version: string;
  p10_speed_kmh: number;
  p50_speed_kmh: number;
  p90_speed_kmh: number;
  actual_speed_kmh: number | null;
  absolute_error_kmh: number | null;
};
type Model = { model_name: string; model_version: string; feature_version: string; dataset_id: string } | null;

function ForecastPage() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: "/forecast" });
  const { data: roads } = useSWR<Road[]>(`/roads?city=${search.city}`, apiGet);
  const { data: current } = useSWR<CurrentRoad[]>(`/traffic/current?city=${search.city}`, apiGet, { refreshInterval: 30_000 });
  const roadId = search.segment || roads?.[0]?.road_id || "";
  const { data: forecasts, error, isLoading } = useSWR<Forecast[]>(
    roadId ? `/forecasts?road_id=${encodeURIComponent(roadId)}` : null,
    apiGet,
    { refreshInterval: 30_000, shouldRetryOnError: false },
  );
  const { data: model } = useSWR<Model>("/models/current", apiGet, { shouldRetryOnError: false });
  const selectedRoad = roads?.find((road) => road.road_id === roadId);
  const currentRoad = current?.find((road) => road.road_id === roadId);
  const latestByHorizon = [15, 60, 240].map((horizon) =>
    forecasts?.find((forecast) => forecast.horizon_minutes === horizon),
  );
  const series = [...(forecasts ?? [])]
    .reverse()
    .slice(-60)
    .map((forecast) => ({
      time: new Date(forecast.target_time).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
      p10: forecast.p10_speed_kmh,
      p50: forecast.p50_speed_kmh,
      p90: forecast.p90_speed_kmh,
      actual: forecast.actual_speed_kmh,
    }));

  return (
    <PlaceholderPage title="Forecasting" subtitle="Quantile forecasts and observed outcomes">
      <div className="rounded-2xl bg-card p-4">
        <label className="text-xs text-muted-foreground">Road</label>
        <select
          className="mt-2 w-full rounded-xl bg-secondary px-3 py-2 text-sm"
          value={roadId}
          onChange={(event) => navigate({ search: { city: search.city, segment: event.target.value } })}
        >
          {(roads ?? []).map((road) => <option key={road.road_id} value={road.road_id}>{road.name} · {road.road_id}</option>)}
        </select>
      </div>
      {error && <div className="rounded-2xl bg-destructive/10 p-4 text-sm text-destructive">Forecast storage is unavailable.</div>}
      <div className="grid gap-4 md:grid-cols-4">
        <Metric label="Current" value={currentRoad ? `${currentRoad.speed_kmh.toFixed(1)} km/h` : "n/a"} />
        {latestByHorizon.map((forecast, index) => (
          <Metric
            key={[15, 60, 240][index]}
            label={`${[15, 60, 240][index]} minute P50`}
            value={forecast ? `${forecast.p50_speed_kmh.toFixed(1)} km/h` : "n/a"}
            detail={forecast ? `P10 ${forecast.p10_speed_kmh.toFixed(1)} · P90 ${forecast.p90_speed_kmh.toFixed(1)}` : undefined}
          />
        ))}
      </div>
      <div className="rounded-3xl bg-card p-6">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold">{(selectedRoad?.name ?? roadId) || "Select a road"}</h2>
            <p className="text-xs text-muted-foreground">Actual values appear only after prediction outcomes are matched.</p>
          </div>
          <div className="text-right text-xs text-muted-foreground">
            Model {model?.model_version ?? "unavailable"}<br />Dataset {model?.dataset_id ?? "unavailable"}
          </div>
        </div>
        <div className="h-80">
          {isLoading ? <div className="text-sm text-muted-foreground">Loading…</div> : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="time" minTickGap={40} />
                <YAxis unit=" km/h" />
                <Tooltip />
                <Line dataKey="p10" stroke="#94a3b8" dot={false} strokeDasharray="4 4" />
                <Line dataKey="p50" stroke="#6366f1" dot={false} strokeWidth={2} />
                <Line dataKey="p90" stroke="#94a3b8" dot={false} strokeDasharray="4 4" />
                <Line dataKey="actual" stroke="#16a34a" dot={false} strokeWidth={2} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </PlaceholderPage>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="rounded-2xl bg-card p-5"><div className="text-xs text-muted-foreground">{label}</div><div className="mt-2 text-xl font-semibold">{value}</div>{detail && <div className="mt-1 text-xs text-muted-foreground">{detail}</div>}</div>;
}
