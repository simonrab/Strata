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
import { RiskOfBias } from "./pages/RiskOfBias";
import { GradeDetail } from "./pages/GradeDetail";
import { Updates } from "./pages/Updates";
import { AuditTrail } from "./pages/AuditTrail";
import { SnapshotView } from "./pages/SnapshotView";
import { CompetitorLandscape } from "./pages/CompetitorLandscape";
import { AssetProfile } from "./pages/AssetProfile";
import { AssetDossier } from "./pages/AssetDossier";
import { IndicationMap } from "./pages/IndicationMap";

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
              <Route path="/landscape" element={<CompetitorLandscape />} />
              <Route path="/landscape/asset/:name" element={<AssetProfile />} />
              <Route path="/asset/:name" element={<AssetDossier />} />
              <Route path="/indication/:name" element={<IndicationMap />} />
              <Route path="/run" element={<RunningPipeline />} />
              <Route path="/report" element={<Report />} />
              <Route path="/reviews/:id/evidence" element={<EvidenceLedger />} />
              <Route
                path="/reviews/:id/evidence/:trialId"
                element={<ExtractionConfirmation />}
              />
              <Route path="/reviews/:id/rob" element={<RiskOfBias />} />
              <Route path="/reviews/:id/grade" element={<GradeDetail />} />
              <Route path="/reviews/:id/report" element={<ReviewReport />} />
              <Route path="/reviews/:id/updates" element={<Updates />} />
              <Route path="/reviews/:id/audit" element={<AuditTrail />} />
              <Route path="/reviews/:id/versions/:version" element={<SnapshotView />} />
            </Routes>
          </main>
        </div>
      </ReviewProvider>
    </BrowserRouter>
  );
}
