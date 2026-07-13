import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { PipelineEvent, Question, ReviewResult, Source } from "./types";

type Status = "idle" | "running" | "done" | "error";

interface ReviewState {
  status: Status;
  events: PipelineEvent[];
  result: ReviewResult | null;
  runningId: string | null;
  start: (question: Question, sources?: Source[]) => void;
  reset: () => void;
}

const ReviewContext = createContext<ReviewState | null>(null);

function wsUrl(path: string): string {
  // In production the backend is on another origin (Railway); derive the ws(s)
  // URL from VITE_API_URL. Unset in dev, so we fall back to the same-origin host
  // and the Vite proxy forwards /ws to the local backend.
  const base = import.meta.env.VITE_API_URL as string | undefined;
  if (base) {
    return `${base.replace(/^http/, "ws").replace(/\/$/, "")}${path}`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}

export function ReviewProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("idle");
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const reset = useCallback(() => {
    socketRef.current?.close();
    setStatus("idle");
    setEvents([]);
    setResult(null);
  }, []);

  const start = useCallback((q: Question, sources?: Source[]) => {
    setEvents([]);
    setResult(null);
    setStatus("running");
    setRunningId(q.id);

    // PubMed discovery is opt-in: the backend widens the search to Europe PMC
    // only when `pubmed` is named in the ws query string.
    const qs = sources && sources.length ? `?sources=${sources.join(",")}` : "";
    const socket = new WebSocket(wsUrl(`/ws/review${qs}`));
    socketRef.current = socket;

    socket.onopen = () => socket.send(JSON.stringify({ question: q }));
    socket.onmessage = (msg) => {
      const event: PipelineEvent = JSON.parse(msg.data);
      setEvents((prev) => [...prev, event]);
      if (event.stage === "done") {
        const done = event.data as ReviewResult;
        setResult(done);
        setRunningId(done.question.id);
        setStatus("done");
      }
    };
    socket.onerror = () => setStatus("error");
  }, []);

  const value = useMemo<ReviewState>(
    () => ({ status, events, result, runningId, start, reset }),
    [status, events, result, runningId, start, reset]
  );

  return <ReviewContext.Provider value={value}>{children}</ReviewContext.Provider>;
}

export function useReview(): ReviewState {
  const ctx = useContext(ReviewContext);
  if (!ctx) throw new Error("useReview must be used within a ReviewProvider");
  return ctx;
}
