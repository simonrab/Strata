import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { getAssetTimeline } from "../lib/api";
import type { DevelopmentEvent } from "../lib/types";
import { PHASE_LABEL } from "../lib/types";
import { Icon } from "../components/Icon";
import { StagePill } from "../components/StagePill";
import { ProvenancePopover } from "../components/ProvenancePopover";
import { LoadingState } from "../components/Loading";

function eventLabel(e: DevelopmentEvent): string {
  const map: Record<string, string> = {
    trial_start: "Trial started",
    trial_status: "Status",
    readout: "Read out",
    filing: "Regulatory filing",
    approval: "Approval",
    announcement: "Announcement",
  };
  return map[e.event_type] ?? e.event_type;
}

export function AssetProfile() {
  const { name = "" } = useParams();
  const [params] = useSearchParams();
  const condition = params.get("condition") ?? "";
  const [events, setEvents] = useState<DevelopmentEvent[] | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Reset on navigation so the loading state shows instead of a blank body or
    // the previous asset's events while the next fetch is in flight.
    setLoading(true);
    setError(false);
    setEvents(null);
    getAssetTimeline(condition, name)
      .then((e) => setEvents([...e].sort((a, b) => (a.date ?? "").localeCompare(b.date ?? ""))))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [condition, name]);

  const sponsor = events?.find((e) => e.sponsor)?.sponsor;

  return (
    <div className="mx-auto max-w-3xl px-8 py-10">
      <Link
        to={`/landscape`}
        className="mb-4 inline-flex items-center gap-1 text-[12px] text-accent hover:underline"
      >
        <Icon name="chevron_left" size={14} /> Landscape
      </Link>

      <span className="text-label-caps uppercase text-ink-muted-light">Development timeline</span>
      <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-sans text-display-lg text-ink-light">{decodeURIComponent(name)}</h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
            Dated milestones in {condition || "all indications"}
            {sponsor ? " · " : ""}
            {sponsor && (
              <Link
                to={`/company/${encodeURIComponent(sponsor)}`}
                className="text-accent hover:underline"
                title={`See ${sponsor}'s entire pipeline`}
              >
                {sponsor}
              </Link>
            )}
            .
          </p>
        </div>
        {/* This page is a timeline, not the asset page — link out to the full
            dossier so the two aren't confused. */}
        <Link
          to={`/asset/${encodeURIComponent(name)}`}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-sm bg-ink-light px-3 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
          title={`Open the full dossier for ${decodeURIComponent(name)}`}
        >
          <Icon name="science" size={15} /> Full asset dossier
          <Icon name="chevron_right" size={14} />
        </Link>
      </div>

      {loading && <LoadingState label="Loading timeline…" />}

      {error && !loading && (
        <p className="mt-6 font-mono text-[13px] text-risk-high">Could not load the timeline.</p>
      )}

      {!loading && !error && events && events.length === 0 && (
        <p className="mt-6 text-[14px] text-ink-muted-light">
          No dated development events recorded for this asset in {condition || "this condition"}.
        </p>
      )}

      {events && events.length > 0 && (
        <ol className="mt-8 space-y-0">
          {events.map((e, i) => (
            <li key={i} className="relative flex gap-4 pb-8 last:pb-0">
              {/* timeline rail */}
              <div className="flex flex-col items-center">
                <span className="mt-1 h-2.5 w-2.5 rounded-full bg-accent" />
                {i < events.length - 1 && <span className="w-px flex-1 bg-hairline-light" />}
              </div>
              <div className="flex-1 pb-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[12px] text-ink-muted-light">
                    {e.date ?? "undated"}
                  </span>
                  <StagePill phase={e.phase} />
                  <span className="text-[11px] uppercase tracking-wider text-outline">
                    {e.source_type}
                  </span>
                </div>
                <p className="mt-1 text-[14px] text-ink-light">
                  {eventLabel(e)} · {PHASE_LABEL[e.phase]} for {e.indication}
                </p>
                <div className="mt-1">
                  <ProvenancePopover provenance={e.provenance} />
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
