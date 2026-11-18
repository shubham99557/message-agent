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
  ExternalLink,
  Plus
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
  const [showAddModal, setShowAddModal] = useState(false);
  const [newCompany, setNewCompany] = useState({
    name: '',
    website: '',
    city: 'Siliguri',
    state: 'West Bengal',
    industry: 'Software Development',
    public_email: '',
    public_phone: '',
    decision_maker_name: '',
    decision_maker_role: '',
    laptop_count_verified: '',
    laptop_count_evidence: '',
    source_url: ''
  });
  const [creating, setCreating] = useState(false);

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
          <button
            onClick={() => setShowAddModal(true)}
            className="px-3 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Company</span>
          </button>
          <button
            onClick={async () => {
              try {
                await api.exportCompaniesCsv();
              } catch (err: any) {
                alert(`Export error: ${err.message}`);
              }
            }}
            className="px-3 py-1.5 bg-cobalt-900 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium transition-colors flex items-center space-x-1.5"
          >
            <Download className="w-3.5 h-3.5 text-cobalt-400" />
            <span>Export CSV</span>
          </button>
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
                      <div className="flex items-center space-x-1.5 flex-wrap">
                        <span className="font-semibold text-slate-100">{c.name}</span>
                        {(c.is_demo || c.verification_status === 'demo_fixture') ? (
                          <span className="px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[9px] font-mono uppercase">
                            DEMO FIXTURE
                          </span>
                        ) : (
                          <span
                            className={`px-1.5 py-0.5 rounded text-[9px] font-mono border ${
                              c.verification_status === 'verified'
                                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                                : 'bg-cobalt-950 text-slate-400 border-cobalt-800'
                            }`}
                          >
                            {c.verification_status || 'unverified'}
                          </span>
                        )}
                      </div>
                      {c.public_email && <div className="text-[11px] text-slate-400 font-mono">{c.public_email}</div>}
                    </td>
                    <td className="py-3 px-3">
                      <div>{c.city}, {c.state || c.country}</div>
                      <div className="text-[11px] text-slate-400">{c.industry || 'Unspecified'}</div>
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-medium text-slate-200">{c.decision_maker_name || 'Unverified'}</div>
                      <div className="text-[11px] text-slate-400">{c.decision_maker_role || 'Role not verified'}</div>
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

      {/* Add Company Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-cobalt-900 border border-cobalt-700 rounded-lg p-5 w-full max-w-lg space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
              <h3 className="font-bold text-slate-100 text-sm">Add Verified B2B Prospect</h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setCreating(true);
                try {
                  await api.createCompany({
                    name: newCompany.name,
                    website: newCompany.website || undefined,
                    city: newCompany.city,
                    state: newCompany.state || undefined,
                    industry: newCompany.industry || undefined,
                    public_email: newCompany.public_email || undefined,
                    public_phone: newCompany.public_phone || undefined,
                    decision_maker_name: newCompany.decision_maker_name || undefined,
                    decision_maker_role: newCompany.decision_maker_role || undefined,
                    laptop_count_verified: newCompany.laptop_count_verified ? Number(newCompany.laptop_count_verified) : undefined,
                    laptop_count_evidence: newCompany.laptop_count_evidence || undefined,
                    source_url: newCompany.source_url || newCompany.website || 'Manual Entry',
                    is_demo: false
                  });
                  setShowAddModal(false);
                  setNewCompany({
                    name: '', website: '', city: 'Siliguri', state: 'West Bengal',
                    industry: 'Software Development', public_email: '', public_phone: '',
                    decision_maker_name: '', decision_maker_role: '',
                    laptop_count_verified: '', laptop_count_evidence: '', source_url: ''
                  });
                  loadCompanies();
                } catch (err: any) {
                  alert(`Create error: ${err.message}`);
                } finally {
                  setCreating(false);
                }
              }}
              className="space-y-3"
            >
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Company Name *</label>
                  <input required type="text" value={newCompany.name} onChange={(e) => setNewCompany({ ...newCompany, name: e.target.value })} className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200" />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Official Website</label>
                  <input type="url" placeholder="https://..." value={newCompany.website} onChange={(e) => setNewCompany({ ...newCompany, website: e.target.value })} className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200" />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">City *</label>
                  <input required type="text" value={newCompany.city} onChange={(e) => setNewCompany({ ...newCompany, city: e.target.value })} className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200" />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Industry</label>
                  <input type="text" value={newCompany.industry} onChange={(e) => setNewCompany({ ...newCompany, industry: e.target.value })} className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200" />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Public Business Email</label>
                  <input type="email" value={newCompany.public_email} onChange={(e) => setNewCompany({ ...newCompany, public_email: e.target.value })} className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200" />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Public Phone</label>
                  <input type="text" value={newCompany.public_phone} onChange={(e) => setNewCompany({ ...newCompany, public_phone: e.target.value })} className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200" />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Verified Laptop Count</label>
                  <input type="number" min="0" value={newCompany.laptop_count_verified} onChange={(e) => setNewCompany({ ...newCompany, laptop_count_verified: e.target.value })} className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200" />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Laptop Evidence Source</label>
                  <input type="text" placeholder="e.g. Careers page / MCA filing" value={newCompany.laptop_count_evidence} onChange={(e) => setNewCompany({ ...newCompany, laptop_count_evidence: e.target.value })} className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200" />
                </div>
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button type="button" onClick={() => setShowAddModal(false)} className="px-3 py-1.5 bg-cobalt-950 text-slate-300 rounded">Cancel</button>
                <button type="submit" disabled={creating} className="px-4 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded font-medium">
                  {creating ? 'Saving...' : 'Save Company'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
