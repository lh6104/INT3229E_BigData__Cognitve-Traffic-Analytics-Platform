import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { Bell, Clock, MapPin, Save, Settings as SettingsIcon } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { apiGet, apiPut } from "@/lib/api/client";

type CityKey = "hanoi" | "hcmc";

type CityRuntime = {
  enabled: boolean;
  status: "online" | "offline";
  segment_count: number;
  latest_timestamp: string | null;
  avg_speed: number | null;
  avg_jam_factor: number | null;
};

type SettingsData = {
  city_toggles: Record<CityKey, boolean>;
  thresholds: {
    critical_jam_factor: number;
    high_jam_factor: number;
    medium_jam_factor: number;
  };
  intervals: {
    traffic_seconds: number;
    weather_seconds: number;
    alerts_seconds: number;
    monitoring_seconds: number;
  };
  map: {
    default_city: CityKey;
    zoom_level: number;
  };
  updated_at: string | null;
};

type SettingsResponse = SettingsData & {
  cities: Record<CityKey, CityRuntime>;
  storage_path: string;
};

const CITY_LABEL: Record<CityKey, string> = {
  hanoi: "Hanoi",
  hcmc: "Ho Chi Minh City",
};

const intervalOptions = [15, 30, 60, 300, 900];

export const Route = createFileRoute("/_app/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const { data, error, isLoading, mutate } = useSWR<SettingsResponse>("/settings", apiGet, {
    refreshInterval: 60_000,
  });
  const [draft, setDraft] = useState<SettingsData | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (data) {
      setDraft({
        city_toggles: data.city_toggles,
        thresholds: data.thresholds,
        intervals: data.intervals,
        map: data.map,
        updated_at: data.updated_at,
      });
    }
  }, [data]);

  const dirty = useMemo(() => {
    if (!draft || !data) return false;
    return JSON.stringify({
      city_toggles: data.city_toggles,
      thresholds: data.thresholds,
      intervals: data.intervals,
      map: data.map,
    }) !== JSON.stringify({
      city_toggles: draft.city_toggles,
      thresholds: draft.thresholds,
      intervals: draft.intervals,
      map: draft.map,
    });
  }, [data, draft]);

  const updateDraft = (next: Partial<SettingsData>) => {
    setDraft((prev) => (prev ? { ...prev, ...next } : prev));
  };

  const setThreshold = (key: keyof SettingsData["thresholds"], value: number) => {
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            thresholds: { ...prev.thresholds, [key]: value },
          }
        : prev
    );
  };

  const setInterval = (key: keyof SettingsData["intervals"], value: number) => {
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            intervals: { ...prev.intervals, [key]: value },
          }
        : prev
    );
  };

  const toggleCity = (city: CityKey) => {
    setDraft((prev) =>
      prev
        ? {
            ...prev,
            city_toggles: { ...prev.city_toggles, [city]: !prev.city_toggles[city] },
          }
        : prev
    );
  };

  const handleSave = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const saved = await apiPut<SettingsResponse>("/settings", draft);
      await mutate(saved, { revalidate: false });
      toast.success("Settings saved to backend");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  };

  const thresholdMeta: {
    key: keyof SettingsData["thresholds"];
    label: string;
    description: string;
    min: number;
    max: number;
    step: number;
  }[] = [
    {
      key: "critical_jam_factor",
      label: "Critical jam factor",
      description: "Critical alerts trigger at or above this jam factor",
      min: 5,
      max: 10,
      step: 0.1,
    },
    {
      key: "high_jam_factor",
      label: "High jam factor",
      description: "High alerts trigger at or above this jam factor",
      min: 3,
      max: 8,
      step: 0.1,
    },
    {
      key: "medium_jam_factor",
      label: "Medium jam factor",
      description: "Medium alerts trigger at or above this jam factor",
      min: 1,
      max: 6,
      step: 0.1,
    },
  ];

  if (error) {
    return (
      <div>
        <PageHeader title="Settings" subtitle="Configure platform runtime settings" />
        <div className="rounded-2xl border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm font-medium text-destructive">
          Settings API unavailable: {error.message}
        </div>
      </div>
    );
  }

  if (!draft || isLoading) {
    return (
      <div>
        <PageHeader title="Settings" subtitle="Configure platform runtime settings" />
        <div className="rounded-3xl bg-card p-6 text-sm text-muted-foreground">Loading settings...</div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Configure monitored cities, alert thresholds, refresh intervals, and default map behavior"
      />
      <div className="space-y-4">
        <section className="rounded-3xl bg-card p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-accent-foreground">
                <SettingsIcon className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-base font-semibold">Runtime State</h2>
                <p className="text-xs text-muted-foreground">
                  Settings are persisted through the FastAPI backend.
                </p>
              </div>
            </div>
            <div className="text-right text-[11px] text-muted-foreground">
              <div>Storage: <span className="font-mono">{data?.storage_path ?? "data/app_settings.json"}</span></div>
              <div>Updated: {data?.updated_at ? new Date(data.updated_at).toLocaleString() : "not saved yet"}</div>
            </div>
          </div>
        </section>

        <section className="rounded-3xl bg-card p-6">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-accent-foreground">
                <MapPin className="h-4 w-4" />
              </div>
              <h2 className="text-base font-semibold">Cities & Coverage</h2>
            </div>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            City status and coverage come from latest local Gold traffic features.
          </p>
          <div className="mt-4 space-y-3">
            {(Object.keys(CITY_LABEL) as CityKey[]).map((cityKey) => {
              const city = data?.cities[cityKey];
              const enabled = draft.city_toggles[cityKey];
              return (
                <div
                  key={cityKey}
                  className="flex items-center justify-between rounded-2xl border border-border px-4 py-3"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span
                      className={`h-2 w-2 rounded-full ${
                        city?.status === "online" && enabled ? "bg-success" : "bg-destructive"
                      }`}
                    />
                    <div className="min-w-0">
                      <div className="text-sm font-medium">{CITY_LABEL[cityKey]}</div>
                      <div className="truncate text-[11px] text-muted-foreground">
                        {city?.segment_count ?? 0} segments · {formatSpeed(city?.avg_speed)} avg · Jam {city?.avg_jam_factor ?? "n/a"} · Updated {formatDate(city?.latest_timestamp)}
                      </div>
                    </div>
                  </div>
                  <Switch
                    checked={enabled}
                    onCheckedChange={() => toggleCity(cityKey)}
                    aria-label={`Toggle ${CITY_LABEL[cityKey]}`}
                  />
                </div>
              );
            })}
          </div>
        </section>

        <section className="rounded-3xl bg-card p-6">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-accent-foreground">
                <Bell className="h-4 w-4" />
              </div>
              <h2 className="text-base font-semibold">Alert Thresholds</h2>
            </div>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Thresholds are validated by the backend before saving.
          </p>
          <div className="mt-4 space-y-5">
            {thresholdMeta.map((t) => (
              <div key={t.key}>
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-sm font-medium">{t.label}</Label>
                    <p className="text-[11px] text-muted-foreground">{t.description}</p>
                  </div>
                  <span className="rounded-full bg-secondary px-2.5 py-1 text-xs font-semibold text-secondary-foreground">
                    {draft.thresholds[t.key].toFixed(1)}
                  </span>
                </div>
                <div className="mt-3">
                  <Slider
                    value={[draft.thresholds[t.key]]}
                    onValueChange={(val) => setThreshold(t.key, val[0])}
                    min={t.min}
                    max={t.max}
                    step={t.step}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-3xl bg-card p-6">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-accent-foreground">
                <Clock className="h-4 w-4" />
              </div>
              <h2 className="text-base font-semibold">Refresh & Map Defaults</h2>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {([
              ["traffic_seconds", "Traffic"],
              ["weather_seconds", "Weather"],
              ["alerts_seconds", "Alerts"],
              ["monitoring_seconds", "Monitoring"],
            ] as [keyof SettingsData["intervals"], string][]).map(([key, label]) => (
              <div key={key}>
                <Label className="mb-2 block text-sm font-medium">{label}</Label>
                <Select
                  value={String(draft.intervals[key])}
                  onValueChange={(val) => setInterval(key, Number(val))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {intervalOptions.map((opt) => (
                      <SelectItem key={opt} value={String(opt)}>
                        {formatInterval(opt)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ))}
            <div>
              <Label className="mb-2 block text-sm font-medium">Default city</Label>
              <Select
                value={draft.map.default_city}
                onValueChange={(val) =>
                  updateDraft({ map: { ...draft.map, default_city: val as CityKey } })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="hanoi">Hanoi</SelectItem>
                  <SelectItem value="hcmc">Ho Chi Minh City</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="mt-5">
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-medium">Map zoom level</Label>
                <p className="text-[11px] text-muted-foreground">Default initial zoom for map workflows</p>
              </div>
              <span className="rounded-full bg-secondary px-2.5 py-1 text-xs font-semibold text-secondary-foreground">
                {draft.map.zoom_level}
              </span>
            </div>
            <div className="mt-3">
              <Slider
                value={[draft.map.zoom_level]}
                onValueChange={(val) => updateDraft({ map: { ...draft.map, zoom_level: val[0] } })}
                min={8}
                max={18}
                step={1}
              />
            </div>
          </div>
        </section>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => data && setDraft({
            city_toggles: data.city_toggles,
            thresholds: data.thresholds,
            intervals: data.intervals,
            map: data.map,
            updated_at: data.updated_at,
          })} disabled={!dirty || saving}>
            Reset
          </Button>
          <Button onClick={handleSave} disabled={!dirty || saving}>
            <Save className="mr-2 h-4 w-4" />
            {saving ? "Saving..." : "Save settings"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function formatSpeed(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)} km/h` : "n/a";
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "n/a";
}

function formatInterval(seconds: number) {
  if (seconds < 60) return `${seconds}s`;
  return `${Math.round(seconds / 60)}min`;
}
