import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ReviewProvider } from "./lib/review";
import { Sidebar } from "./components/Sidebar";
import { Dashboard } from "./pages/Dashboard";
import { Ask } from "./pages/Ask";
import { RunningPipeline } from "./pages/RunningPipeline";
import { Report } from "./pages/Report";
import { EvidenceLedger } from "./pages/EvidenceLedger";
import { ExtractionConfirmation } from "./pages/ExtractionConfirmation";
import { ReviewReport } from "./pages/ReviewReport";

export default function App() {
  return (
    <BrowserRouter>
      <ReviewProvider>
        <div className="min-h-screen bg-canvas-light text-ink-light">
          <Sidebar />
          <main className="md:pl-64">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/ask" element={<Ask />} />
              <Route path="/run" element={<RunningPipeline />} />
              <Route path="/report" element={<Report />} />
              <Route path="/reviews/:id/evidence" element={<EvidenceLedger />} />
              <Route
                path="/reviews/:id/evidence/:trialId"
                element={<ExtractionConfirmation />}
              />
              <Route path="/reviews/:id/report" element={<ReviewReport />} />
            </Routes>
          </main>
        </div>
      </ReviewProvider>
    </BrowserRouter>
  );
}
