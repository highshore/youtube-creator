"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import JobDetailPanel from "../components/JobDetail";
import JobList from "../components/JobList";
import LibraryPanel from "../components/LibraryPanel";
import { ApiError, createJob, getJob, getJobs, getLibrary, submitReview } from "../lib/api";
import type { JobDetail, JobSummary, LibraryItem, ReviewDecision } from "../types";

export default function Home() {
  const [topic, setTopic] = useState("");
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);
  const [library, setLibrary] = useState<LibraryItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshAll = useCallback(async () => {
    try {
      const [jobRows, libraryRows] = await Promise.all([getJobs(), getLibrary()]);
      setJobs(jobRows);
      setLibrary(libraryRows);

      let resolvedSelectedId = selectedJobId;
      if (!resolvedSelectedId || !jobRows.some((j) => j.job_id === resolvedSelectedId)) {
        resolvedSelectedId = jobRows[0]?.job_id ?? null;
        setSelectedJobId(resolvedSelectedId);
      }

      if (!resolvedSelectedId) {
        setSelectedJob(null);
        setError(null);
        return;
      }

      try {
        const detail = await getJob(resolvedSelectedId);
        setSelectedJob(detail);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          setSelectedJob(null);
          const fallbackId = jobRows[0]?.job_id ?? null;
          setSelectedJobId(fallbackId);
        } else {
          throw e;
        }
      }

      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "unknown error");
    }
  }, [selectedJobId]);

  useEffect(() => {
    refreshAll();
    const timer = setInterval(refreshAll, 3000);
    return () => clearInterval(timer);
  }, [refreshAll]);

  const handleCreate = async () => {
    const text = topic.trim();
    if (!text) return;
    setBusy(true);
    try {
      const job = await createJob(text);
      setSelectedJobId(job.job_id);
      setTopic("");
      await refreshAll();
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to create job");
    } finally {
      setBusy(false);
    }
  };

  const handleReview = async (jobId: string, decision: ReviewDecision, notes: string) => {
    try {
      await submitReview(jobId, decision, notes);
      await refreshAll();
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to submit review");
    }
  };

  const selectedTitle = useMemo(() => jobs.find((j) => j.job_id === selectedJobId)?.topic, [jobs, selectedJobId]);

  return (
    <main className="page">
      <section className="hero">
        <h1>LangGraph Shorts Studio</h1>
        <p>Generate script, gather royalty-free assets, assemble video, and review before publishing.</p>
      </section>

      <section className="composer panel">
        <label htmlFor="topic">Topic or POI</label>
        <div className="row">
          <input
            id="topic"
            placeholder="e.g. Kyoto hidden temples at sunrise"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
          <button disabled={busy} onClick={handleCreate}>
            {busy ? "Creating..." : "Create Job"}
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {selectedTitle ? <p className="subtle">Selected: {selectedTitle}</p> : null}
      </section>

      <section className="layout">
        <div className="leftCol">
          <JobList jobs={jobs} selectedJobId={selectedJobId} onSelect={setSelectedJobId} />
          <LibraryPanel items={library} />
        </div>
        <JobDetailPanel job={selectedJob} onReview={handleReview} />
      </section>
    </main>
  );
}
