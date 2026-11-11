import { useRef, useState } from "react";
import { ApiError, ask } from "./api";
import type { AskResult, Jurisdiction } from "./types";
import { T } from "./strings";
import Topbar from "./components/Topbar";
import Header from "./components/Header";
import Footer from "./components/Footer";
import AskPanel from "./components/AskPanel";
import ResultView from "./components/ResultView";
import LetterDialog from "./components/LetterDialog";
import Bi from "./components/Bi";
import { HowItWorks, TopicCards, TrustStrip } from "./components/Sections";

export default function App() {
  const [question, setQuestion] = useState("");
  const [jurisdiction, setJurisdiction] = useState<"" | Jurisdiction>("");
  const [result, setResult] = useState<AskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rateLimited, setRateLimited] = useState(false);
  const [letterOpen, setLetterOpen] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);

  async function run(q: string, j: "" | Jurisdiction) {
    if (loading || !q.trim()) return;
    setLoading(true);
    setError("");
    setRateLimited(false);
    try {
      setResult(await ask({ question: q, jurisdiction: j || null }));
      requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (e) {
      setResult(null);
      // Too many requests from this client is a different message from "the service failed": wait, do not retry at once.
      if (e instanceof ApiError && e.code === "rate_limited") setRateLimited(true);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <a className="skip" href="#ask">{T.askThis}</a>
      <Topbar />
      <section className="hero">
        <div className="hero-inner">
          <Header />
          <AskPanel question={question} setQuestion={setQuestion} jurisdiction={jurisdiction}
            setJurisdiction={setJurisdiction} loading={loading} onSubmit={() => run(question, jurisdiction)} />
        </div>
      </section>
      <div className="wrap">
        <main ref={resultRef} aria-live="polite" className="results">
          {rateLimited && (
            <div className="hq-notice caution" role="alert">
              <Bi ur={T.rateLimited} en={T.rateLimitedEn} />
            </div>
          )}
          {error && (
            <div className="hq-notice danger" role="alert">
              <p lang="ur" dir="rtl" className="hq-ul" style={{ margin: "0 0 8px" }}>{T.errorTitle}</p>
              <p style={{ margin: "0 0 8px" }}>{error}</p>
              <button type="button" className="hq-btn ghost" onClick={() => run(question, jurisdiction)}><Bi inline ur={T.retry} en={T.retryEn} /></button>
            </div>
          )}
          {result && !loading && (
            <ResultView r={result}
              onProvince={(j) => { setJurisdiction(j); run(question, j); }}
              onLetter={() => setLetterOpen(true)}
              onRetry={() => run(question, jurisdiction)} />
          )}
        </main>
        <TopicCards disabled={loading} onPick={(q) => { setQuestion(q); run(q, jurisdiction); }} />
        <HowItWorks />
        <TrustStrip />
        {result && result.letter_type && (
          <LetterDialog r={result} question={question} open={letterOpen} onClose={() => setLetterOpen(false)} />
        )}
        <Footer />
      </div>
    </div>
  );
}
