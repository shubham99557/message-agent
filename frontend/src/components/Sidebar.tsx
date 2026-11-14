import React from 'react';
import { ViewType } from '../types';
import {
  LayoutDashboard,
  Search,
  Database,
  BrainCircuit,
  Mail,
  MessageSquare,
  Megaphone,
  CheckSquare,
  Inbox,
  GitBranch,
  BarChart3,
  Layers,
  Settings,
  Shield,
  LogOut
} from 'lucide-react';

interface SidebarProps {
  currentView: ViewType;
  onSelectView: (view: ViewType) => void;
  pendingApprovalsCount: number;
  inboxCount: number;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onSelectView,
  pendingApprovalsCount,
  inboxCount,
  onLogout
}) => {
  const navItems = [
    { id: 'dashboard' as ViewType, label: 'Dashboard', icon: LayoutDashboard },
    { id: 'discovery' as ViewType, label: 'Discover Companies', icon: Search },
    { id: 'leads' as ViewType, label: 'Lead Database', icon: Database },
    { id: 'research' as ViewType, label: 'AI Research', icon: BrainCircuit },
    { id: 'email' as ViewType, label: 'Email Outreach', icon: Mail },
    { id: 'whatsapp' as ViewType, label: 'WhatsApp Outreach', icon: MessageSquare },
    { id: 'campaigns' as ViewType, label: 'Campaigns', icon: Megaphone },
    {
      id: 'approvals' as ViewType,
      label: 'Approval Queue',
      icon: CheckSquare,
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined,
      badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/30'
    },
    {
      id: 'inbox' as ViewType,
      label: 'Inbox & Replies',
      icon: Inbox,
      badge: inboxCount > 0 ? inboxCount : undefined,
      badgeColor: 'bg-cobalt-500/20 text-cobalt-300 border-cobalt-500/30'
    },
    { id: 'crm' as ViewType, label: 'CRM Pipeline', icon: GitBranch },
    { id: 'analytics' as ViewType, label: 'Analytics', icon: BarChart3 },
    { id: 'integrations' as ViewType, label: 'Integrations', icon: Layers },
    { id: 'settings' as ViewType, label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-64 bg-cobalt-950 border-r border-cobalt-800/80 flex flex-col h-screen select-none shrink-0">
      {/* Brand Header */}
      <div className="p-5 border-b border-cobalt-800/80 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-cobalt-600 flex items-center justify-center shadow-lg shadow-cobalt-600/30 border border-cobalt-500/40">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-bold text-slate-100 tracking-tight leading-none text-base">ActTrident</div>
            <div className="text-[11px] font-mono text-cobalt-400 font-medium tracking-wide mt-1 uppercase">Outreach Agent</div>
          </div>
        </div>
      </div>

      {/* Target Market Indicator */}
      <div className="px-5 py-2.5 bg-cobalt-900/60 border-b border-cobalt-800/50 flex items-center justify-between text-[11px] text-slate-400">
        <span>Active Markets:</span>
        <span className="font-mono text-slate-300 font-medium">WB • SK • BR</span>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectView(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-md text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-cobalt-600 text-white shadow-sm'
                  : 'text-slate-300 hover:bg-cobalt-900/80 hover:text-slate-100'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && (
                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full border ${item.badgeColor || 'bg-cobalt-800 text-slate-300'}`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer / User Profile */}
      <div className="p-3 border-t border-cobalt-800/80 bg-cobalt-900/40">
        <div className="flex items-center justify-between px-2 py-1.5">
          <div className="flex items-center space-x-2.5 overflow-hidden">
            <div className="w-7 h-7 rounded bg-cobalt-800 border border-cobalt-700 flex items-center justify-center text-xs font-semibold text-cobalt-300 shrink-0">
              AT
            </div>
            <div className="truncate">
              <div className="text-xs font-medium text-slate-200 truncate">BD Sales Team</div>
              <div className="text-[10px] font-mono text-slate-400">acttrident.ai</div>
            </div>
          </div>
          <button
            onClick={onLogout}
            title="Sign out"
            className="p-1.5 rounded hover:bg-cobalt-800 text-slate-400 hover:text-rose-400 transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
