"use client";

import type { JobSummary } from "../types";

type Props = {
  jobs: JobSummary[];
  selectedJobId: string | null;
  onSelect: (jobId: string) => void;
};

export default function JobList({ jobs, selectedJobId, onSelect }: Props) {
  return (
    <section className="panel">
      <header className="panelHeader">
        <h2>Jobs</h2>
        <span>{jobs.length}</span>
      </header>
      <div className="jobList">
        {jobs.map((job) => (
          <button
            key={job.job_id}
            className={`jobItem ${selectedJobId === job.job_id ? "active" : ""}`}
            onClick={() => onSelect(job.job_id)}
          >
            <strong>{job.topic}</strong>
            <small>{job.status}</small>
          </button>
        ))}
        {jobs.length === 0 ? <p className="empty">No jobs yet.</p> : null}
      </div>
    </section>
  );
}
