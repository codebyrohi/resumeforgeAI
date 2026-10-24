import { useState } from "react";
import { api, pollJob } from "../api";

const TYPES = {
  ats: { title: "ATS PDF", blurb: "Plain single-column PDF that ATS parsers can read.", action: "Generate PDF" },
  cinematic: { title: "Cinematic page", blurb: "Animated, shareable web page for human readers.", action: "Publish page" },
};

function ExportCard({ type, disabled }) {
  const [state, setState] = useState({ busy: false, job: null, error: "" });
  const meta = TYPES[type];

  async function run() {
    setState({ busy: true, job: null, error: "" });
    try {
      const started = await api("/resume/export", { method: "POST", json: { type } });
      const job = await pollJob(`/resume/export/${started.id}`);
      if (job.status === "failed") throw new Error(job.error || "Export failed");
      setState({ busy: false, job, error: "" });
    } catch (err) {
      setState({ busy: false, job: null, error: err.message });
    }
  }

  const link = state.job && (type === "ats" ? state.job.output_url : state.job.public_url);
  return (
    <div className="card">
      <h2>{meta.title}</h2>
      <p className="muted">{meta.blurb}</p>
      <button className="primary" onClick={run} disabled={disabled || state.busy}>
        {state.busy ? "Rendering…" : meta.action}
      </button>
      {link && (
        <p className="info">
          {type === "ats" ? "Ready: " : "Live at "}
          <a href={link} target="_blank" rel="noreferrer">{type === "ats" ? "Download PDF" : link}</a>
          {type === "cinematic" && (
            <button className="link" onClick={() => navigator.clipboard.writeText(link)}>Copy link</button>
          )}
        </p>
      )}
      {state.error && <p className="error">{state.error}</p>}
    </div>
  );
}

export default function ExportPanel({ disabled }) {
  return (
    <div className="two-col">
      <ExportCard type="ats" disabled={disabled} />
      <ExportCard type="cinematic" disabled={disabled} />
    </div>
  );
}
