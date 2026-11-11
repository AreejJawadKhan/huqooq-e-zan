import { useState } from "react";
import { ask } from "./api";
import type { AskResponse, Jurisdiction } from "./types";
import { T } from "./strings";
import Bi from "./components/Bi";
import Header from "./components/Header";
import Footer from "./components/Footer";
import AskPanel from "./components/AskPanel";
import ResultView from "./components/ResultView";
import LetterDialog from "./components/LetterDialog";

export default function App() {
  const [question, setQuestion] = useState("");
  const [jurisdiction, setJurisdiction] = useState<"" | Jurisdiction>("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [letterOpen, setLetterOpen] = useState(false);

  async function run(j: "" | Jurisdiction) {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      setResult(await ask({ question, jurisdiction: j || null }));
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="hq app">
      <Header />
      <AskPanel question={question} setQuestion={setQuestion} jurisdiction={jurisdiction}
        setJurisdiction={setJurisdiction} loading={loading} onSubmit={() => run(jurisdiction)} />
      <main aria-live="polite">
        {error && (
          <div className="hq-notice danger" role="alert">
            <p style={{ margin: "0 0 8px" }}>{error}</p>
            <button type="button" className="hq-btn ghost" onClick={() => run(jurisdiction)}><Bi inline ur={T.retry} en={T.retryEn} /></button>
          </div>
        )}
        {result && !loading && (
          <ResultView r={result}
            onProvince={(j) => { setJurisdiction(j); run(j); }}
            onLetter={() => setLetterOpen(true)} />
        )}
      </main>
      {result && result.letter_type && (
        <LetterDialog r={result} question={question} open={letterOpen} onClose={() => setLetterOpen(false)} />
      )}
      <Footer />
    </div>
  );
}
