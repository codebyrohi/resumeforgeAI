import { useState } from "react";
import { api, pollJob } from "../api";

// Upload PDF/DOCX -> backend parses with the LLM in the background -> we poll for the draft.
export default function UploadResume({ onDraft }) {
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError("");
    setBusy(true);
    try {
      setStatus("Uploading…");
      const form = new FormData();
      form.append("file", file);
      const upload = await api("/resume/upload", { method: "POST", form });
      setStatus("Reading your resume (this can take a few seconds)…");
      const result = await pollJob(`/resume/upload/${upload.id}`);
      if (result.status === "failed") throw new Error(result.error || "Parsing failed");
      onDraft(result.parsed_json);
      setStatus("Draft loaded below. Review it, then click Save.");
    } catch (err) {
      setStatus("");
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Autofill from an existing resume</h2>
      <p className="muted">PDF or DOCX, up to 5 MB. Nothing is saved until you review and click Save.</p>
      <input type="file" accept=".pdf,.docx" onChange={handleFile} disabled={busy} />
      {status && <p className="info">{status}</p>}
      {error && <p className="error">{error}</p>}
    </section>
  );
}
