// Typed REST client for the LiveMeta backend. The WebSocket run flow lives in
// review.tsx; everything request/response goes through here.

import type { Question, ReviewDecision, ReviewResult, ReviewSummary } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export async function parseQuestion(text: string): Promise<Question> {
  return json<Question>(
    await fetch("/api/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    })
  );
}

export async function listReviews(): Promise<ReviewSummary[]> {
  return json<ReviewSummary[]>(await fetch("/api/reviews"));
}

export async function getReview(id: string): Promise<ReviewResult> {
  return json<ReviewResult>(await fetch(`/api/reviews/${encodeURIComponent(id)}`));
}

export async function postDecision(
  id: string,
  decision: Pick<ReviewDecision, "study_id" | "decision" | "reason">
): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch(`/api/reviews/${encodeURIComponent(id)}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(decision),
    })
  );
}
