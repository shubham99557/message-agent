import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Company } from '../types';
import {
  Linkedin,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Copy,
  Send,
  AlertTriangle,
  Plus,
} from 'lucide-react';

interface LinkedInViewProps {
  selectedCompany?: Company | null;
}

export const LinkedInView: React.FC<LinkedInViewProps> = ({ selectedCompany }) => {
  const [status, setStatus] = useState<any>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [companyId, setCompanyId] = useState<number | ''>(selectedCompany?.id ?? '');
  const [profileUrl, setProfileUrl] = useState(selectedCompany?.linkedin_url ?? '');
  const [recipientName, setRecipientName] = useState(selectedCompany?.decision_maker_name ?? '');
  const [messageType, setMessageType] = useState<'connection_note' | 'direct_message' | 'follow_up'>('connection_note');
  const [tone, setTone] = useState('Consultative');
  const [customMessage, setCustomMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [st, comps, msgs] = await Promise.all([
        api.getLinkedInStatus().catch(() => null),
        api.getCompanies({ limit: 100 }).catch(() => ({ items: [] })),
        api.getLinkedInMessages().catch(() => []),
      ]);
      setStatus(st);
      setCompanies(comps.items || []);
      setMessages(msgs || []);
      if (!companyId && comps.items?.length) {
        const first = comps.items[0];
        setCompanyId(first.id);
        setProfileUrl(first.linkedin_url || '');
        setRecipientName(first.decision_maker_name || '');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCompanyChange = (id: number) => {
    setCompanyId(id);
    const found = companies.find((c) => c.id === id);
    if (found) {
      setProfileUrl(found.linkedin_url || '');
      setRecipientName(found.decision_maker_name || '');
    }
  };

  const handleCreateDraft = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyId) return;
    setSubmitting(true);
    setFeedback(null);
    try {
      await api.draftLinkedInMessage({
        company_id: Number(companyId),
        recipient_name: recipientName || undefined,
        recipient_profile_url: profileUrl || undefined,
        message_type: messageType,
        tone,
        custom_message: customMessage.trim() || undefined,
      });
      setCustomMessage('');
      setFeedback('LinkedIn outreach draft created and queued for mandatory human approval.');
      await loadData();
    } catch (err: any) {
      alert(`Draft error: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprove = async (id: number) => {
    try {
      await api.approveLinkedInMessage(id);
      await loadData();
    } catch (err: any) {
      alert(`Approve error: ${err.message}`);
    }
  };

  const handleReject = async (id: number) => {
    const reason = prompt('Enter rejection reason:');
    if (!reason) return;
    try {
      await api.rejectLinkedInMessage(id, reason);
      await loadData();
    } catch (err: any) {
      alert(`Reject error: ${err.message}`);
    }
  };

  const handleDispatch = async (id: number) => {
    try {
      const res = await api.dispatchLinkedInMessage(id);
      if (res.status === 'ready_for_manual_send') {
        setFeedback('Prepared for compliant human-assisted handoff. Copy the approved message, send inside LinkedIn, then click Confirm Manual Send.');
      } else {
        setFeedback(`Dispatched via Authorized LinkedIn Partner API (ID: ${res.provider_message_id}).`);
      }
      await loadData();
    } catch (err: any) {
      alert(`Dispatch error: ${err.message}`);
    }
  };

  const handleConfirmManual = async (id: number) => {
    try {
      await api.confirmLinkedInManualSend(id, 'Confirmed sent manually inside LinkedIn');
      setFeedback('Manual LinkedIn outreach logged to CRM & Audit Log.');
      await loadData();
    } catch (err: any) {
      alert(`Confirm error: ${err.message}`);
    }
  };

  const maxChars = messageType === 'connection_note' ? 300 : 1900;

  return (
    <div className="p-6 space-y-6">
      {/* Honest Connection & Compliance Banner */}
      <div className="bg-cobalt-900/90 border border-cobalt-800 rounded-lg p-4 space-y-2">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-sky-500/15 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <Linkedin className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-sm font-bold text-slate-100">Official LinkedIn Outreach Workspace</h2>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${
                    status?.connected
                      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                      : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                  }`}
                >
                  OAuth: {status?.status || 'disconnected'}
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cobalt-950 border border-cobalt-700 text-slate-300">
                  Mode: {status?.active_mode || 'manual_handoff_only'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {status?.mode_summary ||
                  'Uses official LinkedIn OAuth 2.0 and compliant human-assisted handoff. No passwords, cookies, or scraping.'}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-1.5 text-[11px] text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 rounded px-2.5 py-1.5 shrink-0">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Zero Cookie / Scraping Policy Enforced</span>
          </div>
        </div>
      </div>

      {feedback && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-300 flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {/* Draft Generator Panel */}
      <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5">
        <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-3">
          Draft Compliant LinkedIn Outreach
        </h3>
        <form onSubmit={handleCreateDraft} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Target Company *</label>
              <select
                required
                value={companyId}
                onChange={(e) => handleCompanyChange(Number(e.target.value))}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200"
              >
                <option value="">Select company...</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.city})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] text-slate-400 mb-1">LinkedIn Profile / Company URL *</label>
              <input
                required
                type="url"
                placeholder="https://www.linkedin.com/in/..."
                value={profileUrl}
                onChange={(e) => setProfileUrl(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200 font-mono"
              />
            </div>

            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Recipient Name</label>
              <input
                type="text"
                placeholder="Decision maker name"
                value={recipientName}
                onChange={(e) => setRecipientName(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200"
              />
            </div>

            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Message Type</label>
              <select
                value={messageType}
                onChange={(e) => setMessageType(e.target.value as any)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-slate-200"
              >
                <option value="connection_note">Connection Note (300 char max)</option>
                <option value="direct_message">Direct Message (1900 char max)</option>
                <option value="follow_up">Follow-Up Message</option>
              </select>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-[11px] text-slate-400">
                Custom Message (leave blank to auto-generate ActTrident 90-day evaluation copy)
              </label>
              <span className={`text-[10px] font-mono ${customMessage.length > maxChars ? 'text-rose-400' : 'text-slate-400'}`}>
                {customMessage.length} / {maxChars} chars
              </span>
            </div>
            <textarea
              rows={3}
              value={customMessage}
              onChange={(e) => setCustomMessage(e.target.value)}
              placeholder="Optional custom message — or leave blank to generate compliant ActTrident outreach..."
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded p-2.5 text-slate-200"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting || customMessage.length > maxChars}
              className="px-4 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-medium flex items-center space-x-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>{submitting ? 'Creating Draft...' : 'Create LinkedIn Draft'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* LinkedIn Outreach Queue */}
      <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg overflow-hidden">
        <div className="p-4 border-b border-cobalt-800 flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-200">
            LinkedIn Approval & Handoff Queue ({messages.length})
          </h3>
          <span className="text-[11px] text-slate-400 font-mono">
            Mandatory Human Approval • Content-Hash Verified
          </span>
        </div>

        {loading ? (
          <div className="p-10 text-center text-xs text-slate-400">Loading LinkedIn outreach queue...</div>
        ) : messages.length === 0 ? (
          <div className="p-10 text-center text-xs text-slate-400">
            No LinkedIn outreach drafts yet. Create one above to start the approval workflow.
          </div>
        ) : (
          <div className="divide-y divide-cobalt-800/60">
            {messages.map((m) => (
              <div key={m.id} className="p-4 space-y-2.5 text-xs">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                  <div className="flex items-center flex-wrap gap-2">
                    <span className="font-semibold text-slate-100">{m.company_name || `Company #${m.company_id}`}</span>
                    {m.recipient_name && <span className="text-slate-400">• {m.recipient_name}</span>}
                    <span className="px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 text-[10px] font-mono text-slate-300">
                      {m.message_type}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                        m.approval_status === 'sent_via_api' || m.approval_status === 'manually_sent_confirmed'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                          : m.approval_status === 'approved' || m.approval_status === 'ready_for_manual_send'
                          ? 'bg-sky-500/20 text-sky-300 border-sky-500/30'
                          : m.approval_status === 'rejected' || m.approval_status === 'failed'
                          ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                          : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                      }`}
                    >
                      {m.approval_status}
                    </span>
                  </div>

                  <div className="flex items-center flex-wrap gap-1.5">
                    <a
                      href={m.recipient_profile_url}
                      target="_blank"
                      rel="noreferrer"
                      className="px-2 py-1 rounded bg-cobalt-950 hover:bg-cobalt-800 border border-cobalt-700 text-sky-300 text-[11px] flex items-center space-x-1"
                    >
                      <span>Open Profile</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(m.message_body);
                        setFeedback('Approved message copied to clipboard.');
                      }}
                      className="px-2 py-1 rounded bg-cobalt-950 hover:bg-cobalt-800 border border-cobalt-700 text-slate-300 text-[11px] flex items-center space-x-1"
                    >
                      <Copy className="w-3 h-3" />
                      <span>Copy</span>
                    </button>

                    {m.approval_status === 'draft' && (
                      <>
                        <button
                          onClick={() => handleApprove(m.id)}
                          className="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-medium"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleReject(m.id)}
                          className="px-2.5 py-1 rounded bg-rose-950/60 hover:bg-rose-900/70 border border-rose-700/50 text-rose-300 text-[11px]"
                        >
                          Reject
                        </button>
                      </>
                    )}

                    {m.approval_status === 'approved' && (
                      <button
                        onClick={() => handleDispatch(m.id)}
                        className="px-2.5 py-1 rounded bg-cobalt-600 hover:bg-cobalt-500 text-white text-[11px] font-medium flex items-center space-x-1"
                      >
                        <Send className="w-3 h-3" />
                        <span>{status?.direct_messaging_api_approved ? 'Send via Partner API' : 'Prepare Manual Handoff'}</span>
                      </button>
                    )}

                    {m.approval_status === 'ready_for_manual_send' && (
                      <button
                        onClick={() => handleConfirmManual(m.id)}
                        className="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-medium flex items-center space-x-1"
                      >
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Confirm Manual Send</span>
                      </button>
                    )}
                  </div>
                </div>

                <p className="text-slate-300 bg-cobalt-950/70 p-3 rounded border border-cobalt-800/70 whitespace-pre-wrap leading-relaxed">
                  {m.message_body}
                </p>

                {m.rejection_reason && (
                  <div className="text-[11px] text-rose-300 flex items-center space-x-1">
                    <XCircle className="w-3.5 h-3.5" />
                    <span>Rejected: {m.rejection_reason}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
