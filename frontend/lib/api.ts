import type { JobDetail, JobSummary, LibraryItem, ReviewDecision } from "../types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export function createJob(topic: string): Promise<JobSummary> {
  return request<JobSummary>("/api/jobs", {
    method: "POST",
    body: JSON.stringify({ topic }),
  });
}

export function getJobs(): Promise<JobSummary[]> {
  return request<JobSummary[]>("/api/jobs");
}

export function getJob(jobId: string): Promise<JobDetail> {
  return request<JobDetail>(`/api/jobs/${jobId}`);
}

export function submitReview(
  jobId: string,
  humanDecision: ReviewDecision,
  reviewNotes: string
): Promise<JobSummary> {
  return request<JobSummary>(`/api/jobs/${jobId}/review`, {
    method: "POST",
    body: JSON.stringify({
      human_decision: humanDecision,
      review_notes: reviewNotes,
    }),
  });
}

export function getLibrary(): Promise<LibraryItem[]> {
  return request<LibraryItem[]>("/api/library");
}

export function mediaUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}
