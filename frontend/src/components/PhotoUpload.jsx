import { useEffect, useState } from "react";
import { api } from "../api";

const PREVIEW = 160;

// Square crop picker: zoom + horizontal/vertical position. Sends the crop box in the
// image's natural pixels; the server does the actual crop/resize.
export default function PhotoUpload({ photoUrl, onUploaded }) {
  const [file, setFile] = useState(null);
  const [src, setSrc] = useState("");
  const [dims, setDims] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [ox, setOx] = useState(0.5);
  const [oy, setOy] = useState(0.5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => () => src && URL.revokeObjectURL(src), [src]);

  function pick(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setError("");
    setFile(f);
    setZoom(1); setOx(0.5); setOy(0.5); setDims(null);
    const url = URL.createObjectURL(f);
    setSrc(url);
    const img = new Image();
    img.onload = () => setDims({ w: img.naturalWidth, h: img.naturalHeight });
    img.src = url;
  }

  const crop = dims && (() => {
    const size = Math.floor(Math.min(dims.w, dims.h) / zoom);
    return { size, x: Math.round((dims.w - size) * ox), y: Math.round((dims.h - size) * oy) };
  })();

  async function upload() {
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("crop_x", crop.x);
      form.append("crop_y", crop.y);
      form.append("crop_size", crop.size);
      const resume = await api("/resume/photo", { method: "POST", form });
      onUploaded(resume.photo_url);
      setFile(null);
      setSrc("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const scale = crop ? PREVIEW / crop.size : 1;
  return (
    <section className="card">
      <h2>Profile photo</h2>
      <p className="muted">Shown on your cinematic page only. The ATS PDF has no photo.</p>
      <div className="row gap wrap">
        {src && crop ? (
          <div className="avatar" style={{
            width: PREVIEW,
            height: PREVIEW,
            backgroundImage: `url(${src})`,
            backgroundSize: `${dims.w * scale}px ${dims.h * scale}px`,
            backgroundPosition: `${-crop.x * scale}px ${-crop.y * scale}px`,
          }} />
        ) : photoUrl ? (
          <img className="avatar" src={photoUrl} alt="Current profile" />
        ) : (
          <div className="avatar placeholder">No photo</div>
        )}
        <div className="stack grow">
          <input type="file" accept="image/jpeg,image/png,image/webp" onChange={pick} />
          {crop && (
            <>
              <label>Zoom<input type="range" min="1" max="3" step="0.05" value={zoom} onChange={(e) => setZoom(+e.target.value)} /></label>
              <label>Horizontal<input type="range" min="0" max="1" step="0.01" value={ox} onChange={(e) => setOx(+e.target.value)} /></label>
              <label>Vertical<input type="range" min="0" max="1" step="0.01" value={oy} onChange={(e) => setOy(+e.target.value)} /></label>
              <button className="primary" onClick={upload} disabled={busy}>{busy ? "Uploading…" : "Save photo"}</button>
            </>
          )}
          {error && <p className="error">{error}</p>}
        </div>
      </div>
    </section>
  );
}
