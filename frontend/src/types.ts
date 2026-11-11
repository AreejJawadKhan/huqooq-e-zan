// Mirrors backend/app/schemas.py. Keep in sync (see docs/API.md).

export type Jurisdiction = "pakistan" | "punjab" | "sindh" | "kp" | "balochistan" | "ict";
export type Topic = "harassment" | "wages" | "property" | "tenancy" | "other";
export type Status = "answered" | "not_found" | "out_of_scope" | "danger";
export type Confidence = "high" | "medium" | "low" | "none";
export type LetterType = "harassment_complaint" | "wage_complaint" | "property_complaint";

export interface AskRequest {
  question: string;
  jurisdiction?: Jurisdiction | null;
}

export interface Citation {
  chunk_id: string;
  act: string;
  section: string;
  heading: string;
  jurisdiction: string;
  source_url: string;
  excerpt: string;
}

export interface Referral {
  name: string;
  number: string | null;
  note: string;
  source_url: string;
  verified: boolean;
}

export interface WageInfo {
  jurisdiction: string;
  monthly_pkr: number | null;
  status: "notified_reported" | "proposed" | "unconfirmed" | string;
  effective_from: string | null;
  notification_date: string | null;
  as_of: string;
  verified: boolean;
  source_url: string;
  note: string;
}

export interface Caveat {
  en: string;
  ur: string;
}

export interface Detected {
  language: string;
  topic: Topic;
  jurisdiction: Jurisdiction | null;
  english_query: string;
}

export interface AskResponse {
  status: Status;
  answer_ur: string;
  answer_en: string;
  confidence: Confidence;
  citations: Citation[];
  where_to_go: Referral[];
  wage: WageInfo | null;
  caveats: Caveat[];
  needs_province: boolean;
  letter_type: LetterType | null;
  detected: Detected;
  disclaimer_ur: string;
  disclaimer_en: string;
}

export interface LetterRequest {
  letter_type: LetterType;
  complainant_name: string;
  complainant_address?: string;
  complainant_cnic?: string;
  respondent_name?: string;
  respondent_details?: string;
  city?: string;
  facts: string;
  relief?: string;
  legal_basis?: string[];
}
