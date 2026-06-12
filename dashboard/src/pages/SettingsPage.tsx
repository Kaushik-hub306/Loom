import { useState, useEffect } from "react";
import {
  Key,
  Copy,
  Check,
  Trash2,
  Eye,
  EyeOff,
  Shield,
  Download,
  Globe,
  Loader2,
} from "lucide-react";
import { getMe, getOrgs, type UserResponse, type OrgResponse } from "../api/client";

export default function SettingsPage() {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [orgs, setOrgs] = useState<OrgResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // API token state
  const [apiToken, setApiToken] = useState<string | null>(null);
  const [showToken, setShowToken] = useState(false);
  const [tokenCopied, setTokenCopied] = useState(false);
  const [generating, setGenerating] = useState(false);

  // Private mode
  const [privateMode, setPrivateMode] = useState(false);

  useEffect(() => {
    Promise.all([
      getMe().catch(() => null),
      getOrgs().catch(() => [] as OrgResponse[]),
    ])
      .then(([usr, orgList]) => {
        setUser(usr);
        setOrgs(Array.isArray(orgList) ? orgList : []);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load settings");
      })
      .finally(() => setLoading(false));
  }, []);

  function handleGenerateToken() {
    setGenerating(true);
    // Simulate token generation — in production this would call an API
    setTimeout(() => {
      const token = `lt-${crypto.randomUUID()}${crypto.randomUUID()}`.replace(/-/g, "");
      setApiToken(token);
      setShowToken(true);
      setGenerating(false);
    }, 800);
  }

  function handleRevokeToken() {
    setApiToken(null);
    setShowToken(false);
  }

  async function handleCopyToken() {
    if (!apiToken) return;
    try {
      await navigator.clipboard.writeText(apiToken);
      setTokenCopied(true);
      setTimeout(() => setTokenCopied(false), 2000);
    } catch {
      // Fallback
      const ta = document.createElement("textarea");
      ta.value = apiToken;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setTokenCopied(true);
      setTimeout(() => setTokenCopied(false), 2000);
    }
  }

  function handleExportData() {
    alert("Data export will be available in a future release.");
  }

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

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Manage your account and workspace preferences
        </p>
      </div>

      {/* Profile */}
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-4">Profile</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-gray-400">User ID</span>
            <p className="text-gray-700 font-mono text-xs truncate">{user?.user_id ?? "—"}</p>
          </div>
          <div>
            <span className="text-gray-400">Organization ID</span>
            <p className="text-gray-700 font-mono text-xs truncate">{user?.org_id ?? "—"}</p>
          </div>
          <div>
            <span className="text-gray-400">Scope</span>
            <p className="text-gray-700">{user?.scope ?? "—"}</p>
          </div>
          <div>
            <span className="text-gray-400">Organizations</span>
            <p className="text-gray-700">{orgs.length} org{orgs.length !== 1 ? "s" : ""}</p>
          </div>
        </div>
      </section>

      {/* API Token */}
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-1 flex items-center gap-2">
          <Key className="w-4 h-4 text-gray-400" />
          API Token
        </h2>
        <p className="text-xs text-gray-500 mb-4">
          Generate a personal API token for use with the Loom CLI or MCP server.
        </p>

        {!apiToken ? (
          <button
            onClick={handleGenerateToken}
            disabled={generating}
            className="flex items-center gap-2 px-4 py-2.5 bg-gray-900 text-white rounded-lg text-sm
                       font-medium hover:bg-gray-800 disabled:opacity-50 transition-colors"
          >
            {generating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Key className="w-4 h-4" />
                Generate API Token
              </>
            )}
          </button>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-mono text-gray-700 select-all overflow-x-auto">
                {showToken ? apiToken : apiToken?.replace(/./g, "•")}
              </code>
              <button
                onClick={() => setShowToken(!showToken)}
                className="p-2.5 text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg"
                title={showToken ? "Hide token" : "Show token"}
              >
                {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
              <button
                onClick={handleCopyToken}
                className="p-2.5 text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg"
                title="Copy token"
              >
                {tokenCopied ? (
                  <Check className="w-4 h-4 text-emerald-500" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
            </div>
            <button
              onClick={handleRevokeToken}
              className="flex items-center gap-1.5 text-sm text-red-600 hover:text-red-700"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Revoke token
            </button>
          </div>
        )}
      </section>

      {/* Private mode */}
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-1 flex items-center gap-2">
          <Shield className="w-4 h-4 text-gray-400" />
          Privacy
        </h2>
        <p className="text-xs text-gray-500 mb-4">
          In private mode, observations are never shared externally and are only visible to your
          organization.
        </p>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={privateMode}
            onChange={(e) => setPrivateMode(e.target.checked)}
            className="sr-only peer"
          />
          <div className="w-10 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2
                          peer-focus:ring-violet-300 rounded-full peer
                          peer-checked:after:translate-x-full peer-checked:after:border-white
                          after:content-[''] after:absolute after:top-[2px] after:start-[2px]
                          after:bg-white after:border-gray-300 after:border after:rounded-full
                          after:h-4 after:w-4 after:transition-all peer-checked:bg-violet-600"
          />
          <span className="ms-3 text-sm text-gray-600">
            {privateMode ? "Private mode enabled" : "Private mode disabled"}
          </span>
        </label>
      </section>

      {/* Domains */}
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-1 flex items-center gap-2">
          <Globe className="w-4 h-4 text-gray-400" />
          Domain Configuration
        </h2>
        <p className="text-xs text-gray-500 mb-4">
          Domains are created automatically when observations are added with new domain names. The
          following domains have been observed in your workspace:
        </p>
        <div className="flex flex-wrap gap-2">
          {["coding", "design", "devops", "security", "testing", "documentation", "general"].map(
            (d) => (
              <span
                key={d}
                className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-sm"
              >
                {d}
              </span>
            ),
          )}
        </div>
      </section>

      {/* Export */}
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-1 flex items-center gap-2">
          <Download className="w-4 h-4 text-gray-400" />
          Export Data
        </h2>
        <p className="text-xs text-gray-500 mb-4">
          Download all observations and audit logs in JSON format. This may take a moment for large
          workspaces.
        </p>
        <button
          onClick={handleExportData}
          className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm
                     font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          <Download className="w-4 h-4" />
          Export all data
        </button>
      </section>
    </div>
  );
}
