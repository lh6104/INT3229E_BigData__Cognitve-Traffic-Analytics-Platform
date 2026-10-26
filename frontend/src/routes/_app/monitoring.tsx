import { createFileRoute } from "@tanstack/react-router";
import useSWR from "swr";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { apiGet } from "@/lib/api/client";

export const Route = createFileRoute("/_app/monitoring")({ component: MonitoringPage });

type Health = { status: string; dependencies: Record<string, string>; timestamp: string };
type Quality = {
  measured_at: string;
  stream: string;
  events_received: number;
  invalid_events: number;
  duplicates: number;
  late_events: number;
  freshness_p95_seconds: number | null;
  roads_reporting: number | null;
  expected_roads: number | null;
};
type Model = { model_name: string; model_version: string; dataset_id: string; feature_version: string; git_sha: string } | null;
type Metric = { horizon_minutes: number; sample_count: number; mae: number; rmse: number; bias: number; window_end: string };

function MonitoringPage() {
  const { data: health, error: healthError } = useSWR<Health>("/system/health", apiGet, { refreshInterval: 15_000, shouldRetryOnError: false });
  const { data: quality, error: qualityError } = useSWR<Quality[]>("/system/data-quality", apiGet, { refreshInterval: 30_000, shouldRetryOnError: false });
  const { data: model } = useSWR<Model>("/models/current", apiGet, { refreshInterval: 60_000, shouldRetryOnError: false });
  const { data: metrics } = useSWR<Metric[]>("/models/metrics", apiGet, { refreshInterval: 60_000, shouldRetryOnError: false });

  return (
    <PlaceholderPage title="Platform" subtitle="Data freshness, quality, and observed model performance">
      {(healthError || qualityError) && <div className="rounded-2xl bg-destructive/10 p-4 text-sm text-destructive">One or more operational stores are unavailable.</div>}
      <div className="grid gap-4 md:grid-cols-3">
        <Card label="System" value={health?.status ?? "unavailable"} detail={health ? Object.entries(health.dependencies).map(([key, value]) => `${key}: ${value}`).join(" · ") : undefined} />
        <Card label="Champion" value={model?.model_version ?? "none"} detail={model ? `features ${model.feature_version} · dataset ${model.dataset_id}` : undefined} />
        <Card label="Latest evaluation" value={metrics?.[0] ? `MAE ${metrics[0].mae.toFixed(2)} km/h` : "not measured"} detail={metrics?.[0] ? `${metrics[0].sample_count} outcomes · ${metrics[0].horizon_minutes}m` : undefined} />
      </div>
      <section className="rounded-3xl bg-card p-6">
        <h2 className="font-semibold">Stream quality</h2>
        <p className="mt-1 text-xs text-muted-foreground">Measured records only; no generated health values.</p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted-foreground"><tr><th className="py-2">Stream</th><th>Received</th><th>Invalid</th><th>Duplicate</th><th>Late</th><th>Freshness p95</th><th>Roads</th></tr></thead>
            <tbody>{(quality ?? []).map((row) => <tr key={`${row.stream}-${row.measured_at}`} className="border-t border-border"><td className="py-3">{row.stream}</td><td>{row.events_received}</td><td>{row.invalid_events}</td><td>{row.duplicates}</td><td>{row.late_events}</td><td>{row.freshness_p95_seconds == null ? "n/a" : `${row.freshness_p95_seconds.toFixed(0)}s`}</td><td>{row.roads_reporting ?? "n/a"}/{row.expected_roads ?? "n/a"}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
      <section className="rounded-3xl bg-card p-6">
        <h2 className="font-semibold">Prediction outcomes</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {(metrics ?? []).slice(0, 6).map((metric) => <Card key={`${metric.horizon_minutes}-${metric.window_end}`} label={`${metric.horizon_minutes} minute · ${metric.sample_count} outcomes`} value={`MAE ${metric.mae.toFixed(2)}`} detail={`RMSE ${metric.rmse.toFixed(2)} · bias ${metric.bias.toFixed(2)}`} />)}
        </div>
      </section>
    </PlaceholderPage>
  );
}

function Card({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="rounded-2xl bg-card p-5"><div className="text-xs text-muted-foreground">{label}</div><div className="mt-2 text-xl font-semibold capitalize">{value}</div>{detail && <div className="mt-1 text-xs text-muted-foreground">{detail}</div>}</div>;
}
