import { useRef, useState } from "react";
import { ask, downloadLetter } from "./api";
import type { AskResponse, Jurisdiction } from "./types";

// Starter UI: it exercises every field the API returns so you can see the whole contract working.
// Replace freely. All the logic you need is in api.ts and types.ts.

const PROVINCES: { value: "" | Jurisdiction; label: string }[] = [
  { value: "", label: "Province (optional)" },
  { value: "punjab", label: "Punjab" },
  { value: "sindh", label: "Sindh" },
  { value: "kp", label: "Khyber Pakhtunkhwa" },
  { value: "balochistan", label: "Balochistan" },
  { value: "ict", label: "Islamabad" },
];

export default function App() {
  const [question, setQuestion] = useState("");
  const [jurisdiction, setJurisdiction] = useState<"" | Jurisdiction>("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [listening, setListening] = useState(false);
  const recRef = useRef<any>(null);

  // Voice input via the browser Web Speech API. Urdu support varies by browser/device: test early,
  // and keep typing as the fallback.
  function toggleMic() {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      setError("Voice input is not supported in this browser. Please type your question.");
      return;
    }
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const rec = new SR();
    rec.lang = "ur-PK";
    rec.interimResults = false;
    rec.onresult = (e: any) => setQuestion(e.results[0][0].transcript);
    rec.onerror = () => setError("Could not hear that. Please try again or type.");
    rec.onend = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError("");
    try {
      setResult(await ask({ question, jurisdiction: jurisdiction || null }));
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function draftLetter() {
    if (!result?.letter_type) return;
    const name = window.prompt("Your full name for the letter?");
    if (!name) return;
    await downloadLetter({
      letter_type: result.letter_type,
      complainant_name: name,
      facts: question,
      legal_basis: result.citations.map((c) => `${c.act}, s.${c.section}`),
    });
  }

  return (
    <main className="wrap">
      <h1>
        Huqooq <span className="ur">حقوق</span>
      </h1>
      <p className="sub">Know your rights: workplace harassment, minimum wage, women's property.</p>

      <form onSubmit={submit}>
        <textarea
          dir="auto"
          rows={4}
          placeholder="Ask in Urdu, Roman Urdu or English"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="row">
          <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value as "" | Jurisdiction)}>
            {PROVINCES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          <button type="button" onClick={toggleMic}>
            {listening ? "Stop" : "🎤 Speak"}
          </button>
          <button type="submit" disabled={loading}>
            {loading ? "Thinking…" : "Ask"}
          </button>
        </div>
      </form>

      {error && <div className="box error">{error}</div>}

      {result && (
        <section>
          {result.status === "danger" && <div className="box danger">{result.answer_ur}<br />{result.answer_en}</div>}

          {result.status !== "danger" && (
            <div className="box">
              <p className="ur-answer" dir="rtl" lang="ur">{result.answer_ur}</p>
              <p className="en-answer">{result.answer_en}</p>
              {result.needs_province && <p className="note">Tell us your province for a precise answer.</p>}
            </div>
          )}

          {result.wage && (
            <div className="box">
              <strong>
                {result.detected.jurisdiction}: Rs{result.wage.monthly_pkr?.toLocaleString()} / month
              </strong>{" "}
              <small>
                as of {result.wage.as_of}
                {!result.wage.verified && " · not yet verified against the official notification"}
              </small>
            </div>
          )}

          {result.caveats.map((c, i) => (
            <div key={i} className="box caveat">
              <div>{c.en}</div>
              <div dir="rtl" lang="ur">{c.ur}</div>
            </div>
          ))}

          {result.citations.length > 0 && (
            <div className="box">
              <h3>Legal basis</h3>
              {result.citations.map((c) => (
                <details key={c.chunk_id}>
                  <summary>
                    {c.act}, s.{c.section} {c.heading && `(${c.heading})`}
                  </summary>
                  <p>{c.excerpt}</p>
                  {c.source_url && (
                    <a href={c.source_url} target="_blank" rel="noreferrer">
                      Source
                    </a>
                  )}
                </details>
              ))}
            </div>
          )}

          {result.where_to_go.length > 0 && (
            <div className="box">
              <h3>Where to go</h3>
              <ul>
                {result.where_to_go.map((r) => (
                  <li key={r.name}>
                    <strong>{r.name}</strong> {r.number && <a href={`tel:${r.number.replace(/\s/g, "")}`}>{r.number}</a>}
                    <div className="note">{r.note}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.letter_type && <button onClick={draftLetter}>Draft my complaint letter (.docx)</button>}

          <p className="disclaimer">{result.disclaimer_en}</p>
          <p className="disclaimer" dir="rtl" lang="ur">{result.disclaimer_ur}</p>
        </section>
      )}
    </main>
  );
}
