import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Link2,
  Trash2,
  TrendingUp,
  TrendingDown,
  Loader2,
  ExternalLink,
  Tag,
  Calendar,
} from "lucide-react";
import {
  getObservation,
  deleteObservation,
  updateObservation,
  getRelated,
  type Observation,
  type RelatedResponse,
} from "../api/client";
import ConfidenceBadge from "../components/ConfidenceBadge";
import DomainBadge from "../components/DomainBadge";

export default function ObservationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [observation, setObservation] = useState<Observation | null>(null);
  const [related, setRelated] = useState<RelatedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);

    Promise.all([
      getObservation(id).catch(() => null),
      getRelated(id, 1).catch(() => null),
    ]).then(([obs, rel]) => {
      if (obs) {
        setObservation(obs);
      } else {
        setError("Observation not found");
      }
      setRelated(rel);
      setLoading(false);
    });
  }, [id]);

  async function handlePromote() {
    if (!observation) return;
    setActionLoading(true);
    try {
      const newConf = Math.min(10, observation.confidence + 1);
      const updated = await updateObservation(observation.id, {
        confidence: newConf,
      });
      setObservation(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to promote");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDemote() {
    if (!observation) return;
    setActionLoading(true);
    try {
      const newConf = Math.max(1, observation.confidence - 1);
      const updated = await updateObservation(observation.id, {
        confidence: newConf,
      });
      setObservation(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to demote");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDelete() {
    if (!observation) return;
    setActionLoading(true);
    try {
      await deleteObservation(observation.id);
      navigate("/observations", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
      </div>
    );
  }

  if (error || !observation) {
    return (
      <div className="max-w-2xl mx-auto">
        <button
          onClick={() => navigate("/observations")}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to observations
        </button>
        <div className="p-6 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error || "Observation not found"}
        </div>
      </div>
    );
  }

  const {
    content,
    confidence,
    domain,
    category,
    observation_type,
    tags,
    times_confirmed,
    times_violated,
    source_urls,
    source_agent,
    source_session,
    created_at,
    updated_at,
    access_scope,
    context,
  } = observation;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Back link */}
      <button
        onClick={() => navigate("/observations")}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to observations
      </button>

      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <DomainBadge domain={domain} />
          <span className="text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
            {observation_type}
          </span>
          <span className="text-xs text-gray-400">{category}</span>
          <ConfidenceBadge confidence={confidence} />
        </div>

        <div className="prose prose-sm max-w-none mb-6">
          <p className="text-gray-800 text-base leading-relaxed whitespace-pre-wrap">
            {content}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-4 border-t border-gray-100">
          <button
            onClick={handlePromote}
            disabled={actionLoading || confidence >= 10}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-lg
                       text-sm font-medium hover:bg-emerald-100 disabled:opacity-40 transition-colors"
            title="Increase confidence"
          >
            <TrendingUp className="w-4 h-4" />
            Promote
          </button>
          <button
            onClick={handleDemote}
            disabled={actionLoading || confidence <= 1}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg
                       text-sm font-medium hover:bg-amber-100 disabled:opacity-40 transition-colors"
            title="Decrease confidence"
          >
            <TrendingDown className="w-4 h-4" />
            Demote
          </button>
          <div className="flex-1" />
          {!deleteConfirm ? (
            <button
              onClick={() => setDeleteConfirm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-600 rounded-lg
                         text-sm font-medium hover:bg-red-100 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-red-600">Confirm delete?</span>
              <button
                onClick={handleDelete}
                disabled={actionLoading}
                className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-sm font-medium
                           hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                {actionLoading ? "Deleting..." : "Yes"}
              </button>
              <button
                onClick={() => setDeleteConfirm(false)}
                className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium
                           hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Metadata */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-4">Metadata</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-gray-400">Domain</span>
            <p className="text-gray-700">{domain}</p>
          </div>
          <div>
            <span className="text-gray-400">Category</span>
            <p className="text-gray-700">{category}</p>
          </div>
          <div>
            <span className="text-gray-400">Type</span>
            <p className="text-gray-700">{observation_type}</p>
          </div>
          <div>
            <span className="text-gray-400">Access Scope</span>
            <p className="text-gray-700">{access_scope}</p>
          </div>
          <div>
            <span className="text-gray-400">Times Confirmed</span>
            <p className="text-gray-700">{times_confirmed}</p>
          </div>
          <div>
            <span className="text-gray-400">Times Violated</span>
            <p className="text-gray-700">{times_violated}</p>
          </div>
          <div>
            <span className="text-gray-400">Source Agent</span>
            <p className="text-gray-700">{source_agent || "—"}</p>
          </div>
          <div>
            <span className="text-gray-400">Source Session</span>
            <p className="text-gray-700 truncate">{source_session || "—"}</p>
          </div>
        </div>

        {tags?.length > 0 && (
          <div className="mt-4 pt-3 border-t border-gray-100">
            <span className="text-xs text-gray-400 flex items-center gap-1 mb-2">
              <Tag className="w-3 h-3" />
              Tags
            </span>
            <div className="flex flex-wrap gap-1.5">
              {tags.map((t) => (
                <span
                  key={t}
                  className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="mt-4 pt-3 border-t border-gray-100 flex items-center gap-4 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            Created: {new Date(created_at).toLocaleString()}
          </span>
          <span>Updated: {new Date(updated_at).toLocaleString()}</span>
        </div>

        {context && Object.keys(context).length > 0 && (
          <div className="mt-4 pt-3 border-t border-gray-100">
            <span className="text-xs text-gray-400 block mb-1.5">Context</span>
            <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-auto max-h-40">
              {JSON.stringify(context, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Source URLs */}
      {source_urls?.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Link2 className="w-4 h-4 text-gray-400" />
            Sources
          </h2>
          <ul className="space-y-2">
            {source_urls.map((url, i) => (
              <li key={i}>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-sm text-violet-600 hover:text-violet-700"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  {url}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Related observations */}
      {related && related.links && related.links.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Link2 className="w-4 h-4 text-gray-400" />
            Related Observations
          </h2>
          <ul className="space-y-2">
            {related.links.map((link, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                  {link.relation}
                </span>
                <button
                  onClick={() => {
                    const targetId = link.target === id ? link.source : link.target;
                    navigate(`/observations/${targetId}`);
                  }}
                  className="text-violet-600 hover:text-violet-700 font-mono text-xs truncate"
                >
                  {link.target === id ? link.source : link.target}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
