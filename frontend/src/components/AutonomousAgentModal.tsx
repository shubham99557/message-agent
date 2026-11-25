import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ViewType } from '../types';
import {
  BrainCircuit,
  Play,
  CheckCircle2,
  AlertTriangle,
  X,
  RefreshCw,
  ArrowRight,
  ShieldCheck,
  Mail,
  MessageSquare,
  Linkedin,
  Cpu,
  Layers,
  Sparkles,
  ExternalLink,
  Flame
} from 'lucide-react';

interface AutonomousAgentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (view: ViewType) => void;
  onCycleComplete?: () => void;
}

export const AutonomousAgentModal: React.FC<AutonomousAgentModalProps> = ({
  isOpen,
  onClose,
  onNavigate,
  onCycleComplete,
}) => {
  const [targetCity, setTargetCity] = useState<string>('All');
  const [customCity, setCustomCity] = useState<string>('');
  const [maxProspects, setMaxProspects] = useState<number>(10);
  const [autoApprove, setAutoApprove] = useState<boolean>(true);
  const [channels, setChannels] = useState<{ email: boolean; whatsapp: boolean; linkedin: boolean }>({
    email: true,
    whatsapp: true,
    linkedin: true,
  });

  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [agentStatus, setAgentStatus] = useState<any>(null);

  useEffect(() => {
    if (isOpen) {
      api.getAgentStatus()
        .then(setAgentStatus)
        .catch(console.error);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleLaunchCycle = async () => {
    setIsRunning(true);
    setError(null);
    setResult(null);

    const activeChannels: string[] = [];
    if (channels.email) activeChannels.push('email');
    if (channels.whatsapp) activeChannels.push('whatsapp');
    if (channels.linkedin) activeChannels.push('linkedin');

    try {
      const selectedCity = targetCity === 'Custom' ? (customCity.trim() || undefined) : (targetCity === 'All' ? undefined : targetCity);
      const res = await api.runAutonomousCycle({
        target_city: selectedCity,
        channels: activeChannels,
        max_prospects: maxProspects,
        auto_approve_simulation: autoApprove,
      });
      setResult(res);
      if (onCycleComplete) {
        onCycleComplete();
      }
    } catch (err: any) {
      setError(err.message || 'Autonomous cycle failed to execute.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-cobalt-950 border border-cobalt-800 rounded-xl shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden text-slate-200">
        
        {/* Modal Header */}
        <div className="p-5 bg-gradient-to-r from-cobalt-900 to-cobalt-950 border-b border-cobalt-800 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-cobalt-800/90 border border-cobalt-700 flex items-center justify-center p-1.5 shadow-inner">
              <img src="/acttrident-mark.png" alt="ActTrident" className="w-full h-full object-contain" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-slate-100 tracking-tight">ActTrident Autonomous Sales Outreach Agent</h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  BRAIN V2 ACTIVE
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Full-cycle automation: Regional Discovery ➔ AI Tech Profiling ➔ 7-Factor Qualification (5+ Laptops) ➔ Copywriting ➔ Dispatch ➔ CRM.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-cobalt-800/60 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          
          {/* Controls Bar */}
          <div className="bg-cobalt-900/60 border border-cobalt-800 rounded-lg p-4 space-y-4">
            <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
              <Sparkles className="w-3.5 h-3.5 text-cobalt-400" />
              <span>Outreach Run Configuration</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Region */}
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Target Cluster / Geography</label>
                <select
                  value={targetCity}
                  onChange={(e) => setTargetCity(e.target.value)}
                  disabled={isRunning}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600 font-medium"
                >
                  <option value="All">All Nationwide Hubs (Multi-City)</option>
                  <optgroup label="Regional Focus Hubs">
                    <option value="Siliguri">Siliguri, WB (North Bengal Hub)</option>
                    <option value="Gangtok">Gangtok, Sikkim (Alpine Tech Hub)</option>
                    <option value="Patna">Patna, Bihar (Capital Tech Corridor)</option>
                    <option value="Bhagalpur">Bhagalpur, Bihar (Commercial District)</option>
                  </optgroup>
                  <optgroup label="Tier 1 Metros & Tech Corridors">
                    <option value="Bengaluru">Bengaluru, KA (Silicon Valley of India)</option>
                    <option value="Hyderabad">Hyderabad, TG (HITEC City Hub)</option>
                    <option value="Pune">Pune, MH (IT & Auto Cluster)</option>
                    <option value="Mumbai">Mumbai, MH (Financial & SaaS Metro)</option>
                    <option value="Delhi">Delhi NCR (National Capital Region)</option>
                    <option value="Gurugram">Gurugram, HR (Enterprise Tech)</option>
                    <option value="Noida">Noida, UP (IT & Tech Corridor)</option>
                    <option value="Chennai">Chennai, TN (SaaS & Hardware Corridor)</option>
                    <option value="Kolkata">Kolkata, WB (Salt Lake / New Town Hub)</option>
                    <option value="Ahmedabad">Ahmedabad, GJ (Commercial & FinTech)</option>
                  </optgroup>
                  <optgroup label="Emerging Commercial Centers">
                    <option value="Jaipur">Jaipur, RJ (Emerging Tech)</option>
                    <option value="Indore">Indore, MP (Central India Hub)</option>
                    <option value="Kochi">Kochi, Kerala (Infopark Hub)</option>
                    <option value="Bhubaneswar">Bhubaneswar, Odisha (Smart Tech City)</option>
                    <option value="Chandigarh">Chandigarh (Northern IT Park)</option>
                    <option value="Guwahati">Guwahati, Assam (Northeast Gateway)</option>
                    <option value="Lucknow">Lucknow, UP (State Capital Corridor)</option>
                  </optgroup>
                  <option value="Custom">✨ Custom City / Any Other Location...</option>
                </select>

                {targetCity === 'Custom' && (
                  <div className="mt-2">
                    <input
                      type="text"
                      placeholder="Type ANY city, town or state (e.g. Surat, Ranchi, Dehradun)..."
                      value={customCity}
                      onChange={(e) => setCustomCity(e.target.value)}
                      disabled={isRunning}
                      className="w-full bg-cobalt-950 border border-cobalt-700 rounded px-3 py-1.5 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cobalt-500"
                      autoFocus
                    />
                  </div>
                )}
              </div>

              {/* Max Prospects */}
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Max Prospects</label>
                <select
                  value={maxProspects}
                  onChange={(e) => setMaxProspects(Number(e.target.value))}
                  disabled={isRunning}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
                >
                  <option value={5}>Top 5 Verified Enterprises</option>
                  <option value={10}>Top 10 Verified Enterprises</option>
                  <option value={20}>Batch of 20 Enterprises</option>
                </select>
              </div>

              {/* Execution Mode */}
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Execution Mode</label>
                <select
                  value={autoApprove ? 'auto' : 'manual'}
                  onChange={(e) => setAutoApprove(e.target.value === 'auto')}
                  disabled={isRunning}
                  className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
                >
                  <option value="auto">Safe Simulation & Auto-Queue (Recommended)</option>
                  <option value="manual">Manual Approval First (Hold in Review Queue)</option>
                </select>
              </div>
            </div>

            {/* Channels Row */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-cobalt-800/80">
              <div className="flex items-center space-x-4 text-xs">
                <span className="text-slate-400 font-medium">Active Channels:</span>
                <label className="flex items-center space-x-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={channels.email}
                    onChange={(e) => setChannels({ ...channels, email: e.target.checked })}
                    disabled={isRunning}
                    className="rounded bg-cobalt-950 border-cobalt-700 text-cobalt-600 focus:ring-0"
                  />
                  <span className="flex items-center space-x-1 text-slate-300">
                    <Mail className="w-3.5 h-3.5 text-cobalt-400" />
                    <span>Email (SMTP / Gmail)</span>
                  </span>
                </label>

                <label className="flex items-center space-x-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={channels.whatsapp}
                    onChange={(e) => setChannels({ ...channels, whatsapp: e.target.checked })}
                    disabled={isRunning}
                    className="rounded bg-cobalt-950 border-cobalt-700 text-cobalt-600 focus:ring-0"
                  />
                  <span className="flex items-center space-x-1 text-slate-300">
                    <MessageSquare className="w-3.5 h-3.5 text-emerald-400" />
                    <span>WhatsApp (Meta v22.0)</span>
                  </span>
                </label>

                <label className="flex items-center space-x-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={channels.linkedin}
                    onChange={(e) => setChannels({ ...channels, linkedin: e.target.checked })}
                    disabled={isRunning}
                    className="rounded bg-cobalt-950 border-cobalt-700 text-cobalt-600 focus:ring-0"
                  />
                  <span className="flex items-center space-x-1 text-slate-300">
                    <Linkedin className="w-3.5 h-3.5 text-sky-400" />
                    <span>LinkedIn (Manual Handoff)</span>
                  </span>
                </label>
              </div>

              <button
                onClick={handleLaunchCycle}
                disabled={isRunning}
                className="px-5 py-2.5 bg-gradient-to-r from-cobalt-600 to-indigo-600 hover:from-cobalt-500 hover:to-indigo-500 disabled:opacity-50 text-white font-semibold rounded-lg text-xs transition-all flex items-center space-x-2 shadow-lg shadow-cobalt-900/50"
              >
                {isRunning ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Agent Running Autonomous Outreach...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-white" />
                    <span>🚀 Launch Autonomous Outreach Run</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Error Notice */}
          {error && (
            <div className="bg-rose-950/60 border border-rose-500/40 rounded-lg p-4 flex items-start space-x-3 text-xs text-rose-300">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <strong>Execution Error:</strong> {error}
              </div>
            </div>
          )}

          {/* Result Telemetry Banner */}
          {result && (
            <div className="space-y-4">
              <div className="bg-emerald-950/40 border border-emerald-500/40 rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-xs font-semibold text-emerald-300">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Autonomous Outreach Run Completed Successfully in {result.duration_seconds}s</span>
                  </div>
                  <span className="text-[11px] text-slate-400 font-mono">
                    Campaign: <strong>{result.campaign_name}</strong>
                  </span>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 text-xs">
                  <div className="bg-cobalt-950 p-2.5 rounded border border-cobalt-800 text-center">
                    <span className="text-slate-400 block text-[10px]">Discovered</span>
                    <span className="text-lg font-mono font-bold text-slate-100">{result.metrics.prospects_discovered}</span>
                  </div>
                  <div className="bg-cobalt-950 p-2.5 rounded border border-cobalt-800 text-center">
                    <span className="text-slate-400 block text-[10px]">Researched</span>
                    <span className="text-lg font-mono font-bold text-cobalt-400">{result.metrics.researched}</span>
                  </div>
                  <div className="bg-cobalt-950 p-2.5 rounded border border-cobalt-800 text-center">
                    <span className="text-slate-400 block text-[10px]">Qualified (5+)</span>
                    <span className="text-lg font-mono font-bold text-emerald-400">{result.metrics.qualified}</span>
                  </div>
                  <div className="bg-cobalt-950 p-2.5 rounded border border-cobalt-800 text-center">
                    <span className="text-slate-400 block text-[10px]">Drafts Created</span>
                    <span className="text-lg font-mono font-bold text-indigo-400">{result.metrics.drafts_created}</span>
                  </div>
                  <div className="bg-cobalt-950 p-2.5 rounded border border-cobalt-800 text-center">
                    <span className="text-slate-400 block text-[10px]">Approved</span>
                    <span className="text-lg font-mono font-bold text-amber-300">{result.metrics.approved}</span>
                  </div>
                  <div className="bg-cobalt-950 p-2.5 rounded border border-cobalt-800 text-center">
                    <span className="text-slate-400 block text-[10px]">Outbox Staged</span>
                    <span className="text-lg font-mono font-bold text-sky-400">{result.metrics.outbox_queued}</span>
                  </div>
                  <div className="bg-cobalt-950 p-2.5 rounded border border-cobalt-800 text-center">
                    <span className="text-slate-400 block text-[10px]">Dispatched</span>
                    <span className="text-lg font-mono font-bold text-emerald-400">{result.metrics.dispatched}</span>
                  </div>
                </div>

                {/* Action Shortcuts */}
                <div className="pt-2 flex flex-wrap items-center justify-between gap-2 border-t border-emerald-500/20 text-xs">
                  <span className="text-slate-400">Next Recommended Action:</span>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => {
                        onClose();
                        onNavigate('approvals');
                      }}
                      className="px-3 py-1.5 bg-cobalt-900 hover:bg-cobalt-800 border border-cobalt-700 text-slate-200 rounded text-xs font-medium transition-colors flex items-center space-x-1"
                    >
                      <span>Review Approval Queue ({result.metrics.approved || 0})</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        onClose();
                        onNavigate('campaigns');
                      }}
                      className="px-3 py-1.5 bg-cobalt-900 hover:bg-cobalt-800 border border-cobalt-700 text-slate-200 rounded text-xs font-medium transition-colors flex items-center space-x-1"
                    >
                      <span>Check Campaigns & Dispatch ({result.metrics.dispatched || 0})</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        onClose();
                        onNavigate('crm');
                      }}
                      className="px-3 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1"
                    >
                      <span>View CRM Pipeline</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Execution Log Stream */}
              <div className="bg-cobalt-950 border border-cobalt-800 rounded-lg p-4 space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-400 uppercase tracking-wider pb-2 border-b border-cobalt-800">
                  <div className="flex items-center space-x-1.5">
                    <Cpu className="w-3.5 h-3.5 text-cobalt-400" />
                    <span>Agent Brain Execution Chronology ({result.logs.length} Steps)</span>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">Simulated Safe Outreach</span>
                </div>

                <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1 text-[11px] font-mono">
                  {result.logs.map((log: any, idx: number) => (
                    <div
                      key={idx}
                      className={`p-2 rounded border flex items-start space-x-2.5 ${
                        log.level === 'warning'
                          ? 'bg-amber-950/20 border-amber-500/30 text-amber-300'
                          : log.level === 'error'
                          ? 'bg-rose-950/30 border-rose-500/40 text-rose-300'
                          : 'bg-cobalt-900/40 border-cobalt-800 text-slate-300'
                      }`}
                    >
                      <span className="text-[10px] text-slate-400 shrink-0 mt-0.5">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                      <div className="flex-1">
                        <strong className="text-slate-100 block">{log.title}</strong>
                        <p className="text-slate-400 text-[10px] mt-0.5 leading-relaxed">{log.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Explanatory Pipeline Cards */}
          {!result && !isRunning && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div className="bg-cobalt-900/40 border border-cobalt-800 p-3.5 rounded-lg space-y-1.5">
                <div className="font-semibold text-slate-200 flex items-center space-x-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span>1. Verified Device Verification</span>
                </div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Strictly verifies 5+ managed laptops using official MCA registry filings, careers portals, or government vendor registries. Never fabricates device counts.
                </p>
              </div>

              <div className="bg-cobalt-900/40 border border-cobalt-800 p-3.5 rounded-lg space-y-1.5">
                <div className="font-semibold text-slate-200 flex items-center space-x-1.5">
                  <BrainCircuit className="w-4 h-4 text-cobalt-400" />
                  <span>2. Tailored 90-Day Proposal</span>
                </div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Synthesizes custom value propositions addressing browser security, code exfiltration, and distributed workstation posture with a 90-day complimentary evaluation.
                </p>
              </div>

              <div className="bg-cobalt-900/40 border border-cobalt-800 p-3.5 rounded-lg space-y-1.5">
                <div className="font-semibold text-slate-200 flex items-center space-x-1.5">
                  <Layers className="w-4 h-4 text-indigo-400" />
                  <span>3. Production Safety Guard</span>
                </div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Fails closed by default (<code className="text-cobalt-300 font-mono">LIVE_SEND_ENABLED=false</code>). Simulates dispatch safely locally until live credentials and operator approval are provided.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-cobalt-950 border-t border-cobalt-800 flex items-center justify-between text-xs">
          <div className="text-slate-400 flex items-center space-x-2">
            <span>Kill Switch:</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
              agentStatus?.kill_switch?.active ? 'bg-rose-500/20 text-rose-300' : 'bg-emerald-500/20 text-emerald-400'
            }`}>
              {agentStatus?.kill_switch?.active ? 'HALTED' : 'READY'}
            </span>
            <span className="text-slate-600">•</span>
            <span>Live Sending:</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
              agentStatus?.live_send_enabled ? 'bg-amber-500/20 text-amber-300' : 'bg-cobalt-500/20 text-cobalt-300'
            }`}>
              {agentStatus?.live_send_enabled ? 'LIVE ACTIVE' : 'SAFE SIMULATION'}
            </span>
          </div>

          <button
            onClick={onClose}
            className="px-4 py-2 bg-cobalt-900 hover:bg-cobalt-800 border border-cobalt-700 text-slate-200 rounded text-xs font-medium transition-colors"
          >
            Close Console
          </button>
        </div>

      </div>
    </div>
  );
};
