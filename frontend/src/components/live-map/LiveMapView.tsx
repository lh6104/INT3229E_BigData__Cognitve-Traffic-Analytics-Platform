import { useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import useSWR from "swr";
import { apiGet } from "@/lib/api/client";

type City = "All" | "Hanoi" | "HCMC";
type CurrentRoad = {
  road_id: string;
  city: "hanoi" | "hcmc";
  name: string;
  category: string;
  geometry: { type: "LineString"; coordinates: [number, number][] } | null;
  latitude: number;
  longitude: number;
  coordinate_kind: "configured_anchor";
  status: "missing" | "stale" | "live";
  event_time: string | null;
  speed_kmh: number | null;
  free_flow_speed_kmh: number | null;
  confidence: number;
  source: string;
};

const centers: Record<City, [number, number]> = {
  All: [16.2, 106.4],
  Hanoi: [21.0285, 105.8542],
  HCMC: [10.7769, 106.7009],
};

function color(road: CurrentRoad) {
  if (road.status !== "live" || road.speed_kmh === null || road.free_flow_speed_kmh === null) return "#64748b";
  const ratio = road.free_flow_speed_kmh > 0 ? road.speed_kmh / road.free_flow_speed_kmh : 0;
  if (ratio >= 0.75) return "#16a34a";
  if (ratio >= 0.5) return "#f59e0b";
  if (ratio >= 0.3) return "#ef4444";
  return "#7f1d1d";
}

export function LiveMapView({
  city = "All",
  onCityChange,
  onViewForecast,
}: {
  city?: City;
  onCityChange?: (city: City) => void;
  onViewForecast: (roadId: string, city: "hanoi" | "hcmc") => void;
}) {
  const apiCity = city === "All" ? "" : city === "Hanoi" ? "hanoi" : "hcmc";
  const { data, error, isLoading, mutate } = useSWR<CurrentRoad[]>(
    `/monitoring/points${apiCity ? `?city=${apiCity}` : ""}`,
    apiGet,
    { refreshInterval: 30_000, shouldRetryOnError: false },
  );
  const points = data ?? [];
  const roads = useMemo(() => (data ?? []).filter((road) => road.geometry?.coordinates.length && road.speed_kmh !== null), [data]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-card p-4">
        <div className="flex gap-2">
          {(["Hanoi", "HCMC", "All"] as City[]).map((item) => (
            <button
              key={item}
              onClick={() => onCityChange?.(item)}
              className={`rounded-full px-4 py-2 text-sm ${item === city ? "bg-primary text-primary-foreground" : "bg-secondary"}`}
            >
              {item}
            </button>
          ))}
        </div>
        <button className="text-sm text-muted-foreground" onClick={() => mutate()}>
          Refresh
        </button>
      </div>
      {error && (
        <div className="rounded-2xl border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive">
          Monitoring data is unavailable. {error.message}
        </div>
      )}
      <div className="overflow-hidden rounded-3xl bg-card">
        <MapContainer key={city} center={centers[city]} zoom={city === "All" ? 6 : 13} className="h-[640px] w-full">
          <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {points.map((point) => (
            <CircleMarker key={point.road_id} center={[point.latitude, point.longitude]} radius={8}
              pathOptions={{ color: color(point), fillOpacity: 0.7 }}>
              <Popup>
                <div className="min-w-48 space-y-2">
                  <strong>{point.name}</strong>
                  <div>Configured monitoring anchor · {point.status}</div>
                  <div>Coordinates are anchors; road geometry is unverified unless separately supplied.</div>
                  {point.speed_kmh === null ? <div>No measurement available</div> : (
                    <><div>{point.speed_kmh.toFixed(1)} / {point.free_flow_speed_kmh?.toFixed(1)} km/h</div>
                      <div>Observed {point.event_time && new Date(point.event_time).toLocaleString()}</div>
                      <div>Source: {point.source}</div></>
                  )}
                  <button onClick={() => onViewForecast(point.road_id, point.city)}>View forecast</button>
                </div>
              </Popup>
            </CircleMarker>
          ))}
          {roads.map((road) => (
            <Polyline
              key={road.road_id}
              positions={road.geometry!.coordinates.map(([lon, lat]) => [lat, lon])}
              pathOptions={{ color: color(road), weight: 6, opacity: 0.85 }}
            >
              <Popup>
                <div className="min-w-48 space-y-2">
                  <strong>{road.name}</strong>
                  <div>{road.speed_kmh?.toFixed(1)} / {road.free_flow_speed_kmh?.toFixed(1)} km/h</div>
                  <div>Updated {road.event_time && new Date(road.event_time).toLocaleString()}</div>
                  <div>Source: {road.source}</div>
                  <button onClick={() => onViewForecast(road.road_id, road.city)}>View forecast</button>
                </div>
              </Popup>
            </Polyline>
          ))}
        </MapContainer>
      </div>
      <div className="text-xs text-muted-foreground">
        {isLoading ? "Loading current road state…" : `${points.length} configured anchors · ${points.filter((point) => point.status === "missing").length} missing · ${points.filter((point) => point.status === "stale").length} stale · ${roads.length} roads with supplied geometry`}
      </div>
    </div>
  );
}
