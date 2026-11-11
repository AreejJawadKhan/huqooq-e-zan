import type { AskRequest, AskResponse, LetterRequest } from "./types";

async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

export async function ask(req: AskRequest): Promise<AskResponse> {
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await errorText(res));
  return res.json();
}

/** Posts the form and triggers a browser download of the generated .docx letter. */
export async function downloadLetter(req: LetterRequest): Promise<void> {
  const res = await fetch("/api/letter", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await errorText(res));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `huqooq_${req.letter_type}.docx`;
  a.click();
  URL.revokeObjectURL(url);
}
