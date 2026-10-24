import { useEffect, useState } from "react";

export function Field({ label, value, onChange, textarea, ...rest }) {
  const Tag = textarea ? "textarea" : "input";
  return (
    <label>
      {label}
      <Tag value={value ?? ""} onChange={(e) => onChange(e.target.value)} rows={textarea ? 4 : undefined} {...rest} />
    </label>
  );
}

const sameList = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

// Edits a string[] as raw text (comma- or newline-separated). Keeps its own text so typing a
// trailing separator doesn't get normalised away mid-keystroke, and re-syncs whenever the
// value changes from outside (autofill, reordering or removing items).
export function ListField({ label, value, onChange, separator = ",", textarea, hint }) {
  const joiner = separator === "\n" ? "\n" : ", ";
  const parse = (t) => t.split(separator).map((s) => s.trim()).filter(Boolean);
  const [text, setText] = useState((value || []).join(joiner));
  useEffect(() => {
    if (!sameList(parse(text), value || [])) setText((value || []).join(joiner));
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  const Tag = textarea ? "textarea" : "input";
  return (
    <label>
      {label}
      <Tag
        value={text}
        rows={textarea ? 4 : undefined}
        onChange={(e) => {
          setText(e.target.value);
          onChange(parse(e.target.value));
        }}
      />
      {hint && <small className="muted">{hint}</small>}
    </label>
  );
}

// A repeatable section (experience, education, ...): renders one card per item.
export function Repeater({ title, items, onChange, makeBlank, render }) {
  const update = (i, patch) => onChange(items.map((it, j) => (j === i ? { ...it, ...patch } : it)));
  const remove = (i) => onChange(items.filter((_, j) => j !== i));
  const move = (i, d) => {
    const next = [...items];
    const j = i + d;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };
  return (
    <section className="card">
      <div className="row between">
        <h2>{title}</h2>
        <button type="button" onClick={() => onChange([...items, makeBlank()])}>+ Add</button>
      </div>
      {items.length === 0 && <p className="muted">Nothing here yet.</p>}
      {items.map((item, i) => (
        <div key={i} className="repeat-item">
          <div className="grid">{render(item, (patch) => update(i, patch))}</div>
          <div className="row gap">
            <button type="button" onClick={() => move(i, -1)} disabled={i === 0}>↑</button>
            <button type="button" onClick={() => move(i, 1)} disabled={i === items.length - 1}>↓</button>
            <button type="button" className="danger" onClick={() => remove(i)}>Remove</button>
          </div>
        </div>
      ))}
    </section>
  );
}
