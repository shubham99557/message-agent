import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { ViewType } from '../types';
import { AutonomousAgentModal } from '../components/AutonomousAgentModal';
import {
  Building2,
  CheckCircle2,
  Send,
  MessageSquare,
  Award,
  ArrowUpRight,
  TrendingUp,
  MapPin,
  Clock,
  Layers,
  ArrowRight,
  Activity,
  Cpu,
  RefreshCw,
  AlertTriangle,
  BrainCircuit,
  Sparkles,
  Play,
  BookOpen
} from 'lucide-react';

interface DashboardViewProps {
  onNavigate: (view: ViewType) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ onNavigate }) => {
  const [metrics, setMetrics] = useState<any>(null);
  const [cityStats, setCityStats] = useState<any[]>([]);
  const [queueHealth, setQueueHealth] = useState<any>(null);
  const [recentJobs, setRecentJobs] = useState<any[]>([]);
  const [runningJob, setRunningJob] = useState<string | null>(null);
  const [showAgentModal, setShowAgentModal] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [dashMetrics, cities, queue, history] = await Promise.all([
        api.getDashboardAnalytics(),
        api.getCityAnalytics(),
        api.getQueueHealth().catch(() => null),
        api.getTaskHistory().catch(() => [])
      ]);
      setMetrics(dashMetrics);
      setCityStats(cities);
      setQueueHealth(queue);
      setRecentJobs(Array.isArray(history) ? history.slice(0, 6) : []);
    } catch (err) {
      console.error('Failed to load dashboard data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunJob = async (category: string, payload: any = {}) => {
    setRunningJob(category);
    try {
      const res = await api.triggerBackgroundTask({
        category,
        payload,
        execute_sync: true
      });
      await loadData();
      alert(`Job '${category}' finished with status: ${res.status}`);
    } catch (err: any) {
      alert(`Job error: ${err.message}`);
    } finally {
      setRunningJob(null);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Executive Welcome & Primary Offer Banner */}
      <div className="bg-gradient-to-r from-cobalt-900 to-cobalt-950 border border-cobalt-800 rounded-lg p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-md">
        <div className="flex items-center space-x-3.5">
          <div className="w-12 h-12 rounded-lg bg-cobalt-800/80 border border-cobalt-700 p-1 flex items-center justify-center shrink-0 shadow-inner">
            <img src="/acttrident-mark.png" alt="ActTrident" className="w-full h-full object-contain" />
          </div>
          <div>
            <div className="flex items-center space-x-2 text-xs font-mono text-cobalt-400 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>SYSTEM ACTIVE • PRODUCTION B2B AUTOMATION</span>
            </div>
            <h2 className="text-xl font-bold text-slate-100 tracking-tight mt-0.5">ActTrident B2B Sales Automation</h2>
            <p className="text-xs text-slate-400 mt-0.5 max-w-2xl leading-relaxed">
              Targeting SMBs and technology enterprises managing 5+ laptops across <strong className="text-slate-300">any target city</strong> or nationwide technology corridors with the proposed <strong className="text-cobalt-300">90-Day Free Product Evaluation</strong>.
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2 shrink-0">
          <button
            onClick={() => onNavigate('discovery')}
            className="px-3.5 py-2 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded text-xs font-medium transition-colors flex items-center space-x-1.5 shadow-sm"
          >
            <span>Discover Companies</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onNavigate('approvals')}
            className="px-3.5 py-2 bg-cobalt-900 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded text-xs font-medium transition-colors"
          >
            Approval Queue
          </button>
        </div>
      </div>

      {/* Autonomous Outreach Agent (Brain) Hero Banner */}
      <div className="bg-gradient-to-r from-indigo-950/70 via-cobalt-900/90 to-cobalt-950 border border-indigo-500/30 rounded-xl p-5 shadow-lg relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-full bg-gradient-to-l from-indigo-500/10 to-transparent pointer-events-none" />
        
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5 relative z-10">
          <div className="flex items-start space-x-4">
            <div className="w-14 h-14 rounded-xl bg-indigo-950/90 border border-indigo-500/40 p-2 flex items-center justify-center shrink-0 shadow-lg relative group">
              <img src="/acttrident-logo.png" alt="ActTrident AI" className="w-full h-full object-contain filter drop-shadow-md group-hover:scale-105 transition-transform" />
              <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 border-2 border-cobalt-950 flex items-center justify-center" title="Autonomous Outreach Brain Active">
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <h3 className="text-base font-bold text-slate-100 tracking-tight">ActTrident Autonomous Sales Outreach Agent (Brain)</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  END-TO-END PIPELINE READY
                </span>
              </div>
              <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">
                Single-click autonomous orchestration across all 8 phases: Multi-Region Discovery ➔ Deep AI Tech Profiling ➔ 7-Factor Qualification (5+ Laptops) ➔ Campaign Enrollment ➔ Personalized 90-Day Evaluation Copywriting ➔ Staging & Dispatch ➔ CRM Pipeline.
              </p>
              <div className="flex flex-wrap items-center gap-3 pt-1 text-[11px] text-slate-400 font-mono">
                <span className="flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                  <span>Target Coverage: Nationwide • Any Location or City</span>
                </span>
                <span>•</span>
                <span className="text-indigo-300">Channels: Email (SMTP/Gmail) • WhatsApp (Meta v22.0) • LinkedIn</span>
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-3 shrink-0">
            <button
              onClick={() => onNavigate('integrations')}
              className="px-3.5 py-2.5 bg-cobalt-950 hover:bg-cobalt-900 border border-cobalt-700 text-slate-300 rounded-lg text-xs font-medium transition-colors flex items-center space-x-1.5"
            >
              <BookOpen className="w-3.5 h-3.5 text-cobalt-400" />
              <span>Channel Guide</span>
            </button>
            <button
              onClick={() => setShowAgentModal(true)}
              className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-cobalt-600 hover:from-indigo-500 hover:to-cobalt-500 text-white font-bold rounded-lg text-xs transition-all flex items-center space-x-2 shadow-lg shadow-indigo-900/40"
            >
              <Play className="w-4 h-4 fill-white" />
              <span>🚀 Launch Outreach Agent</span>
            </button>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* Card 1 */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Companies</span>
            <Building2 className="w-4 h-4 text-cobalt-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono mt-2">
            {metrics?.total_companies_researched ?? (loading ? '...' : 0)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1 flex items-center">
            <span>Researched in DB</span>
          </div>
        </div>

        {/* Card 2 */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Qualified Leads</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono mt-2">
            {metrics?.qualified_leads ?? (loading ? '...' : 0)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1 font-mono">
            {metrics?.qualification_rate ?? 0}% qualification
          </div>
        </div>

        {/* Card 3 */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Approved Drafts</span>
            <Clock className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 font-mono mt-2">
            {metrics?.emails_approved ?? (loading ? '...' : 0)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1 font-mono">
            of {metrics?.emails_drafted ?? 0} drafted
          </div>
        </div>

        {/* Card 4 */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Emails Sent</span>
            <Send className="w-4 h-4 text-cobalt-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono mt-2">
            {metrics?.emails_sent ?? (loading ? '...' : 0)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1 font-mono">
            Delivered: {metrics?.emails_delivered ?? 0}
          </div>
        </div>

        {/* Card 5 */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Inbound Replies</span>
            <MessageSquare className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-indigo-400 font-mono mt-2">
            {metrics?.replies_received ?? (loading ? '...' : 0)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1 font-mono">
            {metrics?.reply_rate ?? 0}% reply rate
          </div>
        </div>

        {/* Card 6 */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>90-Day Trials</span>
            <Award className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono mt-2">
            {metrics?.trials_started ?? (loading ? '...' : 0)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1 font-mono">
            Evaluation active
          </div>
        </div>
      </div>

      {/* Target City Performance Breakdown & Outreach Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* City Comparison Table */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-100">Target Cities Overview</h3>
              <p className="text-xs text-slate-400 mt-0.5">Verified companies with 5+ managed laptops</p>
            </div>
            <button
              onClick={() => onNavigate('discovery')}
              className="text-xs text-cobalt-400 hover:text-cobalt-300 font-medium flex items-center space-x-1"
            >
              <span>Explore All</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cobalt-950/60 text-slate-400 border-b border-cobalt-800/80">
                <tr>
                  <th className="py-2.5 px-3 font-medium">City</th>
                  <th className="py-2.5 px-3 font-medium">Companies</th>
                  <th className="py-2.5 px-3 font-medium">5+ Laptops Verified</th>
                  <th className="py-2.5 px-3 font-medium">Sent</th>
                  <th className="py-2.5 px-3 font-medium">Trials</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cobalt-800/40 text-slate-200">
                {cityStats.map((item, idx) => (
                  <tr key={idx} className="hover:bg-cobalt-850/50 transition-colors">
                    <td className="py-2.5 px-3 font-medium flex items-center space-x-2">
                      <MapPin className="w-3.5 h-3.5 text-cobalt-400 shrink-0" />
                      <span>{item.city}</span>
                    </td>
                    <td className="py-2.5 px-3 font-mono">{item.companies_count}</td>
                    <td className="py-2.5 px-3 font-mono text-emerald-400">{item.verified_5_plus_laptops_count}</td>
                    <td className="py-2.5 px-3 font-mono">{item.sent_count}</td>
                    <td className="py-2.5 px-3 font-mono text-cobalt-300 font-semibold">{item.trials_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Real Outreach Funnel */}
        <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-100">B2B Conversion Pipeline</h3>
              <p className="text-xs text-slate-400 mt-0.5">Calculated using authentic non-inflated denominators</p>
            </div>
            <span className="text-[11px] font-mono text-slate-400 bg-cobalt-950 px-2 py-0.5 rounded border border-cobalt-800">
              Zero Draft Inflation
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>1. Researched Companies</span>
                <span className="font-mono font-semibold">{metrics?.total_companies_researched ?? 0}</span>
              </div>
              <div className="w-full bg-cobalt-950 rounded-full h-2">
                <div className="bg-cobalt-600 h-2 rounded-full w-full"></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>2. AI Qualified (5+ Devices & Tech Sector)</span>
                <span className="font-mono text-emerald-400 font-semibold">
                  {metrics?.qualified_leads ?? 0} ({metrics?.qualification_rate ?? 0}%)
                </span>
              </div>
              <div className="w-full bg-cobalt-950 rounded-full h-2">
                <div
                  className="bg-emerald-500 h-2 rounded-full"
                  style={{ width: `${Math.min(100, metrics?.qualification_rate ?? 0)}%` }}
                ></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>3. Human Approved for Dispatch</span>
                <span className="font-mono text-amber-300 font-semibold">
                  {metrics?.emails_approved ?? 0} ({metrics?.approval_rate ?? 0}%)
                </span>
              </div>
              <div className="w-full bg-cobalt-950 rounded-full h-2">
                <div
                  className="bg-amber-500 h-2 rounded-full"
                  style={{ width: `${Math.min(100, metrics?.approval_rate ?? 0)}%` }}
                ></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>4. Genuinely Dispatched & Delivered</span>
                <span className="font-mono text-cobalt-400 font-semibold">
                  {metrics?.emails_sent ?? 0} sent ({metrics?.delivery_rate ?? 0}% delivered)
                </span>
              </div>
              <div className="w-full bg-cobalt-950 rounded-full h-2">
                <div
                  className="bg-cobalt-400 h-2 rounded-full"
                  style={{ width: `${Math.min(100, metrics?.delivery_rate ?? 0)}%` }}
                ></div>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-slate-300 mb-1">
                <span>5. Proposed 90-Day Evaluations Activated</span>
                <span className="font-mono text-indigo-400 font-semibold">
                  {metrics?.trials_started ?? 0} ({metrics?.trial_conversion_rate ?? 0}% conversion)
                </span>
              </div>
              <div className="w-full bg-cobalt-950 rounded-full h-2">
                <div
                  className="bg-indigo-500 h-2 rounded-full"
                  style={{ width: `${Math.min(100, (metrics?.trials_started ?? 0) * 15)}%` }}
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Autonomous Background Job Engine & Queue Status */}
      <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-cobalt-800">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${queueHealth?.status === 'healthy' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}>
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-semibold text-slate-100">Background Job Engine & Queue Status</h3>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded uppercase tracking-wider font-semibold ${
                  queueHealth?.status === 'healthy' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}>
                  {queueHealth?.status || 'Active'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Autonomous 13-stage background pipeline running in <strong className="text-slate-300">Asia/Kolkata (IST)</strong>
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2 text-xs font-mono">
            <span className="text-slate-400">Workers:</span>
            <span className="bg-cobalt-950 px-2 py-1 rounded border border-cobalt-800 text-cobalt-300 font-semibold">
              {queueHealth?.celery?.worker_count ?? 1} Online
            </span>
            <span className="text-slate-400 ml-2">Redis:</span>
            <span className={`px-2 py-1 rounded border font-semibold ${
              queueHealth?.redis?.connected ? 'bg-emerald-950/60 border-emerald-800 text-emerald-400' : 'bg-slate-800 border-slate-700 text-slate-400'
            }`}>
              {queueHealth?.redis?.connected ? `${queueHealth.redis.ping_ms || 1.2}ms` : 'Local Fallback'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mt-4 text-xs">
          <div className="bg-cobalt-950/60 p-3 rounded border border-cobalt-800">
            <span className="text-slate-400 block text-[11px]">Pending Jobs</span>
            <span className="text-lg font-mono font-bold text-amber-400">{queueHealth?.tasks?.pending ?? 0}</span>
          </div>
          <div className="bg-cobalt-950/60 p-3 rounded border border-cobalt-800">
            <span className="text-slate-400 block text-[11px]">Running Now</span>
            <span className="text-lg font-mono font-bold text-cobalt-400">{queueHealth?.tasks?.running ?? 0}</span>
          </div>
          <div className="bg-cobalt-950/60 p-3 rounded border border-cobalt-800">
            <span className="text-slate-400 block text-[11px]">Completed</span>
            <span className="text-lg font-mono font-bold text-emerald-400">{queueHealth?.tasks?.completed ?? 0}</span>
          </div>
          <div className="bg-cobalt-950/60 p-3 rounded border border-cobalt-800">
            <span className="text-slate-400 block text-[11px]">Failed</span>
            <span className="text-lg font-mono font-bold text-rose-400">{queueHealth?.tasks?.failed ?? 0}</span>
          </div>
          <div className="bg-cobalt-950/60 p-3 rounded border border-cobalt-800">
            <span className="text-slate-400 block text-[11px]">Dead Letter Queue</span>
            <span className="text-lg font-mono font-bold text-amber-300">{queueHealth?.tasks?.dead_letter_unresolved ?? 0}</span>
          </div>
          <div className="bg-cobalt-950/60 p-3 rounded border border-cobalt-800">
            <span className="text-slate-400 block text-[11px]">24h Error Rate</span>
            <span className="text-lg font-mono font-bold text-slate-200">{queueHealth?.tasks?.failure_rate_24h_percent ?? 0}%</span>
          </div>
        </div>

        {/* Interactive Automation Job Controls */}
        <div className="mt-4 pt-4 border-t border-cobalt-800 flex flex-wrap items-center justify-between gap-2 text-xs">
          <span className="text-slate-400 font-medium">Run Autonomous Pipelines On-Demand:</span>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleRunJob('company_discovery', { cities: ['Siliguri', 'Gangtok', 'Patna', 'Bhagalpur', 'Bengaluru', 'Delhi', 'Mumbai'] })}
              disabled={runningJob !== null}
              className="px-2.5 py-1.5 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded disabled:opacity-50"
            >
              {runningJob === 'company_discovery' ? 'Running...' : 'Run Nationwide Discovery'}
            </button>
            <button
              onClick={() => handleRunJob('lead_qualification', { recheck_stale_only: false })}
              disabled={runningJob !== null}
              className="px-2.5 py-1.5 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded disabled:opacity-50"
            >
              {runningJob === 'lead_qualification' ? 'Running...' : 'Qualify All Prospects'}
            </button>
            <button
              onClick={() => handleRunJob('followup_scheduling', {})}
              disabled={runningJob !== null}
              className="px-2.5 py-1.5 bg-cobalt-950 hover:bg-cobalt-850 border border-cobalt-700 text-slate-200 rounded disabled:opacity-50"
            >
              {runningJob === 'followup_scheduling' ? 'Running...' : 'Run Follow-Up Engine'}
            </button>
            <button
              onClick={() => handleRunJob('daily_reporting', {})}
              disabled={runningJob !== null}
              className="px-2.5 py-1.5 bg-cobalt-600 hover:bg-cobalt-500 text-white rounded disabled:opacity-50"
            >
              {runningJob === 'daily_reporting' ? 'Generating...' : 'Generate Daily Digest'}
            </button>
          </div>
        </div>

        {recentJobs.length > 0 && (
          <div className="mt-4 pt-3 border-t border-cobalt-800/80">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Recent Background Executions</div>
            <div className="space-y-1.5 text-[11px] font-mono">
              {recentJobs.map((job) => (
                <div key={job.id} className="flex items-center justify-between bg-cobalt-950/60 px-3 py-1.5 rounded border border-cobalt-800/70">
                  <span className="text-cobalt-300">{job.category}</span>
                  <span className={job.status === 'completed' ? 'text-emerald-400' : job.status === 'failed' ? 'text-rose-400' : 'text-amber-400'}>
                    {job.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Autonomous Outreach Agent Modal Runner */}
      <AutonomousAgentModal
        isOpen={showAgentModal}
        onClose={() => setShowAgentModal(false)}
        onNavigate={onNavigate}
        onCycleComplete={loadData}
      />
    </div>
  );
};
