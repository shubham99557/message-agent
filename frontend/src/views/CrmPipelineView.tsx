import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Lead, ViewType } from '../types';
import {
  GitBranch,
  Calendar,
  Clock,
  Award,
  Ban,
  CheckCircle2,
  AlertCircle,
  Plus,
  ArrowRight,
  Download
} from 'lucide-react';

export const CrmPipelineView: React.FC = () => {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [validStatuses, setValidStatuses] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState('All');
  const [cityFilter, setCityFilter] = useState('All');
  const [loading, setLoading] = useState(true);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  const availableCities = Array.from(
    new Set(['Siliguri', 'Gangtok', 'Patna', 'Bhagalpur', ...leads.map((l) => l.company?.city).filter(Boolean)])
  );

  const statusDisplayMap: Record<string, string> = {
    new: 'New Lead',
    researching: 'Researched',
    qualified: 'Qualified',
    draft_ready: 'Draft Ready',
    awaiting_approval: 'Awaiting Approval',
    contacted: 'Contacted',
    replied: 'Replied',
    interested: 'Interested',
    meeting_scheduled: 'Meeting Scheduled',
    demo_completed: 'Demo Completed',
    trial_offered: 'Evaluation Offered',
    trial_activated: 'Evaluation Active',
    converted: 'Converted',
    not_interested: 'Not Interested',
    lost: 'Lost',
    do_not_contact: 'Unsubscribed'
  };

  // Modals
  const [showMeetingModal, setShowMeetingModal] = useState(false);
  const [meetingTitle, setMeetingTitle] = useState('ActTrident Demo & Workspace Review');
  const [meetingDate, setMeetingDate] = useState('');

  const [showTrialModal, setShowTrialModal] = useState(false);
  const [trialDevices, setTrialDevices] = useState(8);

  const loadLeads = async () => {
    setLoading(true);
    try {
      const data = await api.getLeads(
        statusFilter === 'All' ? undefined : statusFilter,
        cityFilter === 'All' ? undefined : cityFilter
      );
      setLeads(data.items);
      setValidStatuses(data.valid_statuses);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLeads();
  }, [statusFilter, cityFilter]);

  const handleExportCsv = async () => {
    try {
      await api.exportCrmLeadsCsv(statusFilter, cityFilter);
    } catch (err: any) {
      alert(`Export error: ${err.message}`);
    }
  };

  const handleStatusChange = async (leadId: number, newStatus: string) => {
    try {
      await api.updateLeadStatus(leadId, newStatus);
      loadLeads();
    } catch (err: any) {
      alert(`Error updating status: ${err.message}`);
    }
  };

  const handleScheduleMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLead || !meetingDate) return;
    try {
      await api.scheduleMeeting(selectedLead.id, {
        title: meetingTitle,
        scheduled_at: new Date(meetingDate).toISOString(),
        duration_minutes: 30
      });
      alert('Meeting scheduled successfully! Lead updated to "meeting_scheduled".');
      setShowMeetingModal(false);
      loadLeads();
    } catch (err: any) {
      alert(`Meeting error: ${err.message}`);
    }
  };

  const handleActivateTrial = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLead) return;
    try {
      const start = new Date();
      const end = new Date();
      end.setDate(end.getDate() + 90);
      await api.activateTrial(selectedLead.id, {
        program_name: 'ActTrident 90-Day Free Evaluation',
        start_date: start.toISOString(),
        end_date: end.toISOString(),
        devices_count: trialDevices
      });
      alert(`ActTrident 90-day evaluation activated for ${trialDevices} managed laptops!`);
      setShowTrialModal(false);
      loadLeads();
    } catch (err: any) {
      alert(`Trial error: ${err.message}`);
    }
  };

  const handleOptOut = async (lead: Lead) => {
    const email = lead.company?.public_email;
    if (!email) return;
    if (confirm(`Immediately halt all communication and mark ${lead.company?.name} as Do Not Contact?`)) {
      try {
        await api.recordOptOut(email, 'all', 'user_explicit_opt_out');
        alert('Account suppressed and marked as do_not_contact.');
        loadLeads();
      } catch (err: any) {
        alert(`Opt-out error: ${err.message}`);
      }
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 tracking-tight">16-Stage B2B Sales CRM Pipeline</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Manages prospect lifecycle from discovery through demo, 90-day evaluation, and conversion.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={cityFilter}
            onChange={(e) => setCityFilter(e.target.value)}
            className="bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
          >
            <option value="All">All Cities ({leads.length})</option>
            {availableCities.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-cobalt-950 border border-cobalt-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 font-mono"
          >
            <option value="All">All Pipeline Stages ({leads.length})</option>
            {validStatuses.map((s) => (
              <option key={s} value={s}>
                {statusDisplayMap[s] || s.replace(/_/g, ' ')}
              </option>
            ))}
          </select>

          <button
            onClick={handleExportCsv}
            className="px-3 py-1.5 bg-cobalt-900 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium transition-colors flex items-center space-x-1.5"
            title="Export CRM pipeline accounts to CSV"
          >
            <Download className="w-3.5 h-3.5 text-cobalt-400" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Leads Table */}
      <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg overflow-hidden">
        <div className="p-3.5 border-b border-cobalt-800 flex items-center justify-between text-xs font-semibold text-slate-200">
          <span>Active Accounts ({leads.length})</span>
          <span className="text-[11px] font-mono text-slate-400">Automatic Opt-Out Suppression Enforced</span>
        </div>

        {loading ? (
          <div className="p-16 text-center text-xs text-slate-400">Loading pipeline accounts...</div>
        ) : leads.length === 0 ? (
          <div className="p-16 text-center text-xs text-slate-400">No accounts in this pipeline stage.</div>
        ) : (
          <div className="overflow-x-auto text-xs">
            <table className="w-full text-left">
              <thead className="bg-cobalt-950/60 text-slate-400 border-b border-cobalt-800/80 font-medium">
                <tr>
                  <th className="py-2.5 px-3">Company & City</th>
                  <th className="py-2.5 px-3">Pipeline Stage</th>
                  <th className="py-2.5 px-3">Verified Devices</th>
                  <th className="py-2.5 px-3">90-Day Evaluation</th>
                  <th className="py-2.5 px-3">Last Contact</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cobalt-800/40 text-slate-200">
                {leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-cobalt-850/50 transition-colors">
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-100">{lead.company?.name || 'Company'}</div>
                      <div className="text-[11px] text-slate-400">{lead.company?.city} • {lead.company?.industry}</div>
                    </td>
                    <td className="py-3 px-3">
                      <select
                        value={lead.pipeline_status}
                        onChange={(e) => handleStatusChange(lead.id, e.target.value)}
                        className={`bg-cobalt-950 border border-cobalt-800 rounded px-2 py-1 text-[11px] font-mono capitalize focus:outline-none focus:border-cobalt-600 ${
                          lead.pipeline_status === 'trial_activated' || lead.pipeline_status === 'converted'
                            ? 'text-emerald-300'
                            : lead.pipeline_status === 'do_not_contact' || lead.pipeline_status === 'lost'
                            ? 'text-rose-400'
                            : 'text-cobalt-300'
                        }`}
                      >
                        {validStatuses.map((s) => (
                          <option key={s} value={s}>
                            {statusDisplayMap[s] || s.replace(/_/g, ' ')}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-3 px-3 font-mono">
                      {lead.company?.laptop_count_verified ? (
                        <span className="text-emerald-400 font-medium">{lead.company.laptop_count_verified} Laptops</span>
                      ) : (
                        <span className="text-slate-500">Unverified</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      {lead.trial_status === 'active' ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                          Active ({lead.trial_device_count} Laptops)
                        </span>
                      ) : (
                        <button
                          onClick={() => {
                            setSelectedLead(lead);
                            setShowTrialModal(true);
                          }}
                          className="px-2 py-0.5 rounded text-[10px] font-mono bg-cobalt-950 hover:bg-cobalt-850 text-cobalt-300 border border-cobalt-800"
                        >
                          + Activate 90-Day Trial
                        </button>
                      )}
                    </td>
                    <td className="py-3 px-3 text-[11px] text-slate-400 font-mono">
                      {lead.last_contact_date
                        ? new Date(lead.last_contact_date).toLocaleDateString()
                        : 'Not contacted'}
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end space-x-1.5">
                        <button
                          onClick={() => {
                            setSelectedLead(lead);
                            setShowMeetingModal(true);
                          }}
                          title="Schedule Demo Meeting"
                          className="px-2 py-1 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs"
                        >
                          Demo
                        </button>
                        <button
                          onClick={() => handleOptOut(lead)}
                          title="Opt Out / Suppress"
                          className="p-1 hover:bg-rose-950/40 text-slate-500 hover:text-rose-400 rounded"
                        >
                          <Ban className="w-3.5 h-3.5" />
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

      {/* Schedule Meeting Modal */}
      {showMeetingModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-cobalt-900 border border-cobalt-700 rounded-lg p-5 w-full max-w-md space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
              <h3 className="font-bold text-slate-100 text-sm">Schedule Demo / Meeting</h3>
              <button onClick={() => setShowMeetingModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <form onSubmit={handleScheduleMeeting} className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Meeting Title</label>
                <input
                  type="text"
                  value={meetingTitle}
                  onChange={(e) => setMeetingTitle(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  required
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Date & Time</label>
                <input
                  type="datetime-local"
                  value={meetingDate}
                  onChange={(e) => setMeetingDate(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  required
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowMeetingModal(false)}
                  className="px-3 py-1.5 bg-cobalt-950 text-slate-300 rounded text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium"
                >
                  Confirm Meeting
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Activate Trial Modal */}
      {showTrialModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-cobalt-900 border border-cobalt-700 rounded-lg p-5 w-full max-w-md space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
              <h3 className="font-bold text-slate-100 text-sm">Activate ActTrident 90-Day Free Evaluation</h3>
              <button onClick={() => setShowTrialModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <form onSubmit={handleActivateTrial} className="space-y-3">
              <p className="text-slate-300 text-xs">
                Activating zero-cost evaluation for <strong>{selectedLead?.company?.name}</strong>.
              </p>
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Number of Protected Laptops (Min 5)</label>
                <input
                  type="number"
                  min={5}
                  value={trialDevices}
                  onChange={(e) => setTrialDevices(Number(e.target.value))}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  required
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowTrialModal(false)}
                  className="px-3 py-1.5 bg-cobalt-950 text-slate-300 rounded text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium"
                >
                  Activate Evaluation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
