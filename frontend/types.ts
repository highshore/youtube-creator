export type JobStatus = "queued" | "running" | "waiting_review" | "completed" | "failed";

export type JobSummary = {
  job_id: string;
  topic: string;
  status: JobStatus | string;
  created_at: string;
  updated_at: string;
};

export type JobDetail = {
  job_id: string;
  thread_id: string;
  topic: string;
  status: JobStatus | string;
  created_at: string;
  updated_at: string;
  review_payload?: Record<string, unknown> | null;
  state: Record<string, unknown>;
  error?: string | null;
};

export type LibraryItem = {
  job_id?: string | null;
  topic?: string | null;
  script?: string | null;
  final_video?: string | null;
  final_video_url?: string | null;
  metadata_path?: string | null;
  created_at?: string | null;
};

export type ReviewDecision =
  | "approved"
  | "needs_script_revision"
  | "find_more_assets"
  | "reassemble";
