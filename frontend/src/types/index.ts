export type ViewType =
  | 'dashboard'
  | 'discovery'
  | 'leads'
  | 'followups'
  | 'services'
  | 'research'
  | 'email'
  | 'whatsapp'
  | 'linkedin'
  | 'campaigns'
  | 'approvals'
  | 'inbox'
  | 'crm'
  | 'analytics'
  | 'integrations'
  | 'automation'
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
  website_classification?: string;
  email_verification_status?: string;
  phone_verification_status?: string;
  matched_service_id?: number;
  matched_service_name?: string;
  matched_service_rationale?: string;
  followup_status?: string;
  internal_notes?: string;
  is_demo?: boolean;
  verification_status?: string;
  verification_method?: string;
  date_last_verified: string;
  created_at: string;
  sources: ContactSource[];
}

export interface ContactSource {
  id: number;
  field_name: string;
  source_url: string;
  source_type: string;
  verification_status?: string;
  verification_method?: string;
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

export interface EmailVariationItem {
  variation_type: string;
  label: string;
  subject: string;
  body_text: string;
  body_html: string;
  tone: string;
  description: string;
}

export interface EmailVariationsResponse {
  company_id: number;
  company_name: string;
  website?: string;
  city: string;
  industry?: string;
  recipient_name?: string;
  recipient_email?: string;
  recipient_role?: string;
  recipient_phone?: string;
  matched_service_code?: string;
  matched_service_name?: string;
  service_match_reason?: string;
  service_match_evidence?: string;
  service_match_confidence: number;
  unsupported_assumptions: string[];
  missing_information: string[];
  source_evidence: Record<string, any>[];
  subject_suggestions: string[];
  variations: EmailVariationItem[];
  generation_model: string;
  is_synthetic: boolean;
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
  draft_type?: string;
  variation_type?: string;
  generation_model?: string;
  matched_service_code?: string;
  matched_service_name?: string;
  subject_suggestions?: string[];
  source_evidence?: string[];
  missing_information?: string[];
  approval_status: string;
  rejection_reason?: string;
  approval_hash?: string;
  approved_by_id?: number;
  approved_at?: string;
  version?: number;
  content_hash?: string;
  sent_at?: string;
  provider: string;
  company_name?: string;
  company_city?: string;
  contact_source_url?: string;
  consent_status?: string;
  campaign_name?: string;
  created_at?: string;
  updated_at?: string;
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

export interface DiscoveredCompanyItem {
  name: string;
  website?: string;
  city: string;
  state?: string;
  country?: string;
  industry?: string;
  description?: string;
  public_email?: string;
  public_phone?: string;
  public_whatsapp?: string;
  linkedin_url?: string;
  decision_maker_name?: string;
  decision_maker_role?: string;
  employee_count_min?: number;
  employee_count_max?: number;
  employee_size_evidence?: string;
  laptop_count_verified?: number;
  laptop_count_evidence?: string;
  laptop_fleet_status?: string;
  source_url: string;
  contact_page_url?: string;
  business_address?: string;
  missing_information?: string[];
  source_type: string;
  is_demo: boolean;
  verification_status: string;
  email_verification_status?: string;
  phone_verification_status?: string;
  website_status?: string;
  website_classification?: string;
  confidence_level: number;
  qualification_score?: number;
  qualification_category?: string;
  qualification_reason?: string;
  crm_id?: number;
  crm_status?: string;
  matched_service_id?: number;
  matched_service_name?: string;
  matched_service_rationale?: string;
}

export interface ServiceCatalogueItem {
  id: number;
  service_code: string;
  service_name: string;
  description: string;
  target_business_types: string[];
  common_business_problems: string[];
  required_qualification_signals: Record<string, any>;
  approved_claims: string[];
  disallowed_claims: string[];
  discovery_questions?: string[];
  outreach_templates?: Record<string, Record<string, string>>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ServiceCatalogueCreate {
  service_code: string;
  service_name: string;
  description: string;
  target_business_types: string[];
  common_business_problems: string[];
  required_qualification_signals?: Record<string, any>;
  approved_claims: string[];
  disallowed_claims: string[];
  discovery_questions?: string[];
  outreach_templates?: Record<string, Record<string, string>>;
  is_active?: boolean;
}

export interface FollowupTask {
  id: number;
  lead_id: number;
  company_id?: number;
  company_name?: string;
  scheduled_date: string;
  due_date?: string;
  status: string;
  suggested_channel: string;
  reminder_at?: string;
  reason?: string;
  next_action?: string;
  assigned_user_id?: number;
  completed_at?: string;
  notes?: string;
  created_at: string;
  updated_at?: string;
}

export interface SuppressionItem {
  id: number;
  identifier: string;
  channel: string;
  reason: string;
  created_at: string;
}

export interface DiscoveryRunItem {
  id: number;
  run_uuid: string;
  query_summary: string;
  city?: string;
  state?: string;
  country?: string;
  industry?: string;
  scope: string;
  active_providers?: string[];
  raw_candidates_count: number;
  unique_businesses_count: number;
  filtered_facilities_count: number;
  authentic_websites_count: number;
  listed_phones_count: number;
  verified_emails_count: number;
  high_priority_count: number;
  medium_priority_count: number;
  low_priority_count: number;
  execution_duration_seconds: number;
  created_at: string;
}
