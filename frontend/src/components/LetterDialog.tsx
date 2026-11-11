import { useEffect, useRef, useState } from "react";
import { downloadLetter } from "../api";
import type { AskResponse } from "../types";
import { T } from "../strings";
import Bi from "./Bi";

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
      setMsg("Letter downloaded. Please check every detail before use.");
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
        <label className="hq-label">Your full name *<input className="hq-input" required value={f.name} onChange={set("name")} autoComplete="name" /></label>
        <label className="hq-label">Address<input className="hq-input" value={f.address} onChange={set("address")} autoComplete="street-address" /></label>
        <label className="hq-label">CNIC<input className="hq-input" inputMode="numeric" value={f.cnic} onChange={set("cnic")} /></label>
        <label className="hq-label">Other party's name<input className="hq-input" value={f.respondent} onChange={set("respondent")} /></label>
        <label className="hq-label">Other party's details (job title, workplace)<input className="hq-input" value={f.details} onChange={set("details")} /></label>
        <label className="hq-label">City<input className="hq-input" value={f.city} onChange={set("city")} /></label>
        <label className="hq-label">What happened * (5 to 6000 characters)
          <textarea className="hq-input" required minLength={5} maxLength={6000} value={f.facts} onChange={set("facts")} />
        </label>
        <label className="hq-label">What you want (relief)<textarea className="hq-input" value={f.relief} onChange={set("relief")} /></label>
        <p className="hq-hint">Legal basis added from the answer: {r.citations.map((c) => `${c.act}, s.${c.section}`).join("; ")}. Do not include details you are not comfortable sharing with the model provider.</p>
        <div aria-live="polite">
          {msg && <p className="hq-notice caution">{msg}</p>}
          {err && <p className="hq-notice danger" role="alert">{err}</p>}
        </div>
        <div className="hq-actions">
          <button type="submit" className="hq-btn" disabled={busy || !f.name.trim() || !factsOk}>{busy ? "…" : "Download .docx"}</button>
          <button type="button" className="hq-btn ghost" onClick={onClose}>Close</button>
        </div>
      </form>
    </dialog>
  );
}
