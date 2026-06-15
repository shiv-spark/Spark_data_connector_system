import { Routes, Route } from "react-router-dom";
import { Layout } from "@/components/Layout";
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

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/"             element={<DashboardStudio />} />
        <Route path="/studio/:dashboardId" element={<DashboardEditor />} />
        <Route path="/connections"  element={<Connections />} />
        <Route path="/monitoring"   element={<Dashboard />} />
        <Route path="/create"       element={<CreatePipeline />} />
        <Route path="/pipelines"    element={<Pipelines />} />
        <Route path="/ingest"       element={<DirectIngest />} />
        <Route path="/preview"      element={<DataPreview />} />
        <Route path="/metrics"      element={<Metrics />} />
        <Route path="/logs"         element={<Logs />} />
        <Route path="/multi-source" element={<MultiSource />} />
        <Route path="/assistant"    element={<Assistant />} />
        <Route path="/text2sql"     element={<Text2SQL />} />
        <Route path="/datagenerator" element={<DataGenerator />} />
      </Route>
    </Routes>
  );
}
