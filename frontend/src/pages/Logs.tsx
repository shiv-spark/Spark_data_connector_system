import { FormEvent, useState, useEffect, useRef } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ScrollText, Search, MessageCircle, Send, Loader2, KeyRound, Eye, EyeOff } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { fdt } from "@/lib/format";

type LogsTable =
  | "pipeline_logs"
  | "pipeline_runs"
  | "airflow_pipeline_runs"
  | "pipeline_dag_logs"
  | "pipeline_metrics";

const tableLabels: Record<LogsTable, string> = {
  pipeline_logs: "Pipeline Logs",
  pipeline_runs: "Pipeline Runs",
  airflow_pipeline_runs: "Airflow Pipeline Runs",
  pipeline_dag_logs: "Pipeline DAG Logs",
  pipeline_metrics: "Pipeline Metrics",
};

const ALL_TABLES: LogsTable[] = [
  "pipeline_logs",
  "pipeline_runs",
  "airflow_pipeline_runs",
  "pipeline_dag_logs",
  "pipeline_metrics",
];

type ChatMessage = { role: "user" | "assistant"; content: string };

const OPENROUTER_KEY_STORAGE = "data_connector_openrouter_key";
const OPENROUTER_MODEL_STORAGE = "data_connector_openrouter_model";
const FALLBACK_DEFAULT_MODEL = "openrouter/free";

export const Logs = () => {
  const [pipeline, setPipeline] = useState("");
  const [activePipeline, setActivePipeline] = useState("");
  const [selectedTable, setSelectedTable] = useState<LogsTable>("pipeline_runs");

  const [openrouterKey, setOpenrouterKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [model, setModel] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatPipelineFilter, setChatPipelineFilter] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const backendConfig = useQuery({
    queryKey: ["chatbot-config"],
    queryFn: async () => (await api.get("/chatbot/config")).data,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    const savedKey = localStorage.getItem(OPENROUTER_KEY_STORAGE);
    if (savedKey) setOpenrouterKey(savedKey);
    const savedModel = localStorage.getItem(OPENROUTER_MODEL_STORAGE);
    if (savedModel) setModel(savedModel);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const saveKey = (value: string) => {
    setOpenrouterKey(value);
    if (value) {
      localStorage.setItem(OPENROUTER_KEY_STORAGE, value);
    } else {
      localStorage.removeItem(OPENROUTER_KEY_STORAGE);
    }
  };

  const saveModel = (value: string) => {
    setModel(value);
    if (value) {
      localStorage.setItem(OPENROUTER_MODEL_STORAGE, value);
    } else {
      localStorage.removeItem(OPENROUTER_MODEL_STORAGE);
    }
  };

  const hasBackendKey = backendConfig.data?.has_backend_key ?? false;
  const backendDefaultModel = backendConfig.data?.default_model ?? FALLBACK_DEFAULT_MODEL;

  const chat = useMutation({
    mutationFn: async (userMessage: string) => {
      const nextMessages: ChatMessage[] = [...messages, { role: "user", content: userMessage }];
      setMessages(nextMessages);

      const response = await api.post("/chatbot", {
        messages: nextMessages,
        openrouter_key: openrouterKey || undefined,
        model: model || undefined,
        pipeline_name: chatPipelineFilter.trim() || null,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setMessages((current) => [...current, { role: "assistant", content: data.answer }]);
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail ?? error.message ?? "Chatbot request failed.";
      setMessages((current) => [...current, { role: "assistant", content: `⚠️ ${detail}` }]);
    },
  });

  const submitChat = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = chatInput.trim();
    if (!trimmed || chat.isPending) return;
    if (!openrouterKey && !hasBackendKey) {
      setMessages((current) => [
        ...current,
        { role: "assistant", content: "⚠️ No API key available — enter your own OpenRouter key above, or ask an admin to configure a backend default." },
      ]);
      return;
    }
    setChatInput("");
    chat.mutate(trimmed);
  };

  const logs = useQuery({
    queryKey: ["pipeline-logs", activePipeline],
    enabled: !!activePipeline,
    queryFn: async () => (await api.get(`/pipeline/${activePipeline}/logs?limit=20`)).data,
  });

  const tableData = useQuery({
    queryKey: ["logs-table", selectedTable],
    queryFn: async () => (await api.get(`/logs_table/${selectedTable}?limit=50`)).data,
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setActivePipeline(pipeline.trim());
  };

  const rows: any[] = tableData.data?.data ?? [];
  const columns: string[] = tableData.data?.columns ?? (rows[0] ? Object.keys(rows[0]) : []);

  const STATUS_COLUMNS = new Set(["status"]);

  const formatCell = (col: string, value: any) => {
    if (value === null || value === undefined) return "-";
    if (STATUS_COLUMNS.has(col)) return <StatusBadge status={String(value)} />;
    if (col.endsWith("_at") || col.endsWith("_date") || col === "logged_at" || col === "start_time" || col === "end_time" || col === "log_time") {
      return fdt(value);
    }
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><ScrollText className="h-5 w-5" /> Logs</h2>

      {/* Chatbot */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2"><MessageCircle className="h-4 w-4" /> Pipeline Assistant</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium">
              <span className="flex items-center gap-1">
                <KeyRound className="h-3.5 w-3.5" /> OpenRouter API key
                {hasBackendKey && <span className="text-xs font-normal text-muted-foreground">(optional — backend default available)</span>}
              </span>
              <div className="relative">
                <Input
                  type={showKey ? "text" : "password"}
                  placeholder={hasBackendKey ? "Leave blank to use backend default" : "sk-or-..."}
                  value={openrouterKey}
                  onChange={(e) => saveKey(e.target.value)}
                  className="pr-10"
                />
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                  onClick={() => setShowKey((v) => !v)}
                  tabIndex={-1}
                >
                  {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </label>
            <label className="space-y-1 text-sm font-medium">
              Focus on pipeline (optional)
              <Input
                placeholder="e.g. sales_csv"
                value={chatPipelineFilter}
                onChange={(e) => setChatPipelineFilter(e.target.value)}
              />
            </label>
            <label className="space-y-1 text-sm font-medium md:col-span-2">
              Model
              <Input
                placeholder={`Leave blank to use backend default (${backendDefaultModel})`}
                value={model}
                onChange={(e) => saveModel(e.target.value)}
              />
            </label>
          </div>
          <p className="text-xs text-muted-foreground">
            Find model IDs at{" "}
            <a href="https://openrouter.ai/models" target="_blank" rel="noreferrer" className="underline hover:text-foreground">
              openrouter.ai/models
            </a>
            . Free models end in <code className="rounded bg-muted px-1 text-foreground">:free</code>.
            {hasBackendKey
              ? " A shared backend key/model is configured — your own values here are optional overrides."
              : " No backend default is configured — you must provide your own key to use the assistant."}
          </p>
          <p className="text-xs text-muted-foreground">
            Your key/model are stored only in your browser's local storage and sent only to your own backend.
          </p>

          <div className="max-h-[420px] space-y-3 overflow-y-auto rounded-md border border-border bg-muted p-3">
            {messages.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Ask about pipeline failures, recent runs, error patterns, or system health — answers are grounded in your live database.
              </p>
            ) : (
              messages.map((msg, i) => (
                <div
                  key={i}
                  className={`rounded-lg px-3 py-2 text-sm ${
                    msg.role === "user"
                      ? "ml-auto max-w-[85%] bg-blue-600 text-white"
                      : "max-w-[90%] bg-card text-foreground shadow-sm"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
              ))
            )}
            {chat.isPending && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Thinking...
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <form onSubmit={submitChat} className="flex gap-3">
            <Input
              placeholder="Why did pipeline_sales_csv fail today?"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              disabled={chat.isPending}
            />
            <Button type="submit" disabled={chat.isPending || !chatInput.trim()}>
              {chat.isPending ? <Loader2 className="animate-spin" /> : <Send />} Send
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Pipeline Log Lookup */}
      <Card>
        <CardHeader><CardTitle className="text-sm">Pipeline Log Lookup</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="flex gap-3">
            <Input placeholder="Pipeline id or name" value={pipeline} onChange={(e) => setPipeline(e.target.value)} />
            <Button type="submit"><Search /> Load Logs</Button>
          </form>
        </CardContent>
      </Card>

      {activePipeline && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              Latest Logs for {activePipeline}
              {logs.data?.count ? <span className="ml-2 text-xs font-normal text-muted-foreground">({logs.data.count} runs)</span> : null}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {logs.isFetching ? <p className="text-sm text-muted-foreground">Loading logs...</p> : logs.error ? (
              <p className="text-sm text-destructive">{(logs.error as any)?.response?.data?.detail ?? (logs.error as Error).message}</p>
            ) : (
              <div className="space-y-4">
                {(logs.data?.logs ?? []).map((entry: any, i: number) => (
                  <div key={entry.dag_run_id ?? i} className="space-y-2 rounded-md border border-border bg-card p-3">
                    <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                      <StatusBadge status={entry.status ?? "UNKNOWN"} />
                      <span>Run: {entry.dag_run_id ?? "-"}</span>
                      <span>Source: {logs.data?.source ?? "-"}</span>
                      <span>Logged: {fdt(entry.logged_at)}</span>
                    </div>
                    <pre className="max-h-[400px] overflow-auto rounded-md bg-background p-4 text-xs text-foreground">
                      {entry.log ?? "No log content."}
                    </pre>
                  </div>
                ))}
                {(logs.data?.logs ?? []).length === 0 && (
                  <p className="text-sm text-muted-foreground">No log content.</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Browse Log / Metrics Tables */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle className="text-sm">Browse Log / Metrics Tables</CardTitle>
          <label className="flex items-center gap-2 text-sm font-medium">
            Table
            <select
              className="h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground"
              value={selectedTable}
              onChange={(e) => setSelectedTable(e.target.value as LogsTable)}
            >
              {ALL_TABLES.map((t) => (
                <option key={t} value={t}>{tableLabels[t]}</option>
              ))}
            </select>
          </label>
        </CardHeader>
        <CardContent>
          {tableData.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading {tableLabels[selectedTable]}...</p>
          ) : tableData.error ? (
            <p className="text-sm text-destructive">
              {(tableData.error as any)?.response?.data?.detail ?? (tableData.error as Error).message}
            </p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No rows found in {tableLabels[selectedTable]}.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
                    {columns.map((col) => (
                      <th key={col} className="py-3 pr-4 whitespace-nowrap">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={row.id ?? row.run_id ?? i} className="border-b border-border">
                      {columns.map((col) => (
                        <td key={col} className="max-w-xs truncate py-3 pr-4 text-muted-foreground">
                          {formatCell(col, row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {tableData.data?.pagination && (
                <p className="mt-3 text-xs text-muted-foreground">
                  Showing {rows.length} of {tableData.data.pagination.total} rows
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
