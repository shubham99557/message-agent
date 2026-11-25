import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import {
  FileText,
  Ban,
  UserCheck,
  Shield,
  OctagonAlert,
  CheckCircle2,
  Cpu,
  Zap,
  Database,
  Sparkles,
  Play,
  RotateCw,
  HardDrive
} from 'lucide-react';
import { FirstRunWizardModal } from '../components/FirstRunWizardModal';

export const SettingsView: React.FC = () => {
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [suppressed, setSuppressed] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [killSwitch, setKillSwitch] = useState<{ active: boolean; reason?: string; updated_at?: string } | null>(null);
  const [ksReason, setKsReason] = useState('');
  const [togglingKs, setTogglingKs] = useState(false);
  const [loading, setLoading] = useState(true);

  // Local AI & Desktop Storage State
  const [aiStatus, setAiStatus] = useState<any>(null);
  const [aiModels, setAiModels] = useState<any>(null);
  const [storageStatus, setStorageStatus] = useState<any>(null);
  const [switchingModel, setSwitchingModel] = useState(false);
  const [benchmarking, setBenchmarking] = useState(false);
  const [benchmarkResult, setBenchmarkResult] = useState<any>(null);
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupNotice, setBackupNotice] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);

  const loadData = async () => {
    try {
      const [me, logs, supp, userList, ks, ai, models, storage] = await Promise.all([
        api.getMe().catch(() => null),
        api.getAuditLogs().catch(() => []),
        api.getSuppressionList().catch(() => []),
        api.getUsers().catch(() => []),
        api.getKillSwitch().catch(() => ({ active: false })),
        api.getLocalAIStatus().catch(() => null),
        api.getLocalAIModels().catch(() => null),
        api.getDesktopStorageStatus().catch(() => null),
      ]);
      setCurrentUser(me);
      setAuditLogs(logs);
      setSuppressed(supp);
      setUsers(userList);
      setKillSwitch(ks);
      setAiStatus(ai);
      setAiModels(models);
      setStorageStatus(storage);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggleKillSwitch = async () => {
    if (!killSwitch) return;
    const nextState = !killSwitch.active;
    if (nextState && !confirm('ACTIVATE EMERGENCY KILL SWITCH? This will immediately halt ALL outbound sending across Email, WhatsApp, LinkedIn, and background workers.')) {
      return;
    }
    setTogglingKs(true);
    try {
      const updated = await api.toggleKillSwitch(nextState, ksReason || undefined);
      setKillSwitch(updated);
      setKsReason('');
      await loadData();
    } catch (err: any) {
      alert(`Kill switch error: ${err.message}`);
    } finally {
      setTogglingKs(false);
    }
  };

  const handleToggleUserStatus = async (userId: number, currentActive: boolean) => {
    try {
      await api.updateUserStatus(userId, !currentActive);
      await loadData();
    } catch (err: any) {
      alert(`Status update failed: ${err.message}`);
    }
  };

  const handleRoleChange = async (userId: number, role: string) => {
    try {
      await api.updateUserRole(userId, role);
      await loadData();
    } catch (err: any) {
      alert(`Role update failed: ${err.message}`);
    }
  };

  const handleSwitchModel = async (modelTag: string) => {
    setSwitchingModel(true);
    try {
      await api.switchLocalModel(modelTag);
      await loadData();
    } catch (err: any) {
      alert(`Model switch failed: ${err.message}`);
    } finally {
      setSwitchingModel(false);
    }
  };

  const handleRunBenchmark = async () => {
    setBenchmarking(true);
    setBenchmarkResult(null);
    try {
      const res = await api.testLocalModel('Confirm local model latency and tokens per second.');
      setBenchmarkResult(res);
    } catch (err: any) {
      setBenchmarkResult({ error: err.message || 'Benchmark failed' });
    } finally {
      setBenchmarking(false);
    }
  };

  const handleTriggerBackup = async () => {
    setBackupLoading(true);
    setBackupNotice(null);
    try {
      const res = await api.triggerInstantBackup();
      const backupFile = res.backup?.backup_file?.split('\\').pop() || 'backup.db';
      setBackupNotice(`Backup successfully saved: ${backupFile} (SHA-256 verified)`);
      await loadData();
    } catch (err: any) {
      alert(`Backup failed: ${err.message}`);
    } finally {
      setBackupLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-100 tracking-tight">System Settings, Local AI Brain & Compliance</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Local Ollama AI configuration, Windows PC hardware acceleration, storage backups, and outbound safety controls.
          </p>
        </div>
        <button
          onClick={() => setWizardOpen(true)}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cobalt-800 hover:bg-cobalt-700 text-cobalt-200 text-xs font-medium border border-cobalt-700/80 transition-colors shrink-0"
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span>Launch Setup Wizard</span>
        </button>
      </div>

      {/* Local AI Brain & Hardware Configuration Card */}
      <div className="rounded-lg p-5 border bg-cobalt-900/80 border-cobalt-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cobalt-800/80 pb-3">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-slate-100">Local AI Brain (Ollama)</h3>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${
                    aiStatus?.is_online
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  }`}
                >
                  {aiStatus?.is_online ? `ONLINE (${aiStatus?.latency_ms || 0}ms)` : 'OFFLINE (Rule Engine Active)'}
                </span>
              </div>
              <p className="text-xs text-slate-400">Zero cloud subscription required. 100% private inference on local GPU/CPU.</p>
            </div>
          </div>

          {/* Model Switcher Dropdown */}
          <div className="flex items-center space-x-2">
            <label className="text-xs text-slate-400 shrink-0">Active Model:</label>
            <select
              value={aiModels?.active_model || 'llama3.2:latest'}
              disabled={switchingModel}
              onChange={(e) => handleSwitchModel(e.target.value)}
              className="bg-cobalt-950 border border-cobalt-800 text-slate-200 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:border-cobalt-500 font-mono"
            >
              {(aiModels?.recommended_catalog || []).map((m: any) => (
                <option key={m.tag} value={m.tag}>
                  {m.name} ({m.parameters}, {m.size_gb} GB)
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Hardware & GPU Acceleration Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div className="bg-cobalt-950/70 border border-cobalt-800/60 rounded p-2.5 space-y-1">
            <span className="text-slate-500 block text-[10px] uppercase font-mono">Acceleration</span>
            <span className="font-mono text-emerald-400 font-semibold flex items-center gap-1">
              <Cpu className="w-3.5 h-3.5" /> NVIDIA GTX 1650 (CUDA)
            </span>
          </div>
          <div className="bg-cobalt-950/70 border border-cobalt-800/60 rounded p-2.5 space-y-1">
            <span className="text-slate-500 block text-[10px] uppercase font-mono">Dedicated VRAM</span>
            <span className="font-mono text-slate-200 font-semibold">4.0 GB GDDR6</span>
          </div>
          <div className="bg-cobalt-950/70 border border-cobalt-800/60 rounded p-2.5 space-y-1">
            <span className="text-slate-500 block text-[10px] uppercase font-mono">Ollama Endpoint</span>
            <span className="font-mono text-slate-300 truncate block">127.0.0.1:11434</span>
          </div>
          <div className="bg-cobalt-950/70 border border-cobalt-800/60 rounded p-2.5 space-y-1">
            <span className="text-slate-500 block text-[10px] uppercase font-mono">Context Window</span>
            <span className="font-mono text-cobalt-300 font-semibold">4,096 tokens</span>
          </div>
        </div>

        {/* Live Model Benchmark Tool */}
        <div className="flex flex-col sm:flex-row items-center gap-3 pt-1">
          <button
            onClick={handleRunBenchmark}
            disabled={benchmarking}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-cobalt-800 hover:bg-cobalt-700 text-slate-100 text-xs font-medium border border-cobalt-700 transition-colors shrink-0"
          >
            {benchmarking ? <RotateCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            <span>{benchmarking ? 'Testing Inference...' : 'Test Local Model Benchmark'}</span>
          </button>
          {benchmarkResult && (
            <div className="text-xs font-mono text-slate-300">
              {benchmarkResult.error ? (
                <span className="text-rose-400">{benchmarkResult.error}</span>
              ) : (
                <span className="text-emerald-400">
                  ✓ Latency: {benchmarkResult.latency_seconds}s | ~{benchmarkResult.tokens_per_second_estimate} tok/s | "{benchmarkResult.response}"
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Local Desktop Storage & Instant Backup Card */}
      <div className="rounded-lg p-5 border bg-cobalt-900/80 border-cobalt-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-cobalt-800/80 pb-3">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-cobalt-800/80 border border-cobalt-700 flex items-center justify-center text-cobalt-300 shrink-0">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-100">Local Desktop Persistent Storage</h3>
              <p className="text-xs text-slate-400">
                Data persists in <code className="text-cobalt-300 font-mono text-[11px]">%LOCALAPPDATA%\ActTrident\data\acttrident.db</code>
              </p>
            </div>
          </div>
          <button
            onClick={handleTriggerBackup}
            disabled={backupLoading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-cobalt-800 hover:bg-cobalt-700 text-slate-100 text-xs font-medium border border-cobalt-700 transition-colors shrink-0"
          >
            {backupLoading ? <RotateCw className="w-3.5 h-3.5 animate-spin" /> : <HardDrive className="w-3.5 h-3.5" />}
            <span>{backupLoading ? 'Creating Backup...' : 'Create Instant Backup'}</span>
          </button>
        </div>

        {backupNotice && (
          <div className="p-2.5 rounded bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs font-mono">
            {backupNotice}
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <div className="bg-cobalt-950/70 border border-cobalt-800/60 rounded p-2.5">
            <span className="text-slate-500 block text-[10px] uppercase font-mono">Database Size</span>
            <span className="font-mono text-slate-200 font-semibold">{storageStatus?.database_size_mb || 0} MB</span>
          </div>
          <div className="bg-cobalt-950/70 border border-cobalt-800/60 rounded p-2.5">
            <span className="text-slate-500 block text-[10px] uppercase font-mono">Free Disk Space</span>
            <span className="font-mono text-slate-200 font-semibold">{storageStatus?.free_disk_space_gb || 0} GB Free</span>
          </div>
          <div className="bg-cobalt-950/70 border border-cobalt-800/60 rounded p-2.5">
            <span className="text-slate-500 block text-[10px] uppercase font-mono">Crash Recovery (WAL)</span>
            <span className="font-mono text-emerald-400 font-semibold">Enabled</span>
          </div>
          <div className="bg-cobalt-950/70 border border-cobalt-800/60 rounded p-2.5">
            <span className="text-slate-500 block text-[10px] uppercase font-mono">Stored Snapshots</span>
            <span className="font-mono text-cobalt-300 font-semibold">{storageStatus?.backups_stored || 0} Backups</span>
          </div>
        </div>
      </div>

      {/* Global Emergency Kill Switch Card */}
      <div
        className={`rounded-lg p-4 border ${
          killSwitch?.active
            ? 'bg-rose-950/50 border-rose-500/60'
            : 'bg-cobalt-900/80 border-cobalt-800'
        }`}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start space-x-3">
            <div
              className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border ${
                killSwitch?.active
                  ? 'bg-rose-500/20 border-rose-500/40 text-rose-300'
                  : 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
              }`}
            >
              {killSwitch?.active ? <OctagonAlert className="w-5 h-5" /> : <CheckCircle2 className="w-5 h-5" />}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-slate-100">Global Emergency Outbound Kill Switch</h3>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${
                    killSwitch?.active
                      ? 'bg-rose-500/25 text-rose-200 border-rose-400/50'
                      : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  }`}
                >
                  {killSwitch?.active ? 'ALL SENDING HALTED' : 'Normal Operation'}
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                {killSwitch?.active
                  ? `Outbound sending is globally blocked across Email, WhatsApp, LinkedIn, Outbox, and Follow-ups. Reason: ${killSwitch.reason || 'Operator halt'}`
                  : 'Immediately halts all outbound sending across Email, WhatsApp, LinkedIn, and background workers if an issue is detected.'}
              </p>
            </div>
          </div>

          {(currentUser?.role === 'admin' || currentUser?.role === 'manager') && (
            <div className="flex items-center space-x-2 shrink-0">
              <input
                type="text"
                placeholder="Reason (optional)..."
                value={ksReason}
                onChange={(e) => setKsReason(e.target.value)}
                className="bg-cobalt-950 border border-cobalt-700 rounded px-2.5 py-1.5 text-xs text-slate-200 w-44"
              />
              <button
                onClick={handleToggleKillSwitch}
                disabled={togglingKs}
                className={`px-3.5 py-1.5 rounded text-xs font-semibold transition-colors ${
                  killSwitch?.active
                    ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                    : 'bg-rose-600 hover:bg-rose-500 text-white'
                }`}
              >
                {togglingKs
                  ? 'Updating...'
                  : killSwitch?.active
                  ? 'Resume Sending'
                  : 'Stop All Outbound Sending'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Admin User & Role Management Card */}
      {users.length > 0 && (
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg overflow-hidden">
          <div className="p-4 border-b border-cobalt-800 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <UserCheck className="w-4 h-4 text-emerald-400" />
              <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                User Access & Role Management ({users.length})
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400">DB-Backed RBAC • Instant Session Revocation</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cobalt-950/60 text-slate-400 border-b border-cobalt-800/80">
                <tr>
                  <th className="py-2.5 px-3">User</th>
                  <th className="py-2.5 px-3">Email</th>
                  <th className="py-2.5 px-3">Role</th>
                  <th className="py-2.5 px-3">Status</th>
                  {currentUser?.role === 'admin' && <th className="py-2.5 px-3 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-cobalt-800/40 text-slate-200">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-cobalt-850/50">
                    <td className="py-2.5 px-3 font-medium">{u.full_name}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300">{u.email}</td>
                    <td className="py-2.5 px-3">
                      {currentUser?.role === 'admin' && u.id !== currentUser.id ? (
                        <select
                          value={u.role}
                          onChange={(e) => handleRoleChange(u.id, e.target.value)}
                          className="bg-cobalt-950 border border-cobalt-800 rounded px-2 py-1 text-[11px] font-mono text-cobalt-300"
                        >
                          <option value="sales_rep">sales_rep</option>
                          <option value="manager">manager</option>
                          <option value="admin">admin</option>
                          <option value="analyst">analyst</option>
                        </select>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-cobalt-950 border border-cobalt-800 font-mono text-[11px] text-cobalt-300">
                          {u.role}
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${
                          u.is_active
                            ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                            : 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                        }`}
                      >
                        {u.is_active ? 'Active' : 'Deactivated'}
                      </span>
                    </td>
                    {currentUser?.role === 'admin' && (
                      <td className="py-2.5 px-3 text-right">
                        {u.id !== currentUser.id ? (
                          <button
                            onClick={() => handleToggleUserStatus(u.id, u.is_active)}
                            className={`px-2.5 py-1 rounded text-[11px] font-medium border ${
                              u.is_active
                                ? 'bg-rose-950/40 hover:bg-rose-900/50 text-rose-300 border-rose-700/50'
                                : 'bg-emerald-950/40 hover:bg-emerald-900/50 text-emerald-300 border-emerald-700/50'
                            }`}
                          >
                            {u.is_active ? 'Deactivate' : 'Reactivate'}
                          </button>
                        ) : (
                          <span className="text-[10px] font-mono text-slate-500">Current Session</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Suppression List Card */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg overflow-hidden">
          <div className="p-4 border-b border-cobalt-800 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Ban className="w-4 h-4 text-rose-400" />
              <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                Global Suppression List ({suppressed.length})
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400">Strict Opt-Out Enforcement</span>
          </div>

          <div className="overflow-x-auto max-h-[420px]">
            {loading ? (
              <div className="p-8 text-center text-xs text-slate-400">Loading compliance records...</div>
            ) : suppressed.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">Suppression list is currently empty.</div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-cobalt-950/60 text-slate-400 border-b border-cobalt-800/80">
                  <tr>
                    <th className="py-2 px-3">Identifier</th>
                    <th className="py-2 px-3">Channel</th>
                    <th className="py-2 px-3">Reason</th>
                    <th className="py-2 px-3">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cobalt-800/40 text-slate-200 font-mono text-[11px]">
                  {suppressed.map((item) => (
                    <tr key={item.id} className="hover:bg-cobalt-850/50">
                      <td className="py-2 px-3 text-rose-300 font-semibold">{item.identifier}</td>
                      <td className="py-2 px-3 uppercase">{item.channel}</td>
                      <td className="py-2 px-3">{item.reason}</td>
                      <td className="py-2 px-3 text-slate-400">{new Date(item.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Security Audit Logs */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg overflow-hidden">
          <div className="p-4 border-b border-cobalt-800 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <FileText className="w-4 h-4 text-cobalt-400" />
              <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                Security Audit Trail ({auditLogs.length})
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-400 flex items-center space-x-1">
              <Shield className="w-3 h-3 text-emerald-400" />
              <span>Immutable</span>
            </span>
          </div>

          <div className="overflow-x-auto max-h-[420px]">
            {auditLogs.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">No audit logs recorded yet.</div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-cobalt-950/60 text-slate-400 border-b border-cobalt-800/80">
                  <tr>
                    <th className="py-2 px-3">Action</th>
                    <th className="py-2 px-3">Entity</th>
                    <th className="py-2 px-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cobalt-800/40 text-slate-200 font-mono text-[11px]">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-cobalt-850/50">
                      <td className="py-2 px-3 text-cobalt-300 font-medium">{log.action}</td>
                      <td className="py-2 px-3">{log.entity_type} {log.entity_id ? `(#${log.entity_id})` : ''}</td>
                      <td className="py-2 px-3 text-slate-400">
                        {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* First-Run Setup Wizard Modal */}
      <FirstRunWizardModal isOpen={wizardOpen} onClose={() => setWizardOpen(false)} />
    </div>
  );
};
