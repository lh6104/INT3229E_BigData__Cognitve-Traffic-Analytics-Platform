import useSWR from "swr";
import { apiGet } from "@/lib/api/client";

type Health = { status: "healthy" | "degraded"; timestamp: string };

export function TopBar() {
  const { data } = useSWR<Health>("/system/health", apiGet, { refreshInterval: 15_000, shouldRetryOnError: false });
  const status = data?.status ?? "unavailable";
  return (
    <div className="mb-6 flex h-12 items-center justify-between rounded-2xl bg-card px-5">
      <div className="text-sm font-medium">Urban traffic operations</div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className={`h-2 w-2 rounded-full ${status === "healthy" ? "bg-success" : "bg-warning"}`} />
        {status}
      </div>
    </div>
  );
}
