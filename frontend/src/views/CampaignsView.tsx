import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { ViewType } from '../types';
import {
  Megaphone,
  Plus,
  Play,
  Pause,
  Square,
  OctagonAlert,
  Users,
  Send,
  Sparkles,
  Calendar,
  Clock,
  ArrowRight
} from 'lucide-react';

interface CampaignsViewProps {
  onNavigate: (view: ViewType) => void;
}

export const CampaignsView: React.FC<CampaignsViewProps> = ({ onNavigate }) => {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState('');
  const [objective, setObjective] = useState('Acquire B2B customers for ActTrident 90-day evaluation');
  const [targetCity, setTargetCity] = useState('Siliguri');
  const [targetIndustry, setTargetIndustry] = useState('Software Development');
  const [businessType, setBusinessType] = useState('IT Services & Technology');
  const [companySize, setCompanySize] = useState('10-50');
  const [minDevices, setMinDevices] = useState(5);
  const [minScore, setMinScore] = useState(0.60);
  const [allowedChannels, setAllowedChannels] = useState('email,whatsapp,linkedin');
  const [dailyEmailLimit, setDailyEmailLimit] = useState(50);
  const [totalEmailLimit, setTotalEmailLimit] = useState(200);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [recipientModalCampaign, setRecipientModalCampaign] = useState<any | null>(null);
  const [allCompanies, setAllCompanies] = useState<any[]>([]);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<number[]>([]);
  const [killSwitchActive, setKillSwitchActive] = useState(false);

  const loadCampaigns = async () => {
    try {
      const [data, comps, ks] = await Promise.all([
        api.getCampaigns(),
        api.getCompanies({ limit: 100 }).catch(() => ({ items: [] })),
        api.getKillSwitch().catch(() => ({ active: false }))
      ]);
      setCampaigns(data);
      setAllCompanies(comps.items || []);
      setKillSwitchActive(Boolean(ks?.active));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleLifecycleAction = async (campaignId: number, action: 'pause' | 'resume' | 'stop') => {
    if (action === 'stop' && !confirm('Permanently stop this campaign? Stopped campaigns cannot be resumed.')) {
      return;
    }
    setProcessingId(campaignId);
    try {
      if (action === 'pause') await api.pauseCampaign(campaignId);
      if (action === 'resume') await api.resumeCampaign(campaignId);
      if (action === 'stop') await api.stopCampaign(campaignId);
      await loadCampaigns();
    } catch (err: any) {
      alert(`Campaign ${action} error: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  useEffect(() => {
    loadCampaigns();
  }, []);

  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createCampaign({
        name,
        objective,
        target_city: targetCity,
        target_industry: targetIndustry,
        business_type: businessType,
        company_size: companySize,
        min_devices: minDevices,
        min_score: minScore,
        allowed_channels: allowedChannels,
        daily_email_limit: dailyEmailLimit,
        total_email_limit: totalEmailLimit,
        start_date: startDate ? new Date(startDate).toISOString() : undefined,
        end_date: endDate ? new Date(endDate).toISOString() : undefined,
        sending_schedule: '09:00-18:00 IST Weekdays'
      });
      setShowCreateModal(false);
      setName('');
      loadCampaigns();
    } catch (err: any) {
      alert(`Create error: ${err.message}`);
    }
  };

  const handleGenerateDrafts = async (campaignId: number) => {
    setProcessingId(campaignId);
    try {
      const res = await api.generateCampaignDrafts(campaignId);
      alert(`Generated ${res.drafts_created} personalized drafts in DRAFT mode! You can now review them in the Approval Queue.`);
      loadCampaigns();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  const handleSendApproved = async (campaignId: number) => {
    setProcessingId(campaignId);
    try {
      const res = await api.sendApprovedCampaignEmails(campaignId);
      const sent = res.sent ?? 0;
      const simulated = res.simulated ?? 0;
      alert(`Campaign dispatch complete: ${sent} sent, ${simulated} simulated.`);
      loadCampaigns();
    } catch (err: any) {
      alert(`Dispatch error: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  const handleAddRecipients = async () => {
    if (!recipientModalCampaign || selectedCompanyIds.length === 0) return;
    setProcessingId(recipientModalCampaign.id);
    try {
      const res = await api.addCampaignRecipients(recipientModalCampaign.id, selectedCompanyIds);
      alert(`Added ${res.added ?? selectedCompanyIds.length} recipients to "${recipientModalCampaign.name}".`);
      setRecipientModalCampaign(null);
      setSelectedCompanyIds([]);
      loadCampaigns();
    } catch (err: any) {
      alert(`Add recipients error: ${err.message}`);
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 tracking-tight">Campaign Management & Outreach Sequences</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Geographic campaigns with conservative daily limits and mandatory human approval checks.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-3.5 py-2 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1.5 shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>New Campaign</span>
        </button>
      </div>

      {killSwitchActive && (
        <div className="p-3 bg-rose-950/60 border border-rose-500/50 rounded-lg text-xs text-rose-200 flex items-center space-x-2">
          <OctagonAlert className="w-4 h-4 text-rose-400 shrink-0" />
          <span>
            <strong>Global Emergency Kill Switch is ACTIVE:</strong> All outbound campaign dispatches are halted. Deactivate in Settings to resume.
          </span>
        </div>
      )}

      {/* Campaigns Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {campaigns.map((camp) => (
          <div key={camp.id} className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cobalt-950 text-cobalt-300 border border-cobalt-800 uppercase">
                  {camp.target_city || 'Regional'}
                </span>
                <h3 className="text-sm font-bold text-slate-100 mt-1.5">{camp.name}</h3>
                <p className="text-xs text-slate-400 mt-0.5">{camp.objective}</p>
              </div>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded uppercase border ${
                  camp.status === 'active' || camp.status === 'running'
                    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                    : camp.status === 'approved' || camp.status === 'ready_for_review'
                    ? 'bg-blue-500/15 text-blue-300 border-blue-500/30'
                    : camp.status === 'scheduled' || camp.status === 'researching'
                    ? 'bg-purple-500/15 text-purple-300 border-purple-500/30'
                    : camp.status === 'completed'
                    ? 'bg-teal-500/15 text-teal-300 border-teal-500/30'
                    : camp.status === 'failed' || camp.status === 'stopped'
                    ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                    : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                }`}
              >
                {camp.status}
              </span>
            </div>

            {/* Campaign Metrics Grid */}
            <div className="grid grid-cols-4 gap-2 text-center py-2.5 bg-cobalt-950/80 rounded border border-cobalt-800 font-mono text-xs">
              <div>
                <div className="text-slate-400 text-[10px]">Recipients</div>
                <div className="text-slate-200 font-bold mt-0.5">{camp.recipients_count}</div>
              </div>
              <div>
                <div className="text-slate-400 text-[10px]">Drafted</div>
                <div className="text-amber-400 font-bold mt-0.5">{camp.emails_drafted}</div>
              </div>
              <div>
                <div className="text-slate-400 text-[10px]">Approved</div>
                <div className="text-emerald-400 font-bold mt-0.5">{camp.emails_approved}</div>
              </div>
              <div>
                <div className="text-slate-400 text-[10px]">Sent</div>
                <div className="text-cobalt-400 font-bold mt-0.5">{camp.emails_sent}</div>
              </div>
            </div>

            <div className="flex flex-col space-y-1 text-[11px] text-slate-400">
              <div className="flex items-center justify-between">
                <span>Daily Limit: <strong>{camp.daily_email_limit} emails/day</strong></span>
                <span>Min Devices: <strong>{camp.min_devices || 5}+ laptops</strong></span>
              </div>
              <div className="flex items-center justify-between">
                <span>Channels: <strong>{camp.allowed_channels || 'email'}</strong></span>
                <span>Schedule: <strong>{camp.sending_schedule}</strong></span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-cobalt-800">
              <button
                onClick={() => {
                  setRecipientModalCampaign(camp);
                  setSelectedCompanyIds([]);
                }}
                disabled={camp.status === 'stopped'}
                className="py-1.5 px-2.5 bg-cobalt-950 hover:bg-cobalt-850 disabled:opacity-40 border border-cobalt-700 text-slate-200 rounded text-xs font-medium flex items-center space-x-1"
              >
                <Users className="w-3.5 h-3.5 text-cobalt-400" />
                <span>Add Leads</span>
              </button>
              <button
                onClick={() => handleGenerateDrafts(camp.id)}
                disabled={processingId === camp.id || camp.recipients_count === 0 || camp.status === 'stopped'}
                className="flex-1 py-1.5 bg-cobalt-950 hover:bg-cobalt-850 disabled:opacity-40 border border-cobalt-700 text-slate-200 rounded text-xs font-medium flex items-center justify-center space-x-1"
              >
                <Sparkles className="w-3.5 h-3.5 text-cobalt-400" />
                <span>Generate Drafts</span>
              </button>
              <button
                onClick={() => handleSendApproved(camp.id)}
                disabled={
                  processingId === camp.id ||
                  camp.emails_approved === 0 ||
                  camp.status === 'paused' ||
                  camp.status === 'stopped' ||
                  killSwitchActive
                }
                className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white rounded text-xs font-medium flex items-center justify-center space-x-1"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Send {camp.emails_approved} Approved</span>
              </button>

              {camp.status !== 'stopped' && (
                <div className="w-full flex items-center justify-end space-x-1.5 pt-1">
                  {camp.status === 'paused' || camp.status === 'draft' ? (
                    <button
                      onClick={() => handleLifecycleAction(camp.id, 'resume')}
                      disabled={processingId === camp.id}
                      className="px-2.5 py-1 bg-emerald-950/50 hover:bg-emerald-900/60 border border-emerald-700/50 text-emerald-300 rounded text-[11px] flex items-center space-x-1"
                    >
                      <Play className="w-3 h-3" />
                      <span>{camp.status === 'draft' ? 'Activate' : 'Resume'}</span>
                    </button>
                  ) : (
                    <button
                      onClick={() => handleLifecycleAction(camp.id, 'pause')}
                      disabled={processingId === camp.id}
                      className="px-2.5 py-1 bg-amber-950/50 hover:bg-amber-900/60 border border-amber-700/50 text-amber-300 rounded text-[11px] flex items-center space-x-1"
                    >
                      <Pause className="w-3 h-3" />
                      <span>Pause</span>
                    </button>
                  )}
                  <button
                    onClick={() => handleLifecycleAction(camp.id, 'stop')}
                    disabled={processingId === camp.id}
                    className="px-2.5 py-1 bg-rose-950/50 hover:bg-rose-900/60 border border-rose-700/50 text-rose-300 rounded text-[11px] flex items-center space-x-1"
                  >
                    <Square className="w-3 h-3" />
                    <span>Stop</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-cobalt-900 border border-cobalt-700 rounded-lg p-5 w-full max-w-md space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
              <h3 className="font-bold text-slate-100 text-sm">Create New Outreach Campaign</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <form onSubmit={handleCreateCampaign} className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Campaign Name</label>
                <input
                  type="text"
                  placeholder="e.g. Siliguri IT Companies Campaign"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  required
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Target Geography / City</label>
                <input
                  type="text"
                  placeholder="e.g. Siliguri, Bengaluru, Mumbai, or Nationwide"
                  list="campaign-cities-list"
                  value={targetCity}
                  onChange={(e) => setTargetCity(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
                  required
                />
                <datalist id="campaign-cities-list">
                  <option value="All">All India / Nationwide</option>
                  <option value="Siliguri">Siliguri (West Bengal)</option>
                  <option value="Gangtok">Gangtok (Sikkim)</option>
                  <option value="Patna">Patna (Bihar)</option>
                  <option value="Bhagalpur">Bhagalpur (Bihar)</option>
                  <option value="Bengaluru">Bengaluru (Karnataka)</option>
                  <option value="Hyderabad">Hyderabad (Telangana)</option>
                  <option value="Pune">Pune (Maharashtra)</option>
                  <option value="Mumbai">Mumbai (Maharashtra)</option>
                  <option value="Delhi">Delhi NCR</option>
                  <option value="Kolkata">Kolkata (West Bengal)</option>
                  <option value="Chennai">Chennai (Tamil Nadu)</option>
                  <option value="Ahmedabad">Ahmedabad (Gujarat)</option>
                  <option value="Jaipur">Jaipur (Rajasthan)</option>
                  <option value="Indore">Indore (Madhya Pradesh)</option>
                  <option value="Chandigarh">Chandigarh</option>
                  <option value="Lucknow">Lucknow (Uttar Pradesh)</option>
                </datalist>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">Target Industry</label>
                  <input
                    type="text"
                    value={targetIndustry}
                    onChange={(e) => setTargetIndustry(e.target.value)}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">Business Type</label>
                  <input
                    type="text"
                    value={businessType}
                    onChange={(e) => setBusinessType(e.target.value)}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">Min Laptops Verified</label>
                  <input
                    type="number"
                    value={minDevices}
                    onChange={(e) => setMinDevices(Number(e.target.value))}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">Allowed Channels</label>
                  <select
                    value={allowedChannels}
                    onChange={(e) => setAllowedChannels(e.target.value)}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  >
                    <option value="email,whatsapp,linkedin">Email + WhatsApp + LinkedIn</option>
                    <option value="email,whatsapp">Email + WhatsApp</option>
                    <option value="email">Email Only</option>
                    <option value="whatsapp">WhatsApp Only</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">Daily Limit (Emails)</label>
                  <input
                    type="number"
                    value={dailyEmailLimit}
                    onChange={(e) => setDailyEmailLimit(Number(e.target.value))}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">Total Campaign Limit</label>
                  <input
                    type="number"
                    value={totalEmailLimit}
                    onChange={(e) => setTotalEmailLimit(Number(e.target.value))}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">Start Date (Optional)</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">End Date (Optional)</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 bg-cobalt-950 text-slate-300 rounded text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium"
                >
                  Create Campaign
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Recipients Modal */}
      {recipientModalCampaign && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-cobalt-900 border border-cobalt-700 rounded-lg p-5 w-full max-w-lg space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
              <h3 className="font-bold text-slate-100 text-sm">Add Companies to "{recipientModalCampaign.name}"</h3>
              <button onClick={() => setRecipientModalCampaign(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <div className="max-h-72 overflow-y-auto space-y-1.5 pr-1">
              {allCompanies.map((c) => {
                const checked = selectedCompanyIds.includes(c.id);
                return (
                  <label key={c.id} className="flex items-center justify-between p-2 rounded bg-cobalt-950/70 border border-cobalt-800 cursor-pointer hover:border-cobalt-600">
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          setSelectedCompanyIds((prev) =>
                            checked ? prev.filter((id) => id !== c.id) : [...prev, c.id]
                          )
                        }
                      />
                      <div>
                        <div className="font-semibold text-slate-200">{c.name}</div>
                        <div className="text-[10px] text-slate-400">{c.city} • {c.public_email || 'No email'}</div>
                      </div>
                    </div>
                    <span className="font-mono text-[10px] text-emerald-400">{c.laptop_count_verified ?? '?'} laptops</span>
                  </label>
                );
              })}
            </div>
            <div className="flex justify-end space-x-2 pt-2 border-t border-cobalt-800">
              <button onClick={() => setRecipientModalCampaign(null)} className="px-3 py-1.5 bg-cobalt-950 text-slate-300 rounded">Cancel</button>
              <button
                onClick={handleAddRecipients}
                disabled={selectedCompanyIds.length === 0 || processingId === recipientModalCampaign.id}
                className="px-3.5 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-40 text-white rounded font-medium"
              >
                Add Selected ({selectedCompanyIds.length})
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
