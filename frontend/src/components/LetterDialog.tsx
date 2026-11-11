import { useEffect, useRef, useState } from "react";
import { downloadLetter } from "../api";
import type { AskResponse } from "../types";
import { T } from "../strings";
import Bi from "./Bi";

/** Bilingual field label; required fields get a visible marker in both languages. */
function Lbl({ k, req = false }: { k: keyof typeof T.f; req?: boolean }) {
  return <Bi ur={T.f[k].ur + (req ? ` (${T.required})` : "")} en={T.f[k].en + (req ? " *" : "")} />;
}

export default function LetterDialog({ r, question, open, onClose }: { r: AskResponse; question: string; open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [f, setF] = useState({ name: "", address: "", cnic: "", respondent: "", details: "", city: "", facts: question, relief: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) { setF((x) => ({ ...x, facts: x.facts || question })); setMsg(""); setErr(""); d.showModal(); }
    if (!open && d.open) d.close();
  }, [open, question]);

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const factsOk = f.facts.trim().length >= 5 && f.facts.length <= 6000;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!r.letter_type || !f.name.trim() || !factsOk) return;
    setBusy(true); setErr(""); setMsg("");
    try {
      await downloadLetter({
        letter_type: r.letter_type,
        complainant_name: f.name.trim(),
        complainant_address: f.address || undefined,
        complainant_cnic: f.cnic || undefined,
        respondent_name: f.respondent || undefined,
        respondent_details: f.details || undefined,
        city: f.city || undefined,
        facts: f.facts.trim(),
        relief: f.relief || undefined,
        legal_basis: r.citations.map((c) => `${c.act}, s.${c.section}`),
      });
      setMsg("ok");
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <dialog ref={ref} className="hq hq-dialog" aria-labelledby="letter-title" onClose={onClose}>
      <form className="hq-stack" onSubmit={submit}>
        <h2 id="letter-title" style={{ margin: 0 }}><Bi ur={T.letter} en={T.letterEn} /></h2>
        <label className="hq-label"><Lbl k="name" req /><input className="hq-input" required value={f.name} onChange={set("name")} autoComplete="name" /></label>
        <label className="hq-label"><Lbl k="address" /><input className="hq-input" value={f.address} onChange={set("address")} autoComplete="street-address" /></label>
        <label className="hq-label"><Lbl k="cnic" /><input className="hq-input" inputMode="numeric" dir="ltr" value={f.cnic} onChange={set("cnic")} /></label>
        <label className="hq-label"><Lbl k="respondent" /><input className="hq-input" value={f.respondent} onChange={set("respondent")} /></label>
        <label className="hq-label"><Lbl k="details" /><input className="hq-input" value={f.details} onChange={set("details")} /></label>
        <label className="hq-label"><Lbl k="city" /><input className="hq-input" value={f.city} onChange={set("city")} /></label>
        <label className="hq-label"><Lbl k="facts" req />
          <textarea className="hq-input" dir="auto" required minLength={5} maxLength={6000} value={f.facts} onChange={set("facts")} />
        </label>
        <label className="hq-label"><Lbl k="relief" /><textarea className="hq-input" dir="auto" value={f.relief} onChange={set("relief")} /></label>
        <div className="hq-hint">
          <Bi ur={T.legalBasisAdded} en={T.legalBasisAddedEn} />
          <p dir="ltr" lang="en" style={{ margin: "4px 0" }}>{r.citations.map((c) => `${c.act}, s.${c.section}`).join("; ")}</p>
          <p style={{ margin: 0 }}><span lang="ur" dir="rtl">{T.letterPrivacy}</span> {T.letterPrivacyEn}</p>
        </div>
        <div aria-live="polite">
          {msg && <p className="hq-notice caution"><Bi ur={T.downloaded} en={T.downloadedEn} /></p>}
          {err && <p className="hq-notice danger" role="alert">{err}</p>}
        </div>
        <div className="hq-actions">
          <button type="submit" className="hq-btn" disabled={busy || !f.name.trim() || !factsOk}>{busy ? "…" : <Bi inline ur={T.download} en={T.downloadEn} />}</button>
          <button type="button" className="hq-btn ghost" onClick={onClose}><Bi inline ur={T.close} en={T.closeEn} /></button>
        </div>
      </form>
    </dialog>
  );
}
