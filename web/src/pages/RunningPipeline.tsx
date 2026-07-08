import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useReview } from "../lib/review";
import { PipelineTimeline } from "../components/PipelineTimeline";
import { Icon } from "../components/Icon";

export function RunningPipeline() {
  const { status, events, runningId } = useReview();
  const navigate = useNavigate();

  useEffect(() => {
    if (status === "done") {
      const t = setTimeout(
        () => navigate(`/reviews/${runningId ?? "glp1-mace"}/evidence`),
        900
      );
      return () => clearTimeout(t);
    }
  }, [status, runningId, navigate]);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-6">
        <p className="flex items-center gap-2 text-label-caps uppercase text-outline">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              status === "running" ? "animate-pulse bg-accent" : "bg-risk-low"
            }`}
          />
          {status === "running" ? "System active" : "Run complete"}
        </p>
        <h1 className="mt-1 font-sans text-display-lg text-ink-light">Pipeline Execution</h1>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="rounded-md hairline bg-card-light p-5 lg:col-span-4">
          <h2 className="mb-4 text-label-caps uppercase text-ink-muted-light">
            Execution sequence
          </h2>
          <PipelineTimeline events={events} done={status === "done"} />
        </section>

        {/* Live terminal — an intentionally dark panel (not full dark mode). */}
        <section className="overflow-hidden rounded-md bg-card-dark lg:col-span-8">
          <div className="flex items-center gap-2 border-b border-[#26282b] px-4 py-2.5">
            <Icon name="terminal" size={16} className="text-[#8a8f98]" />
            <span className="font-mono text-[11px] uppercase tracking-wider text-[#8a8f98]">
              Live stdout
            </span>
            <span className="ml-auto flex gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-[#3a3d42]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[#3a3d42]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[#3a3d42]" />
            </span>
          </div>
          <div className="max-h-[70vh] overflow-y-auto p-4 font-mono text-[12px] leading-[20px]">
            {events.length === 0 && <p className="text-[#5a5f68]">awaiting stream…</p>}
            {events.map((e, i) => (
              <p key={i}>
                <span className="text-accent">[{e.stage}]</span>{" "}
                <span className="text-[#c9ccd1]">{e.message}</span>
              </p>
            ))}
            {status === "running" && (
              <span className="inline-block h-3.5 w-2 animate-pulse bg-accent align-middle" />
            )}
          </div>
        </section>
      </div>

      {status === "error" && (
        <p className="mt-4 font-mono text-[13px] text-risk-high">
          Connection error. Is the backend running on :8000?
        </p>
      )}
    </div>
  );
}
