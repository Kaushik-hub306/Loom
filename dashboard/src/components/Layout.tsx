import { useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import {
  Brain,
  BarChart3,
  Activity,
  Settings,
  Users,
  Menu,
  X,
  LogOut,
  ChevronRight,
} from "lucide-react";
import { clearToken, getMe } from "../api/client";
import { useEffect } from "react";

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
}

const navItems: NavItem[] = [
  { to: "/observations", icon: <Brain className="w-5 h-5" />, label: "Observations" },
  { to: "/analytics", icon: <BarChart3 className="w-5 h-5" />, label: "Analytics" },
  { to: "/activity", icon: <Activity className="w-5 h-5" />, label: "Activity" },
  { to: "/teams", icon: <Users className="w-5 h-5" />, label: "Teams" },
  { to: "/settings", icon: <Settings className="w-5 h-5" />, label: "Settings" },
];

function Breadcrumb() {
  const pathname = window.location.pathname;
  const segments = pathname.split("/").filter(Boolean);

  return (
    <div className="flex items-center gap-1.5 text-sm text-gray-500">
      {segments.map((seg, i) => {
        const isLast = i === segments.length - 1;
        const label = seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        return (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight className="w-3.5 h-3.5 text-gray-400" />}
            <span className={isLast ? "text-gray-900 font-medium" : ""}>{label}</span>
          </span>
        );
      })}
    </div>
  );
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userName, setUserName] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    getMe()
      .then((u) => setUserName(u.user_id))
      .catch(() => {
        /* ignore */
      });
  }, []);

  function handleLogout() {
    clearToken();
    navigate("/login");
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-40 w-60 bg-gray-950 text-gray-300
          transform transition-transform duration-200 ease-in-out
          lg:relative lg:translate-x-0
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        `}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between h-16 px-5 border-b border-gray-800">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
                <Brain className="w-5 h-5 text-white" />
              </div>
              <span className="font-semibold text-white text-lg tracking-tight">
                Loom
              </span>
            </div>
            <button
              className="lg:hidden text-gray-400 hover:text-white"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 py-4 space-y-0.5">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-gray-800 text-white"
                      : "text-gray-400 hover:bg-gray-800/50 hover:text-gray-200"
                  }`
                }
              >
                {item.icon}
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* User */}
          <div className="p-3 border-t border-gray-800">
            <div className="flex items-center justify-between px-3 py-2">
              <span className="text-sm text-gray-400 truncate">
                {userName ?? "..."}
              </span>
              <button
                onClick={handleLogout}
                className="text-gray-500 hover:text-gray-300 transition-colors"
                title="Log out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 lg:px-6 shrink-0">
          <div className="flex items-center gap-3">
            <button
              className="lg:hidden text-gray-500 hover:text-gray-700"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="w-5 h-5" />
            </button>
            <Breadcrumb />
          </div>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-indigo-500 flex items-center justify-center text-white text-xs font-bold">
              {userName?.charAt(0)?.toUpperCase() ?? "?"}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
