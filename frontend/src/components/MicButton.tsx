import { useEffect, useRef, useState } from "react";
import { T } from "../strings";
import { En, usePrefs, type MicLang } from "../prefs";
import { IconMic } from "./Icons";

type SR = {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: ((e: any) => void) | null; onerror: ((e: any) => void) | null; onend: (() => void) | null;
  start(): void; stop(): void;
};

function recognitionCtor(): (new () => SR) | null {
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

/** Big hero microphone. Fills the question with an Urdu transcript; hidden when speech recognition is unavailable. */
export default function MicButton({ onText, onHint }: { onText: (t: string) => void; onHint: (h: string) => void }) {
  const [listening, setListening] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [heard, setHeard] = useState("");
  const { micLang, setMicLang } = usePrefs();
  const ref = useRef<SR | null>(null);
  const activeRef = useRef(false);
  const restartRef = useRef<number | null>(null);
  const lastText = useRef("");
  const supported = recognitionCtor() !== null;

  useEffect(() => () => {
    activeRef.current = false;
    if (restartRef.current !== null) window.clearTimeout(restartRef.current);
    ref.current?.stop();
  }, []);
  useEffect(() => { if (!supported) onHint(T.micUnsupported); }, [supported, onHint]);
  if (!supported || blocked) return null;

  function toggle() {
    if (listening) {
      activeRef.current = false;
      if (restartRef.current !== null) window.clearTimeout(restartRef.current);
      ref.current?.stop();
      setListening(false);
      return;
    }
    const Ctor = recognitionCtor()!;
    const rec = new Ctor();
    rec.lang = micLang; // ur-PK hears Urdu and Urdu-English mixes best; en-IN is for speakers who mostly use English words
    rec.interimResults = true;
    rec.continuous = true;
    rec.onresult = (e: any) => {
      let text = "";
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
      lastText.current = text;
      onText(text);
    };
    rec.onerror = (e: any) => {
      // Silence ("no-speech") and a manual stop ("aborted") are normal: the session restarts in onend. Anything else
      // (permission denied, network, no microphone) is fatal: stop the restart loop, or it would retry every 120 ms forever.
      if (e.error === "no-speech" || e.error === "aborted") return;
      activeRef.current = false;
      if (restartRef.current !== null) window.clearTimeout(restartRef.current);
      setListening(false);
      if (e.error === "not-allowed" || e.error === "service-not-allowed") { setBlocked(true); onHint(T.micDenied); }
      else onHint(T.micFailed);
    };
    rec.onend = () => {
      // Chrome ends recognition after a brief silence even with continuous=true.
      // Keep the user session alive until they press the microphone button again.
      if (activeRef.current) {
        restartRef.current = window.setTimeout(() => {
          try { rec.start(); } catch { /* already restarting */ }
        }, 120);
      } else {
        setListening(false);
        setHeard(lastText.current.trim());
      }
    };
    ref.current = rec;
    lastText.current = "";
    activeRef.current = true;
    setHeard("");
    onHint("");
    setListening(true);
    try {
      rec.start();
    } catch {
      activeRef.current = false;
      setListening(false);
      onHint(T.micFailed);
    }
  }

  return (
    <div className="mic-wrap">
      <button type="button" className={listening ? "hq-mic hq-mic-hero is-listening" : "hq-mic hq-mic-hero"}
        aria-pressed={listening} aria-label={listening ? T.stop : T.speak} onClick={toggle}>
        <IconMic size={44} />
      </button>
      <span className="mic-label" lang="ur" dir="rtl" aria-live="polite">{listening ? T.micListening : T.micPrompt}</span>
      <div className="mic-lang" role="radiogroup" aria-label={`${T.micLangTitle} / ${T.micLangTitleEn}`}>
        {([["ur-PK", T.micLangUr], ["en-IN", T.micLangEn]] as [MicLang, string][]).map(([value, label]) => (
          <button key={value} type="button" role="radio" aria-checked={micLang === value} disabled={listening}
            className={micLang === value ? "mic-lang-btn is-on" : "mic-lang-btn"} onClick={() => setMicLang(value)}>
            <span lang={value === "ur-PK" ? "ur" : "en"} dir={value === "ur-PK" ? "rtl" : "ltr"}>{label}</span>
          </button>
        ))}
      </div>
      <p className="hq-hint mic-lang-hint"><span lang="ur" dir="rtl">{T.micLangHint}</span> <En>{T.micLangHintEn}</En></p>
      {heard && !listening && (
        <div className="mic-heard" role="status">
          <p lang="ur" dir="rtl"><b>{T.heardLabel}</b> «{heard}»</p>
          <p lang="ur" dir="rtl">{T.heardCheck}</p>
          <En as="p">{T.heardCheckEn}</En>
        </div>
      )}
    </div>
  );
}
