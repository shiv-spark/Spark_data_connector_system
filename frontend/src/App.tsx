// import { Routes, Route } from "react-router-dom";
// import { Layout } from "@/components/Layout";
// import { DashboardStudio } from "@/pages/DashboardStudio";
// import { DashboardEditor } from "@/pages/DashboardEditor";
// import { Connections } from "@/pages/Connections";
// import { Dashboard } from "@/pages/Dashboard";
// import { Pipelines } from "@/pages/Pipelines";
// import { CreatePipeline } from "@/pages/CreatePipeline";
// import { DirectIngest } from "@/pages/DirectIngest";
// import { DataPreview } from "@/pages/DataPreview";
// import { Metrics } from "@/pages/Metrics";
// import { Logs } from "@/pages/Logs";
// import { MultiSource } from "@/pages/MultiSource";
// import { Assistant } from "@/pages/Assistant";
// import Text2SQL from "@/pages/Text2SQL";
// import DataGenerator from "@/pages/DataGenerator";
// import { isAdmin } from "@/lib/auth";

// const AdminRoute = () => {
//   if (!isAdmin()) return <Navigate to="/" replace />;
//   return <Outlet />;
// };

// export default function App() {
//   return (
//     <Routes>
//       <Route element={<Layout />}>
//         <Route path="/"             element={<DashboardStudio />} />
//         <Route path="/studio/:dashboardId" element={<DashboardEditor />} />
//         <Route path="/connections"  element={<Connections />} />
//         <Route path="/monitoring"   element={<Dashboard />} />
//         <Route path="/create"       element={<CreatePipeline />} />
//         <Route path="/pipelines"    element={<Pipelines />} />
//         <Route path="/ingest"       element={<DirectIngest />} />
//         <Route path="/preview"      element={<DataPreview />} />
//         <Route path="/metrics"      element={<Metrics />} />
//         <Route path="/logs"         element={<Logs />} />
//         <Route path="/multi-source" element={<MultiSource />} />
//         <Route path="/assistant"    element={<Assistant />} />
//         <Route path="/text2sql"     element={<Text2SQL />} />
//         <Route path="/datagenerator" element={<DataGenerator />} />
//       </Route>
//     </Routes>
//   );
// }


import { Routes, Route, Navigate, Outlet } from "react-router-dom";
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
import { Login } from "@/pages/Login";
import { UserManagement } from "@/pages/UserManagement";
import { AuditLog } from "@/pages/AuditLog";
import { isAuthenticated, isAdmin } from "@/lib/auth";

// Wraps everything that needs a logged-in user. If there's no valid
// token, bounce to /login. <Outlet /> renders whichever nested route
// matched (Layout + its children below).
const ProtectedRoute = () => {
  if (!isAuthenticated()) return <Navigate to="/login" replace />;
  return <Outlet />;
};

// Wraps admin-only pages (user management, audit log). Non-admins get
// sent back to the dashboard rather than seeing a blank/broken page.
const AdminRoute = () => {
  if (!isAdmin()) return <Navigate to="/" replace />;
  return <Outlet />;
};

export default function App() {
  return (
    <Routes>
      {/* Public route — no auth required */}
      <Route path="/login" element={<Login />} />

      {/* Everything below requires a logged-in user */}
      <Route element={<ProtectedRoute />}>
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

          {/* Admin-only pages, nested one level deeper so they still get the Layout */}
          <Route element={<AdminRoute />}>
            <Route path="/admin/users"      element={<UserManagement />} />
            <Route path="/admin/audit-log"  element={<AuditLog />} />
          </Route>
        </Route>
      </Route>

      {/* Catch-all — unknown path redirects to home (which itself redirects
          to /login if not authenticated) */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
