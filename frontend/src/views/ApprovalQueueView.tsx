import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { EmailDraft } from '../types';
import {
  CheckSquare,
  Check,
  X,
  SkipForward,
  Edit3,
  Send,
  Building2,
  ExternalLink,
  ShieldCheck,
  Clock,
  Layers,
  Save,
  RefreshCw,
  Calendar,
  Copy,
  CheckCircle2
} from 'lucide-react';

export const ApprovalQueueView: React.FC = () => {
  const [drafts, setDrafts] = useState<EmailDraft[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('draft');
  const [editingDraft, setEditingDraft] = useState<EmailDraft | null>(null);
  const [editSubject, setEditSubject] = useState('');
  const [editBody, setEditBody] = useState('');
  const [emailMode, setEmailMode] = useState<any>(null);
  const [manualSendDraft, setManualSendDraft] = useState<EmailDraft | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const loadQueue = async () => {
    setLoading(true);
    try {
      const [data, mode] = await Promise.all([
        api.getApprovalQueue(statusFilter),
        api.getGmailStatus().catch(() => null),
      ]);
      setDrafts(data.items);
      setEmailMode(mode);
      setSelectedIds([]);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, [statusFilter]);

  const handleApprove = async (id: number) => {
    try {
      await api.approveEmail(id);
      loadQueue();
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    }
  };

  const handleReject = async (id: number) => {
    const reason = prompt('Please enter rejection reason:', 'Message requires repositioning');
    if (!reason) return;
    try {
      await api.rejectEmail(id, reason);
      loadQueue();
    } catch (err: any) {
      alert(`Reject error: ${err.message}`);
    }
  };

  const handleSkip = async (id: number) => {
    try {
      await api.skipEmail(id);
      loadQueue();
    } catch (err: any) {
      alert(`Skip error: ${err.message}`);
    }
  };

  const handleRegenerate = async (id: number) => {
    const tone = prompt('Select tone: Friendly professional, Formal, Technical, Short introductory, Follow-up', 'Friendly professional');
    if (!tone) return;
    try {
      await api.regenerateEmailDraft(id, tone);
      alert('Draft regenerated successfully and reset to draft status for human review.');
      loadQueue();
    } catch (err: any) {
      alert(`Regeneration error: ${err.message}`);
    }
  };

  const handleSchedule = async (id: number) => {
    const defaultTime = new Date(Date.now() + 3600 * 1000 * 24).toISOString().slice(0, 16);
    const timeStr = prompt('Enter scheduled dispatch time (YYYY-MM-DDTHH:MM):', defaultTime);
    if (!timeStr) return;
    try {
      const scheduledIso = new Date(timeStr).toISOString();
      await api.scheduleEmailDraft(id, scheduledIso);
      alert(`Draft scheduled for ${timeStr} IST.`);
      loadQueue();
    } catch (err: any) {
      alert(`Schedule error: ${err.message}`);
    }
  };

  const handleBulkApprove = async () => {
    if (selectedIds.length === 0) return;
    try {
      await api.bulkApprovalAction(selectedIds, 'approve');
      alert(`Approved ${selectedIds.length} drafts for outbound dispatch.`);
      loadQueue();
    } catch (err: any) {
      alert(`Bulk approval error: ${err.message}`);
    }
  };

  const openEditModal = (d: EmailDraft) => {
    setEditingDraft(d);
    setEditSubject(d.subject);
    setEditBody(d.body_text);
  };

  const handleSaveEdit = async () => {
    if (!editingDraft) return;
    try {
      await api.updateEmailDraft(editingDraft.id, {
        subject: editSubject,
        body_text: editBody
      });
      await api.approveEmail(editingDraft.id);
      setEditingDraft(null);
      loadQueue();
    } catch (err: any) {
      alert(`Save error: ${err.message}`);
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const selectAll = () => {
    if (selectedIds.length === drafts.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(drafts.map((d) => d.id));
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 tracking-tight">Mandatory Human Approval Queue</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Every outbound message requires explicit human review and approval before leaving the system.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {selectedIds.length > 0 && statusFilter === 'draft' && (
            <button
              onClick={handleBulkApprove}
              className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1 shadow-sm"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Approve Selected ({selectedIds.length})</span>
            </button>
          )}

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-cobalt-950 border border-cobalt-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
          >
            <option value="draft">Pending Approval (Drafts)</option>
            <option value="approved">Approved</option>
            <option value="sent">Dispatched (Sent)</option>
            <option value="simulated">Simulated (Mock)</option>
            <option value="rejected">Rejected</option>
            <option value="skipped">Skipped</option>
            <option value="All">All Records</option>
          </select>
        </div>
      </div>

      {/* Honest Simulation / Provider Mode Banner */}
      {emailMode && (
        <div
          className={`p-3 rounded-lg border text-xs flex items-center justify-between ${
            emailMode.is_simulation
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-200'
              : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
          }`}
        >
          <span>
            {emailMode.is_simulation
              ? 'SIMULATION MODE ACTIVE: Emails sent from this queue are recorded as simulated locally and will NOT be transmitted externally.'
              : `LIVE EMAIL PROVIDER CONNECTED: Dispatching via ${emailMode.active_mode.toUpperCase()}${emailMode.gmail?.account_email ? ` (${emailMode.gmail.account_email})` : ''}.`}
          </span>
          <span className="font-mono text-[10px] uppercase px-2 py-0.5 rounded bg-black/30">
            {emailMode.active_mode}
          </span>
        </div>
      )}

      {/* Drafts List / Cards */}
      {loading ? (
        <div className="p-16 text-center text-xs text-slate-400">Loading queue items...</div>
      ) : drafts.length === 0 ? (
        <div className="bg-cobalt-900/60 border border-cobalt-800 rounded-lg p-16 text-center text-xs text-slate-400 space-y-2">
          <CheckSquare className="w-8 h-8 mx-auto text-cobalt-600 opacity-60" />
          <p className="font-semibold text-slate-200">No messages in '{statusFilter}' status.</p>
          <p className="text-[11px] text-slate-400">Generate personalized emails from 'Email Outreach' or 'Campaigns'.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400 px-1">
            <button onClick={selectAll} className="hover:text-slate-200 font-medium">
              {selectedIds.length === drafts.length ? 'Deselect All' : 'Select All'}
            </button>
            <span>Showing {drafts.length} queue items</span>
          </div>

          {drafts.map((draft) => (
            <div
              key={draft.id}
              className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 space-y-4 hover:border-cobalt-700 transition-colors"
            >
              {/* Card Header & Verification Metadata */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cobalt-800 pb-3">
                <div className="flex items-start space-x-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(draft.id)}
                    onChange={() => toggleSelect(draft.id)}
                    className="mt-1 rounded bg-cobalt-950 border-cobalt-800 text-cobalt-600 focus:ring-0"
                  />
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-slate-100 text-sm">{draft.company_name || 'B2B Account'}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 text-slate-300">
                        {draft.company_city || 'Regional'}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 text-cobalt-300 uppercase">
                        {draft.campaign_name || 'Direct Outreach'}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5 flex flex-wrap items-center gap-x-3">
                      <span>Recipient: <strong className="text-slate-300">{draft.recipient_name || 'Lead'}</strong> &lt;{draft.recipient_email}&gt;</span>
                      <span>Source: <a href={draft.contact_source_url || '#'} target="_blank" rel="noreferrer" className="text-cobalt-400 hover:underline">{draft.contact_source_url ? 'Verified URL' : 'Direct'}</a></span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded uppercase border ${
                      draft.approval_status === 'approved'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                        : draft.approval_status === 'sent'
                        ? 'bg-cobalt-500/20 text-cobalt-300 border-cobalt-500/30'
                        : draft.approval_status === 'rejected'
                        ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                    }`}
                  >
                    {draft.approval_status}
                  </span>
                </div>
              </div>

              {/* Message Subject & Body */}
              <div className="space-y-2 text-xs">
                <div className="font-medium text-slate-200">
                  <span className="text-slate-400">Subject: </span>
                  {draft.subject}
                </div>
                <div className="bg-cobalt-950 p-4 rounded border border-cobalt-800/80 text-slate-300 whitespace-pre-wrap font-sans leading-relaxed max-h-56 overflow-y-auto">
                  {draft.body_text}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-2 border-t border-cobalt-800 text-xs">
                <div className="text-[11px] text-slate-400 font-mono">
                  Channel: <strong>EMAIL ({draft.provider.toUpperCase()})</strong> • Tone: <strong>{draft.tone}</strong>
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => openEditModal(draft)}
                    className="px-2.5 py-1 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium flex items-center space-x-1"
                  >
                    <Edit3 className="w-3 h-3 text-cobalt-400" />
                    <span>Edit</span>
                  </button>

                  <button
                    onClick={() => handleRegenerate(draft.id)}
                    className="px-2.5 py-1 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium flex items-center space-x-1"
                    title="Request AI regeneration with different tone or notes"
                  >
                    <RefreshCw className="w-3 h-3 text-amber-400" />
                    <span>Regenerate</span>
                  </button>

                  <button
                    onClick={() => handleSchedule(draft.id)}
                    className="px-2.5 py-1 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium flex items-center space-x-1"
                    title="Set target scheduled dispatch timestamp"
                  >
                    <Calendar className="w-3 h-3 text-cobalt-400" />
                    <span>Schedule</span>
                  </button>

                  {draft.approval_status === 'draft' && (
                    <>
                      <button
                        onClick={() => handleReject(draft.id)}
                        className="px-2.5 py-1 bg-cobalt-950 hover:bg-rose-950/40 border border-cobalt-700 hover:border-rose-700/50 text-rose-300 rounded text-xs font-medium flex items-center space-x-1"
                      >
                        <X className="w-3 h-3" />
                        <span>Reject</span>
                      </button>
                      <button
                        onClick={() => handleSkip(draft.id)}
                        className="px-2.5 py-1 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-300 rounded text-xs font-medium flex items-center space-x-1"
                      >
                        <SkipForward className="w-3 h-3" />
                        <span>Skip</span>
                      </button>
                      <button
                        onClick={() => handleApprove(draft.id)}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium flex items-center space-x-1 shadow-sm"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Approve</span>
                      </button>
                    </>
                  )}

                  {draft.approval_status === 'approved' && (
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setManualSendDraft(draft)}
                        className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-medium flex items-center space-x-1 shadow-sm"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        <span>Manual Send / Copy</span>
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            const res = await api.sendApprovedEmail(draft.id);
                            alert(res.message || `Email status: ${res.status}`);
                            loadQueue();
                          } catch (err: any) {
                            alert(`Notice: ${err.message}`);
                          }
                        }}
                        className="px-3 py-1 bg-cobalt-800 hover:bg-cobalt-700 text-slate-200 rounded text-xs font-medium flex items-center space-x-1 border border-cobalt-700"
                        title="Attempts provider dispatch if live sending is enabled"
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>Dispatch Engine</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Modal */}
      {editingDraft && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-cobalt-900 border border-cobalt-700 rounded-lg p-5 w-full max-w-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
              <h3 className="font-bold text-slate-100 text-sm">Edit & Approve Outreach Draft</h3>
              <button onClick={() => setEditingDraft(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Subject</label>
                <input
                  type="text"
                  value={editSubject}
                  onChange={(e) => setEditSubject(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Message Body</label>
                <textarea
                  rows={12}
                  value={editBody}
                  onChange={(e) => setEditBody(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded p-2.5 text-xs text-slate-200 font-sans leading-relaxed"
                ></textarea>
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingDraft(null)}
                  className="px-3 py-1.5 bg-cobalt-950 text-slate-300 rounded text-xs"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveEdit}
                  className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium flex items-center space-x-1"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>Save & Mark Approved</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Manual Send & Copy Modal */}
      {manualSendDraft && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-cobalt-900 border border-cobalt-700 rounded-xl p-6 w-full max-w-2xl space-y-4 text-xs shadow-2xl">
            <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
              <div>
                <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  Manual Outbound Send & Clipboard Verification
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Fail-closed protocol: copy vetted content into your corporate email or communication client.
                </p>
              </div>
              <button
                onClick={() => { setManualSendDraft(null); setCopyFeedback(null); }}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              {/* Recipient */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-[11px] font-semibold text-slate-300">Recipient</label>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(manualSendDraft.recipient_email || '');
                      setCopyFeedback('recipient');
                      setTimeout(() => setCopyFeedback(null), 2000);
                    }}
                    className="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-mono"
                  >
                    <Copy className="w-3 h-3" />
                    {copyFeedback === 'recipient' ? 'Copied!' : 'Copy Email'}
                  </button>
                </div>
                <div className="p-2 bg-cobalt-950 border border-cobalt-800 rounded font-mono text-slate-200">
                  {manualSendDraft.recipient_name ? `${manualSendDraft.recipient_name} <${manualSendDraft.recipient_email}>` : manualSendDraft.recipient_email}
                </div>
              </div>

              {/* Subject */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-[11px] font-semibold text-slate-300">Subject Line</label>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(manualSendDraft.subject);
                      setCopyFeedback('subject');
                      setTimeout(() => setCopyFeedback(null), 2000);
                    }}
                    className="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-mono"
                  >
                    <Copy className="w-3 h-3" />
                    {copyFeedback === 'subject' ? 'Copied!' : 'Copy Subject'}
                  </button>
                </div>
                <div className="p-2 bg-cobalt-950 border border-cobalt-800 rounded text-slate-200 font-medium">
                  {manualSendDraft.subject}
                </div>
              </div>

              {/* Body */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-[11px] font-semibold text-slate-300">Outreach Body</label>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(manualSendDraft.body_text);
                      setCopyFeedback('body');
                      setTimeout(() => setCopyFeedback(null), 2000);
                    }}
                    className="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-mono"
                  >
                    <Copy className="w-3 h-3" />
                    {copyFeedback === 'body' ? 'Copied!' : 'Copy Body'}
                  </button>
                </div>
                <pre className="p-3 bg-cobalt-950 border border-cobalt-800 rounded text-slate-300 font-sans text-xs whitespace-pre-wrap max-h-60 overflow-y-auto leading-relaxed">
                  {manualSendDraft.body_text}
                </pre>
              </div>

              {/* Actions */}
              <div className="flex justify-between items-center pt-3 border-t border-cobalt-800">
                <span className="text-[10px] text-slate-500 font-mono">
                  Channel: {manualSendDraft.provider || 'Corporate Email'} • Status: Approved
                </span>
                <div className="flex space-x-2">
                  <button
                    onClick={() => { setManualSendDraft(null); setCopyFeedback(null); }}
                    className="px-3 py-1.5 bg-cobalt-950 text-slate-400 hover:text-slate-200 rounded text-xs"
                  >
                    Close
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        await api.updateEmailDraft(manualSendDraft.id, {
                          approval_status: 'sent'
                        });
                        alert('Marked as sent manually. Record transitioned to sent state.');
                        setManualSendDraft(null);
                        loadQueue();
                      } catch (err: any) {
                        alert(`Error: ${err.message}`);
                      }
                    }}
                    className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium flex items-center space-x-1.5 shadow-sm"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Confirm Sent Manually</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
