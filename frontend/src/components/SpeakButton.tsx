import { useEffect, useState } from "react";
import { T } from "../strings";
import Bi from "./Bi";

function urduVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  return window.speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith("ur")) ?? null;
}

/** Reads the Urdu answer aloud with the browser's Urdu voice. Hidden when the device has none. */
export default function SpeakButton({ text }: { text: string }) {
  const [available, setAvailable] = useState(() => urduVoice() !== null);
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const update = () => setAvailable(urduVoice() !== null);
    window.speechSynthesis.addEventListener("voiceschanged", update);
    update();
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", update);
      window.speechSynthesis.cancel();
    };
  }, []);

  if (!available) return null;

  function toggle() {
    const synth = window.speechSynthesis;
    if (speaking) { synth.cancel(); setSpeaking(false); return; }
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "ur-PK";
    u.voice = urduVoice();
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    setSpeaking(true);
    synth.speak(u);
  }

  return (
    <button type="button" className="hq-btn ghost speak-btn" aria-pressed={speaking} onClick={toggle}>
      <Bi inline ur={speaking ? T.stopListening : T.listen} en={speaking ? "Stop" : "Listen"} />
    </button>
  );
}
