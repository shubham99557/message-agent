import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Company, ViewType } from '../types';
import {
  MessageSquare,
  CheckCircle2,
  AlertTriangle,
  Send,
  ExternalLink,
  ShieldAlert,
  FileCheck,
  Plus,
  Lock,
  Clock
} from 'lucide-react';

interface WhatsAppViewProps {
  selectedCompany?: Company | null;
  onNavigate: (view: ViewType) => void;
}

export const WhatsAppView: React.FC<WhatsAppViewProps> = ({ selectedCompany }) => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [activeCompanyId, setActiveCompanyId] = useState<number | null>(selectedCompany?.id ?? null);
  const [activeCompany, setActiveCompany] = useState<Company | null>(selectedCompany ?? null);
  const [templates, setTemplates] = useState<any[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState('acttrident_intro_utility_v1');
  const [recipientPhone, setRecipientPhone] = useState('');
  const [messages, setMessages] = useState<any[]>([]);
  const [draftResult, setDraftResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [waStatus, setWaStatus] = useState<any>(null);
  const [syncingTemplates, setSyncingTemplates] = useState(false);
  const [checkingHealth, setCheckingHealth] = useState(false);

  // Consent modal / recording state
  const [showConsentModal, setShowConsentModal] = useState(false);
  const [consentSource, setConsentSource] = useState('Inbound Website Contact Form');
  const [consentProof, setConsentProof] = useState('https://acttrident.ai/inbound/form-entry');

  const loadData = async () => {
    try {
      const [comps, tmpls, msgs, statusInfo] = await Promise.all([
        api.getCompanies({ limit: 100 }),
        api.getWhatsAppTemplates(true),
        api.getWhatsAppMessages(),
        api.getWhatsAppStatus().catch(() => null),
      ]);
      setCompanies(comps.items);
      setTemplates(tmpls);
      setMessages(msgs);
      setWaStatus(statusInfo);

      if (!activeCompanyId && comps.items.length > 0) {
        setActiveCompanyId(comps.items[0].id);
        setActiveCompany(comps.items[0]);
        setRecipientPhone(comps.items[0].public_whatsapp || comps.items[0].public_phone || '');
      } else if (selectedCompany) {
        setRecipientPhone(selectedCompany.public_whatsapp || selectedCompany.public_phone || '');
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSyncTemplates = async () => {
    setSyncingTemplates(true);
    try {
      const res = await api.syncWhatsAppTemplates();
      alert(`Meta template sync complete: ${res.synced_templates} templates synced (${res.approved_templates} approved).`);
      await loadData();
    } catch (err: any) {
      alert(`Template sync error: ${err.message}`);
    } finally {
      setSyncingTemplates(false);
    }
  };

  const handleCheckHealth = async () => {
    setCheckingHealth(true);
    try {
      const res = await api.checkWhatsAppHealth();
      alert(`Meta Cloud API Connected: ${res.verified_name || res.display_phone_number} (Quality: ${res.quality_rating || 'N/A'})`);
      await loadData();
    } catch (err: any) {
      alert(`Health check error: ${err.message}`);
    } finally {
      setCheckingHealth(false);
    }
  };

  const handleCompanyChange = (id: number) => {
    setActiveCompanyId(id);
    const found = companies.find((c) => c.id === id);
    if (found) {
      setActiveCompany(found);
      setRecipientPhone(found.public_whatsapp || found.public_phone || '');
    }
    setDraftResult(null);
  };

  const handleCreateDraft = async () => {
    if (!activeCompanyId) return;
    setLoading(true);
    try {
      const msg = await api.draftWhatsApp({
        company_id: activeCompanyId,
        template_name: selectedTemplate,
        recipient_phone: recipientPhone || undefined,
        parameters: {
          '1': activeCompany?.decision_maker_name || 'Team Lead',
          '2': activeCompany?.city || 'Siliguri'
        }
      });
      setDraftResult(msg);
      // Refresh messages list
      const msgs = await api.getWhatsAppMessages();
      setMessages(msgs);
    } catch (err: any) {
      alert(`WhatsApp error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRecordConsent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeCompanyId) return;
    try {
      await api.recordWhatsAppConsent({
        company_id: activeCompanyId,
        contact_identifier: recipientPhone || activeCompany?.public_whatsapp || activeCompany?.public_phone || undefined,
        channel: 'whatsapp',
        consent_status: 'opted_in',
        consent_source: consentSource,
        consent_purpose: 'ActTrident 90-day evaluation demonstration inquiry',
        proof_reference: consentProof
      });
      alert('Documented consent recorded successfully! You may now generate approved Meta Cloud API drafts.');
      setShowConsentModal(false);
      handleCreateDraft();
    } catch (err: any) {
      alert(`Consent recording error: ${err.message}`);
    }
  };

  const handleSendApproved = async (msgId: number) => {
    try {
      const res = await api.sendWhatsApp(msgId);
      alert(res.message || 'WhatsApp dispatch processed.');
      const msgs = await api.getWhatsAppMessages();
      setMessages(msgs);
    } catch (err: any) {
      alert(`Send error: ${err.message}`);
    }
  };

  const handleApprove = async (msgId: number) => {
    try {
      await api.approveWhatsApp(msgId);
      const msgs = await api.getWhatsAppMessages();
      setMessages(msgs);
      if (draftResult?.id === msgId) {
        setDraftResult({ ...draftResult, approval_status: 'approved' });
      }
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Honest Meta Cloud API / Simulation Mode Status Bar */}
      {waStatus && (
        <div
          className={`p-3.5 rounded-lg border text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
            waStatus.is_simulation
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-200'
              : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
          }`}
        >
          <div>
            <div className="font-semibold">
              {waStatus.is_simulation
                ? 'SIMULATION MODE ACTIVE — Official Meta WhatsApp Cloud API credentials not configured'
                : `META WHATSAPP CLOUD API CONFIGURED (${waStatus.display_name || waStatus.phone_number_id})`}
            </div>
            <div className="text-[11px] opacity-80 mt-0.5">
              Meta-synced templates: {waStatus.synced_templates_count} • Local seed templates: {waStatus.local_seed_templates_count} • Webhook HMAC Secret: {waStatus.webhook_secret_configured ? 'Configured' : 'Missing'}
            </div>
          </div>
          <div className="flex items-center space-x-2 shrink-0">
            <button
              onClick={handleCheckHealth}
              disabled={checkingHealth}
              className="px-2.5 py-1 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-[11px] font-medium disabled:opacity-50"
            >
              {checkingHealth ? 'Checking...' : 'Check Meta Health'}
            </button>
            <button
              onClick={handleSyncTemplates}
              disabled={syncingTemplates}
              className="px-2.5 py-1 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-[11px] font-medium disabled:opacity-50"
            >
              {syncingTemplates ? 'Syncing...' : 'Sync Meta Templates'}
            </button>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="bg-cobalt-900/90 border border-cobalt-800 rounded-lg p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
            <MessageSquare className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-100 tracking-tight">Official Meta WhatsApp Business Cloud API</h2>
            <p className="text-xs text-slate-400">Strict consent enforcement: Unsolicited promotional messaging is blocked by policy.</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowConsentModal(true)}
            className="px-3 py-1.5 bg-cobalt-900 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium transition-colors flex items-center space-x-1"
          >
            <FileCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Record Valid Consent</span>
          </button>
        </div>
      </div>

      {/* Compliance Policy Notice */}
      <div className="bg-cobalt-950/80 border border-cobalt-800 p-4 rounded-lg flex items-start space-x-3 text-xs">
        <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="space-y-1 text-slate-300">
          <span className="font-semibold text-slate-100 block">WhatsApp Outreach Guardrails:</span>
          <p>
            1. Meta requires documented, valid permission for promotional outreach. Unconsented phone numbers are provided with a compliant click-to-chat link for manual contact.
          </p>
          <p>
            2. Only pre-approved Meta Cloud API templates (Utility / Marketing) can initiate conversations. Unofficial QR bots are strictly prohibited.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Draft Message Form */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 space-y-4 text-xs">
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Configure WhatsApp Message</h3>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Target Account</label>
            <select
              value={activeCompanyId ?? ''}
              onChange={(e) => handleCompanyChange(Number(e.target.value))}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
            >
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.city})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Recipient Number</label>
            <input
              type="text"
              value={recipientPhone}
              onChange={(e) => setRecipientPhone(e.target.value)}
              placeholder="+91-9800000000"
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 font-mono"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Approved Meta Template</label>
            <select
              value={selectedTemplate}
              onChange={(e) => setSelectedTemplate(e.target.value)}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 font-mono text-[11px]"
            >
              {templates.map((t) => (
                <option key={t.id} value={t.meta_template_name}>
                  {t.meta_template_name} ({t.status})
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleCreateDraft}
            disabled={loading || !recipientPhone}
            className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors flex items-center justify-center space-x-1.5 shadow-sm"
          >
            <span>Generate Template Draft</span>
          </button>
        </div>

        {/* Right 2 Columns: Draft Result & Delivery Logs */}
        <div className="lg:col-span-2 space-y-6">
          {/* Active Draft Card */}
          {draftResult && (
            <div className="bg-cobalt-900/90 border border-cobalt-800 rounded-lg p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
                <span className="text-xs font-semibold text-slate-200">Generated WhatsApp Message</span>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                    draftResult.has_valid_consent
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  }`}
                >
                  {draftResult.has_valid_consent ? 'Documented Consent Verified' : 'Unconsented Lead'}
                </span>
              </div>

              <div className="bg-cobalt-950 p-4 rounded border border-cobalt-800 text-xs text-slate-200 font-sans leading-relaxed whitespace-pre-wrap">
                {draftResult.message_text}
              </div>

              {/* If Unconsented: Show Click-to-Chat fallback link */}
              {!draftResult.has_valid_consent && draftResult.click_to_chat_url && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded text-xs text-amber-200 space-y-2">
                  <div className="font-semibold text-amber-300 flex items-center space-x-1">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    <span>Automated Cloud API Send Blocked (Strict Compliance)</span>
                  </div>
                  <p className="text-[11px] text-amber-300/80">
                    To comply with Meta policies and privacy regulations, use this click-to-chat link for manual, appropriate business conversation:
                  </p>
                  <a
                    href={draftResult.click_to_chat_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium"
                  >
                    <span>Open in WhatsApp (wa.me)</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              )}

              {/* If Consented: Allow Approval and Cloud API Dispatch */}
              {draftResult.has_valid_consent && (
                <div className="flex items-center justify-between pt-2">
                  <div className="text-[11px] text-slate-400 font-mono">
                    Approval Status: <strong>{draftResult.approval_status.toUpperCase()}</strong>
                  </div>
                  <div className="flex items-center space-x-2">
                    {draftResult.approval_status !== 'approved' ? (
                      <button
                        onClick={() => handleApprove(draftResult.id)}
                        className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded text-xs font-medium"
                      >
                        Approve for Dispatch
                      </button>
                    ) : (
                      <button
                        onClick={() => handleSendApproved(draftResult.id)}
                        className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium flex items-center space-x-1"
                      >
                        <Send className="w-3.5 h-3.5" />
                        <span>Send via Meta Cloud API</span>
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Delivery History Table */}
          <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg overflow-hidden">
            <div className="p-3.5 border-b border-cobalt-800 flex items-center justify-between text-xs font-semibold text-slate-200">
              <span>WhatsApp Message Logs ({messages.length})</span>
              <span className="text-[11px] font-mono text-slate-400">Meta Webhook Synchronized</span>
            </div>
            {messages.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">No WhatsApp messages dispatched yet.</div>
            ) : (
              <div className="overflow-x-auto text-xs">
                <table className="w-full text-left">
                  <thead className="bg-cobalt-950/60 text-slate-400 border-b border-cobalt-800/80">
                    <tr>
                      <th className="py-2.5 px-3">Recipient Phone</th>
                      <th className="py-2.5 px-3">Consent</th>
                      <th className="py-2.5 px-3">Delivery Status</th>
                      <th className="py-2.5 px-3">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-cobalt-800/40 text-slate-200">
                    {messages.map((m) => (
                      <tr key={m.id} className="hover:bg-cobalt-850/50">
                        <td className="py-2.5 px-3 font-mono">{m.recipient_phone}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                              m.has_valid_consent ? 'text-emerald-300 bg-emerald-500/20' : 'text-amber-300 bg-amber-500/20'
                            }`}
                          >
                            {m.has_valid_consent ? 'Consented' : 'Unconsented'}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono capitalize text-cobalt-300">{m.delivery_status}</td>
                        <td className="py-2.5 px-3 text-[11px] text-slate-400">
                          {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Record Consent Modal */}
      {showConsentModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-cobalt-900 border border-cobalt-700 rounded-lg p-5 w-full max-w-md space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
              <h3 className="font-bold text-slate-100 text-sm">Record Documented Prospect Consent</h3>
              <button
                onClick={() => setShowConsentModal(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleRecordConsent} className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Consent Source</label>
                <input
                  type="text"
                  value={consentSource}
                  onChange={(e) => setConsentSource(e.target.value)}
                  placeholder="e.g. Inbound Website Contact Form, Signed Business Card"
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                  required
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Proof Reference / URL</label>
                <input
                  type="text"
                  value={consentProof}
                  onChange={(e) => setConsentProof(e.target.value)}
                  placeholder="https://acttrident.ai/inbound/form-entry"
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowConsentModal(false)}
                  className="px-3 py-1.5 bg-cobalt-950 text-slate-300 rounded text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium"
                >
                  Confirm & Save Consent
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
