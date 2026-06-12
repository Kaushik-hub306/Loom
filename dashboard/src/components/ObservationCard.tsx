import { useNavigate } from "react-router-dom";
import { ArrowUpRight, Tag } from "lucide-react";
import type { Observation } from "../api/client";
import ConfidenceBadge from "./ConfidenceBadge";
import DomainBadge from "./DomainBadge";

interface Props {
  observation: Observation;
}

export default function ObservationCard({ observation }: Props) {
  const navigate = useNavigate();
  const { id, content, confidence, domain, category, observation_type, tags, source_agent, source_urls } =
    observation;

  const preview = content.length > 200 ? content.slice(0, 200) + "..." : content;

  return (
    <div
      onClick={() => navigate(`/observations/${id}`)}
      className="group bg-white border border-gray-200 rounded-xl p-5 hover:border-violet-300
                 hover:shadow-md transition-all cursor-pointer"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <DomainBadge domain={domain} />
          <span className="text-xs font-medium text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
            {observation_type}
          </span>
          <span className="text-xs text-gray-400">{category}</span>
        </div>
        <ConfidenceBadge confidence={confidence} size="sm" />
      </div>

      <p className="text-sm text-gray-700 leading-relaxed mb-3">{preview}</p>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs text-gray-400">
          {source_agent && <span>via {source_agent}</span>}
          {source_urls?.length > 0 && (
            <span>{source_urls.length} source{source_urls.length !== 1 ? "s" : ""}</span>
          )}
          {tags?.length > 0 && (
            <span className="flex items-center gap-1">
              <Tag className="w-3 h-3" />
              {tags.slice(0, 3).join(", ")}
              {tags.length > 3 && ` +${tags.length - 3}`}
            </span>
          )}
        </div>
        <ArrowUpRight className="w-4 h-4 text-gray-300 group-hover:text-violet-500 transition-colors" />
      </div>
    </div>
  );
}
