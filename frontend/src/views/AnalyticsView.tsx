import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import {
  BarChart3,
  TrendingUp,
  MapPin,
  CheckCircle2,
  Send,
  MessageSquare,
  Award,
  AlertCircle
} from 'lucide-react';

export const AnalyticsView: React.FC = () => {
  const [metrics, setMetrics] = useState<any>(null);
  const [cities, setCities] = useState<any[]>([]);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [dash, cityList, campList] = await Promise.all([
          api.getDashboardAnalytics(),
          api.getCityAnalytics(),
          api.getCampaignAnalytics()
        ]);
        setMetrics(dash);
        setCities(cityList);
        setCampaigns(campList);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="p-6 space-y-6">
      {/* View Header */}
      <div>
        <h2 className="text-base font-bold text-slate-100 tracking-tight">Executive Campaign Analytics & Conversion Funnel</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Authentic metrics with verified denominators. Drafted or queued emails are never counted as sent.
        </p>
      </div>

      {loading ? (
        <div className="p-16 text-center text-xs text-slate-400">Computing analytics...</div>
      ) : (
        <>
          {/* Top Rates Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-4">
              <div className="text-slate-400 text-xs">Qualification Rate</div>
              <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                {metrics?.qualification_rate ?? 0}%
              </div>
              <div className="text-[10px] text-slate-500 font-mono mt-1">
                {metrics?.qualified_leads} of {metrics?.total_companies_researched} accounts
              </div>
            </div>

            <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-4">
              <div className="text-slate-400 text-xs">Approval Rate</div>
              <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
                {metrics?.approval_rate ?? 0}%
              </div>
              <div className="text-[10px] text-slate-500 font-mono mt-1">
                {metrics?.emails_approved} of {metrics?.emails_drafted} drafts
              </div>
            </div>

            <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-4">
              <div className="text-slate-400 text-xs">Inbound Reply Rate</div>
              <div className="text-2xl font-bold font-mono text-cobalt-400 mt-1">
                {metrics?.reply_rate ?? 0}%
              </div>
              <div className="text-[10px] text-slate-500 font-mono mt-1">
                {metrics?.replies_received} of {metrics?.emails_sent} sent emails
              </div>
            </div>

            <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-4">
              <div className="text-slate-400 text-xs">90-Day Trial Conversion</div>
              <div className="text-2xl font-bold font-mono text-indigo-400 mt-1">
                {metrics?.trial_conversion_rate ?? 0}%
              </div>
              <div className="text-[10px] text-slate-500 font-mono mt-1">
                {metrics?.trials_started} trials from outreach
              </div>
            </div>
          </div>

          {/* Full Metrics Funnel Table */}
          <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg p-5">
            <h3 className="text-sm font-semibold text-slate-100 mb-4">Complete Funnel Breakdown</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3 text-xs text-center font-mono">
              <div className="bg-cobalt-950 p-3 rounded border border-cobalt-800">
                <div className="text-slate-400 text-[10px]">1. Researched</div>
                <div className="text-lg font-bold text-slate-200 mt-1">{metrics?.total_companies_researched}</div>
              </div>
              <div className="bg-cobalt-950 p-3 rounded border border-cobalt-800">
                <div className="text-slate-400 text-[10px]">2. Qualified</div>
                <div className="text-lg font-bold text-emerald-400 mt-1">{metrics?.qualified_leads}</div>
              </div>
              <div className="bg-cobalt-950 p-3 rounded border border-cobalt-800">
                <div className="text-slate-400 text-[10px]">3. Approved</div>
                <div className="text-lg font-bold text-amber-400 mt-1">{metrics?.emails_approved}</div>
              </div>
              <div className="bg-cobalt-950 p-3 rounded border border-cobalt-800">
                <div className="text-slate-400 text-[10px]">4. Dispatched</div>
                <div className="text-lg font-bold text-cobalt-400 mt-1">{metrics?.emails_sent}</div>
              </div>
              <div className="bg-cobalt-950 p-3 rounded border border-cobalt-800">
                <div className="text-slate-400 text-[10px]">5. Delivered</div>
                <div className="text-lg font-bold text-slate-200 mt-1">{metrics?.emails_delivered}</div>
              </div>
              <div className="bg-cobalt-950 p-3 rounded border border-cobalt-800">
                <div className="text-slate-400 text-[10px]">6. Replies</div>
                <div className="text-lg font-bold text-indigo-400 mt-1">{metrics?.replies_received}</div>
              </div>
              <div className="bg-cobalt-950 p-3 rounded border border-cobalt-800">
                <div className="text-slate-400 text-[10px]">7. 90-Day Trials</div>
                <div className="text-lg font-bold text-emerald-400 mt-1">{metrics?.trials_started}</div>
              </div>
            </div>
          </div>

          {/* Regional Market Performance */}
          <div className="bg-cobalt-900/80 border border-cobalt-800 rounded-lg overflow-hidden">
            <div className="p-4 border-b border-cobalt-800 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-100">Regional Performance (Target Cities)</h3>
              <span className="text-[11px] font-mono text-slate-400">West Bengal • Sikkim • Bihar</span>
            </div>
            <div className="overflow-x-auto text-xs">
              <table className="w-full text-left">
                <thead className="bg-cobalt-950/60 text-slate-400 border-b border-cobalt-800/80">
                  <tr>
                    <th className="py-2.5 px-3">City</th>
                    <th className="py-2.5 px-3">Total Accounts</th>
                    <th className="py-2.5 px-3">5+ Laptops Verified</th>
                    <th className="py-2.5 px-3">Emails Dispatched</th>
                    <th className="py-2.5 px-3">Inbound Replies</th>
                    <th className="py-2.5 px-3">90-Day Evaluations</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cobalt-800/40 text-slate-200 font-mono">
                  {cities.map((city, idx) => (
                    <tr key={idx} className="hover:bg-cobalt-850/50">
                      <td className="py-3 px-3 font-sans font-semibold text-slate-100 flex items-center space-x-1.5">
                        <MapPin className="w-3.5 h-3.5 text-cobalt-400 shrink-0" />
                        <span>{city.city}</span>
                      </td>
                      <td className="py-3 px-3">{city.companies_count}</td>
                      <td className="py-3 px-3 text-emerald-400 font-semibold">{city.verified_5_plus_laptops_count}</td>
                      <td className="py-3 px-3 text-cobalt-300">{city.sent_count}</td>
                      <td className="py-3 px-3">{city.replies_count}</td>
                      <td className="py-3 px-3 text-emerald-400 font-bold">{city.trials_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
