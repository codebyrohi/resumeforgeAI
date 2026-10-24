import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import ExportPanel from "../components/ExportPanel";

export default function Dashboard() {
  const [resume, setResume] = useState(undefined); // undefined = loading, null = none yet
  const [error, setError] = useState("");

  useEffect(() => {
    api("/resume")
      .then(setResume)
      .catch((err) => (err.status === 404 ? setResume(null) : setError(err.message)));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (resume === undefined) return <p className="muted">Loading…</p>;

  if (resume === null) {
    return (
      <div className="card center">
        <h1>Let's build your resume</h1>
        <p className="muted">Upload an existing resume to autofill, or start from a blank form.</p>
        <Link to="/editor" className="button primary">Start editing</Link>
      </div>
    );
  }

  const { basics } = resume.profile;
  return (
    <div className="stack">
      <div className="card row gap wrap">
        {resume.photo_url ? <img className="avatar" src={resume.photo_url} alt="" />
                          : <div className="avatar placeholder">No photo</div>}
        <div className="grow">
          <h1>{basics.full_name || "Untitled resume"}</h1>
          {basics.headline && <p>{basics.headline}</p>}
          <p className="muted">Last updated {new Date(resume.updated_at + "Z").toLocaleString()}</p>
          {resume.public_url && (
            <p>Public page: <a href={resume.public_url} target="_blank" rel="noreferrer">{resume.public_url}</a></p>
          )}
        </div>
        <Link to="/editor" className="button">Edit resume</Link>
      </div>
      <ExportPanel />
      <p className="muted small">
        Exports render your latest saved version. Re-publish the cinematic page after edits to update it.
      </p>
    </div>
  );
}
