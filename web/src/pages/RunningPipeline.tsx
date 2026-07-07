import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useReview } from "../lib/review";
import { PipelineTimeline } from "../components/PipelineTimeline";

export function RunningPipeline() {
  const { status, events, runningId } = useReview();
  const navigate = useNavigate();

  useEffect(() => {
    if (status === "done") {
      const t = setTimeout(
        () => navigate(`/reviews/${runningId ?? "glp1-mace"}/evidence`),
        600
      );
      return () => clearTimeout(t);
    }
  }, [status, runningId, navigate]);

  return (
    <div className="mx-auto max-w-3xl px-8 py-12">
      <div className="flex items-center gap-3">
        <span
          className={`inline-block h-2 w-2 rounded-full ${
            status === "running" ? "animate-pulse bg-[#2563eb]" : "bg-risk-low"
          }`}
        />
        <h1 className="font-serif text-[24px] text-ink-light">
          {status === "running" ? "Running pipeline…" : "Pipeline complete"}
        </h1>
      </div>

      <div className="mt-8 rounded-md border border-hairline-light bg-card-light p-6">
        <PipelineTimeline events={events} />
      </div>

      {status === "error" && (
        <p className="mt-4 font-mono text-[13px] text-risk-high">
          Connection error. Is the backend running on :8000?
        </p>
      )}
    </div>
  );
}
