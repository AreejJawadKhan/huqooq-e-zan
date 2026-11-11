import { useEffect, useRef, useState } from "react";
import { T } from "../strings";
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
  const ref = useRef<SR | null>(null);
  const supported = recognitionCtor() !== null;

  useEffect(() => () => ref.current?.stop(), []);
  useEffect(() => { if (!supported) onHint(T.micUnsupported); }, [supported, onHint]);
  if (!supported || blocked) return null;

  function toggle() {
    if (listening) { ref.current?.stop(); return; }
    const Ctor = recognitionCtor()!;
    const rec = new Ctor();
    rec.lang = "ur-PK";
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (e: any) => {
      let text = "";
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
      onText(text);
    };
    rec.onerror = (e: any) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") { setBlocked(true); onHint(T.micDenied); }
      else onHint(T.micFailed);
    };
    rec.onend = () => setListening(false);
    ref.current = rec;
    onHint("");
    setListening(true);
    rec.start();
  }

  return (
    <div className="mic-wrap">
      <button type="button" className={listening ? "hq-mic hq-mic-hero is-listening" : "hq-mic hq-mic-hero"}
        aria-pressed={listening} aria-label={listening ? T.stop : T.speak} onClick={toggle}>
        <IconMic size={44} />
      </button>
      <span className="mic-label" lang="ur" dir="rtl" aria-live="polite">{listening ? T.micListening : T.micPrompt}</span>
    </div>
  );
}
