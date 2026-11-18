import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import {
  Layers,
  CheckCircle2,
  Lock,
  Mail,
  MessageSquare,
  Sparkles,
  Save,
  Key
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

  const loadIntegrations = async () => {
    try {
      const list = await api.getIntegrations();
      setSavedIntegrations(list || []);
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
      <div>
        <h2 className="text-base font-bold text-slate-100 tracking-tight">Enterprise Integrations & Service Credentials</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Configure API connectors for AI models, Gmail/SMTP email delivery, and official Meta WhatsApp Cloud API.
        </p>
      </div>

      {savedSuccess && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-300 flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>Integration credentials updated and encrypted in secure storage.</span>
        </div>
      )}

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
              <div>Webhook Verify Token:</div>
              <div className="font-mono text-slate-200 select-all">acttrident_meta_webhook_secret_2026</div>
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
    </div>
  );
};
