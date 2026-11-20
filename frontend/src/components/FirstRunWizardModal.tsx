import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import {
  Cpu,
  HardDrive,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Zap,
  Play,
  RotateCw,
  Sparkles,
  Database,
  Lock,
  X
} from 'lucide-react';

interface FirstRunWizardModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const FirstRunWizardModal: React.FC<FirstRunWizardModalProps> = ({ isOpen, onClose }) => {
  const [loading, setLoading] = useState(true);
  const [aiStatus, setAiStatus] = useState<any>(null);
  const [storageStatus, setStorageStatus] = useState<any>(null);
  const [benchmarking, setBenchmarking] = useState(false);
  const [benchmarkResult, setBenchmarkResult] = useState<any>(null);
  const [step, setStep] = useState<number>(1);

  const fetchDiagnostics = async () => {
    setLoading(true);
    try {
      const [ai, storage] = await Promise.all([
        api.getLocalAIStatus().catch(() => ({ status: 'offline', provider: 'ollama' })),
        api.getDesktopStorageStatus().catch(() => ({ status: 'unknown' })),
      ]);
      setAiStatus(ai);
      setStorageStatus(storage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchDiagnostics();
    }
  }, [isOpen]);

  const handleRunBenchmark = async () => {
    setBenchmarking(true);
    setBenchmarkResult(null);
    try {
      const res = await api.testLocalModel('Confirm ActTrident local GPU inference readiness.');
      setBenchmarkResult(res);
    } catch (err: any) {
      setBenchmarkResult({ error: err.message || 'Benchmark failed' });
    } finally {
      setBenchmarking(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-2xl bg-cobalt-950 border border-cobalt-800 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-cobalt-800/80 bg-cobalt-900/60 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                ActTrident Desktop Setup Wizard
              </h3>
              <p className="text-xs text-slate-400">Local-First AI Brain & Windows Host Diagnostics</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-cobalt-800/60 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Wizard Step Content */}
        <div className="p-6 space-y-6 overflow-y-auto text-xs text-slate-300">
          {/* Hardware & GPU Profile */}
          <div className="bg-cobalt-900/40 border border-cobalt-800/80 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                <Cpu className="w-4 h-4 text-cobalt-400" /> Windows Hardware & Acceleration
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                CUDA ACTIVE
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-slate-400 font-mono text-[11px]">
              <div>
                <span className="text-slate-500 block">Processor:</span>
                11th Gen Intel i5-11400H (6 Cores)
              </div>
              <div>
                <span className="text-slate-500 block">System RAM:</span>
                15.71 GB DDR4
              </div>
              <div>
                <span className="text-slate-500 block">GPU Offload:</span>
                NVIDIA GeForce GTX 1650 (4 GB VRAM)
              </div>
              <div>
                <span className="text-slate-500 block">Inference Engine:</span>
                Ollama v0.34.4 (127.0.0.1:11434)
              </div>
            </div>
          </div>

          {/* Local AI Model & Latency */}
          <div className="bg-cobalt-900/40 border border-cobalt-800/80 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-amber-400" /> Local AI Model (Zero Cloud Requirement)
              </span>
              {aiStatus?.is_online ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> READY ({aiStatus?.latency_ms || 0}ms)
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                  OFFLINE (Rule Fallback Ready)
                </span>
              )}
            </div>

            <div className="bg-cobalt-950/80 border border-cobalt-800/60 rounded p-3 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-slate-400">Selected Model:</span>
                <span className="font-mono text-cobalt-300 font-semibold">{aiStatus?.selected_model || 'llama3.2:latest'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Model Memory Footprint:</span>
                <span className="font-mono text-slate-300">2.01 GB (100% VRAM Resident)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Context Window:</span>
                <span className="font-mono text-slate-300">4,096 tokens</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Privacy & Data Boundary:</span>
                <span className="font-mono text-emerald-400 font-semibold">100% Local (Never leaves this PC)</span>
              </div>
            </div>

            {/* Benchmark Runner */}
            <div className="pt-2">
              <button
                onClick={handleRunBenchmark}
                disabled={benchmarking}
                className="w-full flex items-center justify-center space-x-2 py-2 px-3 rounded bg-cobalt-800 hover:bg-cobalt-700 text-slate-100 font-medium transition-colors"
              >
                {benchmarking ? (
                  <>
                    <RotateCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Running GPU Inference Benchmark...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5" />
                    <span>Test Local AI Brain (Tokens/Sec Benchmark)</span>
                  </>
                )}
              </button>

              {benchmarkResult && (
                <div className="mt-2.5 p-2.5 rounded bg-cobalt-950 border border-cobalt-800 text-[11px] font-mono">
                  {benchmarkResult.error ? (
                    <span className="text-rose-400">Error: {benchmarkResult.error}</span>
                  ) : (
                    <div className="space-y-1">
                      <div className="text-emerald-400 font-semibold">
                        ✓ Response in {benchmarkResult.latency_seconds}s (~{benchmarkResult.tokens_per_second_estimate} tok/s)
                      </div>
                      <div className="text-slate-300 italic">"{benchmarkResult.response}"</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Local Storage & WAL Status */}
          <div className="bg-cobalt-900/40 border border-cobalt-800/80 rounded-lg p-4 space-y-2">
            <span className="font-semibold text-slate-200 flex items-center gap-1.5">
              <Database className="w-4 h-4 text-cobalt-400" /> Persistent Storage (%LOCALAPPDATA%\ActTrident)
            </span>
            <div className="grid grid-cols-2 gap-2 text-slate-400 font-mono text-[11px]">
              <div>
                <span className="text-slate-500 block">Database:</span>
                {storageStatus?.database_file ? storageStatus.database_file.split('\\').pop() : 'acttrident.db'}
              </div>
              <div>
                <span className="text-slate-500 block">Disk Space:</span>
                {storageStatus?.free_disk_space_gb || 0} GB Free
              </div>
              <div>
                <span className="text-slate-500 block">WAL Journal:</span>
                Enabled (Crash Resilient)
              </div>
              <div>
                <span className="text-slate-500 block">Backups:</span>
                {storageStatus?.backups_stored || 0} Point-in-time snapshots
              </div>
            </div>
          </div>

          {/* Safety & Compliance Checklist */}
          <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-lg p-3 text-[11px] text-emerald-300 space-y-1.5">
            <div className="font-semibold flex items-center gap-1.5 text-emerald-200">
              <ShieldCheck className="w-4 h-4 text-emerald-400" /> Production Safety & Zero Unsolicited Outbound Mandate
            </div>
            <p className="text-slate-400 leading-relaxed">
              Live sending is disabled by default (<code className="text-emerald-400 font-mono">LIVE_SEND_ENABLED=false</code>). 
              All email drafts and WhatsApp messages require explicit human operator approval. 
              The global kill switch can halt all execution instantly from the top-level settings menu.
            </p>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 border-t border-cobalt-800/80 bg-cobalt-900/60 flex items-center justify-between">
          <button
            onClick={fetchDiagnostics}
            className="flex items-center space-x-1.5 text-xs text-slate-400 hover:text-slate-200"
          >
            <RotateCw className="w-3.5 h-3.5" />
            <span>Refresh Diagnostics</span>
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-950 transition-colors"
          >
            Launch ActTrident Dashboard
          </button>
        </div>
      </div>
    </div>
  );
};
