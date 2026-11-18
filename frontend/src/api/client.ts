const API_BASE = '/api/v1';

export function getAuthToken(): string | null {
  return localStorage.getItem('acttrident_token');
}

export function getRefreshToken(): string | null {
  return localStorage.getItem('acttrident_refresh_token');
}

export function setAuthTokens(accessToken: string, refreshToken?: string) {
  localStorage.setItem('acttrident_token', accessToken);
  if (refreshToken) {
    localStorage.setItem('acttrident_refresh_token', refreshToken);
  }
}

export function clearAuthTokens() {
  localStorage.removeItem('acttrident_token');
  localStorage.removeItem('acttrident_refresh_token');
}

export const clearAuthToken = clearAuthTokens;

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (res.ok) {
      const data = await res.json();
      setAuthTokens(data.access_token, data.refresh_token);
      return data.access_token;
    }
  } catch {
    // refresh failed
  }

  clearAuthTokens();
  return null;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  let token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  let response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle 401 with Token Rotation / Refresh
  if (response.status === 401 && !endpoint.startsWith('/auth/login') && !endpoint.startsWith('/auth/refresh')) {
    if (!isRefreshing) {
      isRefreshing = true;
      const newToken = await refreshAccessToken();
      isRefreshing = false;

      if (newToken) {
        onRefreshed(newToken);
        headers.set('Authorization', `Bearer ${newToken}`);
        response = await fetch(`${API_BASE}${endpoint}`, {
          ...options,
          headers,
        });
      }
    } else {
      // Wait for existing refresh promise
      const retryToken = await new Promise<string>((resolve) => {
        subscribeTokenRefresh((token) => resolve(token));
      });
      headers.set('Authorization', `Bearer ${retryToken}`);
      response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
      });
    }
  }

  if (!response.ok) {
    let errorDetail = 'An error occurred';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      errorDetail = await response.text();
    }
    throw new Error(errorDetail || `HTTP error ${response.status}`);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // Auth
  login: async (username: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    const res = await request<{ access_token: string; refresh_token?: string; token_type: string; user: any }>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    });
    setAuthTokens(res.access_token, res.refresh_token);
    return res;
  },
  getMe: () => request<any>('/auth/me'),
  getUsers: () => request<any[]>('/auth/users'),
  adminCreateUser: (data: { email: string; full_name: string; password: string; role: string }) =>
    request<any>('/auth/users', { method: 'POST', body: JSON.stringify(data) }),
  updateUserStatus: (userId: number, isActive: boolean) =>
    request<any>(`/auth/users/${userId}/status`, { method: 'PATCH', body: JSON.stringify({ is_active: isActive }) }),
  updateUserRole: (userId: number, role: string) =>
    request<any>(`/auth/users/${userId}/role`, { method: 'PATCH', body: JSON.stringify({ role }) }),
  logout: async () => {
    try {
      await request<any>('/auth/logout', { method: 'POST' });
    } catch {
      // Ignore network errors on logout
    }
    clearAuthTokens();
  },

  // Companies & Leads
  getCompanies: (params: { city?: string; industry?: string; search?: string; skip?: number; limit?: number; is_demo?: boolean } = {}) => {
    const query = new URLSearchParams();
    if (params.city) query.append('city', params.city);
    if (params.industry) query.append('industry', params.industry);
    if (params.search) query.append('search', params.search);
    if (params.is_demo !== undefined) query.append('is_demo', String(params.is_demo));
    if (params.skip !== undefined) query.append('skip', String(params.skip));
    if (params.limit !== undefined) query.append('limit', String(params.limit));
    return request<{ items: any[]; total: number }>(`/companies?${query.toString()}`);
  },
  createCompany: (company: any) => request<any>('/companies', { method: 'POST', body: JSON.stringify(company) }),
  getCompany: (id: number) => request<any>(`/companies/${id}`),
  updateCompany: (id: number, updates: any) => request<any>(`/companies/${id}`, { method: 'PUT', body: JSON.stringify(updates) }),
  verifyCompany: (
    id: number,
    data: {
      verification_status: string;
      verification_method: string;
      laptop_count_verified?: number;
      laptop_count_evidence?: string;
      employee_size_evidence?: string;
      source_url?: string;
      notes?: string;
    }
  ) => request<any>(`/companies/${id}/verify`, { method: 'POST', body: JSON.stringify(data) }),
  uploadCSV: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<any>('/companies/import-csv', { method: 'POST', body: formData });
  },
  exportCompaniesCsv: async () => {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE}/companies/export/csv`, { headers });
    if (!res.ok) throw new Error('Failed to export CSV');
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'acttrident_companies.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },

  // Discovery
  getDiscoverySources: async () => {
    const res = await request<{ sources?: any[] } | any[]>('/discovery/sources');
    return Array.isArray(res) ? res : (res.sources || []);
  },
  searchDiscovery: (params: { city: string; industry?: string; query?: string; min_devices?: number; include_demo?: boolean }) =>
    request<any[]>('/discovery/search', { method: 'POST', body: JSON.stringify(params) }),
  importDiscoveredLead: (lead: any) => request<any>('/discovery/import', { method: 'POST', body: JSON.stringify(lead) }),
  batchImportDiscoveredLeads: (companies: any[]) =>
    request<any[]>('/discovery/batch-import', { method: 'POST', body: JSON.stringify({ companies }) }),
  crawlWebsite: (websiteUrl: string, companyName?: string, city?: string) =>
    request<any>('/discovery/crawl-website', { method: 'POST', body: JSON.stringify({ website_url: websiteUrl, company_name: companyName, city }) }),
  uploadDiscoveryCsv: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<any[]>('/discovery/upload-csv', { method: 'POST', body: formData });
  },

  // Qualification
  qualifyCompany: (companyId: number) => request<any>(`/qualification/company/${companyId}`, { method: 'POST' }),
  batchQualifyCompanies: (companyIds: number[]) =>
    request<any[]>('/qualification/batch', { method: 'POST', body: JSON.stringify(companyIds) }),
  reverifyStaleQualifications: (maxAgeDays: number = 30) =>
    request<any[]>(`/qualification/reverify-stale?max_age_days=${maxAgeDays}`, { method: 'POST' }),

  // Research Report
  generateResearchReport: (companyId: number) => request<any>(`/research/company/${companyId}`, { method: 'POST' }),
  getResearchReport: (companyId: number) => request<any>(`/research/company/${companyId}`),

  // Email Outreach & Approvals
  generateEmail: (data: { company_id: number; tone?: string; custom_notes?: string; campaign_id?: number }) =>
    request<any>('/emails/generate', { method: 'POST', body: JSON.stringify(data) }),
  getApprovalQueue: (status: string = 'draft', campaignId?: number) => {
    const query = new URLSearchParams({ status });
    if (campaignId) query.append('campaign_id', String(campaignId));
    return request<{ items: any[]; total: number }>(`/approvals/queue?${query.toString()}`);
  },
  approveEmail: (draftId: number) => request<any>(`/approvals/approve/${draftId}`, { method: 'POST' }),
  rejectEmail: (draftId: number, reason: string) =>
    request<any>(`/approvals/reject/${draftId}`, { method: 'POST', body: JSON.stringify({ reason }) }),
  skipEmail: (draftId: number) => request<any>(`/approvals/skip/${draftId}`, { method: 'POST' }),
  updateEmailDraft: (draftId: number, data: any) => request<any>(`/emails/drafts/${draftId}`, { method: 'PUT', body: JSON.stringify(data) }),
  sendApprovedEmail: (draftId: number) => request<any>(`/emails/send/${draftId}`, { method: 'POST' }),
  bulkApprovalAction: (draftIds: number[], action: string, reason?: string) =>
    request<any>('/approvals/bulk', { method: 'POST', body: JSON.stringify({ draft_ids: draftIds, action, reason }) }),

  // WhatsApp
  getWhatsAppStatus: () => request<any>('/whatsapp/status'),
  checkWhatsAppHealth: () => request<any>('/whatsapp/health-check', { method: 'POST' }),
  syncWhatsAppTemplates: () => request<any>('/whatsapp/templates/sync', { method: 'POST' }),
  getWhatsAppTemplates: (includeAll: boolean = true) => request<any[]>(`/whatsapp/templates?include_all=${includeAll}`),
  recordWhatsAppConsent: (consent: any) => request<any>('/whatsapp/consent', { method: 'POST', body: JSON.stringify(consent) }),
  draftWhatsApp: (data: any) => request<any>('/whatsapp/draft', { method: 'POST', body: JSON.stringify(data) }),
  approveWhatsApp: (id: number) => request<any>(`/whatsapp/approve/${id}`, { method: 'POST' }),
  sendWhatsApp: (id: number) => request<any>(`/whatsapp/send/${id}`, { method: 'POST' }),
  getWhatsAppMessages: () => request<any[]>('/whatsapp/messages'),

  // Campaigns
  getCampaigns: () => request<any[]>('/campaigns'),
  createCampaign: (data: any) => request<any>('/campaigns', { method: 'POST', body: JSON.stringify(data) }),
  getCampaign: (id: number) => request<any>(`/campaigns/${id}`),
  addCampaignRecipients: (campaignId: number, companyIds: number[]) =>
    request<any>(`/campaigns/${campaignId}/recipients`, { method: 'POST', body: JSON.stringify({ company_ids: companyIds }) }),
  generateCampaignDrafts: (campaignId: number, tone: string = 'Friendly professional') =>
    request<any>(`/campaigns/${campaignId}/batch-draft`, { method: 'POST', body: JSON.stringify({ tone }) }),
  sendApprovedCampaignEmails: (campaignId: number) =>
    request<any>(`/campaigns/${campaignId}/dispatch-approved`, { method: 'POST' }),
  enqueueApprovedCampaignEmails: (campaignId: number) =>
    request<any>(`/campaigns/${campaignId}/enqueue-approved`, { method: 'POST' }),
  pauseCampaign: (campaignId: number) =>
    request<any>(`/campaigns/${campaignId}/pause`, { method: 'POST' }),
  resumeCampaign: (campaignId: number) =>
    request<any>(`/campaigns/${campaignId}/resume`, { method: 'POST' }),
  stopCampaign: (campaignId: number) =>
    request<any>(`/campaigns/${campaignId}/stop`, { method: 'POST' }),

  // CRM Pipeline
  getLeads: (status?: string, city?: string) => {
    const query = new URLSearchParams();
    if (status) query.append('pipeline_status', status);
    if (city) query.append('city', city);
    return request<{ items: any[]; total: number; valid_statuses: string[] }>(`/crm/leads?${query.toString()}`);
  },
  updateLeadStatus: (leadId: number, status: string, notes?: string) =>
    request<any>(`/crm/leads/${leadId}/status`, { method: 'PATCH', body: JSON.stringify({ status, notes }) }),
  scheduleMeeting: (leadId: number, meeting: any) =>
    request<any>(`/crm/leads/${leadId}/meetings`, { method: 'POST', body: JSON.stringify(meeting) }),
  activateTrial: (leadId: number, trial: any) =>
    request<any>(`/crm/leads/${leadId}/trials`, { method: 'POST', body: JSON.stringify(trial) }),
  recordOptOut: (identifier: string, channel: string = 'all', reason: string = 'user_opt_out') =>
    request<any>('/crm/opt-out', { method: 'POST', body: JSON.stringify({ identifier, channel, reason }) }),

  // Inbox & Replies
  getInbox: async (classification?: string) => {
    const query = new URLSearchParams();
    if (classification) query.append('classification', classification);
    const res = await request<{ items: any[]; total: number; categories: string[] }>(`/replies/inbox?${query.toString()}`);
    return {
      ...res,
      available_categories: res.categories || [],
    };
  },
  approveReplyResponse: (replyId: number, approvedOrText: boolean | string = true, editedResponse?: string) => {
    const isBool = typeof approvedOrText === 'boolean';
    const approved = isBool ? approvedOrText : true;
    const text = isBool ? editedResponse : approvedOrText;
    return request<any>('/replies/approve-response', {
      method: 'POST',
      body: JSON.stringify({ reply_id: replyId, approved, edited_response: text, approved_text: text })
    });
  },
  ingestInboundReply: (data: {
    channel: string;
    sender_identifier: string;
    recipient_identifier: string;
    subject?: string;
    message_body: string;
  }) => request<any>('/replies/inbound', { method: 'POST', body: JSON.stringify(data) }),

  // Analytics
  getDashboardAnalytics: (campaignId?: number) => {
    const query = campaignId ? `?campaign_id=${campaignId}` : '';
    return request<any>(`/analytics/dashboard${query}`);
  },
  getCityAnalytics: () => request<any[]>('/analytics/cities'),
  getCampaignAnalytics: () => request<any[]>('/analytics/campaigns'),
  getDailyDigest: () => request<any>('/analytics/daily-digest'),

  // Settings & Integrations
  getIntegrations: () => request<any[]>('/settings/integrations'),
  saveIntegration: (config: any) => request<any>('/settings/integrations', { method: 'POST', body: JSON.stringify(config) }),
  getAuditLogs: () => request<any[]>('/settings/audit-logs'),
  getSuppressionList: () => request<any[]>('/settings/suppression-list'),
  getKillSwitch: () => request<{ active: boolean; reason?: string; updated_at?: string }>('/settings/kill-switch'),
  toggleKillSwitch: (active: boolean, reason?: string) =>
    request<any>('/settings/kill-switch', { method: 'POST', body: JSON.stringify({ active, reason }) }),

  // Gmail OAuth 2.0, LinkedIn OAuth 2.0 & Unified Channel Connections
  getAllChannelStatuses: () => request<{ channels: Record<string, any> }>('/integrations/channels/status'),
  getGmailStatus: () => request<any>('/integrations/gmail/status'),
  startGmailOAuth: () => request<{ authorization_url: string; state: string; scopes: string[] }>('/integrations/gmail/oauth/start'),
  syncGmailReplies: (maxResults: number = 20) =>
    request<any>(`/integrations/gmail/sync-replies?max_results=${maxResults}`, { method: 'POST' }),
  disconnectGmail: () => request<any>('/integrations/gmail/disconnect', { method: 'POST' }),
  getDraftSendAttempts: (draftId: number) => request<any[]>(`/emails/drafts/${draftId}/attempts`),

  // LinkedIn Official OAuth 2.0 & Compliant Outreach
  getLinkedInStatus: () => request<any>('/linkedin/status'),
  startLinkedInOAuth: () => request<{ authorization_url: string; state: string; scopes: string[] }>('/integrations/linkedin/oauth/start'),
  disconnectLinkedIn: () => request<any>('/integrations/linkedin/disconnect', { method: 'POST' }),
  getLinkedInMessages: (statusFilter?: string) => {
    const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : '';
    return request<any[]>(`/linkedin/messages${query}`);
  },
  draftLinkedInMessage: (data: {
    company_id: number;
    recipient_name?: string;
    recipient_profile_url?: string;
    message_type?: string;
    tone?: string;
    custom_message?: string;
    custom_notes?: string;
  }) => request<any>('/linkedin/draft', { method: 'POST', body: JSON.stringify(data) }),
  updateLinkedInMessage: (id: number, data: { recipient_name?: string; recipient_profile_url?: string; message_body?: string }) =>
    request<any>(`/linkedin/messages/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  approveLinkedInMessage: (id: number) => request<any>(`/linkedin/approve/${id}`, { method: 'POST' }),
  rejectLinkedInMessage: (id: number, reason: string) =>
    request<any>(`/linkedin/reject/${id}`, { method: 'POST', body: JSON.stringify({ reason }) }),
  dispatchLinkedInMessage: (id: number) => request<any>(`/linkedin/dispatch/${id}`, { method: 'POST' }),
  confirmLinkedInManualSend: (id: number, notes?: string) =>
    request<any>(`/linkedin/confirm-manual-send/${id}`, { method: 'POST', body: JSON.stringify({ notes }) }),

  // Background Jobs & Queue Automation
  getQueueHealth: () => request<any>('/jobs/health'),
  getTaskHistory: (category?: string, status?: string) => {
    const query = new URLSearchParams();
    if (category) query.append('category', category);
    if (status) query.append('status', status);
    return request<any[]>(`/jobs/history?${query.toString()}`);
  },
  triggerBackgroundTask: (data: { category: string; payload?: any; idempotency_key?: string; campaign_id?: number; execute_sync?: boolean }) =>
    request<any>('/jobs/trigger', { method: 'POST', body: JSON.stringify(data) }),
  cancelTask: (taskId: string) => request<any>(`/jobs/cancel/${taskId}`, { method: 'POST' }),
  getDeadLetterQueue: () => request<any[]>('/jobs/dead-letter'),
  retryDeadLetterTask: (dlqId: number) => request<any>(`/jobs/dead-letter/${dlqId}/retry`, { method: 'POST' }),
  getOutbox: (statusFilter?: string) => {
    const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : '';
    return request<any[]>(`/jobs/outbox${query}`);
  },
  processOutbox: (limit: number = 20) => request<any>(`/jobs/outbox/process?limit=${limit}`, { method: 'POST' }),
};
