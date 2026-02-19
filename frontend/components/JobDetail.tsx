"use client";

import { useMemo, useState } from "react";
import { mediaUrl } from "../lib/api";
import type { JobDetail, ReviewDecision } from "../types";

type Props = {
  job: JobDetail | null;
  onReview: (jobId: string, decision: ReviewDecision, notes: string) => Promise<void>;
};

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

export default function JobDetailPanel({ job, onReview }: Props) {
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const script = useMemo(() => String(job?.state?.script ?? ""), [job?.state]);
  const clips = useMemo(() => asStringArray(job?.state?.clips_urls), [job?.state]);
  const images = useMemo(() => asStringArray(job?.state?.images_urls), [job?.state]);
  const finalVideo = useMemo(() => String(job?.state?.final_video_url ?? ""), [job?.state]);
  const waitingReview = job?.status === "waiting_review";

  if (!job) {
    return (
      <section className="panel detailPanel">
        <p className="empty">Pick a job to inspect script, assets, and final video.</p>
      </section>
    );
  }

  const handleReview = async (decision: ReviewDecision) => {
    setSubmitting(true);
    try {
      await onReview(job.job_id, decision, notes);
      setNotes("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="panel detailPanel">
      <header className="panelHeader">
        <h2>{job.topic}</h2>
        <span>{job.status}</span>
      </header>

      <div className="detailGrid">
        <article className="card">
          <h3>Script</h3>
          <p>{script || "Script is not ready yet."}</p>
        </article>

        <article className="card">
          <h3>Final Video</h3>
          {finalVideo ? (
            <video className="video" controls src={mediaUrl(finalVideo)} />
          ) : (
            <p>Video will appear after assembly.</p>
          )}
        </article>
      </div>

      <div className="detailGrid assets">
        <article className="card">
          <h3>Clips ({clips.length})</h3>
          <div className="mediaList">
            {clips.map((clip) => (
              <video key={clip} controls src={mediaUrl(clip)} />
            ))}
          </div>
        </article>

        <article className="card">
          <h3>Images ({images.length})</h3>
          <div className="mediaList">
            {images.map((image) => (
              <img key={image} src={mediaUrl(image)} alt="asset" />
            ))}
          </div>
        </article>
      </div>

      {waitingReview ? (
        <article className="reviewBox">
          <h3>Human Review</h3>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="revision notes..."
          />
          <div className="reviewActions">
            <button disabled={submitting} onClick={() => handleReview("approved")}>
              Approve
            </button>
            <button disabled={submitting} onClick={() => handleReview("needs_script_revision")}>
              Script Revision
            </button>
            <button disabled={submitting} onClick={() => handleReview("find_more_assets")}>
              Find More Assets
            </button>
            <button disabled={submitting} onClick={() => handleReview("reassemble")}>
              Reassemble
            </button>
          </div>
        </article>
      ) : null}
    </section>
  );
}
