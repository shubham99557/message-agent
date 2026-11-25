import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Company, ViewType } from '../types';
import { AutonomousAgentModal } from '../components/AutonomousAgentModal';
import {
  BrainCircuit,
  CheckCircle2,
  AlertTriangle,
  Laptop,
  Shield,
  Send,
  ExternalLink,
  RefreshCw,
  ArrowRight,
  Play
} from 'lucide-react';

interface ResearchViewProps {
  selectedCompany?: Company | null;
  onNavigate: (view: ViewType) => void;
}

export const ResearchView: React.FC<ResearchViewProps> = ({ selectedCompany, onNavigate }) => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [activeCompanyId, setActiveCompanyId] = useState<number | null>(selectedCompany?.id ?? null);
  const [activeCompany, setActiveCompany] = useState<Company | null>(selectedCompany ?? null);
  const [report, setReport] = useState<any>(null);
  const [qualification, setQualification] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [qualifying, setQualifying] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyMessage, setVerifyMessage] = useState<string | null>(null);
  const [showAgentModal, setShowAgentModal] = useState(false);

  useEffect(() => {
    async function loadCompaniesList() {
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
    loadCompaniesList();
  }, []);

  const fetchDossier = async (companyId: number) => {
    setLoading(true);
    try {
      const comp = await api.getCompany(companyId);
      setActiveCompany(comp);

      // Try get existing report, or generate if absent
      try {
        const rep = await api.getResearchReport(companyId);
        setReport(rep);
      } catch {
        const rep = await api.generateResearchReport(companyId);
        setReport(rep);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeCompanyId) {
      fetchDossier(activeCompanyId);
    }
  }, [activeCompanyId]);

  const handleRunQualification = async () => {
    if (!activeCompanyId) return;
    setQualifying(true);
    try {
      const res = await api.qualifyCompany(activeCompanyId);
      setQualification(res);
      // Refresh company record
      const comp = await api.getCompany(activeCompanyId);
      setActiveCompany(comp);
    } catch (err: any) {
      alert(`Qualification error: ${err.message}`);
    } finally {
      setQualifying(false);
    }
  };

  const handleMarkVerified = async () => {
    if (!activeCompany) return;
    setVerifying(true);
    setVerifyMessage(null);
    try {
      const updated = await api.verifyCompany(activeCompany.id, {
        verification_status: 'verified',
        verification_method: 'manual_analyst_review',
        source_url: activeCompany.website || undefined,
        notes: 'Verified by analyst in Research View',
      });
      setActiveCompany(updated);
      const rep = await api.generateResearchReport(activeCompany.id);
      setReport(rep);
      setVerifyMessage('Record marked as verified and research report refreshed.');
    } catch (err: any) {
      alert(`Verification failed: ${err.message}`);
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Selector Bar */}
      <div className="bg-cobalt-900/90 border border-cobalt-800 rounded-lg p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded bg-cobalt-800 border border-cobalt-700 flex items-center justify-center text-cobalt-400 shrink-0">
            <BrainCircuit className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-100 tracking-tight">AI Research Agent & Lead Qualification</h2>
            <p className="text-xs text-slate-400">Concise business dossiers with zero fabricated claims or security breach hallucinations.</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setShowAgentModal(true)}
            className="px-3.5 py-1.5 bg-gradient-to-r from-indigo-600 to-cobalt-600 hover:from-indigo-500 hover:to-cobalt-500 text-white rounded text-xs font-bold transition-all flex items-center space-x-1.5 shadow"
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            <span>🚀 Run Autonomous Agent</span>
          </button>

          <div className="flex items-center space-x-2">
            <label className="text-xs text-slate-400 shrink-0">Company:</label>
            <select
              value={activeCompanyId ?? ''}
              onChange={(e) => setActiveCompanyId(Number(e.target.value))}
              className="bg-cobalt-950 border border-cobalt-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 min-w-[200px]"
            >
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.city})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="p-16 text-center text-xs text-slate-400">Synthesizing verified company intelligence...</div>
      ) : activeCompany ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: 7-Factor Qualification */}
          <div className="space-y-6">
            <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">7-Factor AI Qualification</h3>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                    activeCompany.qualification_status === 'High priority'
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      : activeCompany.qualification_status === 'Medium priority'
                      ? 'bg-cobalt-500/20 text-cobalt-300 border-cobalt-500/30'
                      : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  }`}
                >
                  {activeCompany.qualification_status}
                </span>
              </div>

              <div className="text-center py-3 bg-cobalt-950/80 rounded border border-cobalt-800 mb-4">
                <div className="text-3xl font-bold font-mono text-cobalt-400">{activeCompany.qualification_score}/100</div>
                <div className="text-[11px] text-slate-400 mt-0.5">Automated Compatibility Score</div>
              </div>

              <div className="text-xs text-slate-300 bg-cobalt-950/60 p-3 rounded border border-cobalt-800/80 mb-4 leading-relaxed">
                <span className="font-semibold text-slate-200 block mb-1">Qualification Rationale:</span>
                {activeCompany.qualification_reason || 'Run evaluation to analyze 7-factor scoring criteria.'}
              </div>

              {/* Render Individual Factors if available */}
              {(() => {
                let factorsList: any[] = qualification?.factors || [];
                if (!factorsList.length && activeCompany.qualification_factors) {
                  try {
                    factorsList = JSON.parse(activeCompany.qualification_factors);
                  } catch {}
                }
                if (!factorsList.length) return null;
                return (
                  <div className="space-y-2 mb-4 max-h-60 overflow-y-auto pr-1">
                    <span className="text-[11px] font-semibold text-slate-300 block uppercase tracking-wider">Scored Factors</span>
                    {factorsList.map((f: any, idx: number) => (
                      <div key={idx} className="bg-cobalt-950/70 p-2.5 rounded border border-cobalt-800/80 text-[11px] space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-slate-200 truncate pr-2">{f.factor_name}</span>
                          <span className={`font-mono font-bold shrink-0 ${f.passed ? 'text-emerald-400' : 'text-slate-400'}`}>
                            +{f.score_weight} pts
                          </span>
                        </div>
                        <p className="text-slate-400 text-[10px] leading-tight">{f.evidence}</p>
                        {f.evidence_source && (
                          <div className="text-[10px] text-cobalt-400 flex items-center justify-between">
                            <span className="truncate max-w-[150px]">Source: {f.evidence_source}</span>
                            <span className="text-slate-400 font-mono">Conf: {Math.round((f.confidence ?? 1) * 100)}%</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                );
              })()}

              {/* Strict Laptop Distinction Alert */}
              <div className="text-[11px] text-amber-300/90 bg-amber-500/10 p-3 rounded border border-amber-500/30 leading-relaxed mb-4">
                <strong className="block text-amber-200 mb-0.5">Compliance Notice:</strong>
                Employee count is distinct from laptop fleet count. 5+ managed devices are certified only with documented public evidence.
              </div>

              <button
                onClick={handleRunQualification}
                disabled={qualifying}
                className="w-full py-2 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors flex items-center justify-center space-x-1.5 shadow-sm"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${qualifying ? 'animate-spin' : ''}`} />
                <span>{qualifying ? 'Evaluating Factors...' : 'Re-run 7-Factor Qualification'}</span>
              </button>
            </div>

            {/* Quick Profile Snapshot */}
            <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5 text-xs space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Company Snapshot</h3>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono border ${
                    activeCompany.is_demo || activeCompany.verification_status === 'demo_fixture'
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                      : activeCompany.verification_status === 'verified'
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      : 'bg-cobalt-950 text-slate-300 border-cobalt-700'
                  }`}
                >
                  {activeCompany.is_demo || activeCompany.verification_status === 'demo_fixture'
                    ? 'DEMO FIXTURE'
                    : (activeCompany.verification_status || 'unverified')}
                </span>
              </div>
              <div className="space-y-2 text-slate-300">
                <div className="flex justify-between">
                  <span className="text-slate-400">Location:</span>
                  <span>{activeCompany.city}{activeCompany.state ? `, ${activeCompany.state}` : ''}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Industry:</span>
                  <span>{activeCompany.industry || 'Unspecified'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Verified Laptops:</span>
                  <span className="font-mono text-emerald-400">{activeCompany.laptop_count_verified ?? 'Unknown'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Decision Maker:</span>
                  <span>{activeCompany.decision_maker_name || 'Unverified'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Official Channel:</span>
                  <span className="font-mono text-cobalt-300">{activeCompany.public_email || activeCompany.public_phone || 'None verified'}</span>
                </div>
              </div>
              {!(activeCompany.is_demo || activeCompany.verification_status === 'demo_fixture') &&
                activeCompany.verification_status !== 'verified' && (
                  <button
                    onClick={handleMarkVerified}
                    disabled={verifying}
                    className="w-full py-1.5 bg-emerald-600/90 hover:bg-emerald-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors flex items-center justify-center space-x-1.5"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>{verifying ? 'Verifying...' : 'Mark Record Verified'}</span>
                  </button>
                )}
              {verifyMessage && (
                <div className="text-[11px] text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 rounded p-2">
                  {verifyMessage}
                </div>
              )}
            </div>
          </div>

          {/* Right 2 Columns: Full Research Report */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-6 space-y-5">
              <div className="flex items-center justify-between border-b border-cobalt-800 pb-4">
                <div>
                  <h3 className="text-base font-bold text-slate-100">{activeCompany.name} - Research Report</h3>
                  <p className="text-xs text-slate-400 mt-0.5">Synthesized by ActTrident Research Agent</p>
                </div>
                <button
                  onClick={() => onNavigate('email')}
                  className="px-3 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1"
                >
                  <span>Draft Outreach Email</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>

              {report ? (
                <div className="space-y-4 text-xs">
                  <div>
                    <h4 className="font-semibold text-slate-200 mb-1">Executive Summary</h4>
                    <p className="text-slate-300 leading-relaxed bg-cobalt-950/60 p-3 rounded border border-cobalt-800/80">
                      {report.summary}
                    </p>
                  </div>

                  <div>
                    <h4 className="font-semibold text-slate-200 mb-1">Services & Operations</h4>
                    <p className="text-slate-300 leading-relaxed bg-cobalt-950/60 p-3 rounded border border-cobalt-800/80">
                      {report.services}
                    </p>
                  </div>

                  <div>
                    <h4 className="font-semibold text-slate-200 mb-1">Likely Technology Requirements</h4>
                    <p className="text-slate-300 leading-relaxed bg-cobalt-950/60 p-3 rounded border border-cobalt-800/80">
                      {report.likely_tech_requirements}
                    </p>
                  </div>

                  <div className="bg-cobalt-950/90 border border-cobalt-700/80 rounded p-4">
                    <h4 className="font-semibold text-cobalt-300 mb-2 flex items-center space-x-1.5">
                      <Shield className="w-4 h-4 text-cobalt-400" />
                      <span>Potential ActTrident Use Cases & 90-Day Evaluation</span>
                    </h4>
                    <pre className="text-slate-200 whitespace-pre-wrap font-sans leading-relaxed">
                      {report.potential_acttrident_use_cases}
                    </pre>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h4 className="font-semibold text-slate-200 mb-1">Target Decision Maker Role</h4>
                      <p className="text-slate-300 bg-cobalt-950/60 p-2.5 rounded border border-cobalt-800/80">
                        {report.relevant_decision_maker_role}
                      </p>
                    </div>
                    <div>
                      <h4 className="font-semibold text-slate-200 mb-1">Recommended Outreach Approach</h4>
                      <p className="text-slate-300 bg-cobalt-950/60 p-2.5 rounded border border-cobalt-800/80">
                        {report.recommended_outreach_approach}
                      </p>
                    </div>
                  </div>

                  {report.missing_information && (
                    <div className="bg-amber-500/10 border border-amber-500/30 rounded p-3">
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="font-semibold text-amber-200 flex items-center space-x-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                          <span>Missing / Unverified Information</span>
                        </h4>
                        {typeof report.confidence_level === 'number' && (
                          <span className="text-[11px] font-mono text-amber-300">
                            Evidence Confidence: {Math.round(report.confidence_level * 100)}%
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-amber-200/90 leading-relaxed">
                        {report.missing_information}
                      </p>
                    </div>
                  )}

                  <div>
                    <h4 className="font-semibold text-slate-400 mb-1">Recorded Information Sources</h4>
                    <p className="text-[11px] font-mono text-slate-400 bg-cobalt-950/60 p-2.5 rounded border border-cobalt-800/80 break-all">
                      {report.sources_summary}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-xs text-slate-400">
                  <p>Click below to generate initial AI research dossier.</p>
                  <button
                    onClick={() => fetchDossier(activeCompany.id)}
                    className="mt-3 px-3 py-1.5 bg-cobalt-600 text-white rounded text-xs font-medium"
                  >
                    Generate Report
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="p-12 text-center text-xs text-slate-400">No company selected.</div>
      )}

      {/* Autonomous Outreach Agent Modal */}
      <AutonomousAgentModal
        isOpen={showAgentModal}
        onClose={() => setShowAgentModal(false)}
        onNavigate={onNavigate}
        onCycleComplete={() => {
          if (activeCompanyId) fetchDossier(activeCompanyId);
        }}
      />
    </div>
  );
};
