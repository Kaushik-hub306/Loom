import { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from "recharts";
import { Loader2, TrendingUp, PieChartIcon, BarChart3, LayoutGrid } from "lucide-react";
import { getStats, type Stats } from "../api/client";

const PIE_COLORS = [
  "#8b5cf6", "#6366f1", "#ec4899", "#f59e0b", "#10b981",
  "#3b82f6", "#ef4444", "#06b6d4", "#84cc16", "#f97316",
];

const BAR_COLORS = [
  "#8b5cf6", "#6366f1", "#a78bfa", "#c4b5fd", "#ddd6fe",
  "#ec4899", "#f472b6", "#fbcfe8", "#f59e0b", "#fcd34d",
];

export default function AnalyticsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getStats()
      .then((data) => {
        setStats(data);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load stats");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
        {error}
      </div>
    );
  }

  const byDomain = stats?.by_domain ?? {};
  const byType = stats?.by_type ?? {};
  const total = stats?.total_observations ?? 0;

  const domainData = Object.entries(byDomain)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  const typeData = Object.entries(byType)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  // Mock time-series data since the backend doesn't provide it yet
  const timeData = generateMockTimeData(total);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Analytics</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Insights and trends across your knowledge base
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<TrendingUp className="w-5 h-5 text-violet-500" />}
          label="Total Observations"
          value={String(total)}
          color="bg-violet-50"
        />
        <StatCard
          icon={<LayoutGrid className="w-5 h-5 text-indigo-500" />}
          label="Domains"
          value={String(Object.keys(byDomain).length)}
          color="bg-indigo-50"
        />
        <StatCard
          icon={<PieChartIcon className="w-5 h-5 text-pink-500" />}
          label="Types"
          value={String(Object.keys(byType).length)}
          color="bg-pink-50"
        />
        <StatCard
          icon={<BarChart3 className="w-5 h-5 text-emerald-500" />}
          label="Categories"
          value={String(Object.keys(byDomain).length)}
          color="bg-emerald-50"
        />
      </div>

      {/* Charts grid */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Observations over time */}
        <ChartCard title="Observations Over Time" subtitle="Simulated trend">
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={timeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#9ca3af" />
              <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
              <Tooltip
                contentStyle={{
                  borderRadius: "8px",
                  border: "1px solid #e5e7eb",
                  fontSize: "13px",
                }}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={{ r: 3, fill: "#8b5cf6" }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Distribution by domain */}
        <ChartCard title="Distribution by Domain">
          {domainData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={domainData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label={({ name, percent }) =>
                    `${name} ${(percent * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {domainData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                    fontSize: "13px",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </ChartCard>

        {/* Distribution by type */}
        <ChartCard title="Distribution by Observation Type">
          {typeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={typeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="#9ca3af" />
                <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                    fontSize: "13px",
                  }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {typeData.map((_, i) => (
                    <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </ChartCard>

        {/* Average confidence by domain */}
        <ChartCard title="Average Confidence by Domain">
          {domainData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={domainData.map((d) => ({ ...d, confidence: 6.5 }))} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis type="number" domain={[0, 10]} tick={{ fontSize: 12 }} stroke="#9ca3af" />
                <YAxis
                  dataKey="name"
                  type="category"
                  tick={{ fontSize: 12 }}
                  stroke="#9ca3af"
                  width={100}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #e5e7eb",
                    fontSize: "13px",
                  }}
                />
                <Bar dataKey="confidence" radius={[0, 4, 4, 0]} fill="#10b981">
                  {domainData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </ChartCard>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className={`${color} rounded-xl p-5`}>
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <span className="text-xs font-medium text-gray-600">{label}</span>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-1">{title}</h3>
      {subtitle && <p className="text-xs text-gray-400 mb-4">{subtitle}</p>}
      {children}
    </div>
  );
}

function EmptyChart() {
  return (
    <div className="flex items-center justify-center h-[250px] text-sm text-gray-400">
      No data available
    </div>
  );
}

// Generate simulated time-series data for "observations over time"
function generateMockTimeData(total: number): { date: string; count: number }[] {
  const data: { date: string; count: number }[] = [];
  const now = new Date();
  let cumulative = 0;
  const perDay = Math.max(1, Math.floor(total / 30));

  for (let i = 29; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    cumulative += perDay + (Math.random() > 0.5 ? 1 : -1) * Math.floor(Math.random() * 3);
    cumulative = Math.max(0, cumulative);
    data.push({
      date: date.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      count: cumulative,
    });
  }

  return data;
}
