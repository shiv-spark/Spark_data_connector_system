

// import { FormEvent, useState, useEffect } from "react";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import { Loader2, PlusCircle, Link2, Link2Off, Check, ChevronLeft, ChevronRight, CheckCircle2, XCircle } from "lucide-react";
// // import { Loader2, PlusCircle, Link2, Link2Off, Check, ChevronLeft, ChevronRight } from "lucide-react";
// import { api } from "@/lib/api";
// import { Button } from "@/components/ui/button";
// import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
// import { Input } from "@/components/ui/input";
// import { SchedulerFields } from "@/components/SchedulerFields";
// import { FolderUpload } from "@/pages/FolderUpload";
// import { buildCron, defaultSchedule } from "@/lib/schedule";

// type Connector = "csv" | "excel" | "google_sheets" | "api" | "postgres" | "s3" | "snowflake";

// const CONNECTOR_TO_SOURCE_TYPE: Record<Connector, string> = {
//   csv: "local_folder",
//   excel: "local_folder",
//   google_sheets: "google_sheet",
//   api: "api",
//   postgres: "postgres",
//   s3: "s3",
//   snowflake: "snowflake",
// };

// const CONNECTOR_LABELS: Record<Connector, string> = {
//   csv: "CSV",
//   excel: "Excel",
//   google_sheets: "Google Sheets",
//   api: "API",
//   postgres: "Postgres",
//   s3: "S3",
//   snowflake: "Snowflake",
// };

// const SUPPORTS_CONNECTIONS: Connector[] = ["csv", "excel", "google_sheets", "api", "postgres", "s3", "snowflake"];

// const STEPS = [
//   { id: 1, label: "Basic Info" },
//   { id: 2, label: "Source Config" },
//   { id: 3, label: "Schedule" },
//   { id: 4, label: "Review & Create" },
// ];

// const base = {
//   pipeline_name: "",
//   connector_type: "csv" as Connector,
//   table_name: "",
//   option: "1",
//   after_first_run: "",
//   sync_mode: "full",
//   incremental_column: "",
//   folder_path: "",
//   file_path: "",
//   sheet_url: "",
//   api_url: "",
//   api_config: "",
//   src_pg_host: "",
//   src_pg_db: "",
//   src_pg_user: "",
//   src_pg_password: "",
//   src_pg_port: "5432",
//   pg_query: "",
//   s3_bucket: "",
//   s3_key: "",
//   s3_file_type: "csv",
//   sf_account: "",
//   sf_user: "",
//   sf_password: "",
//   sf_warehouse: "",
//   sf_database: "",
//   sf_schema: "PUBLIC",
//   sf_role: "",
//   sf_query: "",
// };

// export const CreatePipeline = () => {
//   const qc = useQueryClient();
//   const [form, setForm] = useState(base);
//   const [schedule, setSchedule] = useState(defaultSchedule);
//   const [result, setResult] = useState<any>(null);
//   const [apiConfigError, setApiConfigError] = useState<string>("");
//   const [useExistingConnection, setUseExistingConnection] = useState(false);
//   const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
//   const [connectionError, setConnectionError] = useState<string>("");
//   const [currentStep, setCurrentStep] = useState(1);
//   const [stepError, setStepError] = useState<string>("");

//   const update = (key: keyof typeof base, value: string) => setForm((current) => ({ ...current, [key]: value }));

//   const connections = useQuery({
//     queryKey: ["connections"],
//     queryFn: async () => (await api.get("/connections")).data.connections ?? [],
//   });

//   const filteredConnections = connections.data?.filter(
//     (conn: any) => conn.source_type === CONNECTOR_TO_SOURCE_TYPE[form.connector_type as Connector]
//   ) ?? [];

//   const populateFromConnection = (connId: string) => {
//     if (!connId) return;
//     const conn = filteredConnections.find((c: any) => String(c.id) === connId);
//     if (conn?.config) {
//       const cfg = conn.config;
//       if (form.connector_type === "postgres") {
//         update("src_pg_host", cfg.host || "");
//         update("src_pg_db", cfg.database || "");
//         update("src_pg_user", cfg.user || "");
//         update("src_pg_password", cfg.password || "");
//         update("src_pg_port", cfg.port || "5432");
//       } else if (form.connector_type === "s3") {
//         update("s3_bucket", cfg.bucket || "");
//         update("s3_key", cfg.prefix || "");
//         update("s3_file_type", cfg.file_type || "csv");
//       } else if (form.connector_type === "snowflake") {
//         update("sf_account", cfg.account || "");
//         update("sf_user", cfg.user || "");
//         update("sf_password", cfg.password || "");
//         update("sf_warehouse", cfg.warehouse || "");
//         update("sf_database", cfg.database || "");
//         update("sf_schema", cfg.schema || "PUBLIC");
//         update("sf_role", cfg.role || "");
//       } else if (form.connector_type === "api") {
//         update("api_url", cfg.base_url || "");
//       } else if (form.connector_type === "google_sheets") {
//         update("sheet_url", cfg.sheet_url || "");
//       } else if (form.connector_type === "csv" || form.connector_type === "excel") {
//         update("folder_path", cfg.base_path || "");
//         update("s3_file_type", cfg.file_type || "csv");
//       }
//     }
//   };

//   useEffect(() => {
//     setSelectedConnectionId("");
//     setUseExistingConnection(false);
//     setConnectionError("");
//   }, [form.connector_type]);

//   const create = useMutation({
//     mutationFn: async () => {
//       if (useExistingConnection && !selectedConnectionId) {
//         setConnectionError("Please select a saved connection");
//         throw new Error("No connection selected");
//       }

//       let parsedApiConfig: Record<string, unknown> | null = null;
//       if (form.connector_type === "api" && form.api_config.trim()) {
//         try {
//           parsedApiConfig = JSON.parse(form.api_config);
//         } catch (e) {
//           setApiConfigError("Invalid JSON — please check the syntax.");
//           throw new Error("Invalid api_config JSON");
//         }
//       }

//       const payload = {
//         ...form,
//         api_config: parsedApiConfig,
//         schedule: buildCron(schedule),
//         timezone: schedule.timezone,
//         incremental_column: form.sync_mode === "incremental" ? form.incremental_column : null,
//         after_first_run: form.option === "3" ? form.after_first_run || null : null,
//         connection_id: useExistingConnection ? parseInt(selectedConnectionId) : null,
//       };
//       const response = await api.post("/create_pipeline", payload);
//       return response.data;
//     },
//     onSuccess: (data) => {
//         setResult(data);
//         qc.invalidateQueries({ queryKey: ["pipelines"] });
//         qc.invalidateQueries({ queryKey: ["dashboard"] });

//         // Reset the whole form so the user can immediately create another
//         // pipeline without manually going Back through every step, and
//         // without accidentally resubmitting the same pipeline_name (which
//         // the backend rejects as "already exists").
//         setForm(base);
//         setSchedule(defaultSchedule);
//         setUseExistingConnection(false);
//         setSelectedConnectionId("");
//         setConnectionError("");
//         setApiConfigError("");
//         setStepError("");
//         setCurrentStep(1);
//       },
//   });

//   // ── Step validation — checked before allowing "Next" ─────────────────
//   const validateStep = (step: number): string => {
//     if (step === 1) {
//       if (!form.pipeline_name.trim()) return "Pipeline name is required.";
//       if (!form.table_name.trim()) return "Target table is required.";
//       if (form.option === "3" && !form.after_first_run) return "Select what happens after the first run.";
//       if (form.sync_mode === "incremental" && !form.incremental_column.trim()) return "Incremental column is required.";
//       return "";
//     }
//     if (step === 2) {
//       if (useExistingConnection && !selectedConnectionId) return "Please select a saved connection, or switch to New Connection.";
//       if (!useExistingConnection) {
//         if (["csv", "excel"].includes(form.connector_type) && !form.file_path && !form.folder_path) {
//           return "Provide a file path or folder path.";
//         }
//         if (form.connector_type === "google_sheets" && !form.sheet_url.trim()) return "Sheet URL is required.";
//         if (form.connector_type === "api" && !form.api_url.trim()) return "API URL is required.";
//         if (form.connector_type === "postgres" && (!form.src_pg_host || !form.src_pg_db || !form.src_pg_user || !form.pg_query)) {
//           return "Host, database, user, and query are required for Postgres.";
//         }
//         if (form.connector_type === "s3" && (!form.s3_bucket || !form.s3_key)) return "Bucket and key are required for S3.";
//         if (form.connector_type === "snowflake" && (!form.sf_account || !form.sf_user || !form.sf_warehouse || !form.sf_database || !form.sf_query)) {
//           return "Account, user, warehouse, database, and query are required for Snowflake.";
//         }
//       }
//       if (form.connector_type === "api" && form.api_config.trim()) {
//         try {
//           JSON.parse(form.api_config);
//         } catch {
//           return "Advanced Config has invalid JSON.";
//         }
//       }
//       return "";
//     }
//     return "";
//   };

//   const goNext = () => {
//     const err = validateStep(currentStep);
//     if (err) {
//       setStepError(err);
//       return;
//     }
//     setStepError("");
//     setCurrentStep((s) => Math.min(s + 1, STEPS.length));
//   };

//   const goBack = () => {
//     setStepError("");
//     setCurrentStep((s) => Math.max(s - 1, 1));
//   };

//   const goToStep = (step: number) => {
//     // Only allow jumping backward, or forward if all steps in between are valid
//     if (step < currentStep) {
//       setStepError("");
//       setCurrentStep(step);
//       return;
//     }
//     for (let s = currentStep; s < step; s++) {
//       const err = validateStep(s);
//       if (err) {
//         setStepError(err);
//         return;
//       }
//     }
//     setStepError("");
//     setCurrentStep(step);
//   };

//   const submit = (event: FormEvent) => {
//     event.preventDefault();
//     setConnectionError("");
//     setApiConfigError("");
//     setResult(null);
//     create.mutate();
//   };

//   return (
//     <div className="space-y-5">
//       <h2 className="h-section flex items-center gap-2"><PlusCircle className="h-5 w-5" /> Create Pipeline</h2>

//       {/* ── Stepper ─────────────────────────────────────────────────── */}
//       <Card>
//         <CardContent className="p-4">
//           <div className="flex items-center">
//             {STEPS.map((step, idx) => (
//               <div key={step.id} className="flex flex-1 items-center last:flex-none">
//                 <button
//                   type="button"
//                   onClick={() => goToStep(step.id)}
//                   className="flex items-center gap-2 group"
//                 >
//                   <span
//                     className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-medium transition-colors ${
//                       step.id === currentStep
//                         ? "border-emerald-600 bg-emerald-600 text-white"
//                         : step.id < currentStep
//                         ? "border-emerald-600 bg-emerald-50 text-emerald-600"
//                         : "border-slate-300 bg-white text-slate-400 group-hover:border-slate-400"
//                     }`}
//                   >
//                     {step.id < currentStep ? <Check className="h-4 w-4" /> : step.id}
//                   </span>
//                   <span
//                     className={`hidden text-sm font-medium sm:block ${
//                       step.id === currentStep ? "text-slate-950" : step.id < currentStep ? "text-emerald-700" : "text-slate-400"
//                     }`}
//                   >
//                     {step.label}
//                   </span>
//                 </button>
//                 {idx < STEPS.length - 1 && (
//                   <div className={`mx-3 h-0.5 flex-1 ${step.id < currentStep ? "bg-emerald-600" : "bg-slate-200"}`} />
//                 )}
//               </div>
//             ))}
//           </div>
//         </CardContent>
//       </Card>

//       <Card>
//         <CardHeader>
//           <CardTitle className="text-sm">
//             Step {currentStep} of {STEPS.length}: {STEPS[currentStep - 1].label}
//           </CardTitle>
//         </CardHeader>
//         <CardContent>
//           <form onSubmit={submit} className="space-y-5">

//             {/* ══════════════════ STEP 1 — BASIC INFO ══════════════════ */}
//             {currentStep === 1 && (
//               <div className="space-y-4">
//                 <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
//                   <label className="space-y-1 text-sm font-medium">
//                     Pipeline name
//                     <Input value={form.pipeline_name} onChange={(e) => update("pipeline_name", e.target.value)} placeholder="e.g. daily_sales_sync" required />
//                   </label>
//                   <label className="space-y-1 text-sm font-medium">
//                     Connector
//                     <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.connector_type} onChange={(e) => update("connector_type", e.target.value as Connector)}>
//                       {(Object.keys(CONNECTOR_LABELS) as Connector[]).map((c) => (
//                         <option key={c} value={c}>{CONNECTOR_LABELS[c]}</option>
//                       ))}
//                     </select>
//                   </label>
//                   <label className="space-y-1 text-sm font-medium">
//                     Target table
//                     <Input value={form.table_name} onChange={(e) => update("table_name", e.target.value)} placeholder="e.g. sales_data" required />
//                   </label>
//                   <label className="space-y-1 text-sm font-medium">
//                     Load option
//                     <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.option} onChange={(e) => update("option", e.target.value)}>
//                       <option value="1">Append</option>
//                       <option value="2">Overwrite</option>
//                       <option value="3">Create new</option>
//                     </select>
//                   </label>
//                   <label className="space-y-1 text-sm font-medium">
//                     Sync mode
//                     <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.sync_mode} onChange={(e) => update("sync_mode", e.target.value)}>
//                       <option value="full">Full</option>
//                       <option value="incremental">Incremental</option>
//                     </select>
//                   </label>
//                 </div>

//                 {form.option === "3" && (
//                   <label className="block max-w-md space-y-1 text-sm font-medium">
//                     After first run
//                     <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.after_first_run} onChange={(e) => update("after_first_run", e.target.value)}>
//                       <option value="">Select...</option>
//                       <option value="1">Then append</option>
//                       <option value="2">Then overwrite</option>
//                     </select>
//                   </label>
//                 )}
//                 {form.sync_mode === "incremental" && (
//                   <label className="block max-w-md space-y-1 text-sm font-medium">
//                     Incremental column
//                     <Input value={form.incremental_column} onChange={(e) => update("incremental_column", e.target.value)} placeholder="e.g. updated_at" />
//                   </label>
//                 )}
//               </div>
//             )}

//             {/* ══════════════════ STEP 2 — SOURCE CONFIG ══════════════════ */}
//             {currentStep === 2 && (
//               <div className="space-y-4">
//                 {SUPPORTS_CONNECTIONS.includes(form.connector_type) && (
//                   <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
//                     <div className="flex items-center gap-4">
//                       <label className="flex items-center gap-2 text-sm font-medium">
//                         <input
//                           type="radio"
//                           name="connectionMode"
//                           checked={!useExistingConnection}
//                           onChange={() => {
//                             setUseExistingConnection(false);
//                             setSelectedConnectionId("");
//                             setConnectionError("");
//                           }}
//                         />
//                         <Link2Off className="h-4 w-4" />
//                         New Connection
//                       </label>
//                       <label className="flex items-center gap-2 text-sm font-medium">
//                         <input
//                           type="radio"
//                           name="connectionMode"
//                           checked={useExistingConnection}
//                           onChange={() => setUseExistingConnection(true)}
//                         />
//                         <Link2 className="h-4 w-4" />
//                         Use Saved Connection
//                       </label>
//                     </div>
//                     {useExistingConnection && (
//                       <div className="mt-3">
//                         {connections.isLoading ? (
//                           <p className="text-sm text-muted-foreground">Loading connections...</p>
//                         ) : filteredConnections.length === 0 ? (
//                           <p className="text-sm text-red-500">No saved connections for this connector type. Please create a new connection.</p>
//                         ) : (
//                           <select
//                             className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
//                             value={selectedConnectionId}
//                             onChange={(e) => {
//                               setSelectedConnectionId(e.target.value);
//                               setConnectionError("");
//                               populateFromConnection(e.target.value);
//                             }}
//                           >
//                             <option value="">Select a connection</option>
//                             {filteredConnections.map((conn: any) => (
//                               <option key={conn.id} value={conn.id}>{conn.name}</option>
//                             ))}
//                           </select>
//                         )}
//                         {connectionError && <p className="mt-2 text-sm text-red-500">{connectionError}</p>}
//                       </div>
//                     )}
//                   </div>
//                 )}

//                 {!useExistingConnection && (
//                   <>
//                     {["csv", "excel"].includes(form.connector_type) && (
//                       <div className="space-y-3">
//                         <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
//                           <Input placeholder="File path" value={form.file_path} onChange={(e) => update("file_path", e.target.value)} />
//                           <Input placeholder="Folder path (all files in it)" value={form.folder_path} onChange={(e) => update("folder_path", e.target.value)} />
//                         </div>
//                         <FolderUpload
//                           connectorType={form.connector_type as "csv" | "excel"}
//                           onFolderResolved={(folderPath) => { update("folder_path", folderPath); update("file_path", ""); }}
//                           onFileResolved={(filePath) => { update("file_path", filePath); update("folder_path", ""); }}
//                         />
//                       </div>
//                     )}
//                     {form.connector_type === "google_sheets" && (
//                       <Input placeholder="Sheet URL" value={form.sheet_url} onChange={(e) => update("sheet_url", e.target.value)} />
//                     )}
//                     {form.connector_type === "api" && (
//                       <div className="space-y-2">
//                         <Input placeholder="API URL" value={form.api_url} onChange={(e) => update("api_url", e.target.value)} />
//                         <label className="space-y-1 text-sm font-medium block">
//                           Advanced Config (optional JSON — method, auth_type, body, pagination, etc.)
//                           <textarea
//                             className="min-h-40 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
//                             placeholder={`{\n  "method": "GET",\n  "records_path": "products"\n}`}
//                             value={form.api_config}
//                             onChange={(e) => {
//                               update("api_config", e.target.value);
//                               setApiConfigError("");
//                             }}
//                           />
//                         </label>
//                         {apiConfigError && <p className="text-sm text-red-500">{apiConfigError}</p>}
//                       </div>
//                     )}
//                     {form.connector_type === "postgres" && (
//                       <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
//                         <Input placeholder="Host" value={form.src_pg_host} onChange={(e) => update("src_pg_host", e.target.value)} />
//                         <Input placeholder="Database" value={form.src_pg_db} onChange={(e) => update("src_pg_db", e.target.value)} />
//                         <Input placeholder="User" value={form.src_pg_user} onChange={(e) => update("src_pg_user", e.target.value)} />
//                         <Input placeholder="Password" type="password" value={form.src_pg_password} onChange={(e) => update("src_pg_password", e.target.value)} />
//                         <Input placeholder="Port" value={form.src_pg_port} onChange={(e) => update("src_pg_port", e.target.value)} />
//                         <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={form.pg_query} onChange={(e) => update("pg_query", e.target.value)} />
//                       </div>
//                     )}
//                     {form.connector_type === "s3" && (
//                       <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
//                         <Input placeholder="Bucket" value={form.s3_bucket} onChange={(e) => update("s3_bucket", e.target.value)} />
//                         <Input placeholder="Key" value={form.s3_key} onChange={(e) => update("s3_key", e.target.value)} />
//                         <Input placeholder="File type" value={form.s3_file_type} onChange={(e) => update("s3_file_type", e.target.value)} />
//                       </div>
//                     )}
//                     {form.connector_type === "snowflake" && (
//                       <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
//                         <Input placeholder="Account (e.g. XROJPNQ-RO43084)" value={form.sf_account} onChange={(e) => update("sf_account", e.target.value)} />
//                         <Input placeholder="User" value={form.sf_user} onChange={(e) => update("sf_user", e.target.value)} />
//                         <Input placeholder="Password" type="password" value={form.sf_password} onChange={(e) => update("sf_password", e.target.value)} />
//                         <Input placeholder="Warehouse" value={form.sf_warehouse} onChange={(e) => update("sf_warehouse", e.target.value)} />
//                         <Input placeholder="Database" value={form.sf_database} onChange={(e) => update("sf_database", e.target.value)} />
//                         <Input placeholder="Schema (default PUBLIC)" value={form.sf_schema} onChange={(e) => update("sf_schema", e.target.value)} />
//                         <Input placeholder="Role (optional)" value={form.sf_role} onChange={(e) => update("sf_role", e.target.value)} />
//                         <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={form.sf_query} onChange={(e) => update("sf_query", e.target.value)} />
//                       </div>
//                     )}
//                   </>
//                 )}
//               </div>
//             )}

//             {/* ══════════════════ STEP 3 — SCHEDULE ══════════════════ */}
//             {currentStep === 3 && (
//               <div className="space-y-4">
//                 <SchedulerFields value={schedule} onChange={setSchedule} />
//               </div>
//             )}

//             {/* ══════════════════ STEP 4 — REVIEW & CREATE ══════════════════ */}
//             {currentStep === 4 && (
//               <div className="space-y-4">
//                 <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
//                   <h3 className="mb-3 font-semibold text-slate-950">Review your pipeline</h3>
//                   <dl className="grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2">
//                     <div><dt className="text-muted-foreground">Pipeline name</dt><dd className="font-medium">{form.pipeline_name || "—"}</dd></div>
//                     <div><dt className="text-muted-foreground">Connector</dt><dd className="font-medium">{CONNECTOR_LABELS[form.connector_type]}</dd></div>
//                     <div><dt className="text-muted-foreground">Target table</dt><dd className="font-medium">{form.table_name || "—"}</dd></div>
//                     <div><dt className="text-muted-foreground">Load option</dt><dd className="font-medium">{{ "1": "Append", "2": "Overwrite", "3": "Create new" }[form.option]}</dd></div>
//                     <div><dt className="text-muted-foreground">Sync mode</dt><dd className="font-medium capitalize">{form.sync_mode}</dd></div>
//                     <div><dt className="text-muted-foreground">Schedule</dt><dd className="font-medium">{buildCron(schedule)} ({schedule.timezone})</dd></div>
//                     <div className="md:col-span-2">
//                       <dt className="text-muted-foreground">Source</dt>
//                       <dd className="font-medium">
//                         {useExistingConnection
//                           ? `Saved connection: ${filteredConnections.find((c: any) => String(c.id) === selectedConnectionId)?.name || selectedConnectionId}`
//                           : form.file_path || form.folder_path || form.sheet_url || form.api_url || form.src_pg_host || form.s3_bucket || form.sf_account || "—"}
//                       </dd>
//                     </div>
//                   </dl>
//                 </div>

//                 <p className="text-sm text-muted-foreground">
//                   Everything look right? Click <span className="font-medium text-slate-950">Create Pipeline</span> below to finish.
//                 </p>
//               </div>
//             )}

//             {stepError && <p className="text-sm text-red-500">{stepError}</p>}

//             {/* ══════════════════ NAVIGATION ══════════════════ */}
//             <div className="flex items-center justify-between border-t border-slate-100 pt-4">
//               <Button type="button" variant="outline" onClick={goBack} disabled={currentStep === 1}>
//                 <ChevronLeft className="h-4 w-4" /> Back
//               </Button>

//               {currentStep < STEPS.length ? (
//                 <Button type="button" onClick={goNext}>
//                   Next <ChevronRight className="h-4 w-4" />
//                 </Button>
//               ) : (
//                 <Button type="submit" disabled={create.isPending}>
//                   {create.isPending ? <Loader2 className="animate-spin" /> : <PlusCircle />} Create Pipeline
//                 </Button>
//               )}
//             </div>
//           </form>
//         </CardContent>
//       </Card>

//       {result && (
//   <Card className="border-emerald-200 bg-emerald-50">
//     <CardContent className="flex items-start gap-3 p-4">
//       <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
//       <div className="space-y-1">
//         <p className="font-medium text-emerald-900">Pipeline created successfully</p>
//         <p className="text-sm text-emerald-800">
//           <span className="font-medium">{result.dag_id}</span> is set up and will start running on schedule.
//         </p>
//         {result.message && <p className="text-xs text-emerald-700">{result.message}</p>}
//       </div>
//     </CardContent>
//   </Card>
// )}

// {create.error && (
//   <Card className="border-rose-200 bg-rose-50">
//     <CardContent className="flex items-start gap-3 p-4">
//       <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
//       <div className="space-y-1">
//         <p className="font-medium text-rose-900">Couldn't create pipeline</p>
//         <p className="text-sm text-rose-800">
//           {(create.error as any)?.response?.data?.detail?.error
//             || (create.error as any)?.response?.data?.detail
//             || (create.error as Error).message}
//         </p>
//       </div>
//     </CardContent>
//   </Card>
// )}
import { FormEvent, useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, PlusCircle, Link2, Link2Off, Check, ChevronLeft, ChevronRight, CheckCircle2, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SchedulerFields } from "@/components/SchedulerFields";
import { FolderUpload } from "@/pages/FolderUpload";
import { buildCron, defaultSchedule } from "@/lib/schedule";

type Connector = "csv" | "excel" | "google_sheets" | "api" | "postgres" | "s3" | "snowflake";

const CONNECTOR_TO_SOURCE_TYPE: Record<Connector, string> = {
  csv: "local_folder",
  excel: "local_folder",
  google_sheets: "google_sheet",
  api: "api",
  postgres: "postgres",
  s3: "s3",
  snowflake: "snowflake",
};

const CONNECTOR_LABELS: Record<Connector, string> = {
  csv: "CSV",
  excel: "Excel",
  google_sheets: "Google Sheets",
  api: "API",
  postgres: "Postgres",
  s3: "S3",
  snowflake: "Snowflake",
};

const SUPPORTS_CONNECTIONS: Connector[] = ["csv", "excel", "google_sheets", "api", "postgres", "s3", "snowflake"];

const STEPS = [
  { id: 1, label: "Basic Info" },
  { id: 2, label: "Source Config" },
  { id: 3, label: "Schedule" },
  { id: 4, label: "Review & Create" },
];

const base = {
  pipeline_name: "",
  connector_type: "csv" as Connector,
  table_name: "",
  option: "1",
  after_first_run: "",
  sync_mode: "full",
  incremental_column: "",
  folder_path: "",
  file_path: "",
  sheet_url: "",
  api_url: "",
  api_config: "",
  src_pg_host: "",
  src_pg_db: "",
  src_pg_user: "",
  src_pg_password: "",
  src_pg_port: "5432",
  pg_query: "",
  s3_bucket: "",
  s3_key: "",
  s3_file_type: "csv",
  sf_account: "",
  sf_user: "",
  sf_password: "",
  sf_warehouse: "",
  sf_database: "",
  sf_schema: "PUBLIC",
  sf_role: "",
  sf_query: "",
};

export const CreatePipeline = () => {
  const qc = useQueryClient();
  const [form, setForm] = useState(base);
  const [schedule, setSchedule] = useState(defaultSchedule);
  const [result, setResult] = useState<any>(null);
  const [apiConfigError, setApiConfigError] = useState<string>("");
  const [useExistingConnection, setUseExistingConnection] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [connectionError, setConnectionError] = useState<string>("");
  const [currentStep, setCurrentStep] = useState(1);
  const [stepError, setStepError] = useState<string>("");

  const update = (key: keyof typeof base, value: string) => setForm((current) => ({ ...current, [key]: value }));

  const connections = useQuery({
    queryKey: ["connections"],
    queryFn: async () => (await api.get("/connections")).data.connections ?? [],
  });

  const filteredConnections = connections.data?.filter(
    (conn: any) => conn.source_type === CONNECTOR_TO_SOURCE_TYPE[form.connector_type as Connector]
  ) ?? [];

  const populateFromConnection = (connId: string) => {
    if (!connId) return;
    const conn = filteredConnections.find((c: any) => String(c.id) === connId);
    if (conn?.config) {
      const cfg = conn.config;
      if (form.connector_type === "postgres") {
        update("src_pg_host", cfg.host || "");
        update("src_pg_db", cfg.database || "");
        update("src_pg_user", cfg.user || "");
        update("src_pg_password", cfg.password || "");
        update("src_pg_port", cfg.port || "5432");
      } else if (form.connector_type === "s3") {
        update("s3_bucket", cfg.bucket || "");
        update("s3_key", cfg.prefix || "");
        update("s3_file_type", cfg.file_type || "csv");
      } else if (form.connector_type === "snowflake") {
        update("sf_account", cfg.account || "");
        update("sf_user", cfg.user || "");
        update("sf_password", cfg.password || "");
        update("sf_warehouse", cfg.warehouse || "");
        update("sf_database", cfg.database || "");
        update("sf_schema", cfg.schema || "PUBLIC");
        update("sf_role", cfg.role || "");
      } else if (form.connector_type === "api") {
        update("api_url", cfg.base_url || "");
      } else if (form.connector_type === "google_sheets") {
        update("sheet_url", cfg.sheet_url || "");
      } else if (form.connector_type === "csv" || form.connector_type === "excel") {
        update("folder_path", cfg.base_path || "");
        update("s3_file_type", cfg.file_type || "csv");
      }
    }
  };

  useEffect(() => {
    setSelectedConnectionId("");
    setUseExistingConnection(false);
    setConnectionError("");
  }, [form.connector_type]);

  const create = useMutation({
    mutationFn: async () => {
      if (useExistingConnection && !selectedConnectionId) {
        setConnectionError("Please select a saved connection");
        throw new Error("No connection selected");
      }

      let parsedApiConfig: Record<string, unknown> | null = null;
      if (form.connector_type === "api" && form.api_config.trim()) {
        try {
          parsedApiConfig = JSON.parse(form.api_config);
        } catch (e) {
          setApiConfigError("Invalid JSON — please check the syntax.");
          throw new Error("Invalid api_config JSON");
        }
      }

      const payload = {
        ...form,
        api_config: parsedApiConfig,
        schedule: buildCron(schedule),
        timezone: schedule.timezone,
        incremental_column: form.sync_mode === "incremental" ? form.incremental_column : null,
        after_first_run: form.option === "3" ? form.after_first_run || null : null,
        connection_id: useExistingConnection ? parseInt(selectedConnectionId) : null,
      };
      const response = await api.post("/create_pipeline", payload);
      return response.data;
    },
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });

      setForm(base);
      setSchedule(defaultSchedule);
      setUseExistingConnection(false);
      setSelectedConnectionId("");
      setConnectionError("");
      setApiConfigError("");
      setStepError("");
      setCurrentStep(1);
    },
  });

  const validateStep = (step: number): string => {
    if (step === 1) {
      if (!form.pipeline_name.trim()) return "Pipeline name is required.";
      if (!form.table_name.trim()) return "Target table is required.";
      if (form.option === "3" && !form.after_first_run) return "Select what happens after the first run.";
      if (form.sync_mode === "incremental" && !form.incremental_column.trim()) return "Incremental column is required.";
      return "";
    }
    if (step === 2) {
      if (useExistingConnection && !selectedConnectionId) return "Please select a saved connection, or switch to New Connection.";
      if (!useExistingConnection) {
        if (["csv", "excel"].includes(form.connector_type) && !form.file_path && !form.folder_path) {
          return "Provide a file path or folder path.";
        }
        if (form.connector_type === "google_sheets" && !form.sheet_url.trim()) return "Sheet URL is required.";
        if (form.connector_type === "api" && !form.api_url.trim()) return "API URL is required.";
        if (form.connector_type === "postgres" && (!form.src_pg_host || !form.src_pg_db || !form.src_pg_user || !form.pg_query)) {
          return "Host, database, user, and query are required for Postgres.";
        }
        if (form.connector_type === "s3" && (!form.s3_bucket || !form.s3_key)) return "Bucket and key are required for S3.";
        if (form.connector_type === "snowflake" && (!form.sf_account || !form.sf_user || !form.sf_warehouse || !form.sf_database || !form.sf_query)) {
          return "Account, user, warehouse, database, and query are required for Snowflake.";
        }
      }
      if (form.connector_type === "api" && form.api_config.trim()) {
        try {
          JSON.parse(form.api_config);
        } catch {
          return "Advanced Config has invalid JSON.";
        }
      }
      return "";
    }
    return "";
  };

  const goNext = () => {
    const err = validateStep(currentStep);
    if (err) {
      setStepError(err);
      return;
    }
    setStepError("");
    setCurrentStep((s) => Math.min(s + 1, STEPS.length));
  };

  const goBack = () => {
    setStepError("");
    setCurrentStep((s) => Math.max(s - 1, 1));
  };

  const goToStep = (step: number) => {
    if (step < currentStep) {
      setStepError("");
      setCurrentStep(step);
      return;
    }
    for (let s = currentStep; s < step; s++) {
      const err = validateStep(s);
      if (err) {
        setStepError(err);
        return;
      }
    }
    setStepError("");
    setCurrentStep(step);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setConnectionError("");
    setApiConfigError("");
    setResult(null);
    create.mutate();
  };

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><PlusCircle className="h-5 w-5" /> Create Pipeline</h2>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center">
            {STEPS.map((step, idx) => (
              <div key={step.id} className="flex flex-1 items-center last:flex-none">
                <button type="button" onClick={() => goToStep(step.id)} className="flex items-center gap-2 group">
                  <span
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-medium transition-colors ${
                      step.id === currentStep
                        ? "border-emerald-600 bg-emerald-600 text-white"
                        : step.id < currentStep
                        ? "border-emerald-600 bg-emerald-50 text-emerald-600"
                        : "border-slate-300 bg-white text-slate-400 group-hover:border-slate-400"
                    }`}
                  >
                    {step.id < currentStep ? <Check className="h-4 w-4" /> : step.id}
                  </span>
                  <span
                    className={`hidden text-sm font-medium sm:block ${
                      step.id === currentStep ? "text-slate-950" : step.id < currentStep ? "text-emerald-700" : "text-slate-400"
                    }`}
                  >
                    {step.label}
                  </span>
                </button>
                {idx < STEPS.length - 1 && (
                  <div className={`mx-3 h-0.5 flex-1 ${step.id < currentStep ? "bg-emerald-600" : "bg-slate-200"}`} />
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">
            Step {currentStep} of {STEPS.length}: {STEPS[currentStep - 1].label}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">

            {currentStep === 1 && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <label className="space-y-1 text-sm font-medium">
                    Pipeline name
                    <Input value={form.pipeline_name} onChange={(e) => update("pipeline_name", e.target.value)} placeholder="e.g. daily_sales_sync" required />
                  </label>
                  <label className="space-y-1 text-sm font-medium">
                    Connector
                    <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.connector_type} onChange={(e) => update("connector_type", e.target.value as Connector)}>
                      {(Object.keys(CONNECTOR_LABELS) as Connector[]).map((c) => (
                        <option key={c} value={c}>{CONNECTOR_LABELS[c]}</option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-sm font-medium">
                    Target table
                    <Input value={form.table_name} onChange={(e) => update("table_name", e.target.value)} placeholder="e.g. sales_data" required />
                  </label>
                  <label className="space-y-1 text-sm font-medium">
                    Load option
                    <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.option} onChange={(e) => update("option", e.target.value)}>
                      <option value="1">Append</option>
                      <option value="2">Overwrite</option>
                      <option value="3">Create new</option>
                    </select>
                  </label>
                  <label className="space-y-1 text-sm font-medium">
                    Sync mode
                    <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.sync_mode} onChange={(e) => update("sync_mode", e.target.value)}>
                      <option value="full">Full</option>
                      <option value="incremental">Incremental</option>
                    </select>
                  </label>
                </div>

                {form.option === "3" && (
                  <label className="block max-w-md space-y-1 text-sm font-medium">
                    After first run
                    <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.after_first_run} onChange={(e) => update("after_first_run", e.target.value)}>
                      <option value="">Select...</option>
                      <option value="1">Then append</option>
                      <option value="2">Then overwrite</option>
                    </select>
                  </label>
                )}
                {form.sync_mode === "incremental" && (
                  <label className="block max-w-md space-y-1 text-sm font-medium">
                    Incremental column
                    <Input value={form.incremental_column} onChange={(e) => update("incremental_column", e.target.value)} placeholder="e.g. updated_at" />
                  </label>
                )}
              </div>
            )}

            {currentStep === 2 && (
              <div className="space-y-4">
                {SUPPORTS_CONNECTIONS.includes(form.connector_type) && (
                  <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center gap-4">
                      <label className="flex items-center gap-2 text-sm font-medium">
                        <input
                          type="radio"
                          name="connectionMode"
                          checked={!useExistingConnection}
                          onChange={() => {
                            setUseExistingConnection(false);
                            setSelectedConnectionId("");
                            setConnectionError("");
                          }}
                        />
                        <Link2Off className="h-4 w-4" />
                        New Connection
                      </label>
                      <label className="flex items-center gap-2 text-sm font-medium">
                        <input
                          type="radio"
                          name="connectionMode"
                          checked={useExistingConnection}
                          onChange={() => setUseExistingConnection(true)}
                        />
                        <Link2 className="h-4 w-4" />
                        Use Saved Connection
                      </label>
                    </div>
                    {useExistingConnection && (
                      <div className="mt-3">
                        {connections.isLoading ? (
                          <p className="text-sm text-muted-foreground">Loading connections...</p>
                        ) : filteredConnections.length === 0 ? (
                          <p className="text-sm text-red-500">No saved connections for this connector type. Please create a new connection.</p>
                        ) : (
                          <select
                            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                            value={selectedConnectionId}
                            onChange={(e) => {
                              setSelectedConnectionId(e.target.value);
                              setConnectionError("");
                              populateFromConnection(e.target.value);
                            }}
                          >
                            <option value="">Select a connection</option>
                            {filteredConnections.map((conn: any) => (
                              <option key={conn.id} value={conn.id}>{conn.name}</option>
                            ))}
                          </select>
                        )}
                        {connectionError && <p className="mt-2 text-sm text-red-500">{connectionError}</p>}
                      </div>
                    )}
                  </div>
                )}

                {!useExistingConnection && (
                  <>
                    {["csv", "excel"].includes(form.connector_type) && (
                      <div className="space-y-3">
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                          <Input placeholder="File path" value={form.file_path} onChange={(e) => update("file_path", e.target.value)} />
                          <Input placeholder="Folder path (all files in it)" value={form.folder_path} onChange={(e) => update("folder_path", e.target.value)} />
                        </div>
                        <FolderUpload
                          connectorType={form.connector_type as "csv" | "excel"}
                          onFolderResolved={(folderPath) => { update("folder_path", folderPath); update("file_path", ""); }}
                          onFileResolved={(filePath) => { update("file_path", filePath); update("folder_path", ""); }}
                        />
                      </div>
                    )}
                    {form.connector_type === "google_sheets" && (
                      <Input placeholder="Sheet URL" value={form.sheet_url} onChange={(e) => update("sheet_url", e.target.value)} />
                    )}
                    {form.connector_type === "api" && (
                      <div className="space-y-2">
                        <Input placeholder="API URL" value={form.api_url} onChange={(e) => update("api_url", e.target.value)} />
                        <label className="space-y-1 text-sm font-medium block">
                          Advanced Config (optional JSON — method, auth_type, body, pagination, etc.)
                          <textarea
                            className="min-h-40 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                            placeholder={`{\n  "method": "GET",\n  "records_path": "products"\n}`}
                            value={form.api_config}
                            onChange={(e) => {
                              update("api_config", e.target.value);
                              setApiConfigError("");
                            }}
                          />
                        </label>
                        {apiConfigError && <p className="text-sm text-red-500">{apiConfigError}</p>}
                      </div>
                    )}
                    {form.connector_type === "postgres" && (
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <Input placeholder="Host" value={form.src_pg_host} onChange={(e) => update("src_pg_host", e.target.value)} />
                        <Input placeholder="Database" value={form.src_pg_db} onChange={(e) => update("src_pg_db", e.target.value)} />
                        <Input placeholder="User" value={form.src_pg_user} onChange={(e) => update("src_pg_user", e.target.value)} />
                        <Input placeholder="Password" type="password" value={form.src_pg_password} onChange={(e) => update("src_pg_password", e.target.value)} />
                        <Input placeholder="Port" value={form.src_pg_port} onChange={(e) => update("src_pg_port", e.target.value)} />
                        <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={form.pg_query} onChange={(e) => update("pg_query", e.target.value)} />
                      </div>
                    )}
                    {form.connector_type === "s3" && (
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                        <Input placeholder="Bucket" value={form.s3_bucket} onChange={(e) => update("s3_bucket", e.target.value)} />
                        <Input placeholder="Key" value={form.s3_key} onChange={(e) => update("s3_key", e.target.value)} />
                        <Input placeholder="File type" value={form.s3_file_type} onChange={(e) => update("s3_file_type", e.target.value)} />
                      </div>
                    )}
                    {form.connector_type === "snowflake" && (
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <Input placeholder="Account (e.g. XROJPNQ-RO43084)" value={form.sf_account} onChange={(e) => update("sf_account", e.target.value)} />
                        <Input placeholder="User" value={form.sf_user} onChange={(e) => update("sf_user", e.target.value)} />
                        <Input placeholder="Password" type="password" value={form.sf_password} onChange={(e) => update("sf_password", e.target.value)} />
                        <Input placeholder="Warehouse" value={form.sf_warehouse} onChange={(e) => update("sf_warehouse", e.target.value)} />
                        <Input placeholder="Database" value={form.sf_database} onChange={(e) => update("sf_database", e.target.value)} />
                        <Input placeholder="Schema (default PUBLIC)" value={form.sf_schema} onChange={(e) => update("sf_schema", e.target.value)} />
                        <Input placeholder="Role (optional)" value={form.sf_role} onChange={(e) => update("sf_role", e.target.value)} />
                        <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={form.sf_query} onChange={(e) => update("sf_query", e.target.value)} />
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {currentStep === 3 && (
              <div className="space-y-4">
                <SchedulerFields value={schedule} onChange={setSchedule} />
              </div>
            )}

            {currentStep === 4 && (
              <div className="space-y-4">
                <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
                  <h3 className="mb-3 font-semibold text-slate-950">Review your pipeline</h3>
                  <dl className="grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2">
                    <div><dt className="text-muted-foreground">Pipeline name</dt><dd className="font-medium">{form.pipeline_name || "—"}</dd></div>
                    <div><dt className="text-muted-foreground">Connector</dt><dd className="font-medium">{CONNECTOR_LABELS[form.connector_type]}</dd></div>
                    <div><dt className="text-muted-foreground">Target table</dt><dd className="font-medium">{form.table_name || "—"}</dd></div>
                    <div><dt className="text-muted-foreground">Load option</dt><dd className="font-medium">{{ "1": "Append", "2": "Overwrite", "3": "Create new" }[form.option]}</dd></div>
                    <div><dt className="text-muted-foreground">Sync mode</dt><dd className="font-medium capitalize">{form.sync_mode}</dd></div>
                    <div><dt className="text-muted-foreground">Schedule</dt><dd className="font-medium">{buildCron(schedule)} ({schedule.timezone})</dd></div>
                    <div className="md:col-span-2">
                      <dt className="text-muted-foreground">Source</dt>
                      <dd className="font-medium">
                        {useExistingConnection
                          ? `Saved connection: ${filteredConnections.find((c: any) => String(c.id) === selectedConnectionId)?.name || selectedConnectionId}`
                          : form.file_path || form.folder_path || form.sheet_url || form.api_url || form.src_pg_host || form.s3_bucket || form.sf_account || "—"}
                      </dd>
                    </div>
                  </dl>
                </div>

                <p className="text-sm text-muted-foreground">
                  Everything look right? Click <span className="font-medium text-slate-950">Create Pipeline</span> below to finish.
                </p>
              </div>
            )}

            {stepError && <p className="text-sm text-red-500">{stepError}</p>}

            <div className="flex items-center justify-between border-t border-slate-100 pt-4">
              <Button type="button" variant="outline" onClick={goBack} disabled={currentStep === 1}>
                <ChevronLeft className="h-4 w-4" /> Back
              </Button>

              {currentStep < STEPS.length ? (
                <Button type="button" onClick={goNext}>
                  Next <ChevronRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button type="submit" disabled={create.isPending}>
                  {create.isPending ? <Loader2 className="animate-spin" /> : <PlusCircle />} Create Pipeline
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {result && (
        <Card className="border-emerald-200 bg-emerald-50">
          <CardContent className="flex items-start gap-3 p-4">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            <div className="space-y-1">
              <p className="font-medium text-emerald-900">Pipeline created successfully</p>
              <p className="text-sm text-emerald-800">
                <span className="font-medium">{result.dag_id}</span> is set up and will start running on schedule.
              </p>
              {result.message && <p className="text-xs text-emerald-700">{result.message}</p>}
            </div>
          </CardContent>
        </Card>
      )}

      {create.error && (
        <Card className="border-rose-200 bg-rose-50">
          <CardContent className="flex items-start gap-3 p-4">
            <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
            <div className="space-y-1">
              <p className="font-medium text-rose-900">Couldn't create pipeline</p>
              <p className="text-sm text-rose-800">
                {(create.error as any)?.response?.data?.detail?.error
                  || (create.error as any)?.response?.data?.detail
                  || (create.error as Error).message}
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};