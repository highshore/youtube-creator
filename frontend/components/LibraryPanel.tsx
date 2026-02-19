"use client";

import { mediaUrl } from "../lib/api";
import type { LibraryItem } from "../types";

type Props = {
  items: LibraryItem[];
};

export default function LibraryPanel({ items }: Props) {
  return (
    <section className="panel">
      <header className="panelHeader">
        <h2>Library</h2>
        <span>{items.length}</span>
      </header>
      <div className="libraryList">
        {items.map((item) => (
          <article key={`${item.metadata_path ?? ""}${item.final_video ?? ""}`} className="libraryItem">
            <h4>{item.topic || "Untitled"}</h4>
            <p>{item.script || "No script."}</p>
            {item.final_video_url ? (
              <video controls src={mediaUrl(item.final_video_url)} />
            ) : (
              <small>No video file</small>
            )}
          </article>
        ))}
        {items.length === 0 ? <p className="empty">No completed outputs yet.</p> : null}
      </div>
    </section>
  );
}
