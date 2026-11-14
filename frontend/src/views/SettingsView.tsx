import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import {
  Settings,
  Shield,
  FileText,
  Ban,
  Clock,
  UserCheck
} from 'lucide-react';

export const SettingsView: React.FC = () => {
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [suppressed, setSuppressed] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [logs, supp] = await Promise.all([
          api.getAuditLogs().catch(() => []),
          api.getSuppressionList().catch(() => [])
        ]);
        setAuditLogs(logs);
        setSuppressed(supp);
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
      {/* Header */}
      <div>
        <h2 className="text-base font-bold text-slate-100 tracking-tight">Security Audit Logs & Compliance Settings</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Tamper-evident system activity logging and global suppression management.
        </p>
      </div>

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
            {suppressed.length === 0 ? (
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
            <span className="text-[11px] font-mono text-slate-400">Immutable</span>
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
    </div>
  );
};
