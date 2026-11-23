import React, { useState, useEffect } from 'react';
import {
  Calendar,
  Clock,
  CheckCircle,
  AlertCircle,
  Plus,
  Trash2,
  Search,
  Filter,
  RefreshCw,
  Mail,
  Phone,
  MessageSquare,
  Users,
  ShieldBan,
  ExternalLink,
  CheckSquare
} from 'lucide-react';
import { api } from '../api/client';
import { FollowupTask, SuppressionItem } from '../types';

export const FollowUpManagerView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'followups' | 'suppression'>('followups');
  const [followups, setFollowups] = useState<FollowupTask[]>([]);
  const [suppressionList, setSuppressionList] = useState<SuppressionItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterDueOnly, setFilterDueOnly] = useState<boolean>(false);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Add suppression modal state
  const [showSuppressionModal, setShowSuppressionModal] = useState<boolean>(false);
  const [suppressIdentifier, setSuppressIdentifier] = useState<string>('');
  const [suppressChannel, setSuppressChannel] = useState<string>('all');
  const [suppressReason, setSuppressReason] = useState<string>('manual_suppression');

  const loadData = async () => {
    setLoading(true);
    try {
      const [fuData, suppData] = await Promise.all([
        api.getFollowups({ due_only: filterDueOnly }),
        api.getSuppressionList()
      ]);
      setFollowups(fuData.items || []);
      setSuppressionList(suppData || []);
    } catch (err) {
      console.error('Failed to load followups or suppression list:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filterDueOnly]);

  const handleMarkComplete = async (fu: FollowupTask) => {
    try {
      await api.updateFollowup(fu.id, {
        status: 'completed',
        completed_at: new Date().toISOString()
      });
      setFollowups(followups.map(f => f.id === fu.id ? { ...f, status: 'completed' } : f));
    } catch (err) {
      console.error('Failed to mark followup complete:', err);
    }
  };

  const handleAddSuppression = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!suppressIdentifier.trim()) return;
    try {
      await api.addSuppression({
        identifier: suppressIdentifier.trim(),
        channel: suppressChannel,
        reason: suppressReason
      });
      setShowSuppressionModal(false);
      setSuppressIdentifier('');
      const updated = await api.getSuppressionList();
      setSuppressionList(updated || []);
    } catch (err) {
      console.error('Failed to add suppression entry:', err);
    }
  };

  const handleRemoveSuppression = async (id: number) => {
    if (!window.confirm('Are you sure you want to remove this entry from suppression?')) return;
    try {
      await api.removeSuppression(id);
      setSuppressionList(suppressionList.filter(s => s.id !== id));
    } catch (err) {
      console.error('Failed to remove suppression entry:', err);
    }
  };

  const filteredFollowups = followups.filter(f => {
    if (filterStatus !== 'all' && f.status !== filterStatus) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const name = (f.company_name || '').toLowerCase();
      const notes = (f.notes || '').toLowerCase();
      const reason = (f.reason || '').toLowerCase();
      return name.includes(q) || notes.includes(q) || reason.includes(q);
    }
    return true;
  });

  const dueCount = followups.filter(f => {
    if (f.status === 'completed') return false;
    if (!f.due_date) return false;
    return new Date(f.due_date) <= new Date();
  }).length;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <Clock className="w-7 h-7 text-indigo-600" />
            <h1 className="text-2xl font-bold text-slate-900">Follow-Up & Operations Manager</h1>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Track multi-touch sales cadences, schedule reminders, and enforce strict suppression registry compliance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          {activeTab === 'suppression' && (
            <button
              onClick={() => setShowSuppressionModal(true)}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-lg transition shadow-sm"
            >
              <Plus className="w-4 h-4" />
              Add Suppression
            </button>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Follow-Up Tasks</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{followups.length}</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-semibold text-rose-600 uppercase tracking-wider flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" /> Due / Overdue
          </div>
          <div className="text-2xl font-bold text-rose-600 mt-1">{dueCount}</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-semibold text-emerald-600 uppercase tracking-wider flex items-center gap-1">
            <CheckCircle className="w-3.5 h-3.5" /> Completed
          </div>
          <div className="text-2xl font-bold text-emerald-700 mt-1">
            {followups.filter(f => f.status === 'completed').length}
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-xs font-semibold text-amber-600 uppercase tracking-wider flex items-center gap-1">
            <ShieldBan className="w-3.5 h-3.5" /> Suppression Registry
          </div>
          <div className="text-2xl font-bold text-amber-700 mt-1">{suppressionList.length}</div>
        </div>
      </div>

      {/* View Switcher Tabs */}
      <div className="border-b border-slate-200">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab('followups')}
            className={`pb-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
              activeTab === 'followups'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Calendar className="w-4 h-4" />
            Scheduled Follow-Ups ({followups.length})
          </button>
          <button
            onClick={() => setActiveTab('suppression')}
            className={`pb-3 text-sm font-semibold border-b-2 transition flex items-center gap-2 ${
              activeTab === 'suppression'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <ShieldBan className="w-4 h-4" />
            Suppression & Opt-Out Registry ({suppressionList.length})
          </button>
        </div>
      </div>

      {/* TAB 1: Follow-Ups List */}
      {activeTab === 'followups' && (
        <div className="space-y-4">
          {/* Controls Bar */}
          <div className="flex flex-col sm:flex-row justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
              <input
                type="text"
                placeholder="Search by company, reason, or notes..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filterDueOnly}
                  onChange={e => setFilterDueOnly(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                Show Due / Overdue Only
              </label>

              <select
                value={filterStatus}
                onChange={e => setFilterStatus(e.target.value)}
                className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="all">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="completed">Completed</option>
                <option value="follow_up_due">Follow-Up Due</option>
                <option value="not_contacted">Not Contacted</option>
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3 text-left">Company</th>
                  <th className="px-6 py-3 text-left">Scheduled Date</th>
                  <th className="px-6 py-3 text-left">Channel</th>
                  <th className="px-6 py-3 text-left">Reason / Next Action</th>
                  <th className="px-6 py-3 text-left">Status</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {filteredFollowups.map(fu => {
                  const isDue = fu.due_date && new Date(fu.due_date) <= new Date() && fu.status !== 'completed';
                  return (
                    <tr key={fu.id} className={isDue ? 'bg-rose-50/30' : 'hover:bg-slate-50/50'}>
                      <td className="px-6 py-4 font-medium text-slate-900">
                        {fu.company_name || `Lead #${fu.lead_id}`}
                      </td>
                      <td className="px-6 py-4 text-slate-600">
                        <div>{new Date(fu.scheduled_date).toLocaleDateString()}</div>
                        {fu.due_date && (
                          <div className={`text-xs ${isDue ? 'text-rose-600 font-semibold' : 'text-slate-400'}`}>
                            Due: {new Date(fu.due_date).toLocaleDateString()}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 capitalize">
                          {fu.suggested_channel === 'email' && <Mail className="w-3 h-3 text-blue-500" />}
                          {fu.suggested_channel === 'call' && <Phone className="w-3 h-3 text-emerald-500" />}
                          {fu.suggested_channel === 'whatsapp' && <MessageSquare className="w-3 h-3 text-green-500" />}
                          {fu.suggested_channel || 'email'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-slate-600 max-w-xs truncate">
                        <div>{fu.reason || 'Standard multi-touch follow-up'}</div>
                        {fu.notes && <div className="text-xs text-slate-400 truncate mt-0.5">{fu.notes}</div>}
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${
                          fu.status === 'completed'
                            ? 'bg-emerald-100 text-emerald-800'
                            : isDue
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}>
                          {fu.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        {fu.status !== 'completed' && (
                          <button
                            onClick={() => handleMarkComplete(fu)}
                            className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:text-emerald-900 bg-emerald-50 hover:bg-emerald-100 px-3 py-1.5 rounded-lg transition"
                          >
                            <CheckSquare className="w-3.5 h-3.5" />
                            Mark Done
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}

                {filteredFollowups.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-400 text-sm">
                      No follow-ups matching your current criteria.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: Suppression Registry */}
      {activeTab === 'suppression' && (
        <div className="space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-900 flex items-start gap-3">
            <ShieldBan className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-sm text-amber-950">Fail-Closed Suppression Engine</div>
              <p className="mt-0.5 leading-relaxed">
                Identifiers registered here (emails, domains, or phone numbers) are permanently blocked from AI outreach synthesis, automated follow-ups, and live email/WhatsApp sending.
              </p>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3 text-left">Suppressed Identifier / Domain</th>
                  <th className="px-6 py-3 text-left">Channel</th>
                  <th className="px-6 py-3 text-left">Reason</th>
                  <th className="px-6 py-3 text-left">Date Added</th>
                  <th className="px-6 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {suppressionList.map(item => (
                  <tr key={item.id} className="hover:bg-slate-50/50">
                    <td className="px-6 py-4 font-mono font-medium text-slate-900">
                      {item.identifier}
                    </td>
                    <td className="px-6 py-4 capitalize text-slate-600">
                      {item.channel}
                    </td>
                    <td className="px-6 py-4 text-slate-600">
                      <span className="px-2.5 py-0.5 text-xs bg-slate-100 text-slate-700 rounded">
                        {item.reason}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-500 text-xs">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleRemoveSuppression(item.id)}
                        className="text-rose-600 hover:text-rose-800 p-1.5 hover:bg-rose-50 rounded transition"
                        title="Remove from suppression"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}

                {suppressionList.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-slate-400 text-sm">
                      Suppression registry is currently empty.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal: Add to Suppression */}
      {showSuppressionModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-bold text-slate-900 text-base">Add Identifier to Suppression</h3>
              <button onClick={() => setShowSuppressionModal(false)} className="text-slate-400 hover:text-slate-600">
                ✕
              </button>
            </div>
            <form onSubmit={handleAddSuppression} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Email Address, Phone, or Domain
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. user@prospect.com, example.com, +91..."
                  value={suppressIdentifier}
                  onChange={e => setSuppressIdentifier(e.target.value)}
                  className="w-full text-sm px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Channel Scope</label>
                <select
                  value={suppressChannel}
                  onChange={e => setSuppressChannel(e.target.value)}
                  className="w-full text-sm px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                >
                  <option value="all">All Channels (Complete Opt-Out)</option>
                  <option value="email">Email Only</option>
                  <option value="whatsapp">WhatsApp Only</option>
                  <option value="linkedin">LinkedIn Only</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Reason</label>
                <select
                  value={suppressReason}
                  onChange={e => setSuppressReason(e.target.value)}
                  className="w-full text-sm px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-500"
                >
                  <option value="user_opt_out">User Opt-Out / Unsubscribe</option>
                  <option value="explicit_refusal">Explicit Refusal</option>
                  <option value="bounce_complaint">Email Bounce / Spam Complaint</option>
                  <option value="manual_suppression">Manual Operator Suppression</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowSuppressionModal(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm"
                >
                  Confirm Suppression
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
