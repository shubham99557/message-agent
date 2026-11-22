import React, { useState, useEffect } from 'react';
import { ViewType, Company } from './types';
import { api, getAuthToken, clearAuthToken } from './api/client';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';

// Views
import { DashboardView } from './views/DashboardView';
import { DiscoveryView } from './views/DiscoveryView';
import { LeadsView } from './views/LeadsView';
import { ResearchView } from './views/ResearchView';
import { EmailOutreachView } from './views/EmailOutreachView';
import { WhatsAppView } from './views/WhatsAppView';
import { LinkedInView } from './views/LinkedInView';
import { CampaignsView } from './views/CampaignsView';
import { ApprovalQueueView } from './views/ApprovalQueueView';
import { InboxView } from './views/InboxView';
import { CrmPipelineView } from './views/CrmPipelineView';
import { AnalyticsView } from './views/AnalyticsView';
import { IntegrationsView } from './views/IntegrationsView';
import { AutomationCenterView } from './views/AutomationCenterView';
import { SettingsView } from './views/SettingsView';

import { Shield, Lock } from 'lucide-react';

export const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(Boolean(getAuthToken()));
  const [currentView, setCurrentView] = useState<ViewType>('dashboard');
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState(0);
  const [inboxCount, setInboxCount] = useState(0);

  // Login Form State (never embed default administrator credentials in client code)
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loggingIn, setLoggingIn] = useState(false);

  // Poll badge counts periodically
  useEffect(() => {
    if (!isAuthenticated) return;
    const fetchBadges = async () => {
      try {
        const [approvals, inbox] = await Promise.all([
          api.getApprovalQueue('draft').catch(() => ({ total: 0 })),
          api.getInbox().catch(() => ({ total: 0 }))
        ]);
        setPendingApprovalsCount(approvals.total);
        setInboxCount(inbox.total);
      } catch (e) {
        // Ignore polling errors
      }
    };
    fetchBadges();
    const interval = setInterval(fetchBadges, 15000);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoggingIn(true);
    setLoginError(null);
    try {
      await api.login(email, password);
      setIsAuthenticated(true);
    } catch (err: any) {
      setLoginError(err.message || 'Login failed');
    } finally {
      setLoggingIn(false);
    }
  };

  const handleLogout = async () => {
    await api.logout();
    clearAuthToken();
    setIsAuthenticated(false);
  };

  const handleSelectCompany = (company: Company, targetView: ViewType) => {
    setSelectedCompany(company);
    setCurrentView(targetView);
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-cobalt-950 flex items-center justify-center p-4">
        <div className="w-full max-w-sm bg-cobalt-900 border border-cobalt-800 rounded-xl p-8 space-y-6 shadow-2xl relative overflow-hidden">
          <div className="absolute -top-12 -right-12 w-32 h-32 bg-cobalt-600/10 rounded-full blur-2xl pointer-events-none" />
          <div className="text-center space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-cobalt-950 border border-cobalt-700/80 p-2.5 flex items-center justify-center mx-auto shadow-xl shadow-cobalt-950/80">
              <img src="/acttrident-logo.png" alt="ActTrident Official Logo" className="w-full h-full object-contain" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-100 tracking-tight flex items-center justify-center space-x-1.5">
                <span>ActTrident</span>
                <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">AI</span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">The Human Action Security Broker™</p>
              <p className="text-[11px] font-mono text-cobalt-400 mt-1">Autonomous B2B Sales Outreach Agent</p>
            </div>
          </div>

          {loginError && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded text-xs text-rose-300">
              {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4 text-xs">
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Corporate Email</label>
              <input
                type="email"
                placeholder="name@acttrident.ai"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
                required
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Password</label>
              <input
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-cobalt-950 border border-cobalt-800 rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cobalt-600"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loggingIn}
              className="w-full py-2 bg-cobalt-600 hover:bg-cobalt-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors shadow-sm"
            >
              {loggingIn ? 'Authenticating...' : 'Sign In to Platform'}
            </button>
          </form>

          <div className="pt-2 border-t border-cobalt-800/80 text-[11px] text-slate-400 text-center">
            Nationwide B2B Outreach • Any City, State or Technology Hub
          </div>
        </div>
      </div>
    );
  }

  const getViewTitle = () => {
    switch (currentView) {
      case 'dashboard': return { title: 'Executive Overview', sub: 'Active sales campaigns and performance telemetry' };
      case 'discovery': return { title: 'Company Lead Discovery', sub: 'Public directory intelligence across initial target cities' };
      case 'leads': return { title: 'Lead Database', sub: 'Verified corporate records with source attribution' };
      case 'research': return { title: 'AI Research Agent', sub: '7-factor qualification & truthful company dossiers' };
      case 'email': return { title: 'Email Outreach', sub: 'Personalized AI email generation across 5 tones' };
      case 'whatsapp': return { title: 'WhatsApp Outreach', sub: 'Meta Cloud API messaging with strict consent verification' };
      case 'linkedin': return { title: 'LinkedIn Outreach', sub: 'Official OAuth 2.0 & compliant human-assisted outreach workflow' };
      case 'campaigns': return { title: 'Campaign Management', sub: 'Multi-account sequences with daily rate limits' };
      case 'approvals': return { title: 'Human Approval Queue', sub: 'Mandatory human signoff before any outbound dispatch' };
      case 'inbox': return { title: 'Inbound Inbox & AI Replies', sub: '10-class response categorization and suggested replies' };
      case 'crm': return { title: 'CRM Sales Pipeline', sub: '16-stage opportunity and 90-day evaluation tracking' };
      case 'analytics': return { title: 'Campaign Analytics', sub: 'Genuine conversion metrics with authentic denominators' };
      case 'integrations': return { title: 'Integrations & Credentials', sub: 'Configure AI, Gmail/SMTP and Meta WhatsApp Cloud API' };
      case 'automation': return { title: 'Automation Center', sub: 'Persistent background scheduler, IST business hours guards, and execution telemetry' };
      case 'settings': return { title: 'Settings & Audit Logs', sub: 'Security audit trail and global suppression registry' };
      default: return { title: 'ActTrident Agent', sub: '' };
    }
  };

  const { title, sub } = getViewTitle();

  return (
    <div className="flex h-screen bg-cobalt-950 overflow-hidden font-sans">
      <Sidebar
        currentView={currentView}
        onSelectView={setCurrentView}
        pendingApprovalsCount={pendingApprovalsCount}
        inboxCount={inboxCount}
        onLogout={handleLogout}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header currentView={currentView} title={title} subtitle={sub} />

        <main className="flex-1 overflow-y-auto">
          {currentView === 'dashboard' && <DashboardView onNavigate={setCurrentView} />}
          {currentView === 'discovery' && <DiscoveryView onCompanyImported={() => {}} />}
          {currentView === 'leads' && <LeadsView onSelectCompany={handleSelectCompany} />}
          {currentView === 'research' && (
            <ResearchView selectedCompany={selectedCompany} onNavigate={setCurrentView} />
          )}
          {currentView === 'email' && (
            <EmailOutreachView selectedCompany={selectedCompany} onNavigate={setCurrentView} />
          )}
          {currentView === 'whatsapp' && (
            <WhatsAppView selectedCompany={selectedCompany} onNavigate={setCurrentView} />
          )}
          {currentView === 'linkedin' && (
            <LinkedInView selectedCompany={selectedCompany} />
          )}
          {currentView === 'campaigns' && <CampaignsView onNavigate={setCurrentView} />}
          {currentView === 'approvals' && <ApprovalQueueView />}
          {currentView === 'inbox' && <InboxView />}
          {currentView === 'crm' && <CrmPipelineView />}
          {currentView === 'analytics' && <AnalyticsView />}
          {currentView === 'integrations' && <IntegrationsView />}
          {currentView === 'automation' && <AutomationCenterView />}
          {currentView === 'settings' && <SettingsView />}
        </main>
      </div>
    </div>
  );
};
