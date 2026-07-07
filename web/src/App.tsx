import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { ReviewProvider } from "./lib/review";
import { Ask } from "./pages/Ask";
import { RunningPipeline } from "./pages/RunningPipeline";
import { Report } from "./pages/Report";

function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-hairline-light bg-canvas-light/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-8 py-3">
        <Link to="/" className="flex items-center gap-2">
          <span className="font-mono text-[15px] font-semibold text-ink-light">LiveMeta</span>
          <span className="rounded-full border border-hairline-light px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-muted-light">
            Living meta-analysis
          </span>
        </Link>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ReviewProvider>
        <div className="min-h-screen bg-canvas-light text-ink-light">
          <Header />
          <main>
            <Routes>
              <Route path="/" element={<Ask />} />
              <Route path="/run" element={<RunningPipeline />} />
              <Route path="/report" element={<Report />} />
            </Routes>
          </main>
        </div>
      </ReviewProvider>
    </BrowserRouter>
  );
}
