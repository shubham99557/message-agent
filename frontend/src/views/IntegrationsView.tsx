import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import {
  Layers,
  CheckCircle2,
  Lock,
  Mail,
  MessageSquare,
  Linkedin,
  Sparkles,
  Save,
  Key,
  BookOpen,
  HelpCircle,
  ExternalLink,
  ChevronRight,
  X
} from 'lucide-react';

export const IntegrationsView: React.FC = () => {
  // Provider settings
  const [aiProvider, setAiProvider] = useState('mock');
  const [geminiKey, setGeminiKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');

  // Email
  const [emailProvider, setEmailProvider] = useState('smtp');
  const [smtpHost, setSmtpHost] = useState('smtp.gmail.com');
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUser, setSmtpUser] = useState('outreach@acttrident.ai');
  const [smtpPassword, setSmtpPassword] = useState('');

  // WhatsApp
  const [waToken, setWaToken] = useState('');
  const [waPhoneId, setWaPhoneId] = useState('');
  const [waAccountId, setWaAccountId] = useState('');

  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [savedIntegrations, setSavedIntegrations] = useState<any[]>([]);
  const [gmailStatus, setGmailStatus] = useState<any>(null);
  const [linkedinStatus, setLinkedinStatus] = useState<any>(null);
  const [syncingGmail, setSyncingGmail] = useState(false);
  const [showGuideModal, setShowGuideModal] = useState(false);
  const [guideTab, setGuideTab] = useState<'gmail' | 'whatsapp' | 'linkedin' | 'checklist'>('gmail');

  const loadIntegrations = async () => {
    try {
      const [list, gStatus, liStatus] = await Promise.all([
        api.getIntegrations().catch(() => []),
        api.getGmailStatus().catch(() => null),
        api.getLinkedInStatus().catch(() => null),
      ]);
      setSavedIntegrations(list || []);
      setGmailStatus(gStatus);
      setLinkedinStatus(liStatus);
      for (const item of list || []) {
        if (item.provider === 'gemini' && item.is_active) setAiProvider('gemini');
        if (item.provider === 'openai' && item.is_active) setAiProvider('openai');
        if (item.provider === 'smtp' && item.key_identifier) setSmtpUser(item.key_identifier);
        if (item.provider === 'whatsapp_meta' && item.key_identifier) setWaPhoneId(item.key_identifier);
      }
    } catch {
      // Non-admin users cannot read integrations
    }
  };

  useEffect(() => {
    loadIntegrations();
  }, []);

  const handleConnectGmail = async () => {
    try {
      const res = await api.startGmailOAuth();
      window.open(res.authorization_url, '_blank', 'noopener,noreferrer');
    } catch (err: any) {
      alert(err.message || 'Gmail OAuth 2.0 is not configured on the backend.');
    }
  };

  const handleSyncGmail = async () => {
    setSyncingGmail(true);
    try {
      const res = await api.syncGmailReplies();
      alert(`Gmail sync complete: ${res.synced_replies} new replies, ${res.bounces_recorded} bounces recorded.`);
      await loadIntegrations();
    } catch (err: any) {
      alert(`Sync error: ${err.message}`);
    } finally {
      setSyncingGmail(false);
    }
  };

  const handleDisconnectGmail = async () => {
    if (!confirm('Disconnect Gmail and revoke stored OAuth tokens?')) return;
    try {
      await api.disconnectGmail();
      await loadIntegrations();
    } catch (err: any) {
      alert(`Disconnect error: ${err.message}`);
    }
  };

  const handleConnectLinkedIn = async () => {
    try {
      const res = await api.startLinkedInOAuth();
      window.open(res.authorization_url, '_blank', 'noopener,noreferrer');
    } catch (err: any) {
      alert(err.message || 'LinkedIn OAuth 2.0 is not configured on the backend.');
    }
  };

  const handleDisconnectLinkedIn = async () => {
    if (!confirm('Disconnect LinkedIn and clear stored OAuth tokens?')) return;
    try {
      await api.disconnectLinkedIn();
      await loadIntegrations();
    } catch (err: any) {
      alert(`Disconnect error: ${err.message}`);
    }
  };

  const handleSaveAI = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (geminiKey) {
        await api.saveIntegration({
          provider: 'gemini',
          key_identifier: 'GEMINI_API_KEY',
          encrypted_value: geminiKey,
          is_active: aiProvider === 'gemini'
        });
      }
      if (openaiKey) {
        await api.saveIntegration({
          provider: 'openai',
          key_identifier: 'OPENAI_API_KEY',
          encrypted_value: openaiKey,
          is_active: aiProvider === 'openai'
        });
      }
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      alert(`Save error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSMTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.saveIntegration({
        provider: 'smtp',
        key_identifier: smtpUser,
        encrypted_value: smtpPassword,
        is_active: true
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      alert(`Save error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveWhatsApp = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.saveIntegration({
        provider: 'whatsapp_meta',
        key_identifier: waPhoneId,
        encrypted_value: waToken,
        is_active: true
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      alert(`Save error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-100 tracking-tight">Enterprise Integrations & Service Credentials</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Configure API connectors for AI models, Gmail/SMTP email delivery, and official Meta WhatsApp Cloud API.
          </p>
        </div>
        <button
          onClick={() => setShowGuideModal(true)}
          className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-semibold shadow-sm transition-all border border-cobalt-400/40 shrink-0 cursor-pointer"
        >
          <BookOpen className="w-3.5 h-3.5 text-cobalt-200" />
          <span>📖 Customer Channel Setup Guide</span>
        </button>
      </div>

      {savedSuccess && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-300 flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>Integration credentials updated and encrypted in secure storage.</span>
        </div>
      )}

      {/* Gmail API OAuth 2.0 Status & Controls */}
      <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-cobalt-950 border border-cobalt-700 flex items-center justify-center text-cobalt-400">
              <Mail className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-semibold text-slate-100">Gmail API (Google OAuth 2.0)</h3>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded uppercase border ${
                    gmailStatus?.gmail?.status === 'connected'
                      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                      : gmailStatus?.gmail?.status === 'reauth_required'
                      ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                      : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                  }`}
                >
                  {gmailStatus?.gmail?.status || 'disconnected'}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 text-slate-300">
                  Active Mode: {gmailStatus?.active_mode || 'mock_simulation'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {gmailStatus?.gmail?.account_email
                  ? `Connected mailbox: ${gmailStatus.gmail.account_email}${gmailStatus.gmail.last_synced_at ? ` • Last synced: ${new Date(gmailStatus.gmail.last_synced_at).toLocaleString()}` : ''}`
                  : gmailStatus?.gmail?.oauth_configured
                  ? 'OAuth credentials detected. Click Connect Gmail to authorize least-privilege send & reply sync scopes.'
                  : 'Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in backend environment to enable Google OAuth 2.0.'}
              </p>
              {gmailStatus?.gmail?.last_error && (
                <p className="text-[11px] text-rose-300 mt-1 font-mono">Provider Error: {gmailStatus.gmail.last_error}</p>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-2 shrink-0">
            <button
              onClick={handleConnectGmail}
              className="px-3 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium"
            >
              {gmailStatus?.gmail?.status === 'connected' ? 'Reconnect Gmail' : 'Connect Gmail (OAuth 2.0)'}
            </button>
            {gmailStatus?.gmail?.status === 'connected' && (
              <>
                <button
                  onClick={handleSyncGmail}
                  disabled={syncingGmail}
                  className="px-3 py-1.5 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium disabled:opacity-50"
                >
                  {syncingGmail ? 'Syncing...' : 'Sync Replies'}
                </button>
                <button
                  onClick={handleDisconnectGmail}
                  className="px-3 py-1.5 bg-rose-950/40 hover:bg-rose-900/50 border border-rose-700/50 text-rose-300 rounded text-xs font-medium"
                >
                  Disconnect
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Official LinkedIn OAuth 2.0 Status & Controls */}
      <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-sky-500/15 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <Linkedin className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-semibold text-slate-100">LinkedIn (Official OAuth 2.0 / Authorized API)</h3>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded uppercase border ${
                    linkedinStatus?.connected
                      ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                      : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                  }`}
                >
                  {linkedinStatus?.status || 'disconnected'}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 text-slate-300">
                  Mode: {linkedinStatus?.active_mode || 'manual_handoff_only'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {linkedinStatus?.connected
                  ? `Connected LinkedIn profile: ${linkedinStatus.display_name || linkedinStatus.account_identifier}. ${linkedinStatus.mode_summary}`
                  : linkedinStatus?.oauth_configured
                  ? 'LinkedIn OAuth 2.0 credentials detected. Click Connect LinkedIn to authorize official OpenID scopes.'
                  : 'Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in backend environment. Zero password/cookie scraping.'}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2 shrink-0">
            <button
              onClick={handleConnectLinkedIn}
              className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded text-xs font-medium"
            >
              {linkedinStatus?.connected ? 'Reconnect LinkedIn' : 'Connect LinkedIn (OAuth 2.0)'}
            </button>
            {linkedinStatus?.connected && (
              <button
                onClick={handleDisconnectLinkedIn}
                className="px-3 py-1.5 bg-rose-950/40 hover:bg-rose-900/50 border border-rose-700/50 text-rose-300 rounded text-xs font-medium"
              >
                Disconnect
              </button>
            )}
          </div>
        </div>
      </div>

      {savedIntegrations.length > 0 && (
        <div className="bg-cobalt-900/60 border border-cobalt-800 rounded-lg p-3.5 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-400 font-medium mr-1">Configured Integrations:</span>
          {savedIntegrations.map((item) => (
            <span
              key={item.id}
              className={`px-2 py-0.5 rounded font-mono text-[11px] border ${
                item.is_active
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}
            >
              {item.provider} ({item.is_active ? 'ACTIVE' : 'INACTIVE'})
            </span>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 1. AI Provider Engine */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 space-y-4 text-xs">
          <div className="flex items-center space-x-2.5 border-b border-cobalt-800 pb-3">
            <Sparkles className="w-4 h-4 text-cobalt-400" />
            <h3 className="font-semibold text-slate-200">AI Intelligence Provider</h3>
          </div>

          <form onSubmit={handleSaveAI} className="space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Active Provider</label>
              <select
                value={aiProvider}
                onChange={(e) => setAiProvider(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
              >
                <option value="mock">Built-in Deterministic Engine (Offline Safe)</option>
                <option value="gemini">Google Gemini API (Official)</option>
                <option value="openai">OpenAI / Compatible Endpoint</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Google Gemini API Key</label>
              <input
                type="password"
                placeholder="AIzaSy..."
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">OpenAI API Key (Optional)</label>
              <input
                type="password"
                placeholder="sk-proj-..."
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
              />
            </div>

            <button
              type="submit"
              disabled={saving}
              className="w-full py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium transition-colors flex items-center justify-center space-x-1"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Save AI Settings</span>
            </button>
          </form>
        </div>

        {/* 2. SMTP / Gmail Outbound */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 space-y-4 text-xs">
          <div className="flex items-center space-x-2.5 border-b border-cobalt-800 pb-3">
            <Mail className="w-4 h-4 text-cobalt-400" />
            <h3 className="font-semibold text-slate-200">Email Delivery (SMTP / Gmail)</h3>
          </div>

          <form onSubmit={handleSaveSMTP} className="space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Provider Type</label>
              <select
                value={emailProvider}
                onChange={(e) => setEmailProvider(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
              >
                <option value="smtp">Configurable SMTP (Gmail / Custom)</option>
                <option value="gmail">Google Workspace Gmail API</option>
                <option value="mock">Sandbox Test Provider</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">SMTP Host & Port</label>
              <div className="grid grid-cols-3 gap-2">
                <input
                  type="text"
                  value={smtpHost}
                  onChange={(e) => setSmtpHost(e.target.value)}
                  className="col-span-2 bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
                <input
                  type="number"
                  value={smtpPort}
                  onChange={(e) => setSmtpPort(Number(e.target.value))}
                  className="bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Username / From Address</label>
              <input
                type="text"
                value={smtpUser}
                onChange={(e) => setSmtpUser(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">App Password / Secret</label>
              <input
                type="password"
                placeholder="••••••••••••"
                value={smtpPassword}
                onChange={(e) => setSmtpPassword(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
              />
            </div>

            <button
              type="submit"
              disabled={saving}
              className="w-full py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium transition-colors flex items-center justify-center space-x-1"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Save Email Config</span>
            </button>
          </form>
        </div>

        {/* 3. Official Meta WhatsApp Cloud API */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 space-y-4 text-xs">
          <div className="flex items-center space-x-2.5 border-b border-cobalt-800 pb-3">
            <MessageSquare className="w-4 h-4 text-emerald-400" />
            <h3 className="font-semibold text-slate-200">Meta WhatsApp Cloud API</h3>
          </div>

          <form onSubmit={handleSaveWhatsApp} className="space-y-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Permanent Access Token</label>
              <input
                type="password"
                placeholder="EAAB..."
                value={waToken}
                onChange={(e) => setWaToken(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Phone Number ID</label>
              <input
                type="text"
                placeholder="1000987654321"
                value={waPhoneId}
                onChange={(e) => setWaPhoneId(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">WhatsApp Business Account ID</label>
              <input
                type="text"
                placeholder="1234567890123"
                value={waAccountId}
                onChange={(e) => setWaAccountId(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
              />
            </div>

            <div className="p-2.5 bg-cobalt-950 rounded border border-cobalt-800 text-[11px] text-slate-400 space-y-1">
              <div>Webhook Verify Token &amp; HMAC Secret:</div>
              <div className="font-mono text-slate-300">
                Managed securely via backend <code className="text-cobalt-300">META_WA_VERIFY_TOKEN</code> &amp;{' '}
                <code className="text-cobalt-300">META_APP_SECRET</code> environment variables.
              </div>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="w-full py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium transition-colors flex items-center justify-center space-x-1"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Save Meta WhatsApp API</span>
            </button>
          </form>
        </div>
      </div>

      {/* Step-by-Step Customer Channels Guide Modal */}
      {showGuideModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-cobalt-950 border border-cobalt-700 rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="px-6 py-4 bg-cobalt-900 border-b border-cobalt-800 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded bg-cobalt-600/30 border border-cobalt-500/40 flex items-center justify-center text-cobalt-300">
                  <BookOpen className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-100">Customer Channel Setup & Connection Guide</h3>
                  <p className="text-[11px] text-slate-400">Step-by-step instructions to connect Mail, WhatsApp, and LinkedIn for live outreach.</p>
                </div>
              </div>
              <button
                onClick={() => setShowGuideModal(false)}
                className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-cobalt-800 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Tabs */}
            <div className="px-6 pt-3 bg-cobalt-900/60 border-b border-cobalt-800 flex space-x-2">
              <button
                onClick={() => setGuideTab('gmail')}
                className={`px-3 py-2 text-xs font-medium border-b-2 flex items-center space-x-1.5 transition-colors ${
                  guideTab === 'gmail'
                    ? 'border-cobalt-400 text-cobalt-200 bg-cobalt-850/50 rounded-t'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Mail className="w-3.5 h-3.5" />
                <span>1. Email (Gmail / SMTP)</span>
              </button>
              <button
                onClick={() => setGuideTab('whatsapp')}
                className={`px-3 py-2 text-xs font-medium border-b-2 flex items-center space-x-1.5 transition-colors ${
                  guideTab === 'whatsapp'
                    ? 'border-emerald-400 text-emerald-200 bg-cobalt-850/50 rounded-t'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span>2. Meta WhatsApp API</span>
              </button>
              <button
                onClick={() => setGuideTab('linkedin')}
                className={`px-3 py-2 text-xs font-medium border-b-2 flex items-center space-x-1.5 transition-colors ${
                  guideTab === 'linkedin'
                    ? 'border-sky-400 text-sky-200 bg-cobalt-850/50 rounded-t'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Linkedin className="w-3.5 h-3.5" />
                <span>3. LinkedIn Outreach</span>
              </button>
              <button
                onClick={() => setGuideTab('checklist')}
                className={`px-3 py-2 text-xs font-medium border-b-2 flex items-center space-x-1.5 transition-colors ${
                  guideTab === 'checklist'
                    ? 'border-purple-400 text-purple-200 bg-cobalt-850/50 rounded-t'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>4. First Campaign Checklist</span>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-4 text-xs text-slate-300">
              {guideTab === 'gmail' && (
                <div className="space-y-4">
                  <div className="p-3 bg-cobalt-900/60 border border-cobalt-800 rounded-lg">
                    <h4 className="font-semibold text-slate-200 mb-1 flex items-center space-x-1.5">
                      <span>Option A: Google Workspace / Gmail OAuth 2.0 (Recommended)</span>
                    </h4>
                    <p className="text-[11px] text-slate-400">
                      Enables official least-privilege sending, automatic bounce detection, and two-way reply sync.
                    </p>
                    <ol className="list-decimal list-inside space-y-2 mt-3 text-[11px] text-slate-300">
                      <li>
                        <strong className="text-slate-100">Google Cloud Console:</strong> Navigate to{' '}
                        <code className="text-cobalt-300">console.cloud.google.com</code> and create a new project called <em>ActTrident Outreach</em>.
                      </li>
                      <li>
                        <strong className="text-slate-100">Enable Gmail API:</strong> Go to <em>APIs &amp; Services &gt; Library</em>, search for <strong>Gmail API</strong>, and click <strong>Enable</strong>.
                      </li>
                      <li>
                        <strong className="text-slate-100">Configure OAuth Consent:</strong> Go to <em>OAuth consent screen</em>. Choose <strong>Internal</strong> (for Google Workspace) or <strong>External</strong>. Add scope <code className="text-cobalt-300">https://www.googleapis.com/auth/gmail.send</code> and <code className="text-cobalt-300">https://www.googleapis.com/auth/gmail.readonly</code>.
                      </li>
                      <li>
                        <strong className="text-slate-100">Create OAuth Client ID:</strong> Under <em>Credentials</em>, click <em>+ Create Credentials &gt; OAuth client ID</em> (Web application). Add Authorized redirect URI:
                        <div className="bg-cobalt-950 p-2 rounded border border-cobalt-800 mt-1 font-mono text-[10px] text-cobalt-300 select-all">
                          http://localhost:8000/api/v1/integrations/gmail/callback
                        </div>
                      </li>
                      <li>
                        <strong className="text-slate-100">Save in Environment or Backend:</strong> Put <code className="text-cobalt-300">GMAIL_CLIENT_ID</code> and <code className="text-cobalt-300">GMAIL_CLIENT_SECRET</code> in your backend <code className="text-cobalt-300">.env</code>.
                      </li>
                      <li>
                        <strong className="text-slate-100">Click &quot;Connect Gmail (OAuth 2.0)&quot;:</strong> Click the button on this screen, select your mailbox, and grant permissions.
                      </li>
                    </ol>
                  </div>

                  <div className="p-3 bg-cobalt-900/60 border border-cobalt-800 rounded-lg">
                    <h4 className="font-semibold text-slate-200 mb-1">Option B: Standard SMTP (Microsoft 365, Zoho, Custom Domain)</h4>
                    <p className="text-[11px] text-slate-400">
                      Fill in the <strong>Email Delivery (SMTP)</strong> card on this page with:
                    </p>
                    <ul className="list-disc list-inside space-y-1 mt-2 text-[11px] text-slate-300">
                      <li><strong>Host:</strong> <code className="text-cobalt-300">smtp.office365.com</code> (Outlook) or <code className="text-cobalt-300">smtp.zoho.com</code> (Zoho) or <code className="text-cobalt-300">smtp.gmail.com</code></li>
                      <li><strong>Port:</strong> <code className="text-cobalt-300">587</code> (STARTTLS) or <code className="text-cobalt-300">465</code> (SSL)</li>
                      <li><strong>App Password:</strong> Generate a dedicated App Password from your provider if MFA is enabled.</li>
                      <li>Click <strong>Save Email Config</strong>.</li>
                    </ul>
                  </div>
                </div>
              )}

              {guideTab === 'whatsapp' && (
                <div className="space-y-4">
                  <div className="p-3 bg-emerald-950/30 border border-emerald-800/40 rounded-lg">
                    <h4 className="font-semibold text-emerald-300 mb-1">Official Meta WhatsApp Business Cloud API</h4>
                    <p className="text-[11px] text-slate-300">
                      ActTrident connects to Meta's official Graph API to guarantee zero phone number bans and complete opt-out compliance.
                    </p>
                    <ol className="list-decimal list-inside space-y-2 mt-3 text-[11px] text-slate-300">
                      <li>
                        <strong className="text-slate-100">Meta for Developers:</strong> Log in to <code className="text-emerald-300">developers.facebook.com</code>, create an app of type <strong>Business</strong>, and add <strong>WhatsApp</strong>.
                      </li>
                      <li>
                        <strong className="text-slate-100">Generate Permanent System User Token:</strong>
                        <p className="pl-4 text-slate-400 mt-0.5">
                          In Meta Business Manager (<code className="text-emerald-300">business.facebook.com/settings</code>) &gt; Users &gt; System Users: add an Admin System User, assign your WhatsApp app, and generate a permanent token with <code className="text-emerald-300">whatsapp_business_messaging</code> permissions.
                        </p>
                      </li>
                      <li>
                        <strong className="text-slate-100">Register Utility Template in WhatsApp Manager:</strong>
                        <p className="pl-4 text-slate-400 mt-0.5">
                          Create template name <code className="text-emerald-300">acttrident_intro_utility_v1</code> (Category: Utility, Language: en). Meta usually auto-approves utility templates in 2-5 minutes.
                        </p>
                      </li>
                      <li>
                        <strong className="text-slate-100">Configure Webhook:</strong> Set Callback URL to <code className="text-emerald-300">https://your-domain.com/api/v1/whatsapp/webhook</code> and subscribe to <code className="text-emerald-300">messages</code>.
                      </li>
                      <li>
                        <strong className="text-slate-100">Save in ActTrident:</strong> Paste the <em>Permanent Token</em>, <em>Phone Number ID</em>, and <em>WABA ID</em> into the form on this page and click <strong>Save Meta WhatsApp API</strong>.
                      </li>
                    </ol>
                  </div>
                </div>
              )}

              {guideTab === 'linkedin' && (
                <div className="space-y-4">
                  <div className="p-3 bg-sky-950/30 border border-sky-800/40 rounded-lg">
                    <h4 className="font-semibold text-sky-300 mb-1">Compliant Operator Handoff Architecture</h4>
                    <p className="text-[11px] text-slate-300">
                      LinkedIn actively bans accounts that use unofficial browser scrapers or store session cookies (li_at). ActTrident uses a <strong>100% compliant human-assisted handoff</strong> that keeps your account safe.
                    </p>
                    <ol className="list-decimal list-inside space-y-2 mt-3 text-[11px] text-slate-300">
                      <li>
                        <strong className="text-slate-100">Strict Character Limit:</strong> Connection notes are automatically formatted to &le; 295 characters (under LinkedIn's 300-char limit). InMails are capped at 1,900 chars.
                      </li>
                      <li>
                        <strong className="text-slate-100">Manager Review &amp; Hash Binding:</strong> Sales managers approve personalized LinkedIn messages in the Approval Queue, binding them with SHA-256 cryptographic hashes.
                      </li>
                      <li>
                        <strong className="text-slate-100">1-Click Copy &amp; Deep Link:</strong> In the Operator Dispatch view, reps click <em>Copy to Clipboard</em> and click the direct LinkedIn profile link to paste and send.
                      </li>
                      <li>
                        <strong className="text-slate-100">Audit Sync:</strong> The rep clicks <em>Confirm Sent</em>, advancing the CRM lead stage to &apos;contacted&apos; and logging an immutable audit record.
                      </li>
                    </ol>
                  </div>
                </div>
              )}

              {guideTab === 'checklist' && (
                <div className="space-y-4">
                  <div className="p-3 bg-purple-950/30 border border-purple-800/40 rounded-lg">
                    <h4 className="font-semibold text-purple-300 mb-1">Live Outreach Launch Checklist</h4>
                    <div className="space-y-2.5 mt-3 text-[11px] text-slate-300">
                      <div className="flex items-start space-x-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <div><strong>1. Target Evidence Verified:</strong> Prospect company has 5+ documented laptops (careers page, MCA filing, or physical lab audit).</div>
                      </div>
                      <div className="flex items-start space-x-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <div><strong>2. Channel Connected:</strong> Gmail API / SMTP or WhatsApp credentials configured and active.</div>
                      </div>
                      <div className="flex items-start space-x-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <div><strong>3. Draft Approved by Manager:</strong> Explicit Human-in-the-Loop approval granted with SHA-256 hash match.</div>
                      </div>
                      <div className="flex items-start space-x-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <div><strong>4. Suppression List Clear:</strong> Recipient has not opted out or bounced previously.</div>
                      </div>
                      <div className="flex items-start space-x-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <div><strong>5. Daily Limit Checked:</strong> Global &amp; campaign daily sending quotas not exceeded.</div>
                      </div>
                      <div className="flex items-start space-x-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <div><strong>6. Emergency Kill Switch Disarmed:</strong> Global outbound toggle is in normal operating mode.</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 bg-cobalt-900 border-t border-cobalt-800 flex items-center justify-between">
              <span className="text-[11px] text-slate-400">
                Detailed manual: <code className="text-cobalt-300 font-mono">docs/CUSTOMER_ONBOARDING_AND_CHANNELS_GUIDE.md</code>
              </span>
              <button
                onClick={() => setShowGuideModal(false)}
                className="px-4 py-1.5 bg-cobalt-700 hover:bg-cobalt-600 text-white rounded text-xs font-semibold transition-colors"
              >
                Close Guide
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
