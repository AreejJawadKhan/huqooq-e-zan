import type { AskRequest, AskResponse, LetterRequest } from "./types";

async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

/** `?mock=1` serves the sample responses in public/fixtures so the UI works without a backend. */
export const MOCK = new URLSearchParams(window.location.search).get("mock") === "1";

function mockFixture(q: string): string {
  if (/danger|beat|hit me|kill|threat|suicide|خطر|مار|دھمک/i.test(q)) return "ask_danger";
  if (/wage|salary|pay|تنخواہ|اجرت/i.test(q)) return "ask_answered_wage";
  if (/province|which law/i.test(q)) return "ask_needs_province";
  if (/xyz/i.test(q)) return "ask_not_found";
  if (/cook|recipe|weather|football|کھانا/i.test(q)) return "ask_out_of_scope";
  return "ask_answered";
}

export async function ask(req: AskRequest): Promise<AskResponse> {
  if (MOCK) {
    await new Promise((r) => setTimeout(r, 600));
    const res = await fetch(`/fixtures/${mockFixture(req.question)}.json`);
    return res.json();
  }
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/** Posts the form and triggers a browser download of the generated .docx letter. */
export async function downloadLetter(req: LetterRequest): Promise<void> {
  if (MOCK) {
    save(new Blob([`MOCK LETTER\n\n${JSON.stringify(req, null, 2)}`], { type: "text/plain" }), "huqooq_letter_mock.txt");
    return;
  }
  const res = await fetch("/api/letter", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await errorText(res));
  save(await res.blob(), `huqooq_${req.letter_type}.docx`);
}
