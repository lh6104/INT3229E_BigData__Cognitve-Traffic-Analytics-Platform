import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  Map,
  TrendingUp,
  Flame,
  Bell,
  Brain,
  Activity,
  Settings,
  LogOut,
  Sparkles,
} from "lucide-react";

const overview = [
  { title: "Demo Flow", to: "/demo", icon: Sparkles },
  { title: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
  { title: "Live Map", to: "/live-map", icon: Map },
  { title: "Forecast", to: "/forecast", icon: TrendingUp },
  { title: "Hotspots", to: "/hotspots", icon: Flame },
];

const operations = [
  { title: "Alerts", to: "/alerts", icon: Bell },
  { title: "Explanations", to: "/explanations", icon: Brain, badge: "Demo" },
  { title: "Monitoring", to: "/monitoring", icon: Activity, badge: "Demo" },
];

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const NavItem = ({ to, title, icon: Icon, badge }: { to: string; title: string; icon: typeof Bell; badge?: string }) => {
    const active = pathname === to || (to !== "/" && pathname.startsWith(to));
    return (
      <Link
        to={to}
        className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
          active
            ? "bg-primary-soft text-accent-foreground"
            : "text-muted-foreground hover:bg-secondary hover:text-foreground"
        }`}
      >
        <Icon className="h-[18px] w-[18px]" />
        <span>{title}</span>
        {badge && (
          <span className="ml-auto rounded-full bg-secondary px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">
            {badge}
          </span>
        )}
      </Link>
    );
  };

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col rounded-3xl bg-card p-5">
      <div className="mb-8 flex items-center gap-2.5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <Sparkles className="h-4 w-4" />
        </div>
        <div className="text-[15px] font-semibold leading-tight">
          Cognitive
          <div className="text-[11px] font-normal text-muted-foreground">Traffic Analytics</div>
        </div>
      </div>

      <div className="mb-2 px-3 text-[10px] font-semibold tracking-widest text-muted-foreground">
        OVERVIEW
      </div>
      <nav className="flex flex-col gap-1">
        {overview.map((i) => (
          <NavItem key={i.to} {...i} />
        ))}
      </nav>

      <div className="mb-2 mt-6 px-3 text-[10px] font-semibold tracking-widest text-muted-foreground">
        OPERATIONS
      </div>
      <nav className="flex flex-col gap-1">
        {operations.map((i) => (
          <NavItem key={i.to} {...i} />
        ))}
      </nav>

      <div className="mb-2 mt-auto px-3 text-[10px] font-semibold tracking-widest text-muted-foreground">
        SETTINGS
      </div>
      <nav className="flex flex-col gap-1">
        <NavItem to="/settings" title="Settings" icon={Settings} badge="Local" />
        <button className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-destructive hover:bg-destructive/10">
          <LogOut className="h-[18px] w-[18px]" />
          Logout
        </button>
      </nav>
    </aside>
  );
}
