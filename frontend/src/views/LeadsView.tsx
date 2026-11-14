import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Company, ViewType } from '../types';
import {
  Building2,
  Download,
  Filter,
  Search,
  CheckCircle2,
  AlertTriangle,
  Laptop,
  BrainCircuit,
  Mail,
  ChevronRight,
  ExternalLink
} from 'lucide-react';

interface LeadsViewProps {
  onSelectCompany: (company: Company, view: ViewType) => void;
}

export const LeadsView: React.FC<LeadsViewProps> = ({ onSelectCompany }) => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [cityFilter, setCityFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  const [total, setTotal] = useState(0);

  const loadCompanies = async () => {
    setLoading(true);
    try {
      const data = await api.getCompanies({
        city: cityFilter === 'All' ? undefined : cityFilter,
        search: searchTerm || undefined,
        limit: 100
      });
      setCompanies(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompanies();
  }, [cityFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadCompanies();
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Filter and Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 tracking-tight">Lead Database & Company Directory</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Verified B2B accounts with contact source attribution and managed device fleet evidence.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <a
            href="/api/v1/companies/export/csv"
            download
            className="px-3 py-1.5 bg-cobalt-900 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium transition-colors flex items-center space-x-1.5"
          >
            <Download className="w-3.5 h-3.5 text-cobalt-400" />
            <span>Export CSV</span>
          </a>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-cobalt-900/90 border border-cobalt-800 rounded-lg p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <form onSubmit={handleSearchSubmit} className="flex items-center space-x-2 flex-1 max-w-md">
          <div className="relative w-full">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search companies, decision makers, email..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded pl-8 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 placeholder:text-slate-500"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium"
          >
            Search
          </button>
        </form>

        <div className="flex items-center space-x-2">
          <span className="text-slate-400 text-[11px]">Filter City:</span>
          <select
            value={cityFilter}
            onChange={(e) => setCityFilter(e.target.value)}
            className="bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
          >
            <option value="All">All Cities</option>
            <option value="Siliguri">Siliguri</option>
            <option value="Gangtok">Gangtok</option>
            <option value="Patna">Patna</option>
            <option value="Bhagalpur">Bhagalpur</option>
          </select>
        </div>
      </div>

      {/* Companies Table */}
      <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg overflow-hidden">
        <div className="p-3.5 border-b border-cobalt-800 flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-200">Registered Companies ({total})</span>
          <span className="text-[11px] font-mono text-slate-400">Strict Source Verification</span>
        </div>

        {loading ? (
          <div className="p-10 text-center text-xs text-slate-400">Loading database records...</div>
        ) : companies.length === 0 ? (
          <div className="p-10 text-center text-xs text-slate-400">
            <p>No companies found in database.</p>
            <p className="text-[11px] text-slate-500 mt-1">Use the 'Discover Companies' view or upload a CSV.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cobalt-950/60 text-slate-400 border-b border-cobalt-800/80 font-medium">
                <tr>
                  <th className="py-2.5 px-3">Company</th>
                  <th className="py-2.5 px-3">Location & Industry</th>
                  <th className="py-2.5 px-3">Decision Maker</th>
                  <th className="py-2.5 px-3">Laptops Verified</th>
                  <th className="py-2.5 px-3">Qualification</th>
                  <th className="py-2.5 px-3">Sources</th>
                  <th className="py-2.5 px-3 text-right">Outreach</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cobalt-800/40 text-slate-200">
                {companies.map((c) => (
                  <tr key={c.id} className="hover:bg-cobalt-850/50 transition-colors">
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-100">{c.name}</div>
                      {c.public_email && <div className="text-[11px] text-slate-400 font-mono">{c.public_email}</div>}
                    </td>
                    <td className="py-3 px-3">
                      <div>{c.city}, {c.state || c.country}</div>
                      <div className="text-[11px] text-slate-400">{c.industry || 'Tech'}</div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-medium text-slate-200">{c.decision_maker_name || 'IT Director'}</div>
                      <div className="text-[11px] text-slate-400">{c.decision_maker_role || 'Leadership'}</div>
                    </td>
                    <td className="py-3 px-3">
                      {c.has_verified_5_plus_laptops ? (
                        <div className="flex items-center space-x-1.5 text-emerald-400 font-mono font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>{c.laptop_count_verified} Laptops</span>
                        </div>
                      ) : (
                        <div className="flex items-center space-x-1.5 text-amber-400 font-mono">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          <span>{c.laptop_count_verified ? `${c.laptop_count_verified} (Unconfirmed)` : 'Needs audit'}</span>
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                          c.qualification_status === 'High priority'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                            : c.qualification_status === 'Medium priority'
                            ? 'bg-cobalt-500/20 text-cobalt-300 border-cobalt-500/30'
                            : c.qualification_status === 'Needs manual verification'
                            ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                            : 'bg-slate-700/30 text-slate-400 border-slate-700'
                        }`}
                      >
                        {c.qualification_status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-[11px] font-mono text-slate-400">
                      {c.sources && c.sources.length > 0 ? (
                        <a
                          href={c.sources[0].source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:underline flex items-center space-x-1 text-cobalt-400"
                        >
                          <span className="truncate max-w-[120px]">{c.sources[0].source_type}</span>
                          <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      ) : (
                        <span>Direct profile</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end space-x-1.5">
                        <button
                          onClick={() => onSelectCompany(c, 'research')}
                          title="Generate AI Research Report"
                          className="p-1 rounded bg-cobalt-950 hover:bg-cobalt-800 text-slate-300 hover:text-white border border-cobalt-800"
                        >
                          <BrainCircuit className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => onSelectCompany(c, 'email')}
                          title="Draft Personalized Email"
                          className="p-1 rounded bg-cobalt-600 hover:bg-cobalt-500 text-white"
                        >
                          <Mail className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
