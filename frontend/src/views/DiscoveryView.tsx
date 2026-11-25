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
  Download,
  X,
  Eye,
  ShieldCheck,
  BrainCircuit,
  FileText,
  UserCheck
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

interface PipelineStep {
  step_number: number;
  step_name: string;
  status: string;
  detail: string;
  timestamp: string;
}

export const DiscoveryView: React.FC<DiscoveryViewProps> = ({ onCompanyImported }) => {
  const savedPrefs = (() => {
    try {
      const parsed = JSON.parse(localStorage.getItem('acttrident_discovery_prefs') || '{}');
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    } catch {
      return {};
    }
  })();

  // Scope & Location States
  const initialScope = ['country', 'state', 'city'].includes(savedPrefs.scope) ? savedPrefs.scope : 'city';
  const [scope, setScope] = useState<'country' | 'state' | 'city'>(initialScope);
  const [selectedState, setSelectedState] = useState<string>(savedPrefs.selectedState ?? 'West Bengal');
  const [cityInput, setCityInput] = useState<string>(savedPrefs.cityInput ?? 'Siliguri');
  const [citySuggestions, setCitySuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState<boolean>(false);
  const [statesList, setStatesList] = useState<Array<{ name: string; code: string; region: string }>>([]);
  const [presets, setPresets] = useState<LocationPreset[]>([]);
  const [activePreset, setActivePreset] = useState<string>('target_east_northeast');

  // Search & Filter Parameters
  const [industry, setIndustry] = useState<string>(savedPrefs.industry ?? 'Software Development');
  const [customIndustry, setCustomIndustry] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>(savedPrefs.searchQuery ?? '');
  const [companySize, setCompanySize] = useState<string>('all');
  const [minDevices, setMinDevices] = useState<number | undefined>(undefined);
  const [minScore, setMinScore] = useState<number>(40);
  const [maxLeads, setMaxLeads] = useState<number>(10);
  const [includeDemo, setIncludeDemo] = useState<boolean>(false);
  const [campaignOptions, setCampaignOptions] = useState<Array<{ id: number; name: string; status: string }>>([]);
  const [targetCampaignId, setTargetCampaignId] = useState<number | ''>(() => {
    try {
      const v = localStorage.getItem('acttrident_discovery_campaign_id');
      return v ? Number(v) : '';
    } catch {
      return '';
    }
  });
  const [contactFilter, setContactFilter] = useState<'all' | 'has_email' | 'has_phone'>('all');
  const [sortBy, setSortBy] = useState<string>(savedPrefs.sortBy || 'confidence');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [importStats, setImportStats] = useState<{ found: number; saved: number; skipped: number; failed: number } | null>(null);

  // Lead Quality KPI Metrics State
  const [kpiMetrics, setKpiMetrics] = useState<{
    commercialRelevant: number;
    verifiedWebsites: number;
    verifiedEmails: number;
    verifiedPhones: number;
    highPriority: number;
    mediumPriority: number;
    lowPriority: number;
  }>({
    commercialRelevant: 0,
    verifiedWebsites: 0,
    verifiedEmails: 0,
    verifiedPhones: 0,
    highPriority: 0,
    mediumPriority: 0,
    lowPriority: 0,
  });

  // Pipeline Execution States
  const [runningPipeline, setRunningPipeline] = useState<boolean>(false);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [pipelineSummary, setPipelineSummary] = useState<any>(null);

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

  // Detail Modal State (Dossier & Evidence)
  const [selectedLead, setSelectedLead] = useState<any | null>(null);
  const [reQualifying, setReQualifying] = useState<boolean>(false);
  const [reSearching, setReSearching] = useState<boolean>(false);

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
    api.getCampaigns()
      .then((list: any[]) => {
        const open = list.filter((c) => !['stopped', 'completed', 'failed'].includes(c.status));
        setCampaignOptions(open.map((c) => ({ id: c.id, name: c.name, status: c.status })));
        setTargetCampaignId((prev) => (prev && open.some((c) => c.id === prev) ? prev : ''));
      })
      .catch(() => {});
    executeSearch({ initial: true });
  }, []);

  useEffect(() => {
    try {
      if (targetCampaignId) localStorage.setItem('acttrident_discovery_campaign_id', String(targetCampaignId));
      else localStorage.removeItem('acttrident_discovery_campaign_id');
    } catch {
      /* storage unavailable */
    }
  }, [targetCampaignId]);

  const targetCampaignName = campaignOptions.find((c) => c.id === targetCampaignId)?.name;

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

  // Persist discovery search preferences across page refreshes
  useEffect(() => {
    try {
      localStorage.setItem(
        'acttrident_discovery_prefs',
        JSON.stringify({ scope, selectedState, cityInput, industry, searchQuery, sortBy })
      );
    } catch {
      // ignore storage errors
    }
  }, [scope, selectedState, cityInput, industry, searchQuery, sortBy]);

  // Main search execution function
  const executeSearch = useCallback(async (opts: { newPage?: number; initial?: boolean; newSort?: string; overrideScope?: 'country' | 'state' | 'city'; overrideCity?: string } = {}) => {
    if (searchAbortRef.current) {
      searchAbortRef.current.abort();
    }
    searchAbortRef.current = new AbortController();

    const targetPage = opts.newPage !== undefined ? opts.newPage : (opts.initial ? 1 : page);
    const activeScope = opts.overrideScope || scope;
    const activeCityRaw = opts.overrideCity !== undefined ? opts.overrideCity : cityInput;
    const activeSort = opts.newSort || sortBy;
    setSearching(true);
    setSearchError(null);
    setImportSuccess(null);

    const effectiveIndustry = industry === 'custom'
      ? customIndustry.trim()
      : (industry === 'All' ? undefined : industry);

    let effectiveCity = activeCityRaw.trim();
    if (activeScope === 'country') {
      effectiveCity = 'All';
    } else if (activeScope === 'state' && !effectiveCity) {
      effectiveCity = '';
    }

    const payload = {
      city: effectiveCity || undefined,
      state: selectedState || undefined,
      scope: activeScope,
      industry: effectiveIndustry || undefined,
      query: searchQuery.trim() || undefined,
      company_size: companySize === 'all' ? undefined : companySize,
      min_devices: minDevices,
      include_demo: includeDemo,
      page: targetPage,
      page_size: pageSize,
      sort_by: activeSort,
      sort_order: sortOrder,
    };

    try {
      const data = await api.searchDiscoveryPaginated(payload, searchAbortRef.current.signal);
      const items = data.items || [];
      setResults(items);
      setTotalResults(data.total || 0);
      setKpiMetrics({
        commercialRelevant: data.commercial_relevant ?? items.filter((x: any) => !x.is_demo && x.verification_status !== 'demo_fixture').length,
        verifiedWebsites: data.verified_websites ?? items.filter((x: any) => x.website_status === 'accessible').length,
        verifiedEmails: data.verified_emails ?? items.filter((x: any) => x.public_email).length,
        verifiedPhones: data.verified_phones ?? items.filter((x: any) => x.public_phone).length,
        highPriority: data.high_priority_count ?? items.filter((x: any) => (x.qualification_score || 0) >= 70).length,
        mediumPriority: data.medium_priority_count ?? items.filter((x: any) => (x.qualification_score || 0) >= 50 && (x.qualification_score || 0) < 70).length,
        lowPriority: data.low_priority_count ?? items.filter((x: any) => (x.qualification_score || 0) < 50).length,
      });
      setPage(data.page || 1);
      setTotalPages(data.total_pages || 1);
      setCoverageNote(data.coverage_note || '');
      setActiveStrategy(data.search_strategy || '');
      setActiveProviders(data.active_providers || []);
      setFailedProviders(data.failed_providers || []);

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
    companySize,
    minDevices,
    includeDemo,
    pageSize,
    sortBy,
    sortOrder,
    page,
    searchHistory
  ]);

  // Comprehensive 10-Step Pipeline Execution
  const handleRunFullPipeline = async () => {
    setRunningPipeline(true);
    setSearchError(null);
    setImportSuccess(null);
    setPipelineSteps([]);
    setPipelineSummary(null);

    const effectiveIndustry = industry === 'custom'
      ? customIndustry.trim()
      : (industry === 'All' ? 'Software & IT Services' : industry);

    try {
      const res = await api.runDiscoveryPipeline({
        city: scope === 'country' ? 'All' : (cityInput.trim() || 'Siliguri'),
        state: selectedState || undefined,
        country: 'India',
        scope,
        industry: effectiveIndustry,
        query: searchQuery.trim() || undefined,
        company_size: companySize === 'all' ? undefined : companySize,
        max_leads: maxLeads,
        min_score: minScore,
        include_demo: includeDemo,
        auto_verify: true,
        auto_research: true,
        auto_qualify: true,
        auto_save_crm: true,
        campaign_id: targetCampaignId || undefined,
      });

      setPipelineSteps(res.steps || []);
      setPipelineSummary(res);
      if (res.items && res.items.length > 0) {
        setResults(res.items);
        setTotalResults(res.items.length);
        setKpiMetrics({
          commercialRelevant: res.commercial_relevant ?? res.items.filter((x: any) => !x.is_demo).length,
          verifiedWebsites: res.verified_websites ?? res.websites_verified,
          verifiedEmails: res.verified_emails ?? res.public_emails_found,
          verifiedPhones: res.verified_phones ?? res.items.filter((x: any) => x.public_phone).length,
          highPriority: res.high_priority_count ?? res.items.filter((x: any) => (x.qualification_score || 0) >= 70).length,
          mediumPriority: res.medium_priority_count ?? res.items.filter((x: any) => (x.qualification_score || 0) >= 50 && (x.qualification_score || 0) < 70).length,
          lowPriority: res.low_priority_count ?? res.items.filter((x: any) => (x.qualification_score || 0) < 50).length,
        });
        setImportSuccess(`Pipeline completed! Discovered ${res.total_discovered} real entities, verified ${res.websites_verified} websites, found ${res.public_emails_found} public business emails, and saved ${res.saved_to_crm} qualified leads into CRM.${targetCampaignName ? ` Saved leads are tagged for campaign "${targetCampaignName}".` : ''}`);
        if (onCompanyImported) onCompanyImported();
      } else {
        setSearchError('Pipeline executed across active providers but zero entities matched your search parameters. No mock data was substituted.');
      }
    } catch (err: any) {
      console.error('Pipeline error:', err);
      setSearchError(`Pipeline execution failed: ${err.message}`);
    } finally {
      setRunningPipeline(false);
    }
  };

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
      setPage(1);
      executeSearch({ newPage: 1, overrideScope: 'country', overrideCity: 'All' });
    } else {
      setScope('city');
      setCityInput(preset.cities[0]);
      setPage(1);
      executeSearch({ newPage: 1, overrideScope: 'city', overrideCity: preset.cities[0] });
    }
  };

  const handleImportLead = async (item: any) => {
    setImportingId(item.name);
    setSearchError(null);
    try {
      const saved = await api.importDiscoveredLead(item, targetCampaignId || undefined);
      setResults((prev) =>
        prev.map((r) =>
          r.name === item.name ? { ...r, crm_status: 'previously_known', crm_id: saved.id } : r
        )
      );
      setImportStats({ found: results.length, saved: 1, skipped: 0, failed: 0 });
      setImportSuccess(`Saved "${item.name}" to CRM (ID #${saved.id}) with source attribution and qualification.`);
      if (onCompanyImported) onCompanyImported();
    } catch (err: any) {
      const msg = err?.message || 'Import failed.';
      if (msg.toLowerCase().includes('already exists')) {
        setResults((prev) =>
          prev.map((r) => (r.name === item.name ? { ...r, crm_status: 'previously_known' } : r))
        );
        setImportStats({ found: results.length, saved: 0, skipped: 1, failed: 0 });
        setImportSuccess(`Skipped duplicate: "${item.name}" is already in CRM.`);
      } else {
        setImportStats({ found: results.length, saved: 0, skipped: 0, failed: 1 });
        setSearchError(`Import error for "${item.name}": ${msg}`);
      }
    } finally {
      setImportingId(null);
    }
  };

  const handleBatchImport = async () => {
    if (!results.length) return;
    setSearchError(null);
    try {
      const summary = await api.batchImportDiscoveredLeadsSummary(results, targetCampaignId || undefined);
      const savedByName = new Map<string, number>();
      (summary.saved_companies || []).forEach((c: any) => savedByName.set((c.name || '').toLowerCase(), c.id));
      const skippedSet = new Set((summary.skipped_names || []).map((n: string) => n.toLowerCase()));

      setResults((prev) =>
        prev.map((r) => {
          const low = (r.name || '').toLowerCase();
          if (savedByName.has(low)) {
            return { ...r, crm_status: 'previously_known', crm_id: savedByName.get(low) };
          }
          if (skippedSet.has(low)) {
            return { ...r, crm_status: 'previously_known' };
          }
          return r;
        })
      );
      setImportStats({
        found: summary.total_submitted,
        saved: summary.saved_count,
        skipped: summary.duplicates_skipped,
        failed: summary.failed_count,
      });
      setImportSuccess(
        `Import summary — Found: ${summary.total_submitted}, Saved: ${summary.saved_count}, Duplicates skipped: ${summary.duplicates_skipped}, Failed: ${summary.failed_count}.`
      );
      if (summary.saved_count > 0 && onCompanyImported) onCompanyImported();
    } catch (e: any) {
      setSearchError(`Batch import failed: ${e.message}`);
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

  const [exportingCsv, setExportingCsv] = useState(false);
  const handleExportCsv = async () => {
    try {
      setExportingCsv(true);
      const queryParams = {
        city: scope === 'country' ? 'All' : cityInput.trim(),
        state: selectedState || undefined,
        scope: scope,
        industry: (industry === 'All' ? undefined : (industry === 'custom' ? customIndustry : industry)) || undefined,
        query: searchQuery.trim() || undefined,
        min_devices: minDevices || undefined,
        include_demo: includeDemo,
      };
      const blob = await api.exportDiscoveryCsv(queryParams);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `discovered_prospects_${scope === 'country' ? 'nationwide' : cityInput || 'export'}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setExportingCsv(false);
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

  // Re-run AI research on selected lead
  const handleReRunResearch = async (lead: any) => {
    if (!lead.crm_id) return;
    setReSearching(true);
    try {
      const rep = await api.generateResearchReport(lead.crm_id);
      setSelectedLead((prev: any) => ({
        ...prev,
        research_dossier: {
          ...prev.research_dossier,
          company_overview: rep.summary,
          main_services: rep.services,
          potential_acttrident_use_cases: rep.potential_acttrident_use_cases,
          missing_information: rep.missing_information,
        },
        research_summary: rep.summary,
      }));
    } catch (err: any) {
      alert(`Re-run research error: ${err.message}`);
    } finally {
      setReSearching(false);
    }
  };

  // Re-run qualification on selected lead
  const handleReRunQualification = async (lead: any) => {
    if (!lead.crm_id) return;
    setReQualifying(true);
    try {
      const q = await api.qualifyCompany(lead.crm_id);
      setSelectedLead((prev: any) => ({
        ...prev,
        qualification_score: q.score,
        qualification_category: q.status,
        qualification_reason: q.reason,
        qualification_factors: q.factors,
      }));
    } catch (err: any) {
      alert(`Re-run qualification error: ${err.message}`);
    } finally {
      setReQualifying(false);
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
            <span>Autonomous B2B Lead Discovery & Qualification</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time public business discovery across India with 7-factor deterministic qualification and field provenance.
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
              <span>{src.label}: {src.configured ? 'Active' : 'Standby / Key required'}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Location Presets & Quick Corridors */}
      <div className="bg-cobalt-900/60 border border-cobalt-800 rounded-lg p-3">
        <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
          <MapPin className="w-3.5 h-3.5 text-cobalt-400" />
          <span>Regional Focus Presets</span>
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
              <option value="Software Development">Software Development & Engineering</option>
              <option value="IT Services & Cloud Hosting">IT Services & Cloud Hosting</option>
              <option value="BPO & Customer Support">BPO & Technical Support</option>
              <option value="Digital Marketing & Web Design">Digital Agencies & Web Tech</option>
              <option value="All">All Tech Categories</option>
              {industriesList.map((ind) => (
                <option key={ind.id} value={ind.name}>
                  {ind.name}
                </option>
              ))}
              <option value="custom">-- Custom Keyword --</option>
            </select>
          </div>
        </div>

        {/* Target campaign: leads saved by this discovery are tagged for the chosen campaign */}
        <div className="flex flex-col md:flex-row md:items-center gap-2 rounded border border-cobalt-800 bg-cobalt-950/60 px-3 py-2">
          <label htmlFor="discovery-target-campaign" className="text-[11px] font-medium text-slate-300 shrink-0">
            Discover leads for campaign
          </label>
          <select
            id="discovery-target-campaign"
            value={targetCampaignId}
            onChange={(e) => setTargetCampaignId(e.target.value ? Number(e.target.value) : '')}
            className="flex-1 md:max-w-sm bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
          >
            <option value="">No campaign (save to CRM only)</option>
            {campaignOptions.map((c) => (
              <option key={c.id} value={c.id}>{c.name} ({c.status})</option>
            ))}
          </select>
          <span className="text-[10px] text-slate-400">
            {targetCampaignId
              ? 'Leads saved or imported now will appear in the "Add Leads" list of this campaign.'
              : 'Pick a campaign so its "Add Leads" list shows only these discoveries.'}
          </span>
        </div>

        {/* Row 2: Custom Keywords, Company Size, Max Leads, Min Score, Trigger Actions */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          {industry === 'custom' ? (
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Custom Business Category</label>
              <input
                type="text"
                placeholder="e.g. Telecom BPO, FinTech, Pathology"
                value={customIndustry}
                onChange={(e) => setCustomIndustry(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
              />
            </div>
          ) : (
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Search Keyword (Optional)</label>
              <input
                type="text"
                placeholder="e.g. infotech, software, cloud"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 placeholder:text-slate-500"
              />
            </div>
          )}

          {/* Company Size Selector */}
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Company Size</label>
            <select
              value={companySize}
              onChange={(e) => setCompanySize(e.target.value)}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
            >
              <option value="all">All Sizes</option>
              <option value="1-10">Micro (1-10)</option>
              <option value="11-50">Small (11-50)</option>
              <option value="51-200">Medium (51-200)</option>
              <option value="200+">Enterprise (200+)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Max Prospects</label>
            <select
              value={maxLeads}
              onChange={(e) => setMaxLeads(Number(e.target.value))}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
            >
              <option value="5">5 Leads (Quick Check)</option>
              <option value="10">10 Leads (Standard)</option>
              <option value="20">20 Leads (Extended)</option>
              <option value="50">50 Leads (Deep Search)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Min Qualification Score</label>
            <select
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
            >
              <option value="0">All Leads (0+)</option>
              <option value="40">40+ (Low Potential & Above)</option>
              <option value="60">60+ (Medium Potential & Above)</option>
              <option value="80">80+ (High Potential Only)</option>
            </select>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={handleRunFullPipeline}
              disabled={runningPipeline || searching}
              className="flex-1 py-2 bg-gradient-to-r from-cobalt-600 to-indigo-600 hover:from-cobalt-500 hover:to-indigo-500 disabled:opacity-50 text-white rounded text-xs font-semibold transition-all flex items-center justify-center space-x-1.5 shadow-md border border-cobalt-400/30"
              title="Runs the end-to-end 10-step discovery, website verification, AI research, qualification, and CRM storage"
            >
              {runningPipeline ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Executing Pipeline...</span>
                </>
              ) : (
                <>
                  <BrainCircuit className="w-3.5 h-3.5 text-cobalt-200" />
                  <span>Start Autonomous Pipeline</span>
                </>
              )}
            </button>
            <button
              type="submit"
              disabled={searching || runningPipeline}
              className="py-2 px-3 bg-cobalt-800 hover:bg-cobalt-700 disabled:opacity-50 text-slate-200 rounded text-xs font-medium transition-colors flex items-center justify-center border border-cobalt-700"
              title="Search Directory Only"
            >
              <Search className="w-3.5 h-3.5" />
            </button>
          </div>
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

      {/* 10-Step Pipeline Progress Tracker Drawer (When Pipeline Executes or Finished) */}
      {(runningPipeline || pipelineSteps.length > 0) && (
        <div className="bg-cobalt-950 border border-cobalt-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <BrainCircuit className="w-4 h-4 text-cobalt-400" />
              <span className="text-xs font-semibold text-slate-200">
                Autonomous Lead Discovery Workflow (10 Steps)
              </span>
              {runningPipeline && <span className="text-[10px] text-amber-400 animate-pulse font-mono font-medium">In Progress...</span>}
            </div>
            {pipelineSummary && (
              <span className="text-[11px] text-slate-400 font-mono">
                Duration: {pipelineSummary.duration_seconds}s | Saved: {pipelineSummary.saved_to_crm} leads
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-2">
            {[
              "1. Connecting Sources",
              "2. Searching Businesses",
              "3. Normalizing Results",
              "4. Removing Duplicates",
              "5. Verifying Websites",
              "6. Collecting Contacts",
              "7. Researching (Ollama)",
              "8. Evaluating 7-Factors",
              "9. Saving into CRM",
              "10. Completing Search"
            ].map((stepName, idx) => {
              const stepNumber = idx + 1;
              const matchingStep = pipelineSteps.find(s => s.step_number === stepNumber);
              const isDone = Boolean(matchingStep && matchingStep.status === 'completed');
              const isCurrent = runningPipeline && !isDone && (pipelineSteps.length + 1 === stepNumber);

              return (
                <div
                  key={idx}
                  className={`p-2 rounded border text-[11px] flex items-center space-x-2 ${
                    isDone
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                      : isCurrent
                      ? 'bg-cobalt-800/80 border-cobalt-600 text-cobalt-200 animate-pulse'
                      : 'bg-cobalt-900/40 border-cobalt-800/60 text-slate-400'
                  }`}
                >
                  {isDone ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  ) : (
                    <span className="w-3.5 h-3.5 rounded-full border border-slate-600 flex items-center justify-center text-[9px] shrink-0 font-mono">
                      {stepNumber}
                    </span>
                  )}
                  <span className="truncate font-medium">{stepName}</span>
                </div>
              );
            })}
          </div>

          {pipelineSteps.length > 0 && (
            <div className="pt-2 border-t border-cobalt-800/60 text-[11px] text-slate-400 space-y-1 max-h-24 overflow-y-auto">
              {pipelineSteps.map((s, i) => (
                <div key={i} className="flex items-center space-x-2">
                  <span className="text-emerald-400 font-mono">[{s.step_number}/10]</span>
                  <span className="text-slate-300">{s.detail}</span>
                </div>
              ))}
            </div>
          )}
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
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-300 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{importSuccess}</span>
          </div>
          <div className="flex items-center space-x-2">
            {importStats && (
              <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-mono">
                <span className="px-1.5 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 text-slate-200">Found: {importStats.found}</span>
                <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/30 text-emerald-300">Saved: {importStats.saved}</span>
                <span className="px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/30 text-amber-300">Skipped: {importStats.skipped}</span>
                {importStats.failed > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-rose-500/20 border border-rose-500/30 text-rose-300">Failed: {importStats.failed}</span>
                )}
              </div>
            )}
            <button onClick={() => setImportSuccess(null)} className="text-slate-400 hover:text-slate-200">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Real Lead Quality KPI Summary Metrics Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-2.5">
          <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Discovered</div>
          <div className="text-lg font-bold text-slate-100 mt-0.5">{totalResults}</div>
          <div className="text-[10px] text-cobalt-400 font-mono mt-0.5">Commercial: {kpiMetrics.commercialRelevant}</div>
        </div>
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-2.5">
          <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Verified Websites</div>
          <div className="text-lg font-bold text-emerald-400 mt-0.5">{kpiMetrics.verifiedWebsites}</div>
          <div className="text-[10px] text-emerald-400/80 font-mono mt-0.5">Active & Reachable</div>
        </div>
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-2.5">
          <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Public Emails Found</div>
          <div className="text-lg font-bold text-emerald-400 mt-0.5">{kpiMetrics.verifiedEmails}</div>
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">Non-demo, Source-attributed</div>
        </div>
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-2.5">
          <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Phones Found</div>
          <div className="text-lg font-bold text-emerald-400 mt-0.5">{kpiMetrics.verifiedPhones}</div>
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">Direct & WhatsApp</div>
        </div>
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-2.5">
          <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Priority Leads</div>
          <div className="text-lg font-bold text-indigo-300 mt-0.5">{kpiMetrics.highPriority} <span className="text-xs font-normal text-slate-400">/ {kpiMetrics.mediumPriority}</span></div>
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">Low: {kpiMetrics.lowPriority}</div>
        </div>
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-2.5">
          <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Data Providers</div>
          <div className="text-xs font-bold text-slate-200 mt-1 truncate">
            {activeProviders.length > 0 ? activeProviders.map(p => p.replace('_search', '').replace('_nominatim', '')).join(', ') : 'OSM Nominatim'}
          </div>
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">Deduplicated & Merged</div>
        </div>
      </div>

      {/* Results Header, Sorting & Filter Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-cobalt-900/80 border border-cobalt-800 rounded-t-lg p-3">
        <div className="text-xs font-semibold text-slate-200 flex items-center space-x-2">
          <span>Discovered Entities</span>
          <span className="px-2 py-0.5 rounded-full bg-cobalt-800 text-cobalt-300 font-mono text-[11px]">
            {totalResults} {totalResults === 1 ? 'record' : 'records'}
          </span>
          {(searching || runningPipeline) && <span className="text-[11px] text-cobalt-400 animate-pulse font-normal">Processing...</span>}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Contact filter */}
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
            aria-label="Sort discovered companies"
            value={sortBy}
            onChange={(e) => {
              const nextSort = e.target.value;
              setSortBy(nextSort);
              executeSearch({ newPage: 1, newSort: nextSort });
            }}
            className="bg-cobalt-950 border border-cobalt-800 rounded px-2 py-1 text-[11px] text-slate-300"
          >
            <option value="confidence">Sort by Confidence</option>
            <option value="name">Sort by Company Name</option>
            <option value="city">Sort by City</option>
            <option value="devices">Sort by Laptops</option>
            <option value="retrieval">Sort by Recent</option>
          </select>

          {/* Export CSV Button */}
          {results.length > 0 && (
            <button
              type="button"
              onClick={handleExportCsv}
              disabled={exportingCsv}
              className="px-2.5 py-1 bg-cobalt-800 hover:bg-cobalt-700 text-cobalt-200 border border-cobalt-700 rounded text-xs font-medium transition-colors flex items-center space-x-1 disabled:opacity-50"
              title="Download results as CSV with verified/unverified distinctions"
            >
              <Download className="w-3.5 h-3.5 text-cobalt-400" />
              <span>{exportingCsv ? 'Exporting...' : 'Export CSV'}</span>
            </button>
          )}

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

      {/* Discovered Results Table */}
      <div className="bg-cobalt-900/80 border-x border-b border-cobalt-800 rounded-b-lg overflow-hidden">
        {searching && results.length === 0 ? (
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
          <div className="p-12 text-center text-xs text-slate-400 space-y-2">
            <Building2 className="w-8 h-8 mx-auto text-cobalt-600 mb-2 opacity-60" />
            <p className="font-semibold text-slate-300">No matching business records found.</p>
            <p className="text-[11px] mt-1 text-slate-500">
              Run the Autonomous Pipeline or adjust the location and industry filters above.
            </p>
            <button
              type="button"
              onClick={() => executeSearch({ newPage: 1 })}
              className="mt-2 px-3 py-1.5 bg-cobalt-700 hover:bg-cobalt-600 text-white rounded text-[11px] font-medium inline-flex items-center space-x-1.5"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Retry Search</span>
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cobalt-950/60 text-slate-400 border-b border-cobalt-800/80 font-medium">
                <tr>
                  <th className="py-2.5 px-3">Company & Website</th>
                  <th className="py-2.5 px-3">Location & Industry</th>
                  <th className="py-2.5 px-3">Business Contact</th>
                  <th className="py-2.5 px-3">Qualification Score</th>
                  <th className="py-2.5 px-3">Fleet Verification</th>
                  <th className="py-2.5 px-3">CRM Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cobalt-800/40 text-slate-200">
                {filteredResults.map((comp, idx) => {
                  const isDemoItem = comp.is_demo || comp.verification_status === 'demo_fixture';
                  const score = comp.qualification_score;
                  const cat = comp.qualification_category || (score !== undefined ? (score >= 80 ? 'High priority' : score >= 60 ? 'Medium priority' : 'Low priority') : 'Pending');

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
                        {comp.website ? (
                          <div className="flex items-center space-x-1.5 mt-0.5">
                            <a
                              href={comp.website}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[11px] text-cobalt-400 hover:underline flex items-center space-x-1"
                            >
                              <span className="truncate max-w-[160px]">{comp.website}</span>
                              <ExternalLink className="w-3 h-3 shrink-0" />
                            </a>
                            <span className={`px-1.5 py-0.2 rounded text-[9px] font-mono border ${
                              comp.website_classification === 'authentic' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' :
                              comp.website_classification === 'likely_authentic' ? 'bg-blue-500/20 text-blue-300 border-blue-500/30' :
                              comp.website_classification === 'suspicious' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                              comp.website_classification === 'parked' || comp.website_classification === 'unrelated' ? 'bg-rose-500/20 text-rose-300 border-rose-500/30' :
                              comp.website_status === 'accessible' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' : 'bg-slate-800 text-slate-400 border-slate-700'
                            }`}>
                              {comp.website_classification || comp.website_status || 'unverified'}
                            </span>
                          </div>
                        ) : (
                          <span className="text-[11px] text-slate-500 italic block mt-0.5">Website not published</span>
                        )}
                        {comp.matched_service_name && (
                          <div className="text-[9px] font-mono text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 rounded px-1.5 py-0.5 inline-block mt-1">
                            🎯 {comp.matched_service_name}
                          </div>
                        )}
                        {comp.contact_page_url && (
                          <div className="flex items-center space-x-1 mt-0.5">
                            <a
                              href={comp.contact_page_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[10px] text-cyan-400 hover:underline flex items-center space-x-0.5 font-mono"
                            >
                              <span>Contact Page</span>
                              <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                            </a>
                          </div>
                        )}
                        {comp.business_address && (
                          <div className="text-[10px] text-slate-400 line-clamp-1 mt-0.5" title={comp.business_address}>
                            📍 {comp.business_address}
                          </div>
                        )}
                        {comp.source_url && (
                          <div className="text-[10px] text-slate-500 mt-0.5 flex items-center space-x-1">
                            <span>Src:</span>
                            <a
                              href={comp.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-cobalt-400 hover:underline truncate max-w-[140px]"
                            >
                              {comp.source_type || 'discovery'}
                            </a>
                          </div>
                        )}
                        {comp.missing_information && comp.missing_information.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {comp.missing_information.map((m: string, i: number) => (
                              <span key={i} className="px-1.5 py-0.2 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[9px] font-mono">
                                Missing: {m.replace(/_/g, ' ')}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>

                      <td className="py-3 px-3">
                        <div className="font-medium text-slate-200">
                          {comp.city}{comp.state ? `, ${comp.state}` : ''}
                        </div>
                        <div className="text-[11px] text-slate-400">{comp.industry || 'Technology Services'}</div>
                      </td>

                      <td className="py-3 px-3 space-y-0.5 font-mono text-[11px]">
                        {comp.public_email ? (
                          <div className="text-slate-200 flex items-center space-x-1.5 flex-wrap">
                            <span>✉ {comp.public_email}</span>
                            <span 
                              className={`px-1 rounded text-[9px] font-mono border ${
                                comp.email_verification_status === 'independently_verified' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' :
                                comp.email_verification_status === 'source_confirmed' ? 'bg-teal-500/20 text-teal-300 border-teal-500/30' :
                                (comp.email_verification_status === 'domain_mx_confirmed' || comp.email_verification_status === 'domain_checked') ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' :
                                comp.email_verification_status === 'syntax_valid' ? 'bg-blue-500/20 text-blue-300 border-blue-500/30' :
                                'bg-slate-800 text-slate-400 border-slate-700'
                              }`}
                              title={
                                comp.email_verification_status === 'domain_mx_confirmed' ? 'DNS MX records active. Does not guarantee inbox existence or deliverability.' :
                                comp.email_verification_status === 'syntax_valid' ? 'RFC 5322 syntax valid. Inbox existence not verified.' :
                                comp.email_verification_status
                              }
                            >
                              {comp.email_verification_status || 'publicly_listed'}
                            </span>
                          </div>
                        ) : (
                          <div className="text-slate-500 italic">Email not found</div>
                        )}
                        {comp.public_phone && (
                          <div className="text-slate-400 flex items-center space-x-1.5 flex-wrap">
                            <span>☎ {comp.public_phone}</span>
                            {comp.phone_verification_status && (
                              <span 
                                className="px-1 rounded text-[9px] font-mono border bg-slate-800 text-slate-400 border-slate-700"
                                title={comp.phone_verification_status === 'format_valid' ? 'E.164 phone format valid. Active line status not verified.' : comp.phone_verification_status}
                              >
                                {comp.phone_verification_status}
                              </span>
                            )}
                          </div>
                        )}
                        {comp.public_whatsapp && <div className="text-emerald-400">📱 WA: {comp.public_whatsapp}</div>}
                        {comp.decision_maker_name && (
                          <div className="text-slate-300 font-sans text-[10px] mt-0.5">
                            👤 {comp.decision_maker_name} <span className="text-slate-400">({comp.decision_maker_role || 'Executive'})</span>
                          </div>
                        )}
                      </td>

                      <td className="py-3 px-3">
                        {score !== undefined && score !== null ? (
                          <div className="space-y-0.5">
                            <div className="flex items-center space-x-1.5">
                              <span className={`font-mono font-bold text-xs ${
                                score >= 80 ? 'text-emerald-400' : score >= 60 ? 'text-cobalt-400' : 'text-amber-400'
                              }`}>
                                {score} / 100
                              </span>
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                cat === 'High priority' ? 'bg-emerald-500/20 text-emerald-300' : cat === 'Medium priority' ? 'bg-cobalt-500/20 text-cobalt-300' : cat === 'Needs manual verification' ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-800 text-slate-400'
                              }`}>
                                {cat}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-400 line-clamp-1 max-w-[160px]" title={comp.qualification_reason}>
                              {comp.qualification_reason}
                            </div>
                          </div>
                        ) : (
                          <span className="text-slate-500 italic">Pending evaluation</span>
                        )}
                      </td>

                      <td className="py-3 px-3">
                        <div className="space-y-0.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                            comp.laptop_fleet_status === 'VERIFIED' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' :
                            comp.laptop_fleet_status === 'CLAIMED' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
                            'bg-slate-800/80 text-slate-400 border border-slate-700'
                          }`}>
                            {comp.laptop_fleet_status || 'UNKNOWN'}
                          </span>
                          <div className="text-[10px] text-slate-400 truncate max-w-[140px]" title={comp.laptop_count_evidence}>
                            {comp.laptop_count_verified ? `${comp.laptop_count_verified} Laptops` : 'No evidence yet'}
                          </div>
                        </div>
                      </td>

                      <td className="py-3 px-3 text-[11px] font-mono">
                        <span className={`px-2 py-0.5 rounded text-[10px] ${
                          comp.crm_status === 'saved_in_crm' ? 'bg-emerald-500/20 text-emerald-300' :
                          comp.crm_status === 'previously_known' ? 'bg-cobalt-500/20 text-cobalt-300' :
                          'bg-slate-800 text-slate-400'
                        }`}>
                          {comp.crm_status === 'saved_in_crm' ? 'Saved in CRM' : comp.crm_status === 'previously_known' ? 'In CRM' : 'Discovered'}
                        </span>
                      </td>

                      <td className="py-3 px-3 text-right">
                        <div className="flex items-center justify-end space-x-1.5">
                          <button
                            type="button"
                            onClick={() => setSelectedLead(comp)}
                            className="px-2 py-1 bg-cobalt-800 hover:bg-cobalt-700 text-cobalt-200 border border-cobalt-700 rounded text-xs font-medium transition-colors flex items-center space-x-1"
                            title="View Research Dossier & Field Evidence"
                          >
                            <Eye className="w-3.5 h-3.5 text-cobalt-400" />
                            <span>Evidence</span>
                          </button>
                          {!comp.crm_id && (
                            <button
                              onClick={() => handleImportLead(comp)}
                              disabled={importingId === comp.name}
                              className="px-2 py-1 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1"
                            >
                              <Plus className="w-3 h-3" />
                              <span>{importingId === comp.name ? 'Saving...' : 'Add'}</span>
                            </button>
                          )}
                        </div>
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
              Showing page {page} of {totalPages} ({totalResults} total entities)
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

      {/* EVIDENCE & RESEARCH DOSSIER MODAL */}
      {selectedLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="bg-cobalt-900 border border-cobalt-700 rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden text-slate-200">
            {/* Modal Header */}
            <div className="p-4 border-b border-cobalt-800 flex items-center justify-between bg-cobalt-950/80">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <h2 className="text-base font-bold text-slate-100">{selectedLead.name}</h2>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${selectedLead.is_demo ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'bg-cobalt-800 text-cobalt-300'}`}>
                    {selectedLead.is_demo ? 'DEMO FIXTURE' : 'REAL B2B ENTITY'}
                  </span>
                </div>
                <div className="text-xs text-slate-400 flex items-center space-x-3">
                  <span>{selectedLead.city}, {selectedLead.state || 'India'}</span>
                  <span>•</span>
                  <span>{selectedLead.industry}</span>
                  {selectedLead.website && (
                    <>
                      <span>•</span>
                      <a href={selectedLead.website} target="_blank" rel="noreferrer" className="text-cobalt-400 hover:underline flex items-center space-x-1">
                        <span>{selectedLead.website}</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </>
                  )}
                </div>
              </div>
              <button
                onClick={() => setSelectedLead(null)}
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-cobalt-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 overflow-y-auto space-y-5 text-xs">
              {/* 7-Factor Qualification Card */}
              <div className="bg-cobalt-950 border border-cobalt-800 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 font-semibold text-slate-200">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span>7-Factor Qualification Evaluation</span>
                  </div>
                  {selectedLead.qualification_score !== undefined && (
                    <span className="font-mono font-bold text-emerald-400 text-sm">
                      Score: {selectedLead.qualification_score} / 100 ({selectedLead.qualification_category || 'Evaluated'})
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 italic">
                  {selectedLead.qualification_reason || 'Transparent evaluation based on verified industry, business scale, and contact availability.'}
                </p>

                {selectedLead.qualification_factors && selectedLead.qualification_factors.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t border-cobalt-800/60">
                    {selectedLead.qualification_factors.map((f: any, i: number) => (
                      <div key={i} className="flex items-start justify-between p-2 rounded bg-cobalt-900/60 border border-cobalt-800/40 text-[11px]">
                        <div className="space-y-0.5 max-w-md">
                          <div className="font-medium text-slate-200 flex items-center space-x-1.5">
                            <span className={f.passed ? 'text-emerald-400' : 'text-slate-500'}>
                              {f.passed ? '✓' : '✗'}
                            </span>
                            <span>{f.factor_name}</span>
                          </div>
                          <div className="text-[10px] text-slate-400">{f.evidence}</div>
                        </div>
                        <div className="text-right space-y-0.5">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold ${
                            f.verification_state === 'VERIFIED' ? 'bg-emerald-500/20 text-emerald-300' :
                            f.verification_state === 'CLAIMED' ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-800 text-slate-400'
                          }`}>
                            {f.verification_state}
                          </span>
                          <div className="font-mono text-[10px] text-cobalt-400 font-semibold">{f.score_weight} pts</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Research Dossier Card */}
              <div className="bg-cobalt-950 border border-cobalt-800 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 font-semibold text-slate-200">
                    <BrainCircuit className="w-4 h-4 text-cobalt-400" />
                    <span>AI Research Dossier (Local Ollama llama3.2)</span>
                  </div>
                  {selectedLead.crm_id && (
                    <button
                      onClick={() => handleReRunResearch(selectedLead)}
                      disabled={reSearching}
                      className="px-2 py-0.5 bg-cobalt-800 hover:bg-cobalt-700 text-cobalt-200 rounded text-[10px] flex items-center space-x-1 disabled:opacity-50"
                    >
                      <RefreshCw className={`w-3 h-3 ${reSearching ? 'animate-spin' : ''}`} />
                      <span>{reSearching ? 'Analyzing...' : 'Re-run AI'}</span>
                    </button>
                  )}
                </div>

                <div className="text-[11px] text-slate-300 space-y-2">
                  <div>
                    <span className="font-semibold text-slate-200">Overview: </span>
                    <span>{selectedLead.research_summary || selectedLead.description || 'Pending AI dossier analysis.'}</span>
                  </div>
                  {selectedLead.research_dossier && (
                    <>
                      {selectedLead.research_dossier.potential_acttrident_use_cases && (
                        <div>
                          <span className="font-semibold text-slate-200">Target Product Use Cases: </span>
                          <span className="text-cobalt-300">{selectedLead.research_dossier.potential_acttrident_use_cases}</span>
                        </div>
                      )}
                      {selectedLead.research_dossier.potential_security_challenges && (
                        <div>
                          <span className="font-semibold text-amber-300">Security Hypotheses (Not Verified Facts): </span>
                          <span className="text-slate-400">{selectedLead.research_dossier.potential_security_challenges}</span>
                        </div>
                      )}
                      {selectedLead.research_dossier.missing_information && (
                        <div className="p-2 bg-amber-500/10 border border-amber-500/20 rounded text-[11px] text-amber-300">
                          <span className="font-semibold">Missing Facts / Research Gaps: </span>
                          <span>{selectedLead.research_dossier.missing_information}</span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Field-Level Provenance & Evidence Sources Table */}
              <div className="bg-cobalt-950 border border-cobalt-800 rounded-lg p-3 space-y-2">
                <div className="font-semibold text-slate-200 flex items-center space-x-2">
                  <FileText className="w-4 h-4 text-cobalt-400" />
                  <span>Field-Level Evidence & Traceable Provenance</span>
                </div>

                {selectedLead.provenance_sources && selectedLead.provenance_sources.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[11px]">
                      <thead className="bg-cobalt-900/60 text-slate-400 border-b border-cobalt-800 font-mono">
                        <tr>
                          <th className="py-1.5 px-2">Field</th>
                          <th className="py-1.5 px-2">Verified Value</th>
                          <th className="py-1.5 px-2">Source URL</th>
                          <th className="py-1.5 px-2">Status</th>
                          <th className="py-1.5 px-2">Evidence Snippet</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-cobalt-800/40 text-slate-300">
                        {selectedLead.provenance_sources.map((src: any, sIdx: number) => (
                          <tr key={sIdx} className="hover:bg-cobalt-900/40">
                            <td className="py-1.5 px-2 font-mono font-medium text-slate-200">{src.field_name}</td>
                            <td className="py-1.5 px-2 font-mono text-emerald-300">{src.field_value || 'None'}</td>
                            <td className="py-1.5 px-2">
                              {src.source_url ? (
                                <a href={src.source_url} target="_blank" rel="noreferrer" className="text-cobalt-400 hover:underline truncate max-w-[140px] block">
                                  {src.source_url}
                                </a>
                              ) : 'N/A'}
                            </td>
                            <td className="py-1.5 px-2">
                              <span className={`px-1.5 py-0.2 rounded text-[9px] font-mono ${
                                src.verification_status === 'verified' ? 'bg-emerald-500/20 text-emerald-300' :
                                src.verification_status === 'publicly_listed' ? 'bg-cobalt-500/20 text-cobalt-300' :
                                'bg-slate-800 text-slate-400'
                              }`}>
                                {src.verification_status}
                              </span>
                            </td>
                            <td className="py-1.5 px-2 text-[10px] text-slate-400 line-clamp-1 max-w-[200px]" title={src.evidence_snippet}>
                              {src.evidence_snippet || 'Verified via crawler'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-[11px] text-slate-500 italic p-2">
                    Primary Source URL: {selectedLead.source_url} ({selectedLead.source_type})
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-3 border-t border-cobalt-800 bg-cobalt-950 flex items-center justify-between">
              <div className="text-[11px] text-slate-400">
                Truthfulness policy: device counts and contact channels are only awarded points when supported by evidence.
              </div>
              <button
                onClick={() => setSelectedLead(null)}
                className="px-4 py-1.5 bg-cobalt-800 hover:bg-cobalt-700 text-white rounded text-xs font-semibold"
              >
                Close Dossier
              </button>
            </div>
          </div>
        </div>
      )}

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
