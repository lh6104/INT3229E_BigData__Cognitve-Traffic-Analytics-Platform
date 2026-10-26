import { Link, useRouterState } from "@tanstack/react-router";
import { Activity, Map, TrendingUp } from "lucide-react";

const areas = [
  { title: "Traffic", subtitle: "Current state and alerts", to: "/live-map", icon: Map },
  { title: "Forecasting", subtitle: "Intervals and outcomes", to: "/forecast", icon: TrendingUp },
  { title: "Platform", subtitle: "Freshness, lag, and model", to: "/monitoring", icon: Activity },
];

export function AppSidebar() {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  return (
    <aside className="flex h-[calc(100vh-2rem)] w-64 shrink-0 flex-col rounded-3xl bg-card p-5">
      <div className="mb-10 border-b border-border pb-5">
        <div className="text-base font-semibold">Cognitive Traffic</div>
        <div className="mt-1 text-xs text-muted-foreground">Stream processing and forecasting</div>
      </div>
      <nav className="space-y-2">
        {areas.map(({ title, subtitle, to, icon: Icon }) => {
          const active = pathname === to;
          return (
            <Link
              key={to}
              to={to}
              className={`flex items-start gap-3 rounded-xl px-3 py-3 transition-colors ${
                active ? "bg-primary-soft text-accent-foreground" : "text-muted-foreground hover:bg-secondary"
              }`}
            >
              <Icon className="mt-0.5 h-[18px] w-[18px]" />
              <span>
                <span className="block text-sm font-medium">{title}</span>
                <span className="block text-[11px] opacity-75">{subtitle}</span>
              </span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto text-xs leading-5 text-muted-foreground">
        Live data only. Missing dependencies are shown as unavailable.
      </div>
    </aside>
  );
}
