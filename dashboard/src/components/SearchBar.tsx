import { useState, FormEvent } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";

interface Props {
  value: string;
  onChange: (val: string) => void;
  onSearch: (query: string) => void;
  domains?: string[];
  types?: string[];
  selectedDomain?: string;
  selectedType?: string;
  onDomainChange?: (d: string | undefined) => void;
  onTypeChange?: (t: string | undefined) => void;
  placeholder?: string;
}

export default function SearchBar({
  value,
  onChange,
  onSearch,
  domains = [],
  types = [],
  selectedDomain,
  selectedType,
  onDomainChange,
  onTypeChange,
  placeholder = "Search observations...",
}: Props) {
  const [showFilters, setShowFilters] = useState(false);
  const hasFilters = selectedDomain || selectedType;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSearch(value);
  }

  function clearFilters() {
    onDomainChange?.(undefined);
    onTypeChange?.(undefined);
  }

  return (
    <div className="space-y-2">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm
                       placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/20
                       focus:border-violet-500 transition-colors"
          />
        </div>
        <button
          type="button"
          onClick={() => setShowFilters(!showFilters)}
          className={`p-2.5 rounded-lg border transition-colors ${
            showFilters || hasFilters
              ? "border-violet-500 bg-violet-50 text-violet-600"
              : "border-gray-200 bg-white text-gray-500 hover:bg-gray-50"
          }`}
        >
          <SlidersHorizontal className="w-4 h-4" />
        </button>
        <button
          type="submit"
          className="px-4 py-2.5 bg-gray-900 text-white rounded-lg text-sm font-medium
                     hover:bg-gray-800 transition-colors"
        >
          Search
        </button>
      </form>

      {showFilters && (
        <div className="flex flex-wrap items-center gap-3 p-3 bg-white border border-gray-200 rounded-lg">
          {domains.length > 0 && (
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-gray-500">Domain</label>
              <select
                value={selectedDomain ?? ""}
                onChange={(e) => onDomainChange?.(e.target.value || undefined)}
                className="text-sm border border-gray-200 rounded-md px-2 py-1.5 bg-white focus:outline-none
                           focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
              >
                <option value="">All</option>
                {domains.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
          )}

          {types.length > 0 && (
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-gray-500">Type</label>
              <select
                value={selectedType ?? ""}
                onChange={(e) => onTypeChange?.(e.target.value || undefined)}
                className="text-sm border border-gray-200 rounded-md px-2 py-1.5 bg-white focus:outline-none
                           focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
              >
                <option value="">All</option>
                {types.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          )}

          {hasFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
            >
              <X className="w-3 h-3" />
              Clear filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}
