import { useEffect, useState } from "react";
import type { Jurisdiction } from "../types";
import { EXAMPLES, PROVINCES, T } from "../strings";
import { En } from "../prefs";
import Bi from "./Bi";
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
    <form id="ask" className="ask-card" onSubmit={(e) => { e.preventDefault(); if (question.trim() && !loading) onSubmit(); }}>
      <MicButton onText={setQuestion} onHint={setHint} />
      <div className="ask-or" aria-hidden="true"><span lang="ur">{T.orType}</span></div>
      <label className="hq-label">
        <span className="sr-only">{T.placeholder}</span>
        <textarea id="question" className="hq-field" lang="ur" dir="rtl" value={question} maxLength={2000}
          placeholder={T.placeholder} onChange={(e) => setQuestion(e.target.value)} />
      </label>
      <div className="hq-chips" role="group" aria-label="مثال کے سوالات / Example questions">
        {EXAMPLES.map((q) => (
          <button type="button" key={q} className="hq-chip-btn" lang="ur" dir="rtl" onClick={() => setQuestion(q)}>{q}</button>
        ))}
      </div>
      <div className="ask-row">
        <label className="hq-label ask-province">
          <span lang="ur" dir="rtl">{T.province}</span>
          <select className="hq-input" value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value as "" | Jurisdiction)}>
            <option value="">نہیں معلوم / Not sure</option>
            {PROVINCES.map((p) => <option key={p.value} value={p.value}>{p.ur} / {p.en}</option>)}
          </select>
        </label>
        <button type="submit" className="hq-btn ask-submit" disabled={loading || !question.trim()}>
          <Bi inline ur={T.ask} en={T.askEn} />
        </button>
      </div>
      <p className="hq-hint"><span lang="ur" dir="rtl">{T.privacy}</span> <En>{T.privacyEn}</En></p>
      {hint && <p className="hq-hint" role="status" lang="ur" dir="rtl">{hint}</p>}
      <div aria-live="polite">
        {loading && (
          <p className="hq-hint ask-loading">
            <span className="hq-spinner" aria-hidden="true" /> <span lang="ur" dir="rtl">{slow ? T.slow : T.loading}</span>{" "}
            <En>{slow ? T.slowEn : T.loadingEn}</En>
          </p>
        )}
      </div>
    </form>
  );
}
