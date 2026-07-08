// Typed REST client for the LiveMeta backend. The WebSocket run flow lives in
// review.tsx; everything request/response goes through here.

import type {
  Question,
  ReviewDecision,
  ReviewDiff,
  ReviewResult,
  ReviewSummary,
  SnapshotMeta,
} from "./types";

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

export async function postRobDecision(
  id: string,
  decision: { study_id: string; domain_key: string; reason?: string | null }
): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch(`/api/reviews/${encodeURIComponent(id)}/rob/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(decision),
    })
  );
}

// --- Living layer: inject a trial, read the version history ------------------

export async function seedDemo(): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch("/api/reviews/demo/seed", { method: "POST" })
  );
}

export async function postUpdate(id: string, newTrialId: string): Promise<ReviewDiff> {
  return json<ReviewDiff>(
    await fetch(`/api/reviews/${encodeURIComponent(id)}/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_trial_id: newTrialId }),
    })
  );
}

export async function getHistory(id: string): Promise<SnapshotMeta[]> {
  return json<SnapshotMeta[]>(
    await fetch(`/api/reviews/${encodeURIComponent(id)}/history`)
  );
}

export async function getVersion(id: string, version: number): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch(`/api/reviews/${encodeURIComponent(id)}/versions/${version}`)
  );
}
