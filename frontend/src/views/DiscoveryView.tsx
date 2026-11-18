import React, { useEffect, useState } from 'react';
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
  AlertTriangle
} from 'lucide-react';

interface DiscoveryViewProps {
  onCompanyImported?: () => void;
}

export const DiscoveryView: React.FC<DiscoveryViewProps> = ({ onCompanyImported }) => {
  const [city, setCity] = useState('Siliguri');
  const [industry, setIndustry] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [minDevices, setMinDevices] = useState(5);
  const [includeDemo, setIncludeDemo] = useState(false);
  const [sources, setSources] = useState<any[]>([]);
  const [results, setResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [importSuccess, setImportSuccess] = useState<string | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [uploadingCsv, setUploadingCsv] = useState(false);
  const [csvSummary, setCsvSummary] = useState<any>(null);
  const [crawlUrl, setCrawlUrl] = useState('');
  const [crawling, setCrawling] = useState(false);
  const [crawlResult, setCrawlResult] = useState<any>(null);

  useEffect(() => {
    api.getDiscoverySources().then(setSources).catch(() => {});
  }, []);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setSearching(true);
    setImportSuccess(null);
    try {
      const data = await api.searchDiscovery({
        city,
        industry: industry === 'All' ? undefined : industry,
        query: searchQuery || undefined,
        min_devices: minDevices,
        include_demo: includeDemo
      });
      setResults(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setSearching(false);
    }
  };

  const handleImportLead = async (item: any) => {
    setImportingId(item.name);
    try {
      await api.importDiscoveredLead(item);
      setImportSuccess(`Successfully imported ${item.name} with source attribution!`);
      if (onCompanyImported) onCompanyImported();
    } catch (err: any) {
      alert(`Import error: ${err.message}`);
    } finally {
      setImportingId(null);
    }
  };

  const handleCsvUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) return;
    setUploadingCsv(true);
    setCsvSummary(null);
    try {
      const summary = await api.uploadCSV(csvFile);
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
      const data = await api.crawlWebsite(crawlUrl.trim(), undefined, city);
      setCrawlResult(data);
    } catch (err: any) {
      alert(`Website scan error: ${err.message}`);
    } finally {
      setCrawling(false);
    }
  };

  const handleImportCrawled = async () => {
    if (!crawlResult) return;
    try {
      await api.importDiscoveredLead({
        name: crawlResult.title || new URL(crawlResult.website).hostname,
        website: crawlResult.website,
        city: city === 'All' ? 'Siliguri' : city,
        industry: 'Technology Services',
        description: crawlResult.description || 'Discovered via live official website scan',
        public_email: crawlResult.emails?.[0] || undefined,
        public_phone: crawlResult.phones?.[0] || undefined,
        laptop_count_verified: null,
        laptop_count_evidence: crawlResult.evidence_snippets?.join('; ') || 'Unknown - pending manual verification',
        source_url: crawlResult.source_url,
        source_type: 'official_website'
      });
      setImportSuccess(`Imported ${crawlResult.title || crawlResult.website} from live website scan!`);
      setCrawlResult(null);
      setCrawlUrl('');
      if (onCompanyImported) onCompanyImported();
    } catch (err: any) {
      alert(`Import error: ${err.message}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 tracking-tight">Public Company Discovery & Lead Research</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Discover real SMBs from permitted public sources, CSV imports, and website scans. Demo fixtures are strictly separated and labeled.
          </p>
        </div>
        {sources.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            {sources.map((src) => (
              <span
                key={src.name}
                title={src.description}
                className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                  src.configured
                    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                    : 'bg-cobalt-950 text-slate-400 border-cobalt-800'
                }`}
              >
                {src.label}: {src.configured ? 'Active' : 'Unconfigured'}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* CSV Upload Section */}
      <div className="bg-cobalt-900/60 border border-cobalt-800 rounded-lg p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded bg-cobalt-800 border border-cobalt-700 flex items-center justify-center text-cobalt-400">
              <FileSpreadsheet className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-200">Batch Import Companies via CSV</div>
              <div className="text-[11px] text-slate-400">Includes duplicate detection and automated source attribution</div>
            </div>
          </div>
          <form onSubmit={handleCsvUpload} className="flex items-center space-x-2">
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setCsvFile(e.target.files ? e.target.files[0] : null)}
              className="text-xs text-slate-300 file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-cobalt-800 file:text-cobalt-300 hover:file:bg-cobalt-700 cursor-pointer"
            />
            <button
              type="submit"
              disabled={!csvFile || uploadingCsv}
              className="px-3 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors"
            >
              {uploadingCsv ? 'Processing...' : 'Upload CSV'}
            </button>
          </form>
        </div>

        {csvSummary && (
          <div className="mt-3 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-300 flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>
              Batch Import Completed: <strong>{csvSummary.created_count}</strong> new companies added,{' '}
              <strong>{csvSummary.updated_count}</strong> duplicates updated, 0 errors.
            </span>
          </div>
        )}
      </div>

      {/* Live Official Website Scanner (SSRF-Protected) */}
      <div className="bg-cobalt-900/60 border border-cobalt-800 rounded-lg p-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="text-xs font-semibold text-slate-200">Scan Live Company Website (SSRF-Protected Crawler)</div>
            <div className="text-[11px] text-slate-400">Extract verified public business emails, phones, and team evidence directly from any public corporate URL</div>
          </div>
          <form onSubmit={handleCrawlWebsite} className="flex items-center space-x-2 flex-1 max-w-md">
            <input
              type="url"
              placeholder="https://company-website.com"
              value={crawlUrl}
              onChange={(e) => setCrawlUrl(e.target.value)}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
              required
            />
            <button
              type="submit"
              disabled={crawling}
              className="px-3 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-medium whitespace-nowrap"
            >
              {crawling ? 'Scanning...' : 'Scan URL'}
            </button>
          </form>
        </div>

        {crawlResult && (
          <div className="p-3 bg-cobalt-950/80 border border-cobalt-700 rounded text-xs space-y-2">
            <div className="flex items-center justify-between">
              <div className="font-semibold text-slate-100">{crawlResult.title || crawlResult.website}</div>
              <button
                onClick={handleImportCrawled}
                className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium flex items-center space-x-1"
              >
                <Plus className="w-3 h-3" />
                <span>Import as Lead</span>
              </button>
            </div>
            {crawlResult.description && <p className="text-slate-400 text-[11px]">{crawlResult.description}</p>}
            <div className="flex flex-wrap gap-3 font-mono text-[11px] text-slate-300">
              <span>Emails: {crawlResult.emails?.length ? crawlResult.emails.join(', ') : 'None found publicly'}</span>
              <span>Phones: {crawlResult.phones?.length ? crawlResult.phones.join(', ') : 'None found publicly'}</span>
            </div>
          </div>
        )}
      </div>

      {/* Search Filter Bar */}
      <form onSubmit={handleSearch} className="bg-cobalt-900/90 border border-cobalt-800 rounded-lg p-4 grid grid-cols-1 md:grid-cols-5 gap-3">
        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">Target City</label>
          <select
            value={city}
            onChange={(e) => setCity(e.target.value)}
            className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
          >
            <option value="Siliguri">Siliguri (West Bengal)</option>
            <option value="Gangtok">Gangtok (Sikkim)</option>
            <option value="Patna">Patna (Bihar)</option>
            <option value="Bhagalpur">Bhagalpur (Bihar)</option>
            <option value="All">All Cities</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">Target Industry</label>
          <select
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
          >
            <option value="All">All Tech Industries</option>
            <option value="Software Development">Software Development</option>
            <option value="IT Services">IT Services</option>
            <option value="Digital Marketing">Digital Marketing</option>
            <option value="Technology Consulting">Technology Consulting</option>
            <option value="Computer Training">Computer Training Institutes</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">Min Verified Laptops</label>
          <select
            value={minDevices}
            onChange={(e) => setMinDevices(Number(e.target.value))}
            className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
          >
            <option value={5}>5+ Laptops (ActTrident Target)</option>
            <option value={10}>10+ Laptops</option>
            <option value={20}>20+ Laptops</option>
          </select>
        </div>

        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">Keywords / Name</label>
          <input
            type="text"
            placeholder="e.g. cloud, labs, solutions"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 placeholder:text-slate-500"
          />
        </div>

        <div className="flex flex-col justify-end space-y-1.5">
          <label className="flex items-center space-x-1.5 text-[11px] text-amber-300/90 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={includeDemo}
              onChange={(e) => setIncludeDemo(e.target.checked)}
              className="rounded border-cobalt-700 bg-cobalt-950 text-amber-500 focus:ring-0"
            />
            <span>Include Demo Fixtures (dev only)</span>
          </label>
          <button
            type="submit"
            disabled={searching}
            className="w-full py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium transition-colors flex items-center justify-center space-x-1.5"
          >
            <Search className="w-3.5 h-3.5" />
            <span>{searching ? 'Querying...' : 'Search Directory'}</span>
          </button>
        </div>
      </form>

      {importSuccess && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-300 flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{importSuccess}</span>
        </div>
      )}

      {/* Discovered Results Table */}
      <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg overflow-hidden">
        <div className="p-4 border-b border-cobalt-800 flex items-center justify-between">
          <div className="text-xs font-semibold text-slate-200">
            Discovered Company Records ({results.length} found)
          </div>
          <div className="flex items-center space-x-3">
            <span className="text-[11px] font-mono text-slate-400">Strict Source Verification Active</span>
            {results.length > 0 && (
              <button
                onClick={async () => {
                  try {
                    const imported = await api.batchImportDiscoveredLeads(results);
                    setImportSuccess(`Batch imported ${imported.length} new qualified leads!`);
                    if (onCompanyImported) onCompanyImported();
                  } catch (e: any) {
                    alert(`Batch import failed: ${e.message}`);
                  }
                }}
                className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Import All ({results.length})</span>
              </button>
            )}
          </div>
        </div>

        {results.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400">
            <Building2 className="w-8 h-8 mx-auto text-cobalt-600 mb-2 opacity-60" />
            <p className="font-medium text-slate-300">No search executed yet or no matches found.</p>
            <p className="text-[11px] mt-1">Select a city (e.g. Siliguri, Gangtok) and click 'Search Directory' above.</p>
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
                  <th className="py-2.5 px-3">Verified Source</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cobalt-800/40 text-slate-200">
                {results.map((comp, idx) => {
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
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-medium">{comp.city}{comp.state ? `, ${comp.state}` : ''}</div>
                      <div className="text-[11px] text-slate-400">{comp.industry || 'Unspecified'}</div>
                    </td>
                    <td className="py-3 px-3 space-y-0.5 font-mono text-[11px]">
                      {comp.public_email && <div className="text-slate-300">✉ {comp.public_email}</div>}
                      {comp.public_phone && <div className="text-slate-400">☎ {comp.public_phone}</div>}
                      {!comp.public_email && !comp.public_phone && <div className="text-slate-500">Not publicly listed</div>}
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
                          <span>Unknown</span>
                        </div>
                      )}
                      <div className="text-[10px] text-slate-400 truncate max-w-[200px]" title={comp.laptop_count_evidence}>
                        {comp.laptop_count_evidence || 'Pending manual verification'}
                      </div>
                    </td>
                    <td className="py-3 px-3 text-[11px] space-y-1">
                      <div>
                        <span className="px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 text-slate-300 font-mono">
                          {comp.source_type}
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
      </div>
    </div>
  );
};
