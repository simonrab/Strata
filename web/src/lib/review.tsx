import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { PipelineEvent, Question, ReviewResult } from "./types";

type Status = "idle" | "running" | "done" | "error";

interface ReviewState {
  status: Status;
  events: PipelineEvent[];
  result: ReviewResult | null;
  question: Question | null;
  runningId: string | null;
  start: (question?: Question) => void;
  reset: () => void;
}

const ReviewContext = createContext<ReviewState | null>(null);

function wsUrl(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}

export function ReviewProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("idle");
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const questionLoaded = useRef(false);

  const reset = useCallback(() => {
    socketRef.current?.close();
    setStatus("idle");
    setEvents([]);
    setResult(null);
  }, []);

  const start = useCallback((q?: Question) => {
    setEvents([]);
    setResult(null);
    setStatus("running");
    setRunningId(q?.id ?? "glp1-mace");

    const socket = new WebSocket(wsUrl("/ws/review"));
    socketRef.current = socket;

    socket.onopen = () =>
      socket.send(JSON.stringify(q ? { question: q } : { mode: "demo" }));
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

  // Fetch the demo question once so the Ask screen can show it.
  const value = useMemo<ReviewState>(
    () => ({ status, events, result, question, runningId, start, reset }),
    [status, events, result, question, runningId, start, reset]
  );

  // Lazy-load the demo question exactly once.
  if (!questionLoaded.current) {
    questionLoaded.current = true;
    fetch("/api/demo")
      .then((r) => r.json())
      .then((q: Question) => setQuestion(q))
      .catch(() => undefined);
  }

  return <ReviewContext.Provider value={value}>{children}</ReviewContext.Provider>;
}

export function useReview(): ReviewState {
  const ctx = useContext(ReviewContext);
  if (!ctx) throw new Error("useReview must be used within a ReviewProvider");
  return ctx;
}
