import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Field, ListField, Repeater } from "../components/fields";
import PhotoUpload from "../components/PhotoUpload";
import UploadResume from "../components/UploadResume";
import { blank, emptyProfile } from "../profile";

export default function Editor() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [photoUrl, setPhotoUrl] = useState(null);
  const [correct, setCorrect] = useState(true);
  const [draftNotice, setDraftNotice] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: "", text: "" });

  useEffect(() => {
    api("/resume")
      .then((r) => { setProfile({ ...emptyProfile(), ...r.profile }); setPhotoUrl(r.photo_url); })
      .catch((err) => {
        if (err.status === 404) setProfile(emptyProfile());
        else setMessage({ type: "error", text: err.message });
      });
  }, []);

  if (!profile) return message.text ? <p className="error">{message.text}</p> : <p className="muted">Loading…</p>;

  const set = (key) => (value) => setProfile((p) => ({ ...p, [key]: value }));
  const setBasic = (key) => (value) => setProfile((p) => ({ ...p, basics: { ...p.basics, [key]: value } }));

  function applyDraft(draft) {
    setProfile({ ...emptyProfile(), ...draft });
    setDraftNotice(true);
  }

  // Single CTA: save, then return to the dashboard. The grammar pass (if enabled) runs in the
  // background and lands in the saved resume; on failure we stay here so no edits are lost.
  async function save() {
    setSaving(true);
    setMessage({ type: "", text: "" });
    try {
      await api("/resume", { method: "PUT", json: { profile, correct_text: correct } });
      navigate("/");
    } catch (err) {
      setMessage({ type: "error", text: err.message });
      setSaving(false);
    }
  }

  return (
    <div className="stack">
      <UploadResume onDraft={applyDraft} />
      {draftNotice && (
        <p className="info banner">Autofilled from your file. Check every section, then click Save.</p>
      )}

      <PhotoUpload photoUrl={photoUrl} onUploaded={setPhotoUrl} />

      <section className="card">
        <h2>Basics</h2>
        <div className="grid">
          <Field label="Full name" value={profile.basics.full_name} onChange={setBasic("full_name")} />
          <Field label="Headline" value={profile.basics.headline} onChange={setBasic("headline")}
                 placeholder="e.g. Backend Engineer" />
          <Field label="Email" type="email" value={profile.basics.email} onChange={setBasic("email")} />
          <Field label="Phone" value={profile.basics.phone} onChange={setBasic("phone")} />
          <Field label="Location" value={profile.basics.location} onChange={setBasic("location")} />
        </div>
      </section>

      <section className="card">
        <h2>Summary</h2>
        <Field label="" textarea value={profile.summary} onChange={set("summary")} />
      </section>

      <Repeater title="Experience" items={profile.experience} onChange={set("experience")}
        makeBlank={blank.experience} render={(e, up) => (
          <>
            <Field label="Job title" value={e.title} onChange={(v) => up({ title: v })} />
            <Field label="Company" value={e.company} onChange={(v) => up({ company: v })} />
            <Field label="Location" value={e.location} onChange={(v) => up({ location: v })} />
            <Field label="Start" value={e.start} onChange={(v) => up({ start: v })} placeholder="Jan 2022" />
            <Field label="End" value={e.end} onChange={(v) => up({ end: v })} placeholder="Present" />
            <div className="full">
              <ListField label="Highlights" textarea separator={"\n"} value={e.bullets}
                         onChange={(v) => up({ bullets: v })} hint="One bullet per line" />
            </div>
          </>
        )} />

      <Repeater title="Projects" items={profile.projects} onChange={set("projects")}
        makeBlank={blank.projects} render={(pr, up) => (
          <>
            <Field label="Name" value={pr.name} onChange={(v) => up({ name: v })} />
            <Field label="URL" value={pr.url} onChange={(v) => up({ url: v })} />
            <div className="full">
              <Field label="Description" textarea value={pr.description} onChange={(v) => up({ description: v })} />
            </div>
            <div className="full">
              <ListField label="Technologies" value={pr.tech} onChange={(v) => up({ tech: v })}
                         hint="Comma-separated" />
            </div>
          </>
        )} />

      <Repeater title="Education" items={profile.education} onChange={set("education")}
        makeBlank={blank.education} render={(ed, up) => (
          <>
            <Field label="Institution" value={ed.institution} onChange={(v) => up({ institution: v })} />
            <Field label="Degree" value={ed.degree} onChange={(v) => up({ degree: v })} />
            <Field label="Field of study" value={ed.field} onChange={(v) => up({ field: v })} />
            <Field label="Grade" value={ed.grade} onChange={(v) => up({ grade: v })} />
            <Field label="Start" value={ed.start} onChange={(v) => up({ start: v })} />
            <Field label="End" value={ed.end} onChange={(v) => up({ end: v })} />
            <div className="full">
              <Field label="Details" textarea value={ed.details} onChange={(v) => up({ details: v })} />
            </div>
          </>
        )} />

      <section className="card">
        <h2>Skills</h2>
        <ListField label="" value={profile.skills} onChange={set("skills")} hint="Comma-separated" />
      </section>

      <Repeater title="Links" items={profile.links} onChange={set("links")}
        makeBlank={blank.links} render={(l, up) => (
          <>
            <Field label="Label" value={l.label} onChange={(v) => up({ label: v })} placeholder="GitHub" />
            <Field label="URL" value={l.url} onChange={(v) => up({ url: v })} />
          </>
        )} />

      <div className="card sticky-save row between wrap">
        <label className="row gap inline">
          <input type="checkbox" checked={correct} onChange={(e) => setCorrect(e.target.checked)} />
          Fix spelling &amp; grammar (never rewrites content)
        </label>
        <div className="row gap">
          {message.text && <span className={message.type}>{message.text}</span>}
          <button className="primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
        </div>
      </div>
    </div>
  );
}
