export type ViewType =
  | 'dashboard'
  | 'discovery'
  | 'leads'
  | 'research'
  | 'email'
  | 'whatsapp'
  | 'campaigns'
  | 'approvals'
  | 'inbox'
  | 'crm'
  | 'analytics'
  | 'integrations'
  | 'settings';

export interface Company {
  id: number;
  name: string;
  website?: string;
  industry?: string;
  description?: string;
  city: string;
  state?: string;
  country: string;
  employee_count_min?: number;
  employee_count_max?: number;
  employee_size_evidence?: string;
  laptop_count_verified?: number;
  laptop_count_evidence?: string;
  has_verified_5_plus_laptops: boolean;
  public_email?: string;
  public_phone?: string;
  public_whatsapp?: string;
  linkedin_url?: string;
  decision_maker_name?: string;
  decision_maker_role?: string;
  decision_maker_email?: string;
  qualification_score: number;
  qualification_status: string;
  qualification_reason?: string;
  qualification_factors?: string;
  date_last_verified: string;
  created_at: string;
  sources: ContactSource[];
}

export interface ContactSource {
  id: number;
  field_name: string;
  source_url: string;
  source_type: string;
  verified_at: string;
  notes?: string;
}

export interface Lead {
  id: number;
  company_id: number;
  pipeline_status: string;
  last_contact_date?: string;
  next_followup_date?: string;
  followup_count: number;
  meeting_notes?: string;
  product_feedback?: string;
  trial_status: string;
  trial_start_date?: string;
  trial_end_date?: string;
  trial_device_count?: number;
  conversion_value: number;
  created_at: string;
  company?: Company;
  meetings: any[];
  followups: any[];
  trials: any[];
}

export interface EmailDraft {
  id: number;
  campaign_id?: number;
  company_id: number;
  recipient_email: string;
  recipient_name?: string;
  subject: string;
  body_html: string;
  body_text: string;
  tone: string;
  approval_status: string;
  rejection_reason?: string;
  sent_at?: string;
  provider: string;
  company_name?: string;
  company_city?: string;
  contact_source_url?: string;
  consent_status?: string;
  campaign_name?: string;
}

export interface ReplyItem {
  id: number;
  company_id: number;
  channel: string;
  sender_identifier: string;
  subject?: string;
  message_body: string;
  classification: string;
  classification_confidence: number;
  classification_reason?: string;
  suggested_response?: string;
  is_negotiation: boolean;
  human_approved: boolean;
  is_handled: boolean;
  received_at: string;
  company_name?: string;
}
