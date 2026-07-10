// Typed REST client for the LiveMeta backend. The WebSocket run flow lives in
// review.tsx; everything request/response goes through here.

import type {
  AssetDossier,
  DevelopmentEvent,
  IndicationMap,
  Landscape,
  Question,
  ReviewDecision,
  ReviewDiff,
  ReviewResult,
  ReviewSummary,
  SnapshotMeta,
  Source,
  TrialCandidate,
} from "./types";

// In production the backend lives on a different origin (Railway); VITE_API_URL
// points there. Unset in dev, so requests stay relative and hit the Vite proxy.
const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export async function parseQuestion(text: string): Promise<Question> {
  return json<Question>(
    await fetch(apiUrl("/api/parse"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    })
  );
}

export async function listReviews(): Promise<ReviewSummary[]> {
  return json<ReviewSummary[]>(await fetch(apiUrl("/api/reviews")));
}

export async function getReview(id: string): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch(apiUrl(`/api/reviews/${encodeURIComponent(id)}`))
  );
}

export async function postDecision(
  id: string,
  decision: Pick<ReviewDecision, "study_id" | "decision" | "reason">
): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch(apiUrl(`/api/reviews/${encodeURIComponent(id)}/decision`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(decision),
    })
  );
}

export async function postDiversityDecision(
  id: string,
  reason?: string | null
): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch(apiUrl(`/api/reviews/${encodeURIComponent(id)}/diversity/decision`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason ?? null }),
    })
  );
}

export async function postRobDecision(
  id: string,
  decision: { study_id: string; domain_key: string; reason?: string | null }
): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch(apiUrl(`/api/reviews/${encodeURIComponent(id)}/rob/decision`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(decision),
    })
  );
}

export async function postScreeningDecision(
  id: string,
  decision: { study_id: string; decision: "included" | "excluded"; reason?: string | null }
): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch(apiUrl(`/api/reviews/${encodeURIComponent(id)}/screening/decision`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(decision),
    })
  );
}

// --- Living layer: inject a trial, read the version history ------------------

export async function seedDemo(): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch(apiUrl("/api/reviews/demo/seed"), { method: "POST" })
  );
}

export async function checkUpdates(id: string): Promise<TrialCandidate[]> {
  return json<TrialCandidate[]>(
    await fetch(apiUrl(`/api/reviews/${encodeURIComponent(id)}/check-updates`), {
      method: "POST",
    })
  );
}

export async function postUpdate(id: string, newTrialId: string): Promise<ReviewDiff> {
  return json<ReviewDiff>(
    await fetch(apiUrl(`/api/reviews/${encodeURIComponent(id)}/update`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_trial_id: newTrialId }),
    })
  );
}

export async function getHistory(id: string): Promise<SnapshotMeta[]> {
  return json<SnapshotMeta[]>(
    await fetch(apiUrl(`/api/reviews/${encodeURIComponent(id)}/history`))
  );
}

export async function getVersion(id: string, version: number): Promise<ReviewResult> {
  return json<ReviewResult>(
    await fetch(apiUrl(`/api/reviews/${encodeURIComponent(id)}/versions/${version}`))
  );
}

// --- Competitive-intelligence landscape --------------------------------------

export async function getLandscape(
  condition: string,
  asOf?: string | null
): Promise<Landscape> {
  const params = new URLSearchParams({ condition });
  if (asOf) params.set("as_of", asOf);
  return json<Landscape>(await fetch(apiUrl(`/api/landscape?${params.toString()}`)));
}

export async function getAssetTimeline(
  condition: string,
  name: string
): Promise<DevelopmentEvent[]> {
  const params = new URLSearchParams({ condition });
  return json<DevelopmentEvent[]>(
    await fetch(
      apiUrl(`/api/landscape/asset/${encodeURIComponent(name)}?${params.toString()}`)
    )
  );
}

export async function linkLandscape(body: {
  condition: string;
  asset_name: string;
  indication: string;
  question_id: string;
}): Promise<Landscape> {
  return json<Landscape>(
    await fetch(apiUrl("/api/landscape/link"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export async function ingestLandscape(body: {
  condition: string;
  text: string;
  source_label: string;
}): Promise<Landscape> {
  return json<Landscape>(
    await fetch(apiUrl("/api/landscape/ingest"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

// --- v2: asset dossier + indication map --------------------------------------

function sourcesParam(sources?: Source[]): string {
  return sources && sources.length ? `?sources=${sources.join(",")}` : "";
}

export async function getAssetDossier(
  name: string,
  sources?: Source[]
): Promise<AssetDossier> {
  return json<AssetDossier>(
    await fetch(apiUrl(`/api/asset/${encodeURIComponent(name)}${sourcesParam(sources)}`))
  );
}

export async function getIndicationMap(
  name: string,
  sources?: Source[]
): Promise<IndicationMap> {
  return json<IndicationMap>(
    await fetch(apiUrl(`/api/indication/${encodeURIComponent(name)}${sourcesParam(sources)}`))
  );
}
