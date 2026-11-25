import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import {
  Play,
  Pause,
  Square,
  RefreshCw,
  Clock,
  Shield,
  ShieldAlert,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  Database,
  Mail,
  MessageSquare,
  Activity,
  History,
  Zap,
} from 'lucide-react';

interface SchedulerStatus {
  is_running: boolean;
  is_paused: boolean;
  ist_time: string;
  is_within_ist_business_hours: boolean;
  business_hours_status: string;
  kill_switch_active: boolean;
  kill_switch_reason: string | null;
  last_run: Record<string, string | null>;
  next_run: Record<string, string>;
  intervals_sec: Record<string, number>;
  task_stats: {
    outbox_dispatched: number;
    outbox_failed: number;
    followups_evaluated: number;
    replies_synced: number;
    backups_created: number;
    total_cycles: number;
    errors: number;
  };
  recent_events: Array<{
    job: string;
    status: string;
    detail: string;
    timestamp: string;
  }>;
}

export const AutomationCenterView: React.FC = () => {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [triggeringJob, setTriggeringJob] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const data = await api.getAutomationStatus();
      setStatus(data);
    } catch (err: any) {
      console.error('Failed to load scheduler status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    try {
      const res = await api.startAutomation();
      setStatus(res);
      setActionMessage('Scheduler thread started successfully.');
    } catch (e: any) {
      setActionMessage(`Error starting scheduler: ${e.message}`);
    }
  };

  const handleStop = async () => {
    try {
      const res = await api.stopAutomation();
      setStatus(res);
      setActionMessage('Scheduler thread stopped.');
    } catch (e: any) {
      setActionMessage(`Error stopping scheduler: ${e.message}`);
    }
  };

  const handlePauseResume = async () => {
    if (!status) return;
    try {
      const res = status.is_paused ? await api.resumeAutomation() : await api.pauseAutomation();
      setStatus(res);
      setActionMessage(status.is_paused ? 'Scheduler resumed.' : 'Scheduler paused.');
    } catch (e: any) {
      setActionMessage(`Error: ${e.message}`);
    }
  };

  const handleTriggerJob = async (jobName: string) => {
    setTriggeringJob(jobName);
    setActionMessage(null);
    try {
      const res = await api.triggerAutomationJob(jobName);
      setStatus(res.scheduler_status);
      setActionMessage(`Job '${jobName}' completed: ${JSON.stringify(res.result)}`);
    } catch (e: any) {
      setActionMessage(`Error triggering '${jobName}': ${e.message}`);
    } finally {
      setTriggeringJob(null);
    }
  };

  const handleToggleKillSwitch = async () => {
    if (!status) return;
    try {
      const newActive = !status.kill_switch_active;
      await api.toggleKillSwitch(newActive, newActive ? 'Manual stop from Automation Center' : 'Resumed from Automation Center');
      await fetchStatus();
      setActionMessage(newActive ? 'EMERGENCY KILL SWITCH ACTIVATED.' : 'Kill switch deactivated.');
    } catch (e: any) {
      setActionMessage(`Error toggling kill switch: ${e.message}`);
    }
  };

  const jobsList = [
    {
      id: 'outbox_dispatch',
      name: 'Transactional Outbox Dispatch',
      interval: 'Every 60 seconds',
      description: 'Processes pending/retryable approved messages with atomic locks and backoff.',
      icon: Mail,
    },
    {
      id: 'followup_evaluation',
      name: 'Follow-up Cadence Evaluation',
      interval: 'Every 15 minutes (09:00 - 18:00 IST)',
      description: 'Identifies awaiting leads and schedules context-aware follow-ups during business hours.',
      icon: Clock,
    },
    {
      id: 'inbox_sync',
      name: 'Gmail Reply & Bounce Sync',
      interval: 'Every 5 minutes',
      description: 'Polls connected authorized Gmail inboxes for replies, auto-classifies them, and flags bounces.',
      icon: RefreshCw,
    },
    {
      id: 'nightly_discovery_research',
      name: 'Enterprise Discovery & Maintenance',
      interval: 'Every 24 hours',
      description: 'Refreshes verified corporate target directory and queues stale dossiers for research.',
      icon: Database,
    },
    {
      id: 'database_backup',
      name: 'Local Database Snapshot Backup',
      interval: 'Every 24 hours',
      description: 'Generates timestamped crash-safe SQLite backups to local AppData storage.',
      icon: Zap,
    },
  ];

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Top Banner / Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-cobalt-900/60 border border-cobalt-800 p-5 rounded-xl shadow-lg">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-cobalt-400" />
            Autonomous Outreach Control & Scheduler
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Windows persistent background automation engine • Real-time IST business hour enforcement • Crash-safe local outbox
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={fetchStatus}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-300 bg-cobalt-800/80 hover:bg-cobalt-700 border border-cobalt-700/60 rounded-lg transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>

          {status?.is_running ? (
            <>
              <button
                onClick={handlePauseResume}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition border ${
                  status.is_paused
                    ? 'bg-amber-600/30 text-amber-200 border-amber-500/50 hover:bg-amber-600/50'
                    : 'bg-cobalt-800 text-slate-200 border-cobalt-600 hover:bg-cobalt-700'
                }`}
              >
                {status.is_paused ? <Play className="w-3.5 h-3.5 fill-current" /> : <Pause className="w-3.5 h-3.5" />}
                {status.is_paused ? 'Resume Jobs' : 'Pause Jobs'}
              </button>

              <button
                onClick={handleStop}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-rose-300 bg-rose-950/40 hover:bg-rose-900/60 border border-rose-800/60 rounded-lg transition"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                Stop Scheduler
              </button>
            </>
          ) : (
            <button
              onClick={handleStart}
              className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-emerald-100 bg-emerald-600 hover:bg-emerald-500 rounded-lg shadow-md transition"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              Start Automation
            </button>
          )}

          <button
            onClick={handleToggleKillSwitch}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-bold rounded-lg border transition ${
              status?.kill_switch_active
                ? 'bg-rose-600 text-white border-rose-500 hover:bg-rose-500 shadow-lg shadow-rose-950/50'
                : 'bg-rose-950/30 text-rose-300 border-rose-800/60 hover:bg-rose-900/40'
            }`}
          >
            {status?.kill_switch_active ? (
              <ShieldAlert className="w-4 h-4 text-white animate-pulse" />
            ) : (
              <Shield className="w-4 h-4 text-rose-400" />
            )}
            {status?.kill_switch_active ? 'Kill Switch ACTIVE (Click to Disarm)' : 'Emergency Kill Switch'}
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="bg-cobalt-800/80 border border-cobalt-700/80 p-3 rounded-lg text-xs text-cobalt-200 flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-slate-400 hover:text-white ml-2">
            ✕
          </button>
        </div>
      )}

      {/* 4 Health Indicator Tiles */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Scheduler State */}
        <div className="bg-cobalt-900/40 border border-cobalt-800/80 p-4 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Scheduler Engine</span>
            {status?.is_running ? (
              status.is_paused ? (
                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  Paused
                </span>
              ) : (
                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Running
                </span>
              )
            ) : (
              <span className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-500/20 text-slate-300 border border-slate-500/30">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                Stopped
              </span>
            )}
          </div>
          <div className="text-xl font-bold text-white mt-2">
            {status?.is_running ? (status.is_paused ? 'Suspended' : 'Autonomous Active') : 'Idle / Offline'}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Cycles executed: <span className="font-semibold text-slate-200">{status?.task_stats.total_cycles || 0}</span>
          </p>
        </div>

        {/* IST Business Hours */}
        <div className="bg-cobalt-900/40 border border-cobalt-800/80 p-4 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Asia/Kolkata (IST)</span>
            {status?.is_within_ist_business_hours ? (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                Business Hours
              </span>
            ) : (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                <Clock className="w-3 h-3 text-sky-400" />
                Off-Hours
              </span>
            )}
          </div>
          <div className="text-sm font-bold text-white mt-2 font-mono">
            {status?.ist_time || 'Calculating IST...'}
          </div>
          <p className="text-[11px] text-slate-400 mt-1 truncate">
            {status?.business_hours_status || 'Mon-Fri 09:00 - 18:00 IST'}
          </p>
        </div>

        {/* Outbound Dispatch Queue */}
        <div className="bg-cobalt-900/40 border border-cobalt-800/80 p-4 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Outbox Dispatches</span>
            <span className="text-xs font-mono text-cobalt-300">
              {status?.task_stats.outbox_dispatched || 0} sent
            </span>
          </div>
          <div className="text-xl font-bold text-white mt-2 flex items-baseline gap-2">
            <span>{status?.task_stats.outbox_dispatched || 0}</span>
            <span className="text-xs font-normal text-slate-400">
              / {status?.task_stats.outbox_failed || 0} retried
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Followups generated: <span className="text-slate-200">{status?.task_stats.followups_evaluated || 0}</span>
          </p>
        </div>

        {/* Global Safety Guard */}
        <div className="bg-cobalt-900/40 border border-cobalt-800/80 p-4 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Safety Kill Switch</span>
            {status?.kill_switch_active ? (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                <ShieldAlert className="w-3 h-3" />
                ENGAGED
              </span>
            ) : (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                <Shield className="w-3 h-3" />
                DISARMED
              </span>
            )}
          </div>
          <div className="text-sm font-bold text-white mt-2">
            {status?.kill_switch_active ? 'All Outbound Blocked' : 'Normal Operations'}
          </div>
          <p className="text-[11px] text-slate-400 mt-1 truncate">
            {status?.kill_switch_reason || 'Outbound channels authorized'}
          </p>
        </div>
      </div>

      {/* Scheduled Automation Jobs Table */}
      <div className="bg-cobalt-900/40 border border-cobalt-800/80 rounded-xl overflow-hidden shadow-md">
        <div className="px-5 py-4 border-b border-cobalt-800/80 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-cobalt-400" />
            Scheduled Background Tasks
          </h3>
          <span className="text-xs text-slate-400">Automated cycle timings & manual overrides</span>
        </div>

        <div className="divide-y divide-cobalt-800/60">
          {jobsList.map((job) => {
            const lastTime = status?.last_run[job.id];
            const nextTime = status?.next_run[job.id];
            const isTriggering = triggeringJob === job.id;

            return (
              <div key={job.id} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-cobalt-900/30 transition">
                <div className="flex items-start gap-3">
                  <div className="p-2.5 bg-cobalt-800/60 border border-cobalt-700/60 rounded-lg text-cobalt-300">
                    <job.icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-white flex items-center gap-2">
                      {job.name}
                      <span className="text-[11px] text-slate-400 font-normal">({job.interval})</span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">{job.description}</p>
                    <div className="flex items-center gap-4 text-[11px] text-slate-400 mt-1.5 font-mono">
                      <span>Last run: <strong className="text-slate-300">{lastTime ? new Date(lastTime).toLocaleTimeString() : 'Never'}</strong></span>
                      <span>Next due: <strong className="text-slate-300">{nextTime === 'immediately_due' ? 'Immediately' : nextTime ? new Date(nextTime).toLocaleTimeString() : 'Pending'}</strong></span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    disabled={isTriggering}
                    onClick={() => handleTriggerJob(job.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-cobalt-200 bg-cobalt-800 hover:bg-cobalt-700 border border-cobalt-700/80 rounded-lg transition disabled:opacity-50"
                  >
                    <Play className={`w-3 h-3 ${isTriggering ? 'animate-spin' : ''}`} />
                    {isTriggering ? 'Running...' : 'Run Now'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Execution Telemetry Log */}
      <div className="bg-cobalt-900/40 border border-cobalt-800/80 rounded-xl overflow-hidden shadow-md">
        <div className="px-5 py-3.5 border-b border-cobalt-800/80 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <History className="w-4 h-4 text-cobalt-400" />
            Execution Activity Log
          </h3>
          <span className="text-xs text-slate-400">Last 15 automation events</span>
        </div>

        <div className="p-4">
          {(!status?.recent_events || status.recent_events.length === 0) ? (
            <p className="text-xs text-slate-500 py-4 text-center">No automation events recorded yet.</p>
          ) : (
            <div className="space-y-2">
              {status.recent_events.map((evt, idx) => (
                <div key={idx} className="flex items-start justify-between text-xs p-2.5 rounded-lg bg-cobalt-950/40 border border-cobalt-800/40">
                  <div className="flex items-center gap-2.5">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                      evt.status === 'executed' || evt.status === 'started' || evt.status === 'resumed'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : evt.status === 'failed' || evt.status === 'error'
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    }`}>
                      {evt.status}
                    </span>
                    <span className="font-medium text-slate-200">{evt.job}</span>
                    <span className="text-slate-400">{evt.detail}</span>
                  </div>
                  <span className="text-[11px] text-slate-400 font-mono shrink-0 ml-4">
                    {new Date(evt.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
