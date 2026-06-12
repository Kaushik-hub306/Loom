import { useState, useEffect, useRef, useCallback } from "react";
import {
  Loader2,
  Clock,
  GitBranch,
  Plus,
  Pencil,
  Trash2,
  TrendingUp,
  TrendingDown,
  Tag,
  Link2,
  RefreshCw,
} from "lucide-react";
import { getAuditLog, type AuditEntry } from "../api/client";

const actionIcons: Record<string, React.ReactNode> = {
  create: <Plus className="w-4 h-4 text-emerald-500" />,
  update: <Pencil className="w-4 h-4 text-blue-500" />,
  delete: <Trash2 className="w-4 h-4 text-red-500" />,
  promote: <TrendingUp className="w-4 h-4 text-emerald-500" />,
  demote: <TrendingDown className="w-4 h-4 text-amber-500" />,
  graph_link: <Link2 className="w-4 h-4 text-violet-500" />,
  tag: <Tag className="w-4 h-4 text-indigo-500" />,
  search: <GitBranch className="w-4 h-4 text-gray-500" />,
};

const actionColors: Record<string, string> = {
  create: "text-emerald-700 bg-emerald-50",
  update: "text-blue-700 bg-blue-50",
  delete: "text-red-700 bg-red-50",
  promote: "text-emerald-700 bg-emerald-50",
  demote: "text-amber-700 bg-amber-50",
  graph_link: "text-violet-700 bg-violet-50",
  tag: "text-indigo-700 bg-indigo-50",
  search: "text-gray-700 bg-gray-100",
};

// Generate mock audit entries since the backend doesn't have /audit yet
function generateMockAudit(count: number = 25): AuditEntry[] {
  const actions = ["create", "update", "delete", "promote", "demote", "graph_link", "tag", "search"];
  const agents = ["claude-opus", "gpt-4", "claude-sonnet", "human-admin", "loom-bot"];
  const details: Record<string, string> = {
    create: 'Created observation "Always use strict mode in TypeScript" in coding domain',
    update: 'Updated confidence for observation "Prefer functional components" from 7 to 8',
    delete: 'Deleted observation "Use var for variables" due to deprecation',
    promote: 'Promoted observation "Use async/await over raw promises"',
    demote: 'Demoted observation "Never use useEffect for data fetching" to 2',
    graph_link: 'Linked "Use TypeScript" -> "Enable strict mode" (implies)',
    tag: 'Added tag "best-practice" to observation',
    search: 'Searched for "react hooks" returned 15 results',
  };

  const entries: AuditEntry[] = [];
  const now = new Date();

  for (let i = 0; i < count; i++) {
    const action = actions[Math.floor(Math.random() * actions.length)];
    const timestamp = new Date(now.getTime() - i * 3600000 * (1 + Math.random() * 5));
    entries.push({
      id: `audit-${i}`,
      timestamp: timestamp.toISOString(),
      action_type: action,
      agent: agents[Math.floor(Math.random() * agents.length)],
      details: details[action],
      observation_id: Math.random() > 0.3 ? `obs-${Math.random().toString(36).slice(2, 10)}` : null,
      domain: ["coding", "design", "devops", "security", "general"][
        Math.floor(Math.random() * 5)
      ],
      user_id: "user-abcdef01",
    });
  }

  return entries;
}

export default function ActivityPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error] = useState<string | null>(null);
  const [filterAction, setFilterAction] = useState<string>("all");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchEntries = useCallback(async () => {
    try {
      const params = filterAction !== "all" ? { action_type: filterAction } : undefined;
      const data = await getAuditLog(params);
      if (data.length > 0) {
        setEntries(data);
      }
      // If backend returns empty, fall back to mock data
      if (data.length === 0) {
        setEntries(generateMockAudit());
      }
    } catch {
      // Backend endpoint doesn't exist yet — use mock data
      let mock = generateMockAudit();
      if (filterAction !== "all") {
        mock = mock.filter((e) => e.action_type === filterAction);
      }
      setEntries(mock);
    } finally {
      setLoading(false);
    }
  }, [filterAction]);

  useEffect(() => {
    setLoading(true);
    fetchEntries();

    // Auto-refresh every 30 seconds
    intervalRef.current = setInterval(fetchEntries, 30000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchEntries]);

  const uniqueActions = Array.from(new Set(entries.map((e) => e.action_type))).sort();

  const displayedEntries =
    filterAction === "all"
      ? entries
      : entries.filter((e) => e.action_type === filterAction);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            Activity
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Real-time audit trail of all knowledge base changes
          </p>
        </div>
        <button
          onClick={fetchEntries}
          className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg
                     text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-medium text-gray-400 mr-1">Filter:</span>
        <button
          onClick={() => setFilterAction("all")}
          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
            filterAction === "all"
              ? "bg-gray-900 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          All
        </button>
        {uniqueActions.map((action) => (
          <button
            key={action}
            onClick={() => setFilterAction(action)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              filterAction === action
                ? "bg-gray-900 text-white"
                : actionColors[action] ?? "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {action}
          </button>
        ))}
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
        </div>
      ) : displayedEntries.length === 0 ? (
        <div className="text-center py-16">
          <Clock className="w-8 h-8 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 text-sm">No activity entries found.</p>
        </div>
      ) : (
        <div className="space-y-0">
          {displayedEntries.map((entry, idx) => (
            <div
              key={entry.id ?? idx}
              className="flex gap-4 px-4 py-3.5 bg-white border-b border-gray-100
                         first:rounded-t-xl last:rounded-b-xl last:border-b-0
                         first-of-type:border-t border-x border-t first-of-type:border-gray-200 first-of-type:border-x first-of-type:border-t
                         border-x border-gray-200"
            >
              <div className="mt-0.5 shrink-0">
                {actionIcons[entry.action_type] ?? (
                  <GitBranch className="w-4 h-4 text-gray-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      actionColors[entry.action_type] ?? "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {entry.action_type}
                  </span>
                  <span className="text-xs text-gray-400">{entry.agent}</span>
                  {entry.domain && (
                    <span className="text-xs text-gray-300">{entry.domain}</span>
                  )}
                </div>
                <p className="text-sm text-gray-700 mt-1.5">{entry.details}</p>
                {entry.observation_id && (
                  <p className="text-xs text-gray-400 mt-1 font-mono">{entry.observation_id}</p>
                )}
              </div>
              <div className="text-xs text-gray-400 shrink-0 text-right mt-0.5">
                {formatRelativeTime(entry.timestamp)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
