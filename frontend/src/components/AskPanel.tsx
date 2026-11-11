import { useEffect, useState } from "react";
import type { Jurisdiction } from "../types";
import { EXAMPLES, PROVINCES, T } from "../strings";
import MicButton from "./MicButton";

export default function AskPanel({
  question, setQuestion, jurisdiction, setJurisdiction, loading, onSubmit,
}: {
  question: string; setQuestion: (q: string) => void;
  jurisdiction: "" | Jurisdiction; setJurisdiction: (j: "" | Jurisdiction) => void;
  loading: boolean; onSubmit: () => void;
}) {
  const [hint, setHint] = useState("");
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!loading) { setSlow(false); return; }
    const t = setTimeout(() => setSlow(true), 15000);
    return () => clearTimeout(t);
  }, [loading]);

  return (
    <form className="hq-card wide" onSubmit={(e) => { e.preventDefault(); if (question.trim() && !loading) onSubmit(); }}>
      <label className="hq-label">
        <span className="hq-ul">{T.placeholder}</span>
        <textarea className="hq-field" lang="ur" dir="rtl" value={question} maxLength={2000}
          onChange={(e) => setQuestion(e.target.value)} />
      </label>
      <div className="hq-chips" role="group" aria-label="Example questions">
        {EXAMPLES.map((q) => (
          <button type="button" key={q} className="hq-chip-btn" lang="ur" dir="rtl" onClick={() => setQuestion(q)}>{q}</button>
        ))}
      </div>
      <label className="hq-label">
        <span>{T.province}</span>
        <select className="hq-input" value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value as "" | Jurisdiction)}>
          <option value="">Not sure / نہیں معلوم</option>
          {PROVINCES.map((p) => <option key={p.value} value={p.value}>{p.ur} / {p.en}</option>)}
        </select>
      </label>
      <div className="hq-actions">
        <MicButton onText={setQuestion} onHint={setHint} />
        <button type="submit" className="hq-btn grow" disabled={loading || !question.trim()}>
          <span className="hq-ul">{T.ask}</span> <span>{T.askEn}</span>
        </button>
      </div>
      {hint && <p className="hq-hint" role="status">{hint}</p>}
      <div aria-live="polite">
        {loading && (
          <p className="hq-hint">
            <span className="hq-spinner" aria-hidden="true" /> <span lang="ur" dir="rtl">{slow ? T.slow : T.loading}</span>{" "}
            <span>{slow ? T.slowEn : T.loadingEn}</span>
          </p>
        )}
      </div>
    </form>
  );
}
