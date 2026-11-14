import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { ViewType } from '../types';
import {
  Megaphone,
  Plus,
  Play,
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
  const [dailyEmailLimit, setDailyEmailLimit] = useState(50);
  const [processingId, setProcessingId] = useState<number | null>(null);

  const loadCampaigns = async () => {
    try {
      const data = await api.getCampaigns();
      setCampaigns(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
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
        daily_email_limit: dailyEmailLimit,
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
      alert(`Campaign dispatch complete: ${res.sent} approved emails sent!`);
      loadCampaigns();
    } catch (err: any) {
      alert(`Dispatch error: ${err.message}`);
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
              <span className="text-[10px] font-mono px-2 py-0.5 rounded uppercase border bg-amber-500/10 text-amber-300 border-amber-500/30">
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

            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span>Limit: {camp.daily_email_limit} emails / day</span>
              <span>Schedule: {camp.sending_schedule}</span>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center space-x-2 pt-2 border-t border-cobalt-800">
              <button
                onClick={() => handleGenerateDrafts(camp.id)}
                disabled={processingId === camp.id}
                className="flex-1 py-1.5 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium flex items-center justify-center space-x-1"
              >
                <Sparkles className="w-3.5 h-3.5 text-cobalt-400" />
                <span>Batch Generate Drafts</span>
              </button>
              <button
                onClick={() => handleSendApproved(camp.id)}
                disabled={processingId === camp.id || camp.emails_approved === 0}
                className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white rounded text-xs font-medium flex items-center justify-center space-x-1"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Send {camp.emails_approved} Approved</span>
              </button>
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
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Target Geography</label>
                <select
                  value={targetCity}
                  onChange={(e) => setTargetCity(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                >
                  <option value="Siliguri">Siliguri (West Bengal)</option>
                  <option value="Gangtok">Gangtok (Sikkim)</option>
                  <option value="Patna">Patna (Bihar)</option>
                  <option value="Bhagalpur">Bhagalpur (Bihar)</option>
                </select>
              </div>

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
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Daily Sending Limit</label>
                <input
                  type="number"
                  value={dailyEmailLimit}
                  onChange={(e) => setDailyEmailLimit(Number(e.target.value))}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                />
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
    </div>
  );
};
