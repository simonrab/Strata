import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { getAssetTimeline } from "../lib/api";
import type { DevelopmentEvent } from "../lib/types";
import { PHASE_LABEL } from "../lib/types";
import { Icon } from "../components/Icon";
import { StagePill } from "../components/StagePill";
import { ProvenancePopover } from "../components/ProvenancePopover";

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

  useEffect(() => {
    getAssetTimeline(condition, name)
      .then((e) => setEvents([...e].sort((a, b) => (a.date ?? "").localeCompare(b.date ?? ""))))
      .catch(() => setError(true));
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

      <h1 className="font-sans text-display-lg text-ink-light">{decodeURIComponent(name)}</h1>
      <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
        Development timeline in {condition || "all indications"}
        {sponsor ? ` · ${sponsor}` : ""}.
      </p>

      {error && (
        <p className="mt-6 font-mono text-[13px] text-risk-high">Could not load the timeline.</p>
      )}

      {events && events.length === 0 && (
        <p className="mt-6 text-[14px] text-ink-muted-light">No dated events for this asset.</p>
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
