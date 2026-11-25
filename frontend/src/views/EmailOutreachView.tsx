import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { Company, EmailDraft, EmailVariationItem, EmailVariationsResponse, ServiceCatalogueItem, ViewType } from '../types';
import {
  Mail,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Clock,
  Eye,
  Edit3,
  Save,
  ArrowRight,
  ExternalLink,
  Copy,
  ShieldAlert,
  Layers,
  FileText,
  Check,
  RefreshCw,
  AlertTriangle,
  Info,
  CheckSquare,
  Building2,
  UserCheck,
  Target,
  Sparkle
} from 'lucide-react';

interface EmailOutreachViewProps {
  selectedCompany?: Company | null;
  onNavigate: (view: ViewType) => void;
}

export const EmailOutreachView: React.FC<EmailOutreachViewProps> = ({ selectedCompany, onNavigate }) => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [activeCompanyId, setActiveCompanyId] = useState<number | null>(selectedCompany?.id ?? null);
  const [activeCompany, setActiveCompany] = useState<Company | null>(selectedCompany ?? null);
  const [searchTerm, setSearchTerm] = useState('');

  // Service catalogue & research
  const [services, setServices] = useState<ServiceCatalogueItem[]>([]);
  const [selectedServiceId, setSelectedServiceId] = useState<number | undefined>(undefined);
  const [researchReport, setResearchReport] = useState<any | null>(null);

  // Generation configuration
  const [tone, setTone] = useState<string>('Professional');
  const [customNotes, setCustomNotes] = useState<string>('');
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Phase 3 Variations State
  const [variationsData, setVariationsData] = useState<EmailVariationsResponse | null>(null);
  const [activeVariationIndex, setActiveVariationIndex] = useState<number>(1); // Default to Standard (index 1)

  // Current Draft / Editor state
  const [currentDraft, setCurrentDraft] = useState<EmailDraft | null>(null);
  const [subject, setSubject] = useState('');
  const [bodyText, setBodyText] = useState('');
  const [previewTab, setPreviewTab] = useState<'text' | 'html'>('text');

  // Company draft history
  const [companyDrafts, setCompanyDrafts] = useState<EmailDraft[]>([]);
  const userSelectedRef = useRef<boolean>(false);

  // Phase 4A: Test-Mode & DNS Preflight State
  const [testModeStatus, setTestModeStatus] = useState<any | null>(null);
  const [dnsDomain, setDnsDomain] = useState<string>('acttrident.ai');
  const [dnsSelector, setDnsSelector] = useState<string>('resend');
  const [dnsResult, setDnsResult] = useState<any | null>(null);
  const [dnsLoading, setDnsLoading] = useState<boolean>(false);

  // Phase 4C: Local AI Health, Test-Mode Send & Event Simulator State
  const [localAiStatus, setLocalAiStatus] = useState<any | null>(null);
  const [testSinkRecipient, setTestSinkRecipient] = useState<string>('delivered@resend.dev');
  const [testSendLoading, setTestSendLoading] = useState<boolean>(false);
  const [testSendResult, setTestSendResult] = useState<any | null>(null);
  const [testSendError, setTestSendError] = useState<string | null>(null);
  const [simEventType, setSimEventType] = useState<string>('email.delivered');
  const [simLoading, setSimLoading] = useState<boolean>(false);
  const [simResult, setSimResult] = useState<any | null>(null);
  const [draftTimeline, setDraftTimeline] = useState<any[]>([]);
  const [timelineLoading, setTimelineLoading] = useState<boolean>(false);

  const loadDraftTimeline = async (draftId?: number | null) => {
    if (!draftId) {
      setDraftTimeline([]);
      return;
    }
    setTimelineLoading(true);
    try {
      const res = await api.getDraftTimeline(draftId);
      setDraftTimeline(Array.isArray(res?.items) ? res.items : []);
    } catch {
      setDraftTimeline([]);
    } finally {
      setTimelineLoading(false);
    }
  };

  useEffect(() => {
    loadDraftTimeline(currentDraft?.id);
  }, [currentDraft?.id]);

  // Load companies and services on mount
  useEffect(() => {
    let cancelled = false;
    async function initData() {
      try {
        const [compRes, servRes, tmRes, aiRes] = await Promise.all([
          api.getCompanies({ limit: 100 }),
          api.getServices(true),
          api.getEmailTestModeStatus().catch(() => null),
          api.getLocalAIStatus().catch(() => null),
        ]);
        if (cancelled) return;
        setCompanies(compRes.items || []);
        setServices(servRes || []);
        if (tmRes) {
          setTestModeStatus(tmRes);
          if (tmRes.dkim_selector) setDnsSelector(tmRes.dkim_selector);
        }
        if (aiRes) setLocalAiStatus(aiRes);

        if (compRes.items && compRes.items.length > 0 && !userSelectedRef.current) {
          const initial = selectedCompany
            ? compRes.items.find(c => c.id === selectedCompany.id) || compRes.items[0]
            : compRes.items.find(c => !c.is_demo && c.verification_status !== 'synthetic_fixture' && c.verification_status !== 'historical_test') || compRes.items[0];

          setActiveCompanyId(prev => prev ?? initial.id);
          setActiveCompany(prev => prev ?? initial);
        }
      } catch (err: any) {
        console.error('Initialization error:', err);
        if (!cancelled) setErrorMsg('Failed to initialize company and service catalog data.');
      }
    }
    initData();
    return () => { cancelled = true; };
  }, [selectedCompany]);

  // Load research report and draft history whenever activeCompanyId changes
  useEffect(() => {
    if (!activeCompanyId) return;

    async function loadCompanyDetails() {
      try {
        const [research, drafts] = await Promise.allSettled([
          api.getResearchReport(activeCompanyId!),
          api.listEmailDrafts(activeCompanyId!, 20)
        ]);

        if (research.status === 'fulfilled') {
          setResearchReport(research.value);
        } else {
          setResearchReport(null);
        }

        if (drafts.status === 'fulfilled' && Array.isArray(drafts.value)) {
          setCompanyDrafts(drafts.value);
          if (drafts.value.length > 0 && !currentDraft) {
            // Load latest draft if available
            const latest = drafts.value[0];
            setCurrentDraft(latest);
            setSubject(latest.subject);
            setBodyText(latest.body_text);
          }
        } else {
          setCompanyDrafts([]);
        }
      } catch (e) {
        console.error('Error fetching company details:', e);
      }
    }

    loadCompanyDetails();
  }, [activeCompanyId]);

  const isSyntheticFixture = (company: Company | null): boolean => {
    if (!company) return false;
    return !!(
      company.is_demo ||
      company.verification_status === 'synthetic_fixture' ||
      company.verification_status === 'demo_fixture' ||
      company.verification_status === 'historical_test'
    );
  };

  const handleCompanyChange = (id: number) => {
    userSelectedRef.current = true;
    setActiveCompanyId(id);
    const found = companies.find((c) => c.id === id) || null;
    setActiveCompany(found);
    setVariationsData(null);
    setCurrentDraft(null);
    setSubject('');
    setBodyText('');
    setStatusMsg(null);
    setErrorMsg(null);
    setSelectedServiceId(found?.matched_service_id || undefined);
  };

  // Generate 3 variations using Phase 3 Engine
  const handleGenerateVariations = async () => {
    if (!activeCompanyId || !activeCompany) return;

    if (isSyntheticFixture(activeCompany)) {
      setErrorMsg('Policy Enforcement: Outreach generation is prohibited for synthetic test fixtures.');
      return;
    }

    setGenerating(true);
    setStatusMsg(null);
    setErrorMsg(null);

    try {
      const result: EmailVariationsResponse = await api.generateEmailVariations({
        company_id: activeCompanyId,
        tone,
        service_id: selectedServiceId,
        custom_notes: customNotes || undefined
      });

      setVariationsData(result);

      // Default to Standard (index 1) or first available
      const defaultIdx = result.variations.length > 1 ? 1 : 0;
      setActiveVariationIndex(defaultIdx);

      const activeVar = result.variations[defaultIdx];
      if (activeVar) {
        setSubject(activeVar.subject);
        setBodyText(activeVar.body_text);
      }

      // Also create draft on backend to obtain draft ID and enable approval lifecycle
      try {
        const draft = await api.generateEmail({
          company_id: activeCompanyId,
          tone,
          service_id: selectedServiceId,
          custom_notes: customNotes || undefined,
          variation_type: activeVar ? activeVar.variation_type : 'standard'
        });

        setCurrentDraft(draft);
        setStatusMsg(`Generated 3 variations using ${result.generation_model || 'Ollama llama3.2:latest'}. Initial draft saved (Status: DRAFT).`);

        // Refresh draft history
        const freshDrafts = await api.listEmailDrafts(activeCompanyId, 20);
        setCompanyDrafts(freshDrafts);
      } catch (draftErr: any) {
        setCurrentDraft(null);
        setErrorMsg(`Commercial draft blocked: ${draftErr.message || 'Recipient email validation failed.'}`);
      }
    } catch (err: any) {
      console.error('Generation error:', err);
      setErrorMsg(err.message || 'Email generation failed.');
    } finally {
      setGenerating(false);
    }
  };

  // Switch between Variation A, B, and C
  const handleSelectVariation = (idx: number) => {
    if (!variationsData || !variationsData.variations[idx]) return;
    setActiveVariationIndex(idx);
    const chosen = variationsData.variations[idx];
    setSubject(chosen.subject);
    setBodyText(chosen.body_text);
    const words = chosen.body_text.trim().split(/\s+/).filter(Boolean).length;
    setStatusMsg(`Switched to Variation: ${chosen.label} (${words} words). Save draft to persist.`);
  };

  // Pick a suggested subject line
  const handleSelectSubjectSuggestion = (suggestion: string) => {
    setSubject(suggestion);
    setStatusMsg('Applied subject line suggestion. Remember to save draft edits.');
  };

  // Save edits to backend (invalidates prior approval and increments version)
  const handleSaveEdits = async () => {
    if (!currentDraft) {
      if (!activeCompanyId) return;
      // If no draft exists yet, create one
      try {
        setSaving(true);
        const newDraft = await api.generateEmail({
          company_id: activeCompanyId,
          tone,
          service_id: selectedServiceId,
          custom_notes: customNotes || undefined
        });
        const updated = await api.updateEmailDraft(newDraft.id, {
          subject,
          body_text: bodyText
        });
        setCurrentDraft(updated);
        setStatusMsg(`Draft saved as version v${updated.version || 1}. Status is DRAFT (Pending Review).`);
        const fresh = await api.listEmailDrafts(activeCompanyId, 20);
        setCompanyDrafts(fresh);
      } catch (e: any) {
        setErrorMsg(`Failed to save draft: ${e.message}`);
      } finally {
        setSaving(false);
      }
      return;
    }

    try {
      setSaving(true);
      setErrorMsg(null);
      const updated = await api.updateEmailDraft(currentDraft.id, {
        subject,
        body_text: bodyText
      });
      setCurrentDraft(updated);
      setStatusMsg(`Draft updated to v${updated.version}. Prior approvals invalidated; requires human re-approval.`);
      const fresh = await api.listEmailDrafts(activeCompanyId!, 20);
      setCompanyDrafts(fresh);
    } catch (err: any) {
      console.error('Save error:', err);
      setErrorMsg(err.message || 'Failed to save draft changes.');
    } finally {
      setSaving(false);
    }
  };

  const handleCopyToClipboard = () => {
    const fullText = `Subject: ${subject}\n\n${bodyText}`;
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleLoadHistoricDraft = (draft: EmailDraft) => {
    setCurrentDraft(draft);
    setSubject(draft.subject);
    setBodyText(draft.body_text);
    setTone(draft.tone || 'Professional');
    setStatusMsg(`Loaded historic draft v${draft.version || 1} (Status: ${draft.approval_status.toUpperCase()}).`);
  };

  const filteredCompanies = companies.filter(c => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      c.name.toLowerCase().includes(term) ||
      c.city.toLowerCase().includes(term) ||
      (c.industry && c.industry.toLowerCase().includes(term))
    );
  });

  const realCompanies = filteredCompanies.filter(c => !isSyntheticFixture(c));
  const syntheticCompanies = filteredCompanies.filter(c => isSyntheticFixture(c));
  const isCurrentSynthetic = isSyntheticFixture(activeCompany);

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">
      {/* Top Banner */}
      <div className="bg-cobalt-900/90 border border-cobalt-800 rounded-xl p-4 md:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-sm">
        <div className="flex items-center space-x-3.5">
          <div className="w-10 h-10 rounded-lg bg-cobalt-800 border border-cobalt-700 flex items-center justify-center text-cobalt-400 shrink-0 shadow-inner">
            <Mail className="w-5 h-5 text-cobalt-300" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm md:text-base font-bold text-slate-100 tracking-tight">
                AI Personalized Email Generation Engine
              </h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
                Phase 3 Engine
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Strictly grounded in verified evidence, company research dossiers, and approved ActTrident catalogue. Zero synthetic hallucination.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3 self-start md:self-auto">
          <div className="hidden sm:flex flex-col text-right text-[11px] text-slate-400">
            <span>Local Model: <strong className="text-slate-200">llama3.2:latest</strong></span>
            <span>Policy: <strong className="text-amber-400">Fail-Closed Live Send</strong></span>
          </div>
          <button
            onClick={() => onNavigate('approvals')}
            className="px-3.5 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 rounded-lg text-xs font-medium transition-colors flex items-center space-x-2 shadow-sm"
          >
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span>Human Approval Queue</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Controls & Research (Left 4 cols) | Variations & Editor (Right 8 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* Left Column (5 Cols) */}
        <div className="lg:col-span-5 space-y-5">

          {/* Account Selector Card */}
          <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-xl p-4 md:p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-cobalt-800/80 pb-3">
              <div className="flex items-center space-x-2">
                <Building2 className="w-4 h-4 text-cobalt-400" />
                <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                  Target Account Selection
                </h3>
              </div>
              <span className="text-[11px] text-slate-400">
                {realCompanies.length} Real Leads
              </span>
            </div>

            {/* Filter Input */}
            <div>
              <input
                type="text"
                placeholder="Filter prospects by name or city..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cobalt-600"
              />
            </div>

            {/* Select Dropdown */}
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Select Company Record
              </label>
              <select
                value={activeCompanyId ?? ''}
                onChange={(e) => handleCompanyChange(Number(e.target.value))}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 font-medium"
              >
                <optgroup label="Real Commercial Prospects (Verified & Discovered)">
                  {realCompanies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} — {c.city} [{c.qualification_status.toUpperCase()} ({c.qualification_score}/100)]
                    </option>
                  ))}
                </optgroup>
                <optgroup label="⚠️ Synthetic Test Fixtures (Prohibited from Outreach)">
                  {syntheticCompanies.map((c) => (
                    <option key={c.id} value={c.id} disabled>
                      [SYNTHETIC] {c.name} — Demo Seed #{c.id}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>

            {/* Synthetic Guard Warning */}
            {isCurrentSynthetic && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs text-rose-300 space-y-1.5">
                <div className="flex items-center space-x-1.5 font-semibold text-rose-200">
                  <ShieldAlert className="w-4 h-4 text-rose-400" />
                  <span>Outreach Prohibited for Synthetic Fixture</span>
                </div>
                <p className="text-[11px] text-rose-300/90 leading-relaxed">
                  ActTrident CRM Lead Quality Policy strictly prohibits using synthetic test fixtures (IDs 1–12) for commercial email generation. Please select a genuine discovered commercial business above.
                </p>
              </div>
            )}
          </div>

          {/* Company Dossier & Contact Evidence Card */}
          {activeCompany && !isCurrentSynthetic && (
            <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-xl p-4 md:p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-cobalt-800/80 pb-3">
                <div className="flex items-center space-x-2">
                  <UserCheck className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                    Grounded Research Dossier
                  </h3>
                </div>
                <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${activeCompany.verification_status === 'verified'
                  ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-300'
                  : 'bg-amber-500/10 border border-amber-500/30 text-amber-300'
                  }`}>
                  {activeCompany.verification_status.toUpperCase()}
                </span>
              </div>

              {/* Company Facts */}
              <div className="space-y-2 text-xs">
                <div className="flex items-start justify-between">
                  <span className="text-slate-400">Company:</span>
                  <span className="font-semibold text-slate-100 text-right">{activeCompany.name}</span>
                </div>
                <div className="flex items-start justify-between">
                  <span className="text-slate-400">Location:</span>
                  <span className="text-slate-300 text-right">{activeCompany.city}, {activeCompany.state || activeCompany.country}</span>
                </div>
                <div className="flex items-start justify-between">
                  <span className="text-slate-400">Official Website:</span>
                  {activeCompany.website ? (
                    <a
                      href={activeCompany.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-cobalt-400 hover:text-cobalt-300 flex items-center space-x-1"
                    >
                      <span className="truncate max-w-[190px]">{activeCompany.website}</span>
                      <ExternalLink className="w-3 h-3 shrink-0" />
                    </a>
                  ) : (
                    <span className="text-amber-400/80 italic">Not available</span>
                  )}
                </div>
                <div className="flex items-start justify-between">
                  <span className="text-slate-400">Target Recipient:</span>
                  <span className="text-slate-200 text-right font-medium">
                    {activeCompany.decision_maker_name || 'IT Leadership / Technical Director'}
                    {activeCompany.decision_maker_role ? ` (${activeCompany.decision_maker_role})` : ''}
                  </span>
                </div>
                <div className="flex items-start justify-between">
                  <span className="text-slate-400">Contact Email:</span>
                  <span className="text-slate-200 text-right font-mono text-[11px]">
                    {activeCompany.public_email || 'Verified company domain address'}
                  </span>
                </div>
                {activeCompany.public_phone && (
                  <div className="flex items-start justify-between">
                    <span className="text-slate-400">Public Phone:</span>
                    <span className="text-slate-300 text-right font-mono text-[11px]">{activeCompany.public_phone}</span>
                  </div>
                )}
              </div>

              {/* Research Dossier Summary */}
              {researchReport?.dossier && (
                <div className="bg-cobalt-950/60 border border-cobalt-800/80 rounded-lg p-3 text-[11px] space-y-1.5">
                  <div className="font-semibold text-slate-300 flex items-center space-x-1">
                    <Sparkle className="w-3 h-3 text-cobalt-400" />
                    <span>Observed Capabilities & Context</span>
                  </div>
                  <p className="text-slate-400 leading-relaxed">
                    {researchReport.dossier.business_summary || activeCompany.description || 'Verified commercial IT operation.'}
                  </p>
                  {researchReport.dossier.tech_stack_detected?.length > 0 && (
                    <div className="pt-1 flex flex-wrap gap-1">
                      {researchReport.dossier.tech_stack_detected.slice(0, 4).map((tech: string, i: number) => (
                        <span key={i} className="px-1.5 py-0.5 bg-cobalt-900 border border-cobalt-700 rounded text-[10px] text-slate-300">
                          {tech}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Missing Information Alerts */}
              {variationsData?.missing_information && variationsData.missing_information.length > 0 && (
                <div className="p-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg text-[11px] text-amber-300 space-y-1">
                  <div className="font-semibold flex items-center space-x-1">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    <span>Evidence Boundaries Enforced:</span>
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 text-amber-300/90 text-[10px]">
                    {variationsData.missing_information.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Service Matching & Generation Settings */}
          {!isCurrentSynthetic && (
            <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-xl p-4 md:p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-cobalt-800/80 pb-3">
                <div className="flex items-center space-x-2">
                  <Target className="w-4 h-4 text-cobalt-400" />
                  <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                    Service Catalogue Matching
                  </h3>
                </div>
                <span className="text-[11px] text-cobalt-300 font-mono">
                  {services.length} Services Active
                </span>
              </div>

              {/* Matched Service Card */}
              {variationsData?.matched_service_code && (
                <div className="p-3 bg-cobalt-950/80 border border-cobalt-700/60 rounded-lg text-xs space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-200 font-mono text-[11px] text-cobalt-300">
                      [{variationsData.matched_service_code}]
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 text-[10px] font-semibold">
                      Match: {Math.round((variationsData.service_match_confidence || 0.8) * 100)}%
                    </span>
                  </div>
                  <div className="font-medium text-slate-100">{variationsData.matched_service_name}</div>
                  {variationsData.service_match_reason && (
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      {variationsData.service_match_reason}
                    </p>
                  )}
                  {variationsData.service_match_evidence && (
                    <div className="pt-1 text-[10px] text-slate-400 space-y-0.5">
                      <span className="font-semibold text-slate-300">Evidence Basis:</span>
                      <div className="truncate">• {variationsData.service_match_evidence}</div>
                    </div>
                  )}
                </div>
              )}

              {/* Optional Service Override */}
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">
                  Catalogue Target (Auto-Matched or Selectable)
                </label>
                <select
                  value={selectedServiceId ?? ''}
                  onChange={(e) => setSelectedServiceId(e.target.value ? Number(e.target.value) : undefined)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
                >
                  <option value="">Auto-Detect from Company Signals</option>
                  {services.map((s) => (
                    <option key={s.id} value={s.id}>
                      [{s.service_code}] {s.service_name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Tone Selector Pills */}
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1.5">
                  Tone & Perspective (4 Modes)
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {['Professional', 'Friendly', 'Consultative', 'Technical'].map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setTone(t)}
                      className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border text-center transition-colors ${tone === t
                        ? 'bg-cobalt-600 border-cobalt-500 text-white shadow-sm'
                        : 'bg-cobalt-950 border-cobalt-800 text-slate-300 hover:border-cobalt-700'
                        }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom Angles / Operator Notes */}
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">
                  Operator Notes / Custom Context (Optional)
                </label>
                <textarea
                  rows={2}
                  placeholder="e.g. emphasize endpoint hygiene for remote engineers or recent cloud migration..."
                  value={customNotes}
                  onChange={(e) => setCustomNotes(e.target.value)}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cobalt-600"
                />
              </div>

              {/* Generate Button */}
              <button
                onClick={handleGenerateVariations}
                disabled={generating || isCurrentSynthetic}
                className="w-full py-2.5 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-all flex items-center justify-center space-x-2 shadow-md"
              >
                {generating ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Querying Ollama (llama3.2:latest)...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 text-cobalt-200" />
                    <span>Generate 3 AI Email Variations</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Right Column (7 Cols) — Variations, Editor, Invalidation & History */}
        <div className="lg:col-span-7 space-y-5">

          {/* Main Outreach Workspace Card */}
          <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-xl p-4 md:p-5 flex flex-col space-y-4">

            {/* Status & Error Alerts */}
            {statusMsg && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-xs text-emerald-300 flex items-start space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <span className="leading-relaxed">{statusMsg}</span>
              </div>
            )}
            {errorMsg && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs text-rose-300 flex items-start space-x-2">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span className="leading-relaxed">{errorMsg}</span>
              </div>
            )}

            {/* 3 Variations Selector Tabs */}
            {variationsData && variationsData.variations.length > 0 ? (
              <div className="space-y-3 border-b border-cobalt-800 pb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Layers className="w-4 h-4 text-cobalt-400" />
                    <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                      Select Variation
                    </h3>
                  </div>
                  <span className="text-[11px] text-slate-400">
                    Model: <strong className="text-slate-200 font-mono">{variationsData.generation_model || 'llama3.2:latest'}</strong>
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {variationsData.variations.map((v, idx) => (
                    <button
                      key={v.variation_type}
                      type="button"
                      onClick={() => handleSelectVariation(idx)}
                      className={`p-2.5 rounded-lg text-left border transition-all ${activeVariationIndex === idx
                        ? 'bg-cobalt-800/90 border-cobalt-500 shadow-sm ring-1 ring-cobalt-500'
                        : 'bg-cobalt-950/60 border-cobalt-800 hover:border-cobalt-700 text-slate-400'
                        }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-[10px] font-bold uppercase tracking-wider ${activeVariationIndex === idx ? 'text-cobalt-300' : 'text-slate-500'
                          }`}>
                          Variation {String.fromCharCode(65 + idx)}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {v.body_text.trim().split(/\s+/).filter(Boolean).length}w
                        </span>
                      </div>
                      <div className={`text-xs font-semibold truncate ${activeVariationIndex === idx ? 'text-slate-100' : 'text-slate-300'
                        }`}>
                        {v.label}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Subject Line & Suggestions */}
            {(currentDraft || variationsData) ? (
              <div className="space-y-3">
                {/* Subject Suggestions Pills */}
                {variationsData?.subject_suggestions && variationsData.subject_suggestions.length > 0 && (
                  <div className="space-y-1.5">
                    <label className="block text-[11px] font-medium text-slate-400">
                      Subject Line Suggestions (Click to apply):
                    </label>
                    <div className="flex flex-wrap gap-1.5">
                      {variationsData.subject_suggestions.map((sug, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => handleSelectSubjectSuggestion(sug)}
                          className={`text-left px-2.5 py-1 rounded-md text-[11px] border transition-colors ${subject === sug
                            ? 'bg-cobalt-600/30 border-cobalt-500 text-slate-100 font-medium'
                            : 'bg-cobalt-950 border-cobalt-800/80 text-slate-300 hover:border-cobalt-700'
                            }`}
                        >
                          {sug}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Editable Subject Field */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[11px] font-medium text-slate-400">
                      Subject Line (Editable)
                    </label>
                    <span className="text-[10px] text-slate-500 font-mono">
                      {subject.length} chars
                    </span>
                  </div>
                  <input
                    type="text"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-cobalt-600 font-medium"
                    placeholder="Subject line..."
                  />
                </div>

                {/* Preview Tabs (Text vs HTML) */}
                <div className="flex items-center justify-between pt-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-[11px] font-medium text-slate-400">Body Content</span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      ({bodyText.trim().split(/\s+/).filter(Boolean).length} words)
                    </span>
                  </div>
                  <div className="flex items-center space-x-1.5 bg-cobalt-950 p-1 rounded-lg border border-cobalt-800">
                    <button
                      type="button"
                      onClick={() => setPreviewTab('text')}
                      className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${previewTab === 'text' ? 'bg-cobalt-600 text-white' : 'text-slate-400 hover:text-slate-200'
                        }`}
                    >
                      Plain Text (Edit)
                    </button>
                    <button
                      type="button"
                      onClick={() => setPreviewTab('html')}
                      className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${previewTab === 'html' ? 'bg-cobalt-600 text-white' : 'text-slate-400 hover:text-slate-200'
                        }`}
                    >
                      Rendered HTML
                    </button>
                  </div>
                </div>

                {/* Body Area */}
                {previewTab === 'text' ? (
                  <textarea
                    rows={12}
                    value={bodyText}
                    onChange={(e) => setBodyText(e.target.value)}
                    className="w-full bg-cobalt-950 border border-cobalt-800 rounded-lg p-3 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 font-mono leading-relaxed resize-y"
                    placeholder="Email body text..."
                  />
                ) : (
                  <div
                    className="w-full bg-white text-slate-900 rounded-lg p-4 text-xs overflow-auto max-h-[340px] border border-cobalt-700 leading-relaxed font-sans"
                    dangerouslySetInnerHTML={{
                      __html: currentDraft?.body_html || bodyText.replace(/\n\n/g, '<br/><br/>').replace(/\n/g, '<br/>')
                    }}
                  />
                )}

                {/* Invalidation Warning & Cryptographic Status */}
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-[11px] text-amber-300 space-y-1">
                  <div className="flex items-center space-x-1.5 font-semibold text-amber-200">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    <span>Cryptographic Approval Integrity:</span>
                  </div>
                  <p className="leading-relaxed text-amber-300/90 text-[10px]">
                    Modifying subject or body text increments draft version and invalidates prior cryptographic HMAC approvals. Explicit human re-approval in the queue is strictly required before any transmission.
                  </p>
                </div>

                {/* Footer Controls & Approval Workflow */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 border-t border-cobalt-800">
                  <div className="flex items-center space-x-2 text-[11px] text-slate-400">
                    <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                    <span>
                      Version: <strong className="text-slate-200 font-mono">v{currentDraft?.version || 1}</strong>
                    </span>
                    <span>•</span>
                    <span>
                      Status: <strong className="text-amber-300 font-semibold uppercase">{currentDraft?.approval_status || 'draft'}</strong>
                    </span>
                  </div>

                  <div className="flex items-center space-x-2 w-full sm:w-auto justify-end">
                    <button
                      type="button"
                      onClick={handleCopyToClipboard}
                      className="px-3 py-1.5 bg-cobalt-950 hover:bg-cobalt-900 border border-cobalt-700 text-slate-300 rounded-lg text-xs font-medium transition-colors flex items-center space-x-1"
                    >
                      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
                      <span>{copied ? 'Copied!' : 'Copy'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleSaveEdits}
                      disabled={saving}
                      className="px-3.5 py-1.5 bg-cobalt-800 hover:bg-cobalt-700 border border-cobalt-600 text-slate-100 rounded-lg text-xs font-medium transition-colors flex items-center space-x-1.5 shadow-sm"
                    >
                      <Save className="w-3.5 h-3.5 text-cobalt-300" />
                      <span>{saving ? 'Saving...' : 'Save Draft'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => onNavigate('approvals')}
                      className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition-colors flex items-center space-x-1.5 shadow-sm"
                    >
                      <span>Approval Queue</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-20 text-center text-xs text-slate-400 space-y-2">
                <Mail className="w-10 h-10 mx-auto text-cobalt-600 opacity-40 mb-3" />
                <p className="text-slate-300 font-medium text-sm">
                  {isCurrentSynthetic ? 'Synthetic Fixture Selected' : 'Ready to Generate AI Outreach'}
                </p>
                <p className="text-[11px] max-w-sm mx-auto text-slate-500">
                  {isCurrentSynthetic
                    ? 'Please pick a verified commercial prospect from the left to unlock email generation.'
                    : 'Choose your desired tone on the left and click "Generate 3 AI Email Variations" to consult local llama3.2.'}
                </p>
              </div>
            )}
          </div>

          {/* Historic Drafts for this Company */}
          {companyDrafts.length > 0 && (
            <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-xl p-4 md:p-5 space-y-3">
              <div className="flex items-center justify-between border-b border-cobalt-800 pb-2.5">
                <div className="flex items-center space-x-2">
                  <FileText className="w-4 h-4 text-cobalt-400" />
                  <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                    Company Draft History ({companyDrafts.length})
                  </h3>
                </div>
                <span className="text-[10px] text-slate-400">Click to load draft into editor</span>
              </div>

              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {companyDrafts.map((d) => (
                  <div
                    key={d.id}
                    onClick={() => handleLoadHistoricDraft(d)}
                    className={`p-2.5 rounded-lg border text-xs flex items-center justify-between cursor-pointer transition-colors ${currentDraft?.id === d.id
                      ? 'bg-cobalt-800/80 border-cobalt-600'
                      : 'bg-cobalt-950/60 border-cobalt-800/70 hover:border-cobalt-700'
                      }`}
                  >
                    <div className="space-y-0.5 truncate mr-3">
                      <div className="font-medium text-slate-200 truncate">
                        {d.subject || '(No subject)'}
                      </div>
                      <div className="text-[10px] text-slate-400 flex items-center space-x-2">
                        <span>v{d.version || 1}</span>
                        <span>•</span>
                        <span>{d.tone}</span>
                        <span>•</span>
                        <span>{d.variation_type || 'standard'}</span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2 shrink-0">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${d.approval_status === 'delivered' || d.approval_status === 'approved'
                        ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
                        : d.approval_status === 'sent'
                          ? 'bg-sky-500/10 text-sky-300 border border-sky-500/30'
                          : d.approval_status === 'bounced' || d.approval_status === 'rejected' || d.approval_status === 'failed'
                            ? 'bg-rose-500/10 text-rose-300 border border-rose-500/30'
                            : d.approval_status === 'simulated'
                              ? 'bg-purple-500/10 text-purple-300 border border-purple-500/30'
                              : 'bg-amber-500/10 text-amber-300 border border-amber-500/30'
                        }`}>
                        {d.approval_status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Phase 4D: Email Draft Lifecycle & Event Timeline */}
          {currentDraft && (
            <div data-testid="draft-timeline-card" className="bg-cobalt-900/80 border border-cobalt-800 rounded-xl p-4 md:p-5 space-y-3">
              <div className="flex items-center justify-between border-b border-cobalt-800 pb-2.5">
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                    Draft #{currentDraft.id} Event Timeline ({draftTimeline.length})
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => loadDraftTimeline(currentDraft.id)}
                  className="text-[11px] text-cobalt-300 hover:text-cobalt-200 underline"
                >
                  {timelineLoading ? 'Refreshing...' : 'Refresh Timeline'}
                </button>
              </div>
              {draftTimeline.length === 0 ? (
                <div className="text-[11px] text-slate-400 py-2">No lifecycle events recorded yet for this draft.</div>
              ) : (
                <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  {draftTimeline.map((ev: any) => (
                    <div key={ev.id} className="flex items-start justify-between gap-3 p-2.5 rounded-lg bg-cobalt-950/60 border border-cobalt-800/80 text-xs">
                      <div className="space-y-0.5 min-w-0">
                        <div className="flex items-center flex-wrap gap-2">
                          <span className="font-medium text-slate-200">{ev.label}</span>
                          {ev.is_simulated ? (
                            <span className="px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[10px] font-bold">
                              [SIMULATED]
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 rounded bg-cobalt-800 border border-cobalt-700 text-cobalt-200 text-[10px] font-semibold">
                              {ev.source}
                            </span>
                          )}
                        </div>
                        {ev.details && (
                          <div className="text-[11px] text-slate-400 truncate">{ev.details}</div>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-500 whitespace-nowrap shrink-0">
                        {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '—'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>
      </div>

      {/* Phase 4A: Delivery Readiness, Test-Mode Status & Read-Only DNS Auth Preflight */}
      <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-xl p-4 md:p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-cobalt-800 pb-3">
          <div>
            <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
              Delivery Readiness & DNS Authentication Preflight (Test-Mode Only)
            </h3>
            <p className="text-[11px] text-slate-400">
              Read-only SPF, DKIM, and DMARC inspection. Commercial live sending remains disabled.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold">
            <span className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300">
              LIVE_SEND_ENABLED: {testModeStatus?.live_send_enabled ? 'TRUE' : 'FALSE'}
            </span>
            <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
              TEST_MODE: {testModeStatus?.test_mode_enabled ? 'ENABLED' : 'DISABLED'}
            </span>
            <span className="px-2 py-0.5 rounded bg-cobalt-800 border border-cobalt-700 text-cobalt-200 uppercase">
              PROVIDER: {testModeStatus?.primary_provider || 'resend'}
            </span>
            <span
              data-testid="ollama-status-badge"
              className={`px-2 py-0.5 rounded border ${localAiStatus?.is_online || localAiStatus?.status === 'ready' || localAiStatus?.status === 'online'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                }`}
            >
              OLLAMA: {localAiStatus?.is_online || localAiStatus?.status === 'ready' || localAiStatus?.status === 'online' ? `ONLINE (${localAiStatus?.selected_model || localAiStatus?.active_model || 'llama3.2'})` : 'OFFLINE / FALLBACK'}
            </span>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={dnsDomain}
            onChange={(e) => setDnsDomain(e.target.value)}
            placeholder="Sending domain (e.g. acttrident.ai)"
            className="flex-1 bg-cobalt-950 border border-cobalt-800 rounded-lg px-3 py-1.5 text-xs text-slate-200"
          />
          <input
            type="text"
            value={dnsSelector}
            onChange={(e) => setDnsSelector(e.target.value)}
            placeholder="DKIM selector (e.g. default)"
            className="sm:w-44 bg-cobalt-950 border border-cobalt-800 rounded-lg px-3 py-1.5 text-xs text-slate-200"
          />
          <button
            type="button"
            disabled={dnsLoading}
            onClick={async () => {
              setDnsLoading(true);
              try {
                const res = await api.checkDomainDnsAuth(dnsDomain, dnsSelector);
                setDnsResult(res);
              } catch (e: any) {
                setErrorMsg(e.message || 'DNS check failed.');
              } finally {
                setDnsLoading(false);
              }
            }}
            className="px-4 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium"
          >
            {dnsLoading ? 'Checking DNS...' : 'Check DNS Auth'}
          </button>
        </div>

        {dnsResult && (
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              {(['spf', 'dkim', 'dmarc'] as const).map((proto) => {
                const item = dnsResult[proto];
                return (
                  <div key={proto} className="bg-cobalt-950/70 border border-cobalt-800 rounded-lg p-3 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold uppercase text-slate-200">{proto}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${item?.valid
                        ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
                        : 'bg-rose-500/10 text-rose-300 border border-rose-500/30'
                        }`}>
                        {item?.valid ? 'VALID' : item?.found ? 'INVALID / WARNINGS' : 'MISSING'}
                      </span>
                    </div>
                    {item?.errors?.map((err: string, idx: number) => (
                      <div key={idx} className="text-[11px] text-rose-300">• {err}</div>
                    ))}
                    {item?.warnings?.map((w: string, idx: number) => (
                      <div key={idx} className="text-[11px] text-amber-300">• {w}</div>
                    ))}
                    {item?.recommendations?.slice(0, 1).map((rec: string, idx: number) => (
                      <div key={idx} className="text-[10px] text-slate-400">Fix: {rec}</div>
                    ))}
                  </div>
                );
              })}
            </div>
            {dnsResult.resend_guidance && (
              <div className="bg-cobalt-950/60 border border-cobalt-800 rounded-lg p-3 text-[11px] text-slate-300 space-y-1">
                <div className="font-semibold text-cobalt-300">
                  Resend DNS Verification Guidance (Verified in Resend: {dnsResult.resend_guidance.domain_verified_in_resend ? 'YES' : 'NO'})
                </div>
                <div className="text-slate-400">{dnsResult.resend_guidance.note}</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 pt-1 text-[10px] font-mono text-slate-300">
                  {dnsResult.resend_guidance.required_records_from_resend_dashboard?.map((rec: any, i: number) => (
                    <div key={i}>[{rec.type}] {rec.host}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Phase 4C-A: Safe Test-Mode Resend Sandbox Send & Local Event Simulator */}
        <div className="border-t border-cobalt-800 pt-4 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                Resend Sandbox Test-Mode Send & Local Event Simulator
              </h4>
              <p className="text-[11px] text-slate-400">
                Sends strictly to official Resend test sink addresses while <code className="text-amber-300">LIVE_SEND_ENABLED=false</code>. Real prospect addresses are blocked.
              </p>
            </div>
            {currentDraft && (
              <span className="text-[11px] px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-700 text-slate-300">
                Draft #{currentDraft.id} • Approval: <strong className="uppercase">{currentDraft.approval_status}</strong>
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Test-Mode Sandbox Send */}
            <div className="bg-cobalt-950/60 border border-cobalt-800 rounded-lg p-3.5 space-y-3">
              <div className="text-[11px] font-semibold text-slate-200">1. Send to Official Resend Test Sink</div>
              <div className="flex flex-col sm:flex-row gap-2">
                <select
                  aria-label="Resend test sink recipient"
                  value={testSinkRecipient}
                  onChange={(e) => setTestSinkRecipient(e.target.value)}
                  className="flex-1 min-w-0 bg-cobalt-900 border border-cobalt-700 rounded-lg px-3 py-1.5 text-xs text-slate-200"
                >
                  <option value="delivered@resend.dev">delivered@resend.dev (Simulate Delivery)</option>
                  <option value="bounced@resend.dev">bounced@resend.dev (Simulate Bounce)</option>
                  <option value="complained@resend.dev">complained@resend.dev (Simulate Complaint)</option>
                </select>
                <button
                  type="button"
                  disabled={testSendLoading}
                  onClick={async () => {
                    setTestSendLoading(true);
                    setTestSendError(null);
                    try {
                      const res = await api.sendTestModeEmail({
                        recipient_email: testSinkRecipient,
                        subject: subject.trim() || `[Test-Mode] ActTrident Outreach Verification`,
                        body_text: bodyText.trim() || 'Test-mode sandbox verification message from ActTrident local operator UI.',
                        idempotency_key: `ui-test-${Date.now()}`,
                      });
                      setTestSendResult(res);
                    } catch (e: any) {
                      setTestSendError(e.message || 'Test-mode send failed or blocked.');
                    } finally {
                      setTestSendLoading(false);
                    }
                  }}
                  className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium whitespace-nowrap"
                >
                  {testSendLoading ? 'Sending Test...' : 'Send Test-Mode Email'}
                </button>
              </div>

              {testSendError && (
                <div className="text-[11px] text-rose-300 bg-rose-500/10 border border-rose-500/30 rounded p-2">
                  <strong>Blocked / Error:</strong> {testSendError}
                </div>
              )}

              {testSendResult && (() => {
                const rawStatus = (simResult?.internal_event || testSendResult.status || 'pending').toLowerCase();
                let badgeLabel = 'Pending';
                let badgeClass = 'bg-slate-500/10 text-slate-300 border-slate-500/30';
                if (rawStatus === 'blocked') {
                  badgeLabel = 'Blocked';
                  badgeClass = 'bg-rose-500/10 text-rose-300 border-rose-500/30';
                } else if (rawStatus === 'sent' || rawStatus === 'accepted') {
                  badgeLabel = 'Accepted by Resend';
                  badgeClass = 'bg-sky-500/10 text-sky-300 border-sky-500/30';
                } else if (rawStatus === 'delivered') {
                  badgeLabel = 'Delivered';
                  badgeClass = 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30';
                } else if (rawStatus === 'bounced' || rawStatus === 'bounce') {
                  badgeLabel = 'Bounced';
                  badgeClass = 'bg-rose-500/10 text-rose-300 border-rose-500/30';
                } else if (rawStatus === 'complained' || rawStatus === 'complaint') {
                  badgeLabel = 'Complained';
                  badgeClass = 'bg-amber-500/10 text-amber-300 border-amber-500/30';
                } else if (rawStatus === 'failed') {
                  badgeLabel = 'Failed';
                  badgeClass = 'bg-rose-500/10 text-rose-300 border-rose-500/30';
                } else if (rawStatus === 'deferred') {
                  badgeLabel = 'Delivery Delayed';
                  badgeClass = 'bg-amber-500/10 text-amber-300 border-amber-500/30';
                }
                return (
                  <div className="text-[11px] bg-cobalt-900/70 border border-cobalt-800 rounded p-2.5 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-slate-400">Provider Status:</span>
                      <span data-testid="test-mode-status-badge" className={`px-2 py-0.5 rounded border text-[10px] font-semibold ${badgeClass}`}>
                        {badgeLabel}
                      </span>
                    </div>
                    <div className="text-slate-300 truncate">
                      Message ID: <span className="font-mono text-[10px] text-cobalt-300">{testSendResult.provider_message_id || 'N/A'}</span>
                    </div>
                    <div className="text-slate-400 truncate">
                      Note: {testSendResult.note || testSendResult.provider_response?.id || 'Accepted by Resend sandbox'}
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Safe Local Event Simulator ([SIMULATED]) */}
            <div className="bg-cobalt-950/60 border border-cobalt-800 rounded-lg p-3.5 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-semibold text-slate-200">2. Local Webhook Event Simulator</span>
                <span className="px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[10px] font-bold">
                  [SIMULATED]
                </span>
              </div>
              <div className="flex flex-col sm:flex-row gap-2">
                <select
                  aria-label="Simulated Resend event type"
                  value={simEventType}
                  onChange={(e) => setSimEventType(e.target.value)}
                  className="flex-1 min-w-0 bg-cobalt-900 border border-cobalt-700 rounded-lg px-3 py-1.5 text-xs text-slate-200"
                >
                  <option value="email.sent">[SIMULATED] email.sent</option>
                  <option value="email.delivered">[SIMULATED] email.delivered</option>
                  <option value="email.delivery_delayed">[SIMULATED] email.delivery_delayed</option>
                  <option value="email.bounced">[SIMULATED] email.bounced (Auto-Suppress)</option>
                  <option value="email.complained">[SIMULATED] email.complained (Auto-Suppress)</option>
                  <option value="email.failed">[SIMULATED] email.failed</option>
                </select>
                <button
                  type="button"
                  disabled={simLoading}
                  onClick={async () => {
                    setSimLoading(true);
                    setErrorMsg(null);
                    try {
                      const res = await api.simulateResendEvent({
                        event_type: simEventType,
                        event_id: `sim-ui-${Date.now()}`,
                        recipient_email: testSinkRecipient,
                        draft_id: currentDraft?.id,
                        provider_message_id: testSendResult?.provider_message_id,
                      });
                      setSimResult(res);
                      loadDraftTimeline(currentDraft?.id);
                    } catch (e: any) {
                      setErrorMsg(e.message || 'Simulated event failed.');
                    } finally {
                      setSimLoading(false);
                    }
                  }}
                  className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium whitespace-nowrap"
                >
                  {simLoading ? 'Simulating...' : 'Simulate Event'}
                </button>
              </div>
              {simResult && (
                <div className="text-[11px] bg-cobalt-900/70 border border-amber-500/30 rounded p-2.5 space-y-1">
                  <div className="text-amber-300 font-semibold">[SIMULATED] Local Event Recorded ({simResult.status})</div>
                  <div className="text-slate-300">
                    Event: <span className="font-mono">{simResult.resend_event}</span> • Status: <strong>{simResult.internal_event}</strong>
                  </div>
                  <div className="text-slate-400">
                    Suppressed: {simResult.suppressed_added ? 'YES (Added to Suppression Registry)' : 'NO'}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
