import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { RequireAuth } from "@/components/RequireAuth";
import { MarketingLayout } from "@/components/marketing/MarketingLayout";
import { Landing } from "@/pages/marketing/Landing";
import { Platform } from "@/pages/marketing/Platform";
import { Pricing } from "@/pages/marketing/Pricing";
import { About } from "@/pages/marketing/About";
import { SignIn } from "@/pages/auth/SignIn";
import { SignUp } from "@/pages/auth/SignUp";
import { DashboardStudio } from "@/pages/DashboardStudio";
import { DashboardEditor } from "@/pages/DashboardEditor";
import { Connections } from "@/pages/Connections";
import { Dashboard } from "@/pages/Dashboard";
import { Pipelines } from "@/pages/Pipelines";
import { CreatePipeline } from "@/pages/CreatePipeline";
import { DirectIngest } from "@/pages/DirectIngest";
import { DataPreview } from "@/pages/DataPreview";
import { Metrics } from "@/pages/Metrics";
import { Logs } from "@/pages/Logs";
import { MultiSource } from "@/pages/MultiSource";
import { Assistant } from "@/pages/Assistant";
import Text2SQL from "@/pages/Text2SQL";
import DataGenerator from "@/pages/DataGenerator";
import SqlEditor from "@/pages/SqlEditor";
import { Settings } from "@/pages/Settings";
import { QualityChecks } from "@/pages/QualityChecks";

/** Console paths that used to live at the root, kept working as redirects. */
const MOVED_TO_APP = [
  "connections",
  "monitoring",
  "create",
  "pipelines",
  "ingest",
  "preview",
  "metrics",
  "logs",
  "multi-source",
  "assistant",
  "text2sql",
  "datagenerator",
  "sql-editor",
  "settings",
  "quality"
];

export default function App() {
  return (
    <Routes>
      {/* Public site */}
      <Route element={<MarketingLayout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/platform" element={<Platform />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/about" element={<About />} />
      </Route>

      {/* Auth */}
      <Route path="/signin" element={<SignIn />} />
      <Route path="/signup" element={<SignUp />} />

      {/* Console */}
      <Route element={<RequireAuth />}>
        <Route path="/app" element={<Layout />}>
          <Route index element={<DashboardStudio />} />
          <Route path="studio/:dashboardId" element={<DashboardEditor />} />
          <Route path="connections" element={<Connections />} />
          <Route path="monitoring" element={<Dashboard />} />
          <Route path="create" element={<CreatePipeline />} />
          <Route path="pipelines" element={<Pipelines />} />
          <Route path="ingest" element={<DirectIngest />} />
          <Route path="preview" element={<DataPreview />} />
          <Route path="quality" element={<QualityChecks />} />
          <Route path="metrics" element={<Metrics />} />
          <Route path="logs" element={<Logs />} />
          <Route path="multi-source" element={<MultiSource />} />
          <Route path="assistant" element={<Assistant />} />
          <Route path="text2sql" element={<Text2SQL />} />
          <Route path="datagenerator" element={<DataGenerator />} />
          <Route path="sql-editor" element={<SqlEditor />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Route>

      {/* Legacy console URLs */}
      {MOVED_TO_APP.map((path) => (
        <Route key={path} path={`/${path}`} element={<Navigate to={`/app/${path}`} replace />} />
      ))}
      <Route path="/studio/:dashboardId" element={<LegacyStudioRedirect />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function LegacyStudioRedirect() {
  const { dashboardId } = useParams();
  return <Navigate to={`/app/studio/${dashboardId}`} replace />;
}
