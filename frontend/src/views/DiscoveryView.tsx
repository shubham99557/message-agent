import React, { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '../api/client';
import {
  Search,
  Upload,
  Building2,
  Laptop,
  CheckCircle2,
  ExternalLink,
  Plus,
  Filter,
  FileSpreadsheet,
  AlertCircle,
  AlertTriangle,
  MapPin,
  Globe2,
  Sparkles,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  History,
  X
} from 'lucide-react';

interface DiscoveryViewProps {
  onCompanyImported?: () => void;
}

interface LocationPreset {
  id: string;
  name: string;
  description: string;
  cities: string[];
}

export const DiscoveryView: React.FC<DiscoveryViewProps> = ({ onCompanyImported }) => {
  // Scope & Location States
  const [scope, setScope] = useState<'country' | 'state' | 'city'>('city');
  const [selectedState, setSelectedState] = useState<string>('');
  const [cityInput, setCityInput] = useState<string>('Siliguri');
  const [citySuggestions, setCitySuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState<boolean>(false);
  const [statesList, setStatesList] = useState<Array<{ name: string; code: string; region: string }>>([]);
  const [presets, setPresets] = useState<LocationPreset[]>([]);
  const [activePreset, setActivePreset] = useState<string>('target_east_northeast');

  // Search & Filter Parameters
  const [industry, setIndustry] = useState<string>('All');
  const [customIndustry, setCustomIndustry] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [minDevices, setMinDevices] = useState<number | undefined>(undefined);
  const [includeDemo, setIncludeDemo] = useState<boolean>(false);
  const [contactFilter, setContactFilter] = useState<'all' | 'has_email' | 'has_phone'>('all');
  const [sortBy, setSortBy] = useState<string>('confidence');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Pagination & Results States
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(15);
  const [totalResults, setTotalResults] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [results, setResults] = useState<any[]>([]);
  const [coverageNote, setCoverageNote] = useState<string>('');
  const [activeStrategy, setActiveStrategy] = useState<string>('');
  const [activeProviders, setActiveProviders] = useState<string[]>([]);
  const [failedProviders, setFailedProviders] = useState<string[]>([]);
  const [sources, setSources] = useState<any[]>([]);
  const [industriesList, setIndustriesList] = useState<any[]>([]);

  // Search UI States
  const [searching, setSearching] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchHistory, setSearchHistory] = useState<string[]>(['Siliguri', 'Gangtok', 'Patna', 'All India']);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [importSuccess, setImportSuccess] = useState<string | null>(null);

  // CSV & Crawler States
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [uploadingCsv, setUploadingCsv] = useState<boolean>(false);
  const [csvSummary, setCsvSummary] = useState<any>(null);
  const [crawlUrl, setCrawlUrl] = useState<string>('');
  const [crawling, setCrawling] = useState<boolean>(false);
  const [crawlResult, setCrawlResult] = useState<any>(null);

  // Abort controller refs for canceling stale requests
  const searchAbortRef = useRef<AbortController | null>(null);
  const suggestAbortRef = useRef<AbortController | null>(null);
  const debounceTimerRef = useRef<any>(null);

  // Initial load of metadata: states, sources, presets, industries
  useEffect(() => {
    api.getDiscoverySources().then(setSources).catch(() => {});
    api.getIndianStates().then(setStatesList).catch(() => {});
    api.getLocationPresets().then(setPresets).catch(() => {});
    api.getDiscoveryIndustries().then(setIndustriesList).catch(() => {});
    // Initial search
    executeSearch({ initial: true });
  }, []);

  // Debounced autocomplete for city suggestions
  const handleCityInputChange = (value: string) => {
    setCityInput(value);
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);

    if (suggestAbortRef.current) {
      suggestAbortRef.current.abort();
    }

    if (!value.trim() || value.length < 2) {
      setCitySuggestions([]);
      setShowSuggestions(false);
      return;
    }

    debounceTimerRef.current = setTimeout(async () => {
      suggestAbortRef.current = new AbortController();
      try {
        const list = await api.suggestLocations(
          { q: value.trim(), state: selectedState || undefined, limit: 8 },
          suggestAbortRef.current.signal
        );
        setCitySuggestions(list);
        setShowSuggestions(list.length > 0);
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setCitySuggestions([]);
        }
      }
    }, 350);
  };

  // Main search execution function
  const executeSearch = useCallback(async (opts: { newPage?: number; initial?: boolean } = {}) => {
    if (searchAbortRef.current) {
      searchAbortRef.current.abort();
    }
    searchAbortRef.current = new AbortController();

    const targetPage = opts.newPage !== undefined ? opts.newPage : (opts.initial ? 1 : page);
    setSearching(true);
    setSearchError(null);
    setImportSuccess(null);

    const effectiveIndustry = industry === 'custom'
      ? customIndustry.trim()
      : (industry === 'All' ? undefined : industry);

    let effectiveCity = cityInput.trim();
    if (scope === 'country') {
      effectiveCity = 'All';
    } else if (scope === 'state' && !effectiveCity) {
      effectiveCity = '';
    }

    const payload = {
      city: effectiveCity || undefined,
      state: selectedState || undefined,
      scope,
      industry: effectiveIndustry || undefined,
      query: searchQuery.trim() || undefined,
      min_devices: minDevices,
      include_demo: includeDemo,
      page: targetPage,
      page_size: pageSize,
      sort_by: sortBy,
      sort_order: sortOrder,
    };

    try {
      const data = await api.searchDiscoveryPaginated(payload, searchAbortRef.current.signal);
      setResults(data.items || []);
      setTotalResults(data.total || 0);
      setPage(data.page || 1);
      setTotalPages(data.total_pages || 1);
      setCoverageNote(data.coverage_note || '');
      setActiveStrategy(data.search_strategy || '');
      setActiveProviders(data.active_providers || []);
      setFailedProviders(data.failed_providers || []);

      // Add to search history if unique
      const historyItem = scope === 'country'
        ? 'All India'
        : (effectiveCity ? `${effectiveCity}${selectedState ? `, ${selectedState}` : ''}` : selectedState || 'Nationwide');
      if (historyItem && !searchHistory.includes(historyItem)) {
        setSearchHistory((prev) => [historyItem, ...prev.slice(0, 4)]);
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error('Discovery search error:', err);
        setSearchError(err.message || 'Discovery search failed. Check provider configuration or try again.');
        setResults([]);
      }
    } finally {
      setSearching(false);
    }
  }, [
    scope,
    selectedState,
    cityInput,
    industry,
    customIndustry,
    searchQuery,
    minDevices,
    includeDemo,
    pageSize,
    sortBy,
    sortOrder,
    page,
    searchHistory
  ]);

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setShowSuggestions(false);
    setPage(1);
    executeSearch({ newPage: 1 });
  };

  const handlePresetSelect = (preset: LocationPreset) => {
    setActivePreset(preset.id);
    if (preset.id === 'all_india') {
      setScope('country');
      setCityInput('All');
    } else {
      setScope('city');
      setCityInput(preset.cities[0]);
    }
    setPage(1);
    setTimeout(() => {
      executeSearch({ newPage: 1 });
    }, 50);
  };

  const handleImportLead = async (item: any) => {
    setImportingId(item.name);
    try {
      await api.importDiscoveredLead(item);
      setImportSuccess(`Successfully imported "${item.name}" with full source attribution!`);
      if (onCompanyImported) onCompanyImported();
    } catch (err: any) {
      alert(`Import error: ${err.message}`);
    } finally {
      setImportingId(null);
    }
  };

  const handleBatchImport = async () => {
    if (!results.length) return;
    try {
      const imported = await api.batchImportDiscoveredLeads(results);
      setImportSuccess(`Batch imported ${imported.length} new qualified leads into CRM!`);
      if (onCompanyImported) onCompanyImported();
    } catch (e: any) {
      alert(`Batch import failed: ${e.message}`);
    }
  };

  const handleCsvUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) return;
    setUploadingCsv(true);
    setCsvSummary(null);
    try {
      const summary = await api.uploadDiscoveryCsv(csvFile);
      setCsvSummary(summary);
      setCsvFile(null);
      if (onCompanyImported) onCompanyImported();
    } catch (err: any) {
      alert(`CSV upload error: ${err.message}`);
    } finally {
      setUploadingCsv(false);
    }
  };

  const handleCrawlWebsite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!crawlUrl.trim()) return;
    setCrawling(true);
    setCrawlResult(null);
    try {
      const data = await api.crawlWebsite(crawlUrl.trim(), undefined, cityInput || 'Siliguri');
      setCrawlResult(data);
    } catch (err: any) {
      alert(`Website scan error: ${err.message}`);
    } finally {
      setCrawling(false);
    }
  };

  // Client-side contact availability filter
  const filteredResults = results.filter((comp) => {
    if (contactFilter === 'has_email') return Boolean(comp.public_email);
    if (contactFilter === 'has_phone') return Boolean(comp.public_phone || comp.public_whatsapp);
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Top Header & Provider Connectivity Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
            <Globe2 className="w-5 h-5 text-cobalt-400" />
            <span>Nationwide Business Discovery Engine</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time multi-region discovery across 28 States & 8 Union Territories with strict source verification.
          </p>
        </div>

        {/* Modular Provider Status Pills */}
        <div className="flex flex-wrap items-center gap-2">
          {sources.map((src, i) => (
            <span
              key={i}
              className={`px-2.5 py-1 rounded-full text-[11px] font-mono border flex items-center space-x-1.5 ${
                src.configured
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  : 'bg-cobalt-950 text-slate-400 border-cobalt-800'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${src.configured ? 'bg-emerald-400' : 'bg-slate-500'}`} />
              <span>{src.label}: {src.configured ? 'Active' : 'Unconfigured'}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Location Presets & Quick Corridors */}
      <div className="bg-cobalt-900/60 border border-cobalt-800 rounded-lg p-3">
        <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
          <MapPin className="w-3.5 h-3.5 text-cobalt-400" />
          <span>Saved Regional Focus Presets</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {presets.map((preset) => (
            <button
              key={preset.id}
              onClick={() => handlePresetSelect(preset)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors border ${
                activePreset === preset.id
                  ? 'bg-cobalt-600 border-cobalt-500 text-white shadow-sm'
                  : 'bg-cobalt-950/80 border-cobalt-800 text-slate-300 hover:bg-cobalt-800 hover:text-white'
              }`}
              title={preset.description}
            >
              {preset.name}
            </button>
          ))}
          <button
            onClick={() => {
              setActivePreset('all_india');
              setScope('country');
              setCityInput('All');
              setPage(1);
              setTimeout(() => executeSearch({ newPage: 1 }), 50);
            }}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors border ${
              scope === 'country'
                ? 'bg-cobalt-600 border-cobalt-500 text-white shadow-sm'
                : 'bg-cobalt-950/80 border-cobalt-800 text-slate-300 hover:bg-cobalt-800 hover:text-white'
            }`}
          >
            🇮🇳 All India (Multi-Region)
          </button>
        </div>
      </div>

      {/* Main Search & Discovery Controls Bar */}
      <form onSubmit={handleFormSubmit} className="bg-cobalt-900/90 border border-cobalt-800 rounded-lg p-4 space-y-4">
        {/* Row 1: Scope, State, City Autocomplete, Industry */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {/* Scope Selector */}
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Search Scope</label>
            <select
              value={scope}
              onChange={(e) => {
                const val = e.target.value as 'country' | 'state' | 'city';
                setScope(val);
                if (val === 'country') setCityInput('All');
                else if (val === 'city' && cityInput === 'All') setCityInput('Siliguri');
              }}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
            >
              <option value="city">Specific City / Hub</option>
              <option value="state">Specific State / UT</option>
              <option value="country">All India (Nationwide Corridors)</option>
            </select>
          </div>

          {/* State Selector */}
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">
              State / Union Territory {scope === 'state' && <span className="text-amber-400">*</span>}
            </label>
            <select
              value={selectedState}
              onChange={(e) => setSelectedState(e.target.value)}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
            >
              <option value="">All States & UTs</option>
              {statesList.map((st) => (
                <option key={st.code} value={st.name}>
                  {st.name} ({st.region})
                </option>
              ))}
            </select>
          </div>

          {/* City Input with Debounced Autocomplete */}
          <div className="relative">
            <label className="block text-[11px] font-medium text-slate-400 mb-1">
              Target City / Town {scope === 'country' && <span className="text-slate-500">(Nationwide)</span>}
            </label>
            <input
              type="text"
              disabled={scope === 'country'}
              placeholder={scope === 'country' ? 'All India (Automated Corridors)' : 'e.g. Siliguri, Bengaluru, Patna'}
              value={scope === 'country' ? 'All India' : cityInput}
              onChange={(e) => handleCityInputChange(e.target.value)}
              onFocus={() => {
                if (citySuggestions.length > 0 && scope !== 'country') setShowSuggestions(true);
              }}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 disabled:opacity-60 placeholder:text-slate-500"
            />
            {/* Autocomplete Suggestions Dropdown */}
            {showSuggestions && citySuggestions.length > 0 && (
              <div className="absolute z-20 left-0 right-0 mt-1 bg-cobalt-900 border border-cobalt-700 rounded-md shadow-xl max-h-48 overflow-y-auto">
                {citySuggestions.map((sugg, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => {
                      setCityInput(sugg.city);
                      setSelectedState(sugg.state);
                      setShowSuggestions(false);
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-slate-200 hover:bg-cobalt-800 flex items-center justify-between border-b border-cobalt-800/40 last:border-0"
                  >
                    <div>
                      <span className="font-semibold text-slate-100">{sugg.city}</span>
                      <span className="text-slate-400 text-[11px] ml-1.5">({sugg.state})</span>
                    </div>
                    <span className="text-[10px] font-mono text-cobalt-400">{sugg.tier}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Target Industry Selector */}
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Target Business Type</label>
            <select
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
            >
              <option value="All">All Tech & Professional Categories</option>
              {industriesList.map((ind) => (
                <option key={ind.id} value={ind.name}>
                  {ind.name}
                </option>
              ))}
              <option value="custom">-- Custom Category / Keyword --</option>
            </select>
          </div>
        </div>

        {/* Row 2: Custom Category (if selected), Keywords, Min Laptops, Demo Checkbox, Submit */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          {industry === 'custom' ? (
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Custom Business Category</label>
              <input
                type="text"
                placeholder="e.g. Telecom BPO, Pathology Labs"
                value={customIndustry}
                onChange={(e) => setCustomIndustry(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
              />
            </div>
          ) : (
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Keywords / Name Search</label>
              <input
                type="text"
                placeholder="e.g. cloud, labs, solutions"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 placeholder:text-slate-500"
              />
            </div>
          )}

          {/* Min Laptop Filter */}
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Min Verified Laptops</label>
            <select
              value={minDevices ?? ''}
              onChange={(e) => setMinDevices(e.target.value ? Number(e.target.value) : undefined)}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
            >
              <option value="">Any Fleet Size (Include Pending)</option>
              <option value="5">5+ Laptops (ActTrident Target)</option>
              <option value="10">10+ Laptops</option>
              <option value="20">20+ Laptops</option>
            </select>
          </div>

          {/* Demo Quarantine Checkbox */}
          <div className="flex flex-col justify-end">
            <label className="flex items-center space-x-1.5 text-[11px] text-amber-300/90 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={includeDemo}
                onChange={(e) => setIncludeDemo(e.target.checked)}
                className="rounded border-cobalt-700 bg-cobalt-950 text-amber-500 focus:ring-0"
              />
              <span>Include Demo Fixtures (non-prod only)</span>
            </label>
          </div>

          {/* Search Trigger Button */}
          <button
            type="submit"
            disabled={searching}
            className="w-full py-2 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-semibold transition-colors flex items-center justify-center space-x-1.5 shadow-sm"
          >
            {searching ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Searching Across India...</span>
              </>
            ) : (
              <>
                <Search className="w-3.5 h-3.5" />
                <span>Run Real-Time Discovery</span>
              </>
            )}
          </button>
        </div>

        {/* Recent Search History Tags */}
        {searchHistory.length > 0 && (
          <div className="flex items-center space-x-2 pt-2 border-t border-cobalt-800/60 text-[11px] text-slate-400">
            <History className="w-3.5 h-3.5 text-slate-500" />
            <span>Recent:</span>
            <div className="flex flex-wrap gap-1.5">
              {searchHistory.map((item, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    if (item === 'All India') {
                      setScope('country');
                      setCityInput('All');
                    } else {
                      setScope('city');
                      setCityInput(item.split(',')[0].trim());
                    }
                    setTimeout(() => executeSearch({ newPage: 1 }), 50);
                  }}
                  className="px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 text-slate-300 hover:border-cobalt-600 hover:text-white"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        )}
      </form>

      {/* Strategy and Coverage Banner */}
      {coverageNote && (
        <div className="p-3 bg-cobalt-900/60 border border-cobalt-800 rounded text-xs text-slate-300 flex items-start space-x-2">
          <Sparkles className="w-4 h-4 text-cobalt-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <div className="font-semibold text-slate-200">
              Active Strategy: {activeStrategy || 'Targeted Discovery'}
            </div>
            <div className="text-[11px] text-slate-400">{coverageNote}</div>
          </div>
        </div>
      )}

      {/* Search Error Alert */}
      {searchError && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded text-xs text-rose-300 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{searchError}</span>
          </div>
          <button
            onClick={() => executeSearch()}
            className="px-2.5 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded text-[11px] font-medium"
          >
            Retry Search
          </button>
        </div>
      )}

      {/* Success Notification */}
      {importSuccess && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-300 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{importSuccess}</span>
          </div>
          <button onClick={() => setImportSuccess(null)} className="text-slate-400 hover:text-slate-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Results Header, Sorting & Filter Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-cobalt-900/80 border border-cobalt-800 rounded-t-lg p-3">
        <div className="text-xs font-semibold text-slate-200 flex items-center space-x-2">
          <span>Discovered Prospects</span>
          <span className="px-2 py-0.5 rounded-full bg-cobalt-800 text-cobalt-300 font-mono text-[11px]">
            {totalResults} {totalResults === 1 ? 'record' : 'records'}
          </span>
          {searching && <span className="text-[11px] text-cobalt-400 animate-pulse font-normal">Updating...</span>}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Contact availability filter */}
          <select
            value={contactFilter}
            onChange={(e) => setContactFilter(e.target.value as any)}
            className="bg-cobalt-950 border border-cobalt-800 rounded px-2 py-1 text-[11px] text-slate-300"
          >
            <option value="all">All Contacts</option>
            <option value="has_email">Must have Email</option>
            <option value="has_phone">Must have Phone / WA</option>
          </select>

          {/* Sort By Selector */}
          <select
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value);
              setTimeout(() => executeSearch(), 20);
            }}
            className="bg-cobalt-950 border border-cobalt-800 rounded px-2 py-1 text-[11px] text-slate-300"
          >
            <option value="confidence">Sort by Confidence</option>
            <option value="name">Sort by Company Name</option>
            <option value="city">Sort by City</option>
            <option value="devices">Sort by Laptops</option>
            <option value="retrieval">Sort by Recent</option>
          </select>

          {/* Batch Import Button */}
          {results.length > 0 && (
            <button
              onClick={handleBatchImport}
              className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Import Page ({results.length})</span>
            </button>
          )}
        </div>
      </div>

      {/* Discovered Results Table or Loading Skeletons */}
      <div className="bg-cobalt-900/80 border-x border-b border-cobalt-800 rounded-b-lg overflow-hidden">
        {searching && results.length === 0 ? (
          // Loading Skeletons
          <div className="p-6 space-y-4">
            {[1, 2, 3, 4].map((n) => (
              <div key={n} className="animate-pulse flex items-center justify-between p-3 bg-cobalt-950/60 rounded">
                <div className="space-y-2 flex-1 max-w-sm">
                  <div className="h-4 bg-cobalt-800 rounded w-3/4" />
                  <div className="h-3 bg-cobalt-800/60 rounded w-1/2" />
                </div>
                <div className="h-3 bg-cobalt-800/60 rounded w-32" />
                <div className="h-3 bg-cobalt-800/60 rounded w-24" />
                <div className="h-6 bg-cobalt-800 rounded w-20" />
              </div>
            ))}
          </div>
        ) : filteredResults.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400">
            <Building2 className="w-8 h-8 mx-auto text-cobalt-600 mb-2 opacity-60" />
            <p className="font-semibold text-slate-300">No matching business records found.</p>
            <p className="text-[11px] mt-1 text-slate-500">
              Try broadening your location scope to "All India" or clearing the keyword filter.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cobalt-950/60 text-slate-400 border-b border-cobalt-800/80 font-medium">
                <tr>
                  <th className="py-2.5 px-3">Company & Website</th>
                  <th className="py-2.5 px-3">Location & Industry</th>
                  <th className="py-2.5 px-3">Public Contacts</th>
                  <th className="py-2.5 px-3">Managed Laptops</th>
                  <th className="py-2.5 px-3">Confidence & Source</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cobalt-800/40 text-slate-200">
                {filteredResults.map((comp, idx) => {
                  const isDemoItem = comp.is_demo || comp.verification_status === 'demo_fixture';
                  return (
                    <tr key={idx} className="hover:bg-cobalt-850/50 transition-colors">
                      <td className="py-3 px-3">
                        <div className="flex items-center space-x-1.5">
                          <span className="font-semibold text-slate-100">{comp.name}</span>
                          {isDemoItem && (
                            <span className="px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[9px] font-mono uppercase">
                              DEMO FIXTURE
                            </span>
                          )}
                        </div>
                        {comp.website && (
                          <a
                            href={comp.website}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[11px] text-cobalt-400 hover:underline flex items-center space-x-1 mt-0.5"
                          >
                            <span className="truncate max-w-[180px]">{comp.website}</span>
                            <ExternalLink className="w-3 h-3 shrink-0" />
                          </a>
                        )}
                        {comp.description && (
                          <p className="text-[11px] text-slate-400 line-clamp-1 mt-0.5 max-w-sm">
                            {comp.description}
                          </p>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-medium text-slate-200">
                          {comp.city}{comp.state ? `, ${comp.state}` : ''}
                        </div>
                        <div className="text-[11px] text-slate-400">{comp.industry || 'Technology Services'}</div>
                      </td>
                      <td className="py-3 px-3 space-y-0.5 font-mono text-[11px]">
                        {comp.public_email && <div className="text-slate-300">✉ {comp.public_email}</div>}
                        {comp.public_phone && <div className="text-slate-400">☎ {comp.public_phone}</div>}
                        {!comp.public_email && !comp.public_phone && (
                          <div className="text-slate-500 italic">Pending crawl verification</div>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        {comp.laptop_count_verified ? (
                          <div className={`flex items-center space-x-1.5 font-mono font-medium ${isDemoItem ? 'text-amber-300' : 'text-emerald-400'}`}>
                            <Laptop className="w-3.5 h-3.5" />
                            <span>{comp.laptop_count_verified} Laptops</span>
                          </div>
                        ) : (
                          <div className="flex items-center space-x-1.5 text-slate-400 font-mono">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                            <span>Pending Fleet Audit</span>
                          </div>
                        )}
                        <div className="text-[10px] text-slate-400 truncate max-w-[180px]" title={comp.laptop_count_evidence}>
                          {comp.laptop_count_evidence || 'Evidence required before live outreach'}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-[11px] space-y-1">
                        <div className="flex items-center space-x-1.5">
                          <span className="px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 text-slate-300 font-mono text-[10px]">
                            {comp.source_type}
                          </span>
                          <span className="text-[10px] font-mono text-cobalt-400">
                            {Math.round((comp.confidence_level || 0.5) * 100)}% conf
                          </span>
                        </div>
                        <div className="text-[10px] font-mono text-slate-400">
                          status: {comp.verification_status || (isDemoItem ? 'demo_fixture' : 'unverified')}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={() => handleImportLead(comp)}
                          disabled={importingId === comp.name}
                          className="px-2.5 py-1 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1 ml-auto"
                        >
                          <Plus className="w-3 h-3" />
                          <span>{importingId === comp.name ? 'Saving...' : 'Add Lead'}</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Toolbar */}
        {totalResults > 0 && (
          <div className="p-3 bg-cobalt-950/60 border-t border-cobalt-800 flex items-center justify-between text-xs text-slate-400">
            <div>
              Showing page {page} of {totalPages} ({totalResults} total prospects)
            </div>
            <div className="flex items-center space-x-2">
              <button
                disabled={page <= 1 || searching}
                onClick={() => {
                  const newPage = page - 1;
                  setPage(newPage);
                  executeSearch({ newPage });
                }}
                className="px-2.5 py-1 bg-cobalt-900 border border-cobalt-800 rounded disabled:opacity-40 text-slate-300 hover:text-white flex items-center space-x-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Prev</span>
              </button>
              <span className="font-mono text-slate-300">
                {page} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages || searching}
                onClick={() => {
                  const newPage = page + 1;
                  setPage(newPage);
                  executeSearch({ newPage });
                }}
                className="px-2.5 py-1 bg-cobalt-900 border border-cobalt-800 rounded disabled:opacity-40 text-slate-300 hover:text-white flex items-center space-x-1"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Auxiliary Tools: CSV Batch Import & SSRF-Protected Live Website Crawler */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* CSV Import */}
        <div className="bg-cobalt-900/60 border border-cobalt-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded bg-cobalt-800 border border-cobalt-700 flex items-center justify-center text-cobalt-400">
              <FileSpreadsheet className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-200">Import Prospect Dataset via CSV</div>
              <div className="text-[11px] text-slate-400">Includes duplicate detection and line-level source attribution</div>
            </div>
          </div>
          <form onSubmit={handleCsvUpload} className="flex items-center space-x-2">
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setCsvFile(e.target.files ? e.target.files[0] : null)}
              className="text-xs text-slate-300 file:mr-2 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-xs file:font-medium file:bg-cobalt-800 file:text-cobalt-300 hover:file:bg-cobalt-700 cursor-pointer"
            />
            <button
              type="submit"
              disabled={!csvFile || uploadingCsv}
              className="px-3 py-1 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-medium whitespace-nowrap"
            >
              {uploadingCsv ? 'Processing...' : 'Upload CSV'}
            </button>
          </form>
          {csvSummary && (
            <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-[11px] text-emerald-300 flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Imported {csvSummary.length || 'batch'} companies with line-level source tracking!</span>
            </div>
          )}
        </div>

        {/* Live SSRF-Protected Website Scanner */}
        <div className="bg-cobalt-900/60 border border-cobalt-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded bg-cobalt-800 border border-cobalt-700 flex items-center justify-center text-cobalt-400">
              <Globe2 className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-200">SSRF-Protected Official Website Crawler</div>
              <div className="text-[11px] text-slate-400">Extracts public business contacts and workstation evidence directly</div>
            </div>
          </div>
          <form onSubmit={handleCrawlWebsite} className="flex items-center space-x-2">
            <input
              type="url"
              placeholder="https://company-domain.in"
              value={crawlUrl}
              onChange={(e) => setCrawlUrl(e.target.value)}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
              required
            />
            <button
              type="submit"
              disabled={crawling}
              className="px-3 py-1 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-medium whitespace-nowrap"
            >
              {crawling ? 'Scanning...' : 'Scan URL'}
            </button>
          </form>
          {crawlResult && (
            <div className="p-2.5 bg-cobalt-950/80 border border-cobalt-700 rounded text-xs space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200 truncate max-w-[220px]">
                  {crawlResult.title || crawlResult.website}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    handleImportLead({
                      name: crawlResult.title || new URL(crawlResult.website).hostname,
                      website: crawlResult.website,
                      city: cityInput || 'Siliguri',
                      industry: 'Technology Services',
                      description: crawlResult.description || 'Discovered via official website scan',
                      public_email: crawlResult.emails?.[0],
                      public_phone: crawlResult.phones?.[0],
                      laptop_count_verified: null,
                      laptop_count_evidence: crawlResult.evidence_snippets?.join('; ') || 'Pending manual verification',
                      source_url: crawlResult.source_url,
                      source_type: 'official_website_crawl',
                      is_demo: false,
                      verification_status: 'unverified',
                      confidence_level: 0.70
                    });
                  }}
                  className="px-2 py-0.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[11px] font-medium"
                >
                  Import Lead
                </button>
              </div>
              <div className="font-mono text-[10px] text-slate-400">
                Emails: {crawlResult.emails?.join(', ') || 'None found'} | Phones: {crawlResult.phones?.join(', ') || 'None found'}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
