const API_BASE = '/api/v1';

export function getAuthToken(): string | null {
  return localStorage.getItem('acttrident_token');
}

export function setAuthToken(token: string) {
  localStorage.setItem('acttrident_token', token);
}

export function clearAuthToken() {
  localStorage.removeItem('acttrident_token');
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});
  
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

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
    const res = await request<{ access_token: string; token_type: string; user: any }>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    });
    setAuthToken(res.access_token);
    return res;
  },
  getMe: () => request<any>('/auth/me'),
  logout: () => {
    clearAuthToken();
  },

  // Companies & Leads
  getCompanies: (params: { city?: string; industry?: string; search?: string; skip?: number; limit?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.city) query.append('city', params.city);
    if (params.industry) query.append('industry', params.industry);
    if (params.search) query.append('search', params.search);
    if (params.skip !== undefined) query.append('skip', String(params.skip));
    if (params.limit !== undefined) query.append('limit', String(params.limit));
    return request<{ items: any[]; total: number }>(`/companies?${query.toString()}`);
  },
  createCompany: (company: any) => request<any>('/companies', { method: 'POST', body: JSON.stringify(company) }),
  getCompany: (id: number) => request<any>(`/companies/${id}`),
  updateCompany: (id: number, updates: any) => request<any>(`/companies/${id}`, { method: 'PUT', body: JSON.stringify(updates) }),
  uploadCSV: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<any>('/companies/import-csv', { method: 'POST', body: formData });
  },

  // Discovery
  searchDiscovery: (params: { city: string; industry?: string; query?: string; min_devices?: number }) =>
    request<any[]>('/discovery/search', { method: 'POST', body: JSON.stringify(params) }),
  importDiscoveredLead: (lead: any) => request<any>('/discovery/import', { method: 'POST', body: JSON.stringify(lead) }),

  // Qualification
  qualifyCompany: (companyId: number) => request<any>(`/qualification/company/${companyId}`, { method: 'POST' }),

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
  getWhatsAppTemplates: () => request<any[]>('/whatsapp/templates'),
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
    request<any>(`/campaigns/${campaignId}/generate-drafts`, { method: 'POST', body: JSON.stringify({ tone }) }),
  sendApprovedCampaignEmails: (campaignId: number) =>
    request<any>(`/campaigns/${campaignId}/send-approved`, { method: 'POST' }),

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
  getInbox: (classification?: string) => {
    const query = new URLSearchParams();
    if (classification) query.append('classification', classification);
    return request<{ items: any[]; total: number; available_categories: string[] }>(`/replies/inbox?${query.toString()}`);
  },
  approveReplyResponse: (replyId: number, approvedText: string) =>
    request<any>(`/replies/${replyId}/approve-response`, { method: 'POST', body: JSON.stringify({ approved_text: approvedText }) }),

  // Analytics
  getDashboardAnalytics: (campaignId?: number) => {
    const query = campaignId ? `?campaign_id=${campaignId}` : '';
    return request<any>(`/analytics/dashboard${query}`);
  },
  getCityAnalytics: () => request<any[]>('/analytics/cities'),
  getCampaignAnalytics: () => request<any[]>('/analytics/campaigns'),

  // Settings & Integrations
  getIntegrations: () => request<any[]>('/settings/integrations'),
  saveIntegration: (config: any) => request<any>('/settings/integrations', { method: 'POST', body: JSON.stringify(config) }),
  getAuditLogs: () => request<any[]>('/settings/audit-logs'),
  getSuppressionList: () => request<any[]>('/settings/suppression-list'),
};
