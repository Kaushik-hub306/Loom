import { useState, useEffect, useCallback } from "react";
import { Plus, Loader2 } from "lucide-react";
import { getObservations, searchObservations, getStats, type Observation, type Stats } from "../api/client";
import SearchBar from "../components/SearchBar";
import ObservationCard from "../components/ObservationCard";

export default function ObservationsPage() {
  const [observations, setObservations] = useState<Observation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedDomain, setSelectedDomain] = useState<string | undefined>();
  const [selectedType, setSelectedType] = useState<string | undefined>();
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [availableDomains, setAvailableDomains] = useState<string[]>([]);
  const [availableTypes, setAvailableTypes] = useState<string[]>([]);

  const LIMIT = 50;

  const loadObservations = useCallback(async (searchMode: boolean, append: boolean = false) => {
    try {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(null);

      let results: Observation[];

      if (searchMode && (query || selectedDomain || selectedType)) {
        results = await searchObservations({
          query: query || "",
          domain: selectedDomain ?? null,
          observation_type: selectedType ?? null,
        });
      } else {
        results = await getObservations({
          limit: LIMIT,
          offset: append ? offset : 0,
          domain: selectedDomain,
          type: selectedType,
        });
      }

      if (append) {
        setObservations((prev) => [...prev, ...results]);
      } else {
        setObservations(results);
      }
      setHasMore(results.length === LIMIT);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load observations");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [query, selectedDomain, selectedType, offset]);

  // Initial load + load available domains/types
  useEffect(() => {
    loadObservations(false);

    getStats().then((stats: Stats) => {
      if (stats.by_domain) {
        setAvailableDomains(Object.keys(stats.by_domain));
      }
      if (stats.by_type) {
        setAvailableTypes(Object.keys(stats.by_type));
      }
    }).catch(() => {
      /* ignore */
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSearch() {
    setOffset(0);
    loadObservations(true);
  }

  function handleDomainChange(d: string | undefined) {
    setSelectedDomain(d);
    setOffset(0);
  }

  function handleTypeChange(t: string | undefined) {
    setSelectedType(t);
    setOffset(0);
  }

  function handleLoadMore() {
    const newOffset = offset + LIMIT;
    setOffset(newOffset);
    // We need the new offset in effect, so trigger reload
  }

  // Reload when filters change
  useEffect(() => {
    loadObservations(false);
  }, [selectedDomain, selectedType]); // eslint-disable-line react-hooks/exhaustive-deps

  const isSearching = query.length > 0;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            Observations
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Browse and search your team's knowledge base
          </p>
        </div>
        <button
          className="flex items-center gap-2 px-4 py-2.5 bg-violet-600 text-white rounded-lg text-sm
                     font-medium hover:bg-violet-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Observation
        </button>
      </div>

      <SearchBar
        value={query}
        onChange={setQuery}
        onSearch={handleSearch}
        domains={availableDomains}
        types={availableTypes}
        selectedDomain={selectedDomain}
        selectedType={selectedType}
        onDomainChange={handleDomainChange}
        onTypeChange={handleTypeChange}
      />

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
        </div>
      ) : observations.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-500 text-sm">No observations found.</p>
          <p className="text-gray-400 text-xs mt-1">
            {isSearching
              ? "Try a different search query."
              : "Create your first observation to get started."}
          </p>
        </div>
      ) : (
        <>
          <div className="grid gap-4">
            {observations.map((obs) => (
              <ObservationCard key={obs.id} observation={obs} />
            ))}
          </div>

          {hasMore && !isSearching && (
            <div className="flex justify-center pt-4">
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="flex items-center gap-2 px-6 py-2.5 bg-white border border-gray-200
                           rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50
                           disabled:opacity-50 transition-colors"
              >
                {loadingMore ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading...
                  </>
                ) : (
                  "Load more"
                )}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
