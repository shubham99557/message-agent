import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Company, EmailDraft, ViewType } from '../types';
import {
  Mail,
  Send,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Clock,
  Eye,
  Edit3,
  Save,
  ArrowRight
} from 'lucide-react';

interface EmailOutreachViewProps {
  selectedCompany?: Company | null;
  onNavigate: (view: ViewType) => void;
}

export const EmailOutreachView: React.FC<EmailOutreachViewProps> = ({ selectedCompany, onNavigate }) => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [activeCompanyId, setActiveCompanyId] = useState<number | null>(selectedCompany?.id ?? null);
  const [activeCompany, setActiveCompany] = useState<Company | null>(selectedCompany ?? null);
  const [tone, setTone] = useState<string>('Friendly professional');
  const [customNotes, setCustomNotes] = useState<string>('');
  const [currentDraft, setCurrentDraft] = useState<EmailDraft | null>(null);
  const [subject, setSubject] = useState('');
  const [bodyText, setBodyText] = useState('');
  const [generating, setGenerating] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [previewTab, setPreviewTab] = useState<'text' | 'html'>('text');

  useEffect(() => {
    async function loadCompanies() {
      try {
        const data = await api.getCompanies({ limit: 100 });
        setCompanies(data.items);
        if (!activeCompanyId && data.items.length > 0) {
          setActiveCompanyId(data.items[0].id);
          setActiveCompany(data.items[0]);
        }
      } catch (err) {
        console.error(err);
      }
    }
    loadCompanies();
  }, []);

  const handleCompanyChange = async (id: number) => {
    setActiveCompanyId(id);
    const found = companies.find((c) => c.id === id);
    if (found) setActiveCompany(found);
    setCurrentDraft(null);
  };

  const handleGenerate = async () => {
    if (!activeCompanyId) return;
    setGenerating(true);
    setStatusMsg(null);
    try {
      const draft = await api.generateEmail({
        company_id: activeCompanyId,
        tone,
        custom_notes: customNotes || undefined
      });
      setCurrentDraft(draft);
      setSubject(draft.subject);
      setBodyText(draft.body_text);
      setStatusMsg('AI personalized draft created in DRAFT status. Ready for human review.');
    } catch (err: any) {
      alert(`Generation error: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleSaveEdits = async () => {
    if (!currentDraft) return;
    try {
      const updated = await api.updateEmailDraft(currentDraft.id, {
        subject,
        body_text: bodyText
      });
      setCurrentDraft(updated);
      setStatusMsg('Draft modifications saved successfully.');
    } catch (err: any) {
      alert(`Save error: ${err.message}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* View Header */}
      <div className="bg-cobalt-900/90 border border-cobalt-800 rounded-lg p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded bg-cobalt-800 border border-cobalt-700 flex items-center justify-center text-cobalt-400 shrink-0">
            <Mail className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-100 tracking-tight">AI Personalized Email Generator</h2>
            <p className="text-xs text-slate-400">
              Generates unique 8-part messages presenting the ActTrident 90-day evaluation. All drafts default to human review.
            </p>
          </div>
        </div>

        <button
          onClick={() => onNavigate('approvals')}
          className="px-3 py-1.5 bg-amber-500/10 border border-amber-500/30 text-amber-300 hover:bg-amber-500/20 rounded text-xs font-medium transition-colors flex items-center space-x-1.5 self-start md:self-auto"
        >
          <Clock className="w-3.5 h-3.5" />
          <span>Open Approval Queue</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Generator Controls */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 space-y-4">
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Outreach Configuration</h3>

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
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Selectable Tone (5 Modes)</label>
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 font-medium"
            >
              <option value="Friendly professional">Friendly professional (Warm & value-driven)</option>
              <option value="Formal">Formal (Executive enterprise structure)</option>
              <option value="Technical">Technical (Endpoint isolation & posture)</option>
              <option value="Short introductory">Short introductory (Crisp brief)</option>
              <option value="Follow-up">Follow-up (Polite sequence check-in)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Custom Notes / Angle (Optional)</label>
            <textarea
              rows={3}
              placeholder="e.g. emphasize remote developer laptop isolation or Siliguri office expansion"
              value={customNotes}
              onChange={(e) => setCustomNotes(e.target.value)}
              className="w-full bg-cobalt-950 border border-cobalt-800 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 placeholder:text-slate-500"
            ></textarea>
          </div>

          {activeCompany && (
            <div className="bg-cobalt-950/70 p-3 rounded border border-cobalt-800 text-[11px] text-slate-300 space-y-1">
              <div className="font-semibold text-slate-200">Recipient Verification:</div>
              <div>Recipient: {activeCompany.decision_maker_name || 'IT Leadership'}</div>
              <div>Email: {activeCompany.public_email || 'Verified company domain'}</div>
              <div>Laptops: {activeCompany.laptop_count_verified ?? 'Under Audit'}</div>
            </div>
          )}

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full py-2 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors flex items-center justify-center space-x-1.5 shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{generating ? 'Drafting with Guardrails...' : 'Generate AI Email Draft'}</span>
          </button>
        </div>

        {/* Draft Editor & Live Preview */}
        <div className="lg:col-span-2 bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 flex flex-col space-y-4">
          <div className="flex items-center justify-between border-b border-cobalt-800 pb-3">
            <div>
              <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Email Editor & Preview</h3>
              <p className="text-[11px] text-slate-400">Strict Human Approval Enforced Before Any Dispatch</p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setPreviewTab('text')}
                className={`px-2.5 py-1 rounded text-xs font-medium ${
                  previewTab === 'text' ? 'bg-cobalt-600 text-white' : 'bg-cobalt-950 text-slate-400 hover:text-slate-200'
                }`}
              >
                Plain Text
              </button>
              <button
                onClick={() => setPreviewTab('html')}
                className={`px-2.5 py-1 rounded text-xs font-medium ${
                  previewTab === 'html' ? 'bg-cobalt-600 text-white' : 'bg-cobalt-950 text-slate-400 hover:text-slate-200'
                }`}
              >
                HTML View
              </button>
            </div>
          </div>

          {statusMsg && (
            <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-300 flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{statusMsg}</span>
            </div>
          )}

          {currentDraft ? (
            <div className="flex-1 space-y-4">
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Subject Line</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 font-medium"
                />
              </div>

              {previewTab === 'text' ? (
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">Message Body (Editable)</label>
                  <textarea
                    rows={14}
                    value={bodyText}
                    onChange={(e) => setBodyText(e.target.value)}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded p-3 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 font-sans leading-relaxed"
                  ></textarea>
                </div>
              ) : (
                <div>
                  <label className="block text-[11px] font-medium text-slate-400 mb-1">Rendered HTML Output</label>
                  <div
                    className="w-full bg-white text-slate-900 rounded p-4 text-xs overflow-auto max-h-[380px] border border-cobalt-700"
                    dangerouslySetInnerHTML={{ __html: currentDraft.body_html }}
                  ></div>
                </div>
              )}

              <div className="flex items-center justify-between pt-2 border-t border-cobalt-800">
                <div className="text-[11px] text-slate-400 flex items-center space-x-2">
                  <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                  <span>Status: <strong>DRAFT</strong> (Requires Approval to Send)</span>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleSaveEdits}
                    className="px-3 py-1.5 bg-cobalt-900 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium transition-colors flex items-center space-x-1"
                  >
                    <Save className="w-3.5 h-3.5 text-cobalt-400" />
                    <span>Save Draft</span>
                  </button>
                  <button
                    onClick={() => onNavigate('approvals')}
                    className="px-3.5 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1"
                  >
                    <span>Proceed to Human Approval Queue</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-16 text-center text-xs text-slate-400">
              <Mail className="w-8 h-8 mx-auto text-cobalt-600 mb-2 opacity-50" />
              <p className="text-slate-300 font-medium">No email generated yet for this account.</p>
              <p className="text-[11px] mt-1">Select a tone and click 'Generate AI Email Draft' on the left.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
