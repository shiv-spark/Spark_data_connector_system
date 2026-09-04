import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  History,
  Lightbulb,
  ListChecks,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings2,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { api, fetchPipelineHistory, restorePipelineVersion } from "@/lib/api";
import { HistoryPanel } from "@/components/console/HistoryPanel";
import { QualityGateSummary } from "@/components/console/QualityGateSummary";
import { DataQualityBuilder, PreviewConnector } from "@/components/DataQualityBuilder";
import { SchemaBuilder } from "@/components/SchemaBuilder";
import { OverflowMenu, MenuItem, MenuSeparator } from "@/components/console/OverflowMenu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Panel, PanelBar, PanelSearch, Row, Meta, EmptyState, RowSkeleton } from "@/components/console/Panel";
import { StatusBadge } from "@/components/StatusBadge";
import { fdt } from "@/lib/format";
import { SchedulerFields } from "@/components/SchedulerFields";
import { buildCron, describeSchedule, scheduleFromCron, ScheduleState } from "@/lib/schedule";
import { PageHeader } from "@/components/PageHeader";
import { StatTile } from "@/components/StatTile";
import { SourceTablePicker } from "@/components/SourceTablePicker";
import { parseTableFromSimpleSelect } from "@/lib/sourceQuery";
import { cn } from "@/lib/utils";

// Plain-language names for what's otherwise a raw connector_type string —
// this is the one place a non-technical person reads it, so it should read
// like a product name, not a config key.
const SOURCE_LABELS: Record<string, string> = {
  csv: "CSV file",
  excel: "Excel file",
  google_sheets: "Google Sheets",
  api: "API",
  postgres: "PostgreSQL",
  mysql: "MySQL",
  oracle: "Oracle",
  mongodb: "MongoDB",
  s3: "Amazon S3",
  snowflake: "Snowflake",
  salesforce: "Salesforce",
  hubspot: "HubSpot",
  zoho: "Zoho CRM",
};

const sourceLabel = (connectorType?: string) =>
  (connectorType && SOURCE_LABELS[connectorType]) || connectorType || "Unknown source";

// "pipeline_daily_sales_sync" -> "Daily sales sync" — the friendly title;
// the raw id stays visible underneath in small type for anyone who does
// need it (support tickets, matching a DAG file, etc).
const humanizeName = (rawName: string) => {
  const cleaned = rawName.replace(/^pipeline_/, "").replace(/[_-]+/g, " ").trim();
  if (!cleaned) return rawName;
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
};

// One plain sentence describing what the pipeline does, e.g.
// "Copies data from PostgreSQL into `leads`, every 5 minutes."
const describePipeline = (row: {
  connector_type?: string;
  table_name?: string;
  schedule?: string;
  timezone?: string;
}) => {
  const source = sourceLabel(row.connector_type);
  const schedulePart = row.schedule
    ? describeSchedule(scheduleFromCron(row.schedule, row.timezone ?? "Asia/Kolkata")).replace(/^Runs\s/, "")
    : "on a schedule";
  const target = row.table_name ? ` into "${row.table_name}"` : "";
  return `Copies data from ${source}${target}, ${schedulePart}.`;
};

type Pipeline = {
  dag_id: string;
  size_kb?: number;
  schedule?: string;
  timezone?: string;
  connector_type?: string;
  table_name?: string;
  option?: string;
  after_first_run?: string | null;
  sync_mode?: string;
  incremental_column?: string | null;
  folder_path?: string | null;
  file_path?: string | null;
  sheet_url?: string | null;
  api_url?: string | null;
  src_pg_host?: string | null;
  src_pg_db?: string | null;
  src_pg_user?: string | null;
  src_pg_port?: string | null;
  pg_query?: string | null;
  src_my_host?: string | null;
  src_my_db?: string | null;
  src_my_user?: string | null;
  src_my_port?: string | null;
  my_query?: string | null;
  src_ora_host?: string | null;
  src_ora_db?: string | null;
  src_ora_user?: string | null;
  src_ora_port?: string | null;
  ora_query?: string | null;
  src_mongo_host?: string | null;
  src_mongo_db?: string | null;
  src_mongo_user?: string | null;
  src_mongo_port?: string | null;
  src_mongo_connection_string?: string | null;
  mongo_collection?: string | null;
  mongo_query?: string | null;
  s3_bucket?: string | null;
  s3_key?: string | null;
  s3_file_type?: string | null;
  sf_account?: string | null;
  sf_user?: string | null;
  sf_warehouse?: string | null;
  sf_database?: string | null;
  sf_schema?: string | null;
  sf_role?: string | null;
  sf_query?: string | null;
  sf_crm_instance_url?: string | null;
  sf_crm_login_url?: string | null;
  sf_crm_client_id?: string | null;
  sf_crm_username?: string | null;
  sf_crm_object_name?: string | null;
  sf_crm_fields?: string[] | null;
  sf_crm_soql_query?: string | null;
  hs_object_type?: string | null;
  hs_properties?: string[] | null;
  zoho_accounts_url?: string | null;
  zoho_api_domain?: string | null;
  zoho_client_id?: string | null;
  zoho_module?: string | null;
  zoho_fields?: string[] | null;
  zoho_criteria?: string | null;
  has_src_pg_password?: boolean;
  has_sf_password?: boolean;
  has_s3_secret_key?: boolean;
  has_src_my_password?: boolean;
  has_src_ora_password?: boolean;
  has_src_mongo_password?: boolean;
  has_sf_crm_access_token?: boolean;
  has_sf_crm_client_secret?: boolean;
  has_sf_crm_password?: boolean;
  has_sf_crm_security_token?: boolean;
  has_hs_access_token?: boolean;
  has_zoho_access_token?: boolean;
  has_zoho_refresh_token?: boolean;
  has_zoho_client_secret?: boolean;
  quality_connection_id?: number | null;
  df_quality_config?: Record<string, unknown> | null;
  df_quality_on_fail?: "warn" | "block";
  custom_schema?: Record<string, string> | null;
};

type EditState = {
  schedule: ScheduleState;
  table_name: string;
  option: string;
  after_first_run: string;
  sync_mode: string;
  incremental_column: string;
  folder_path: string;
  file_path: string;
  sheet_url: string;
  api_url: string;
  src_pg_host: string;
  src_pg_db: string;
  src_pg_user: string;
  src_pg_password: string;
  src_pg_port: string;
  pg_query: string;
  pg_mode: "table" | "query";
  pg_table_input: string;
  src_my_host: string;
  src_my_db: string;
  src_my_user: string;
  src_my_password: string;
  src_my_port: string;
  my_query: string;
  src_ora_host: string;
  src_ora_db: string;
  src_ora_user: string;
  src_ora_password: string;
  src_ora_port: string;
  ora_query: string;
  src_mongo_host: string;
  src_mongo_db: string;
  src_mongo_user: string;
  src_mongo_password: string;
  src_mongo_port: string;
  src_mongo_connection_string: string;
  mongo_collection: string;
  mongo_query: string;
  s3_bucket: string;
  s3_key: string;
  s3_file_type: string;
  sf_account: string;
  sf_user: string;
  sf_password: string;
  sf_warehouse: string;
  sf_database: string;
  sf_schema: string;
  sf_role: string;
  sf_query: string;
  sf_mode: "table" | "query";
  sf_table_input: string;
  sf_crm_access_token: string;
  sf_crm_instance_url: string;
  sf_crm_login_url: string;
  sf_crm_client_id: string;
  sf_crm_client_secret: string;
  sf_crm_username: string;
  sf_crm_password: string;
  sf_crm_security_token: string;
  sf_crm_object_name: string;
  sf_crm_soql_query: string;
  hs_access_token: string;
  hs_object_type: string;
  hs_properties: string;
  zoho_access_token: string;
  zoho_refresh_token: string;
  zoho_client_id: string;
  zoho_client_secret: string;
  zoho_accounts_url: string;
  zoho_api_domain: string;
  zoho_module: string;
  zoho_criteria: string;
  df_quality_config: Record<string, unknown> | null;
  df_quality_on_fail: "warn" | "block";
  custom_schema: Record<string, string> | null;
};

const fetchPipelines = async (): Promise<Pipeline[]> => {
  const r = await api.get("/pipelines");
  return r.data?.pipelines ?? [];
};

const fetchStatus = async (name: string) => {
  const r = await api.get(`/pipeline/${name}/status`);
  return r.data;
};

const fetchPipelineQualityLatest = async (name: string) => {
  const r = await api.get(`/pipeline/${name}/quality-latest`);
  return r.data as {
    has_snapshot: boolean;
    ingest_status?: string;
    df_quality?: any;
    quality?: any;
    created_at?: string;
  };
};

// Structured "last run quality" panel for one pipeline — reuses the same
// QualityGateSummary component DirectIngest uses, so a scheduled run's
// data-quality failures (and each check's fix_suggestion) are readable
// here instead of only inside raw pipeline logs.
//
// `onFixInConfig` is threaded straight through to QualityGateSummary: when
// someone reads a failed check (or asks the AI for help) they get a button
// that jumps them to the Configure tab instead of leaving them stuck with
// advice they have no way to act on.
const PipelineQualityPanel = ({
  pipelineName,
  connectionId,
  onFixInConfig,
}: {
  pipelineName: string;
  connectionId?: number | null;
  onFixInConfig?: (target?: "df_quality" | "table_quality", column?: string) => void;
}) => {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["pipeline-quality-latest", pipelineName],
    queryFn: () => fetchPipelineQualityLatest(pipelineName),
  });

  if (isLoading) {
    return <p className="text-xs text-muted-foreground">Loading last run's quality result…</p>;
  }
  if (isError) {
    return <p className="text-xs text-destructive">Couldn't load the quality result for this pipeline.</p>;
  }
  if (!data?.has_snapshot) {
    return (
      <div className="empty !py-10">
        <span className="empty-mark">
          <ShieldCheck className="h-5 w-5" strokeWidth={1.7} />
        </span>
        <p className="text-[13px] font-semibold text-foreground">No quality checks have run yet</p>
        <p className="max-w-[19rem] text-[12px] leading-relaxed text-muted-foreground">
          Add checks under Direct Ingest or Create Pipeline's quality builder to see results here after
          the next run.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {data.created_at && (
        <p className="text-xs text-muted-foreground">
          Last run: {new Date(data.created_at).toLocaleString()} — {data.ingest_status}
        </p>
      )}
      <QualityGateSummary
        title="Pre-ingest data quality"
        gate={data.df_quality}
        connectionId={connectionId}
        onFixInConfig={onFixInConfig}
        fixTarget="df_quality"
      />
      <QualityGateSummary
        title="Post-load data quality"
        gate={data.quality}
        connectionId={connectionId}
        onFixInConfig={onFixInConfig}
        fixTarget="table_quality"
      />
    </div>
  );
};

const buildEditState = (pipeline: Pipeline): EditState => ({
  schedule: scheduleFromCron(pipeline.schedule ?? "*/5 * * * *", pipeline.timezone ?? "Asia/Kolkata"),
  table_name: pipeline.table_name ?? "",
  option: pipeline.option ?? "1",
  after_first_run: pipeline.after_first_run ?? "",
  sync_mode: pipeline.sync_mode ?? "full",
  incremental_column: pipeline.incremental_column ?? "",
  folder_path: pipeline.folder_path ?? "",
  file_path: pipeline.file_path ?? "",
  sheet_url: pipeline.sheet_url ?? "",
  api_url: pipeline.api_url ?? "",
  src_pg_host: pipeline.src_pg_host ?? "",
  src_pg_db: pipeline.src_pg_db ?? "",
  src_pg_user: pipeline.src_pg_user ?? "",
  src_pg_password: "",
  src_pg_port: pipeline.src_pg_port ?? "5432",
  pg_query: pipeline.pg_query ?? "",
  pg_mode: parseTableFromSimpleSelect(pipeline.pg_query) ? "table" : "query",
  pg_table_input: parseTableFromSimpleSelect(pipeline.pg_query) ?? "",
  src_my_host: pipeline.src_my_host ?? "",
  src_my_db: pipeline.src_my_db ?? "",
  src_my_user: pipeline.src_my_user ?? "",
  src_my_password: "",
  src_my_port: pipeline.src_my_port ?? "3306",
  my_query: pipeline.my_query ?? "",
  src_ora_host: pipeline.src_ora_host ?? "",
  src_ora_db: pipeline.src_ora_db ?? "",
  src_ora_user: pipeline.src_ora_user ?? "",
  src_ora_password: "",
  src_ora_port: pipeline.src_ora_port ?? "1521",
  ora_query: pipeline.ora_query ?? "",
  src_mongo_host: pipeline.src_mongo_host ?? "",
  src_mongo_db: pipeline.src_mongo_db ?? "",
  src_mongo_user: pipeline.src_mongo_user ?? "",
  src_mongo_password: "",
  src_mongo_port: pipeline.src_mongo_port ?? "27017",
  src_mongo_connection_string: pipeline.src_mongo_connection_string ?? "",
  mongo_collection: pipeline.mongo_collection ?? "",
  mongo_query: pipeline.mongo_query ?? "",
  s3_bucket: pipeline.s3_bucket ?? "",
  s3_key: pipeline.s3_key ?? "",
  s3_file_type: pipeline.s3_file_type ?? "csv",
  sf_account: pipeline.sf_account ?? "",
  sf_user: pipeline.sf_user ?? "",
  sf_password: "",
  sf_warehouse: pipeline.sf_warehouse ?? "",
  sf_database: pipeline.sf_database ?? "",
  sf_schema: pipeline.sf_schema ?? "PUBLIC",
  sf_role: pipeline.sf_role ?? "",
  sf_query: pipeline.sf_query ?? "",
  sf_mode: parseTableFromSimpleSelect(pipeline.sf_query) ? "table" : "query",
  sf_table_input: parseTableFromSimpleSelect(pipeline.sf_query) ?? "",
  sf_crm_access_token: "",
  sf_crm_instance_url: pipeline.sf_crm_instance_url ?? "",
  sf_crm_login_url: pipeline.sf_crm_login_url ?? "https://login.salesforce.com",
  sf_crm_client_id: pipeline.sf_crm_client_id ?? "",
  sf_crm_client_secret: "",
  sf_crm_username: pipeline.sf_crm_username ?? "",
  sf_crm_password: "",
  sf_crm_security_token: "",
  sf_crm_object_name: pipeline.sf_crm_object_name ?? "",
  sf_crm_soql_query: pipeline.sf_crm_soql_query ?? "",
  hs_access_token: "",
  hs_object_type: pipeline.hs_object_type ?? "contacts",
  hs_properties: (pipeline.hs_properties ?? []).join(", "),
  zoho_access_token: "",
  zoho_refresh_token: "",
  zoho_client_id: pipeline.zoho_client_id ?? "",
  zoho_client_secret: "",
  zoho_accounts_url: pipeline.zoho_accounts_url ?? "https://accounts.zoho.com",
  zoho_api_domain: pipeline.zoho_api_domain ?? "https://www.zohoapis.com",
  zoho_module: pipeline.zoho_module ?? "",
  zoho_criteria: pipeline.zoho_criteria ?? "",
  df_quality_config: pipeline.df_quality_config ?? null,
  df_quality_on_fail: pipeline.df_quality_on_fail ?? "warn",
  custom_schema: pipeline.custom_schema ?? null,
});

type PipelineRow = Pipeline & {
  name: string;
  status: string;
  next_run: string | null;
};

// ── Side detail panel ──────────────────────────────────────────────────────
// Everything about one pipeline — schedule/source config and its last data
// quality result — lives here, behind two tabs, instead of stacked inline
// accordions in the list. It sits beside the list (like the version-history
// panel already does) so opening it never reflows the rows above/below it.
const PipelineManagePanel = ({
  row,
  editState,
  tab,
  onTabChange,
  onUpdateEdit,
  onClose,
  onSave,
  saving,
  onPauseResume,
  pauseResumePending,
  onOpenHistory,
  onDelete,
  highlightConfig,
  highlightTarget,
  highlightColumn,
  highlightToken,
  onFixInConfig,
}: {
  row: PipelineRow;
  editState: EditState;
  tab: "configure" | "quality";
  onTabChange: (tab: "configure" | "quality") => void;
  onUpdateEdit: (patch: Partial<EditState>) => void;
  onClose: () => void;
  onSave: () => void;
  saving: boolean;
  onPauseResume: () => void;
  pauseResumePending: boolean;
  onOpenHistory: () => void;
  onDelete: () => void;
  highlightConfig: boolean;
  /** Which fix the person just clicked "Apply"/"Fix in Configure" for. */
  highlightTarget: "df_quality" | "table_quality" | null;
  /** Which column that fix's failing check pointed at, if any (best-effort). */
  highlightColumn: string | null;
  /** Bumped on every "Fix in Configure" click, so re-clicking re-scrolls. */
  highlightToken: number;
  /** Jump to Configure AND flag that we arrived there because of a quality-check fix. */
  onFixInConfig: (target?: "df_quality" | "table_quality", column?: string) => void;
}) => {
  const connectorType = row.connector_type ?? "";
  const state = editState;

  // What to POST to /preview_source for this pipeline's current (edited)
  // source config — same shape CreatePipeline/DirectIngest build, just
  // read from `state` instead of a fresh-creation form. Passwords are
  // blank on load (never sent back by the backend) — if a check needs a
  // live preview against a DB source, the person needs to re-type the
  // password above first, same as they would to change the SQL query.
  const previewParams = useMemo<Record<string, unknown> | null>(() => {
    if (connectorType === "csv" || connectorType === "excel") {
      // Folder-based pipelines (folder_path set, no single file_path) have
      // no file_path — fall back to folder_path so the backend can preview
      // the first matching file in it (see /preview_source's folder
      // fallback). Without this, previewParams was always null for
      // folder-based pipelines, so DataQualityBuilder/SchemaBuilder never
      // rendered at all — hiding a previously-saved custom_schema even
      // though it was loaded correctly into edit state.
      if (state.file_path) return { file_path: state.file_path };
      if (state.folder_path) return { folder_path: state.folder_path };
      return null;
    }
    if (connectorType === "postgres") {
      if (!state.pg_query.trim() || !state.src_pg_host || !state.src_pg_db || !state.src_pg_user) return null;
      return {
        src_pg_host: state.src_pg_host, src_pg_db: state.src_pg_db, src_pg_user: state.src_pg_user,
        src_pg_password: state.src_pg_password, src_pg_port: state.src_pg_port, pg_query: state.pg_query,
      };
    }
    if (connectorType === "mysql") {
      if (!state.my_query.trim() || !state.src_my_host || !state.src_my_db || !state.src_my_user) return null;
      return {
        src_my_host: state.src_my_host, src_my_db: state.src_my_db, src_my_user: state.src_my_user,
        src_my_password: state.src_my_password, src_my_port: state.src_my_port, my_query: state.my_query,
      };
    }
    if (connectorType === "oracle") {
      if (!state.ora_query.trim() || !state.src_ora_host || !state.src_ora_db || !state.src_ora_user) return null;
      return {
        src_ora_host: state.src_ora_host, src_ora_db: state.src_ora_db, src_ora_user: state.src_ora_user,
        src_ora_password: state.src_ora_password, src_ora_port: state.src_ora_port, ora_query: state.ora_query,
      };
    }
    if (connectorType === "mongodb") {
      if (!state.mongo_collection.trim()) return null;
      if (!state.src_mongo_connection_string && (!state.src_mongo_host || !state.src_mongo_db)) return null;
      return {
        src_mongo_host: state.src_mongo_host, src_mongo_db: state.src_mongo_db,
        src_mongo_user: state.src_mongo_user, src_mongo_password: state.src_mongo_password,
        src_mongo_port: state.src_mongo_port, src_mongo_connection_string: state.src_mongo_connection_string,
        mongo_collection: state.mongo_collection, mongo_query: state.mongo_query,
      };
    }
    if (connectorType === "snowflake") {
      if (!state.sf_query.trim() || !state.sf_account || !state.sf_user || !state.sf_warehouse || !state.sf_database) return null;
      return {
        sf_account: state.sf_account, sf_user: state.sf_user, sf_password: state.sf_password,
        sf_warehouse: state.sf_warehouse, sf_database: state.sf_database, sf_schema: state.sf_schema,
        sf_role: state.sf_role, sf_query: state.sf_query,
      };
    }
    if (connectorType === "s3") {
      if (!state.s3_bucket || !state.s3_key) return null;
      return { s3_bucket: state.s3_bucket, s3_key: state.s3_key, s3_file_type: state.s3_file_type };
    }
    if (connectorType === "salesforce") {
      if (!state.sf_crm_object_name.trim() && !state.sf_crm_soql_query.trim()) return null;
      return {
        sf_crm_access_token: state.sf_crm_access_token, sf_crm_instance_url: state.sf_crm_instance_url,
        sf_crm_login_url: state.sf_crm_login_url, sf_crm_client_id: state.sf_crm_client_id,
        sf_crm_client_secret: state.sf_crm_client_secret, sf_crm_username: state.sf_crm_username,
        sf_crm_password: state.sf_crm_password, sf_crm_security_token: state.sf_crm_security_token,
        sf_crm_object_name: state.sf_crm_object_name, sf_crm_soql_query: state.sf_crm_soql_query,
      };
    }
    if (connectorType === "hubspot") {
      return { hs_access_token: state.hs_access_token, hs_object_type: state.hs_object_type };
    }
    if (connectorType === "zoho") {
      if (!state.zoho_module.trim()) return null;
      return {
        zoho_access_token: state.zoho_access_token, zoho_refresh_token: state.zoho_refresh_token,
        zoho_client_id: state.zoho_client_id, zoho_client_secret: state.zoho_client_secret,
        zoho_accounts_url: state.zoho_accounts_url, zoho_api_domain: state.zoho_api_domain,
        zoho_module: state.zoho_module, zoho_criteria: state.zoho_criteria,
      };
    }
    if (connectorType === "google_sheets") {
      return state.sheet_url.trim() ? { sheet_url: state.sheet_url } : null;
    }
    if (connectorType === "api") {
      return state.api_url.trim() ? { api_url: state.api_url } : null;
    }
    return null;
  }, [connectorType, state]);

  const dfQualityRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (highlightConfig && highlightTarget === "df_quality") {
      dfQualityRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [highlightConfig, highlightTarget]);

  return (
    <aside className="flex h-full w-[480px] shrink-0 flex-col border-l border-border bg-[hsl(var(--surface-1))]">
      <div className="panel-bar !rounded-none">
        <Settings2 className="h-3.5 w-3.5 text-muted-foreground" />
        <div className="min-w-0">
          <span className="panel-title block truncate">{humanizeName(row.name)}</span>
          <span className="mono-meta">{row.name}</span>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-1">
          <StatusBadge status={row.status} />
          <button onClick={onClose} className="icon-btn ml-1 !h-7 !w-7" aria-label="Close">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1.5 border-b border-border px-3 py-2">
        {row.status === "ACTIVE" ? (
          <Button variant="outline" size="sm" disabled={pauseResumePending} onClick={onPauseResume}>
            <Pause /> Pause
          </Button>
        ) : (
          <Button variant="outline" size="sm" disabled={pauseResumePending} onClick={onPauseResume}>
            <Play /> Resume
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={onOpenHistory}>
          <History /> Version history
        </Button>
        <Button variant="outline" size="sm" className="ml-auto text-destructive hover:text-destructive" onClick={onDelete}>
          <Trash2 /> Delete
        </Button>
      </div>

      <Tabs value={tab} onValueChange={(v) => onTabChange(v as "configure" | "quality")} className="flex min-h-0 flex-1 flex-col">
        <div className="border-b border-border px-3 pt-2.5">
          <TabsList className="h-9 w-full bg-[hsl(var(--surface-2))]">
            <TabsTrigger value="configure" className="flex-1 gap-1.5">
              <Settings2 className="h-3.5 w-3.5" /> Configure
            </TabsTrigger>
            <TabsTrigger value="quality" className="flex-1 gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5" /> Data quality
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <TabsContent forceMount value="configure" className="mt-0 space-y-4 data-[state=inactive]:hidden">
            {highlightConfig && (
              <div className="flex items-start gap-2 rounded-md border border-indigo-200 bg-indigo-50 p-2.5 text-xs text-indigo-900 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-200">
                <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {highlightTarget === "table_quality" ? (
                  <span>
                    That check's rule is configured on the{" "}
                    <Link to="/app/quality" className="font-medium underline">
                      Quality Checks page
                    </Link>
                    , not here — table-level checks (schema, business rules, foreign keys, etc.) live there, not
                    in this pipeline's Configure tab.
                  </span>
                ) : (
                  <span>
                    Either clean it at the source (edit the query below), or scroll to{" "}
                    <span className="font-medium">Data quality checks</span> below to change what's expected, then{" "}
                    <span className="font-medium">Save Changes</span>.
                  </span>
                )}
              </div>
            )}

            <div>
              <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Schedule</p>
              <SchedulerFields compact value={state.schedule} onChange={(next) => onUpdateEdit({ schedule: next })} />
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Where the data goes</p>
              <div className="grid grid-cols-1 gap-3">
                <label className="space-y-1 text-sm font-medium text-foreground">
                  Table name
                  <Input value={state.table_name} onChange={(e) => onUpdateEdit({ table_name: e.target.value })} />
                </label>
                <label className="space-y-1 text-sm font-medium text-foreground">
                  When this pipeline runs
                  <select
                    className="select-control"
                    value={state.option}
                    onChange={(e) => onUpdateEdit({ option: e.target.value })}
                  >
                    <option value="1">Add new rows to the table</option>
                    <option value="2">Replace the table each time</option>
                    <option value="3">Create a brand-new table</option>
                  </select>
                </label>
                <label className="space-y-1 text-sm font-medium text-foreground">
                  How much data to pull each time
                  <select
                    className="select-control"
                    value={state.sync_mode}
                    onChange={(e) => onUpdateEdit({ sync_mode: e.target.value })}
                  >
                    <option value="full">Everything, every run</option>
                    <option value="incremental">Only what's new since last run</option>
                  </select>
                </label>
              </div>
            </div>

            {state.option === "3" && (
              <label className="block space-y-1 text-sm font-medium text-foreground">
                After the table is first created, then…
                <select
                  className="select-control"
                  value={state.after_first_run}
                  onChange={(e) => onUpdateEdit({ after_first_run: e.target.value })}
                >
                  <option value="">Keep creating a new table every run</option>
                  <option value="1">Add new rows to it instead</option>
                  <option value="2">Replace it each time instead</option>
                </select>
              </label>
            )}
            {state.sync_mode === "incremental" && (
              <label className="block space-y-1 text-sm font-medium text-foreground">
                Column that shows what's new (e.g. an updated-at or id column)
                <Input
                  value={state.incremental_column}
                  onChange={(e) => onUpdateEdit({ incremental_column: e.target.value })}
                />
              </label>
            )}

            <div>
              <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Where the data comes from</p>

              {(connectorType === "csv" || connectorType === "excel") && (
                <div className="grid grid-cols-1 gap-3">
                  <Input
                    placeholder="File path"
                    value={state.file_path}
                    onChange={(e) => onUpdateEdit({ file_path: e.target.value })}
                  />
                  <Input
                    placeholder="Folder path"
                    value={state.folder_path}
                    onChange={(e) => onUpdateEdit({ folder_path: e.target.value })}
                  />
                </div>
              )}

              {connectorType === "google_sheets" && (
                <Input
                  placeholder="Sheet URL"
                  value={state.sheet_url}
                  onChange={(e) => onUpdateEdit({ sheet_url: e.target.value })}
                />
              )}

              {connectorType === "api" && (
                <Input
                  placeholder="API URL"
                  value={state.api_url}
                  onChange={(e) => onUpdateEdit({ api_url: e.target.value })}
                />
              )}

              {connectorType === "postgres" && (
                <div className="grid grid-cols-1 gap-3">
                  <Input placeholder="Host" value={state.src_pg_host} onChange={(e) => onUpdateEdit({ src_pg_host: e.target.value })} />
                  <Input placeholder="Database" value={state.src_pg_db} onChange={(e) => onUpdateEdit({ src_pg_db: e.target.value })} />
                  <Input placeholder="User" value={state.src_pg_user} onChange={(e) => onUpdateEdit({ src_pg_user: e.target.value })} />
                  <Input
                    placeholder={row.has_src_pg_password ? "Password (leave blank to keep current)" : "Password"}
                    type="password"
                    value={state.src_pg_password}
                    onChange={(e) => onUpdateEdit({ src_pg_password: e.target.value })}
                  />
                  <Input placeholder="Port" value={state.src_pg_port} onChange={(e) => onUpdateEdit({ src_pg_port: e.target.value })} />
                  <SourceTablePicker
                    pipelineName={row.name}
                    connectorType="postgres"
                    mode={state.pg_mode}
                    onModeChange={(m) => onUpdateEdit({ pg_mode: m })}
                    tableInput={state.pg_table_input}
                    onTableInputChange={(v) => onUpdateEdit({ pg_table_input: v })}
                    queryValue={state.pg_query}
                    onQueryChange={(v) => onUpdateEdit({ pg_query: v })}
                  />
                </div>
              )}

              {connectorType === "mysql" && (
                <div className="grid grid-cols-1 gap-3">
                  <Input placeholder="Host" value={state.src_my_host} onChange={(e) => onUpdateEdit({ src_my_host: e.target.value })} />
                  <Input placeholder="Database" value={state.src_my_db} onChange={(e) => onUpdateEdit({ src_my_db: e.target.value })} />
                  <Input placeholder="User" value={state.src_my_user} onChange={(e) => onUpdateEdit({ src_my_user: e.target.value })} />
                  <Input
                    placeholder={row.has_src_my_password ? "Password (leave blank to keep current)" : "Password"}
                    type="password"
                    value={state.src_my_password}
                    onChange={(e) => onUpdateEdit({ src_my_password: e.target.value })}
                  />
                  <Input placeholder="Port" value={state.src_my_port} onChange={(e) => onUpdateEdit({ src_my_port: e.target.value })} />
                  <label className="space-y-1 text-sm font-medium text-foreground">
                    SQL query
                    <textarea
                      className="min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                      value={state.my_query}
                      onChange={(e) => onUpdateEdit({ my_query: e.target.value })}
                    />
                  </label>
                </div>
              )}

              {connectorType === "oracle" && (
                <div className="grid grid-cols-1 gap-3">
                  <Input placeholder="Host" value={state.src_ora_host} onChange={(e) => onUpdateEdit({ src_ora_host: e.target.value })} />
                  <Input placeholder="Service name" value={state.src_ora_db} onChange={(e) => onUpdateEdit({ src_ora_db: e.target.value })} />
                  <Input placeholder="User" value={state.src_ora_user} onChange={(e) => onUpdateEdit({ src_ora_user: e.target.value })} />
                  <Input
                    placeholder={row.has_src_ora_password ? "Password (leave blank to keep current)" : "Password"}
                    type="password"
                    value={state.src_ora_password}
                    onChange={(e) => onUpdateEdit({ src_ora_password: e.target.value })}
                  />
                  <Input placeholder="Port" value={state.src_ora_port} onChange={(e) => onUpdateEdit({ src_ora_port: e.target.value })} />
                  <label className="space-y-1 text-sm font-medium text-foreground">
                    SQL query
                    <textarea
                      className="min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                      value={state.ora_query}
                      onChange={(e) => onUpdateEdit({ ora_query: e.target.value })}
                    />
                  </label>
                </div>
              )}

              {connectorType === "mongodb" && (
                <div className="space-y-3">
                  <Input
                    placeholder="Connection string (mongodb:// or mongodb+srv://) — optional"
                    value={state.src_mongo_connection_string}
                    onChange={(e) => onUpdateEdit({ src_mongo_connection_string: e.target.value })}
                  />
                  <div className="grid grid-cols-1 gap-3">
                    <Input placeholder="Host" value={state.src_mongo_host} onChange={(e) => onUpdateEdit({ src_mongo_host: e.target.value })} disabled={!!state.src_mongo_connection_string} />
                    <Input placeholder="Database" value={state.src_mongo_db} onChange={(e) => onUpdateEdit({ src_mongo_db: e.target.value })} />
                    <Input placeholder="User (optional)" value={state.src_mongo_user} onChange={(e) => onUpdateEdit({ src_mongo_user: e.target.value })} disabled={!!state.src_mongo_connection_string} />
                    <Input
                      placeholder={row.has_src_mongo_password ? "Password (leave blank to keep current)" : "Password (optional)"}
                      type="password"
                      value={state.src_mongo_password}
                      onChange={(e) => onUpdateEdit({ src_mongo_password: e.target.value })}
                      disabled={!!state.src_mongo_connection_string}
                    />
                    <Input placeholder="Port" value={state.src_mongo_port} onChange={(e) => onUpdateEdit({ src_mongo_port: e.target.value })} disabled={!!state.src_mongo_connection_string} />
                  </div>
                  <Input placeholder="Collection" value={state.mongo_collection} onChange={(e) => onUpdateEdit({ mongo_collection: e.target.value })} />
                  <label className="space-y-1 text-sm font-medium text-foreground">
                    Query filter (optional, JSON)
                    <textarea
                      className="min-h-16 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                      value={state.mongo_query}
                      onChange={(e) => onUpdateEdit({ mongo_query: e.target.value })}
                    />
                  </label>
                </div>
              )}

              {connectorType === "s3" && (
                <div className="grid grid-cols-1 gap-3">
                  <Input placeholder="Bucket" value={state.s3_bucket} onChange={(e) => onUpdateEdit({ s3_bucket: e.target.value })} />
                  <Input placeholder="Key" value={state.s3_key} onChange={(e) => onUpdateEdit({ s3_key: e.target.value })} />
                  <Input placeholder="File type" value={state.s3_file_type} onChange={(e) => onUpdateEdit({ s3_file_type: e.target.value })} />
                </div>
              )}

              {connectorType === "snowflake" && (
                <div className="grid grid-cols-1 gap-3">
                  <Input placeholder="Account" value={state.sf_account} onChange={(e) => onUpdateEdit({ sf_account: e.target.value })} />
                  <Input placeholder="User" value={state.sf_user} onChange={(e) => onUpdateEdit({ sf_user: e.target.value })} />
                  <Input
                    placeholder={row.has_sf_password ? "Password (leave blank to keep current)" : "Password"}
                    type="password"
                    value={state.sf_password}
                    onChange={(e) => onUpdateEdit({ sf_password: e.target.value })}
                  />
                  <Input placeholder="Warehouse" value={state.sf_warehouse} onChange={(e) => onUpdateEdit({ sf_warehouse: e.target.value })} />
                  <Input placeholder="Database" value={state.sf_database} onChange={(e) => onUpdateEdit({ sf_database: e.target.value })} />
                  <Input placeholder="Schema" value={state.sf_schema} onChange={(e) => onUpdateEdit({ sf_schema: e.target.value })} />
                  <Input placeholder="Role (optional)" value={state.sf_role} onChange={(e) => onUpdateEdit({ sf_role: e.target.value })} />
                  <SourceTablePicker
                    pipelineName={row.name}
                    connectorType="snowflake"
                    mode={state.sf_mode}
                    onModeChange={(m) => onUpdateEdit({ sf_mode: m })}
                    tableInput={state.sf_table_input}
                    onTableInputChange={(v) => onUpdateEdit({ sf_table_input: v })}
                    queryValue={state.sf_query}
                    onQueryChange={(v) => onUpdateEdit({ sf_query: v })}
                  />
                </div>
              )}

              {connectorType === "salesforce" && (
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    Either paste a ready access token + instance URL, or fill in client id/secret + username/password to log in fresh on every run.
                  </p>
                  <div className="grid grid-cols-1 gap-3">
                    <Input
                      placeholder={row.has_sf_crm_access_token ? "Access token (leave blank to keep current)" : "Access token (optional)"}
                      type="password"
                      value={state.sf_crm_access_token}
                      onChange={(e) => onUpdateEdit({ sf_crm_access_token: e.target.value })}
                    />
                    <Input placeholder="Instance URL (optional)" value={state.sf_crm_instance_url} onChange={(e) => onUpdateEdit({ sf_crm_instance_url: e.target.value })} />
                    <Input placeholder="Login URL" value={state.sf_crm_login_url} onChange={(e) => onUpdateEdit({ sf_crm_login_url: e.target.value })} />
                    <Input placeholder="Client ID" value={state.sf_crm_client_id} onChange={(e) => onUpdateEdit({ sf_crm_client_id: e.target.value })} />
                    <Input
                      placeholder={row.has_sf_crm_client_secret ? "Client secret (leave blank to keep current)" : "Client secret"}
                      type="password"
                      value={state.sf_crm_client_secret}
                      onChange={(e) => onUpdateEdit({ sf_crm_client_secret: e.target.value })}
                    />
                    <Input placeholder="Username" value={state.sf_crm_username} onChange={(e) => onUpdateEdit({ sf_crm_username: e.target.value })} />
                    <Input
                      placeholder={row.has_sf_crm_password ? "Password (leave blank to keep current)" : "Password"}
                      type="password"
                      value={state.sf_crm_password}
                      onChange={(e) => onUpdateEdit({ sf_crm_password: e.target.value })}
                    />
                    <Input
                      placeholder={row.has_sf_crm_security_token ? "Security token (leave blank to keep current)" : "Security token (optional)"}
                      type="password"
                      value={state.sf_crm_security_token}
                      onChange={(e) => onUpdateEdit({ sf_crm_security_token: e.target.value })}
                    />
                  </div>
                  <Input placeholder="Object name, e.g. Account, Contact, Lead" value={state.sf_crm_object_name} onChange={(e) => onUpdateEdit({ sf_crm_object_name: e.target.value })} />
                  <label className="space-y-1 text-sm font-medium text-foreground">
                    Custom SOQL query (optional — overrides object name)
                    <textarea
                      className="min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                      value={state.sf_crm_soql_query}
                      onChange={(e) => onUpdateEdit({ sf_crm_soql_query: e.target.value })}
                    />
                  </label>
                </div>
              )}

              {connectorType === "hubspot" && (
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">HubSpot Private App access tokens don't expire, so this is the only credential needed.</p>
                  <Input
                    placeholder={row.has_hs_access_token ? "Private App access token (leave blank to keep current)" : "Private App access token"}
                    type="password"
                    value={state.hs_access_token}
                    onChange={(e) => onUpdateEdit({ hs_access_token: e.target.value })}
                  />
                  <label className="space-y-1 text-sm font-medium text-foreground">
                    Object type
                    <select
                      className="select-control"
                      value={state.hs_object_type}
                      onChange={(e) => onUpdateEdit({ hs_object_type: e.target.value })}
                    >
                      <option value="contacts">Contacts</option>
                      <option value="companies">Companies</option>
                      <option value="deals">Deals</option>
                      <option value="tickets">Tickets</option>
                    </select>
                  </label>
                  <Input
                    placeholder="Properties (comma-separated, optional)"
                    value={state.hs_properties}
                    onChange={(e) => onUpdateEdit({ hs_properties: e.target.value })}
                  />
                </div>
              )}

              {connectorType === "zoho" && (
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    Either paste a ready access token, or fill in refresh token + client id/secret to mint a fresh one every run (Zoho tokens expire hourly).
                  </p>
                  <Input
                    placeholder={row.has_zoho_access_token ? "Access token (leave blank to keep current)" : "Access token (optional)"}
                    type="password"
                    value={state.zoho_access_token}
                    onChange={(e) => onUpdateEdit({ zoho_access_token: e.target.value })}
                  />
                  <Input
                    placeholder={row.has_zoho_refresh_token ? "Refresh token (leave blank to keep current)" : "Refresh token (optional)"}
                    type="password"
                    value={state.zoho_refresh_token}
                    onChange={(e) => onUpdateEdit({ zoho_refresh_token: e.target.value })}
                  />
                  <div className="grid grid-cols-1 gap-3">
                    <Input placeholder="Client ID" value={state.zoho_client_id} onChange={(e) => onUpdateEdit({ zoho_client_id: e.target.value })} />
                    <Input
                      placeholder={row.has_zoho_client_secret ? "Client secret (leave blank to keep current)" : "Client secret"}
                      type="password"
                      value={state.zoho_client_secret}
                      onChange={(e) => onUpdateEdit({ zoho_client_secret: e.target.value })}
                    />
                  </div>
                  <div className="grid grid-cols-1 gap-3">
                    <Input placeholder="Accounts URL (region, default .com)" value={state.zoho_accounts_url} onChange={(e) => onUpdateEdit({ zoho_accounts_url: e.target.value })} />
                    <Input placeholder="API domain (region, default .com)" value={state.zoho_api_domain} onChange={(e) => onUpdateEdit({ zoho_api_domain: e.target.value })} />
                  </div>
                  <Input placeholder="Module, e.g. Leads, Contacts, Deals" value={state.zoho_module} onChange={(e) => onUpdateEdit({ zoho_module: e.target.value })} />
                  <Input placeholder="Search criteria (optional)" value={state.zoho_criteria} onChange={(e) => onUpdateEdit({ zoho_criteria: e.target.value })} />
                </div>
              )}
            </div>

            <div
              ref={dfQualityRef}
              className={
                highlightConfig && highlightTarget === "df_quality"
                  ? "-m-1 rounded-lg p-1 ring-2 ring-indigo-400 ring-offset-2 ring-offset-[hsl(var(--surface-1))]"
                  : undefined
              }
            >
              <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                Data quality checks (before load)
              </p>
              <p className="mb-2 text-xs text-muted-foreground">
                Runs against a live preview of the source before every load — nulls, types, ranges, duplicates.
                {["postgres", "mysql", "oracle", "mongodb", "snowflake", "salesforce", "hubspot", "zoho"].includes(connectorType) && (
                  <> Passwords/tokens aren't shown here for security — if the preview button below fails, re-enter the credential above first.</>
                )}
              </p>
              <DataQualityBuilder
                connector={connectorType as PreviewConnector}
                params={previewParams}
                auto={["csv", "excel"].includes(connectorType)}
                initialConfig={state.df_quality_config}
                initialOnFail={state.df_quality_on_fail}
                focusColumn={highlightTarget === "df_quality" ? highlightColumn : null}
                focusToken={highlightToken}
                onChange={(result) =>
                  onUpdateEdit({
                    df_quality_config: result.hasAnyCheck ? result.config : null,
                    df_quality_on_fail: result.on_fail,
                  })
                }
              />
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                User-defined schema override
              </p>
              <p className="mb-2 text-xs text-muted-foreground">
                Enforce a type per column instead of the auto-detected schema — applied on every future run.
              </p>
              <SchemaBuilder
                connector={connectorType as PreviewConnector}
                params={previewParams}
                auto={["csv", "excel"].includes(connectorType)}
                initialSchema={state.custom_schema}
                onChange={(result) =>
                  onUpdateEdit({
                    custom_schema: result.hasAnyCustomType ? result.schema : null,
                  })
                }
              />
            </div>
          </TabsContent>

          <TabsContent forceMount value="quality" className="mt-0 data-[state=inactive]:hidden">
            <PipelineQualityPanel
              pipelineName={row.name}
              connectionId={row.quality_connection_id}
              onFixInConfig={onFixInConfig}
            />
          </TabsContent>
        </div>
      </Tabs>

      {tab === "configure" && (
        <div className="flex justify-end gap-2 border-t border-border p-3">
          <Button type="button" variant="outline" onClick={onClose}>
            <X /> Cancel
          </Button>
          <Button type="button" disabled={saving} onClick={onSave}>
            <Save /> {saving ? "Saving…" : "Save Changes"}
          </Button>
        </div>
      )}
    </aside>
  );
};

export const Pipelines = () => {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [managingName, setManagingName] = useState<string | null>(null);
  const [editState, setEditState] = useState<EditState | null>(null);
  const [managingTab, setManagingTab] = useState<"configure" | "quality">("configure");
  const [highlightConfig, setHighlightConfig] = useState(false);
  const [highlightTarget, setHighlightTarget] = useState<"df_quality" | "table_quality" | null>(null);
  const [highlightColumn, setHighlightColumn] = useState<string | null>(null);
  // Bumped on every "Fix in Configure" click so DataQualityBuilder re-opens
  // and re-scrolls to the same column even if it was already the target
  // (e.g. the person scrolled away, then clicked the button again).
  const [highlightToken, setHighlightToken] = useState(0);
  const [historyPipeline, setHistoryPipeline] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const { data: pipes = [], isLoading } = useQuery({
    queryKey: ["pipelines"],
    queryFn: fetchPipelines,
  });

  const statusQueries = useQueries({
    queries: pipes.map((pipeline) => ({
      queryKey: ["pipeline-status", pipeline.dag_id],
      queryFn: () => fetchStatus(pipeline.dag_id.replace(/^pipeline_/, "")),
      staleTime: 15_000,
    })),
  });

  const rows: PipelineRow[] = useMemo(
    () =>
      pipes.map((pipeline, index) => {
        const name = pipeline.dag_id.replace(/^pipeline_/, "");
        const statusData = statusQueries[index]?.data;
        return {
          ...pipeline,
          name,
          status: statusData?.status ?? "UNKNOWN",
          next_run: statusData?.next_run ?? null,
          size_kb: pipeline.size_kb,
          schedule: pipeline.schedule ?? "*/5 * * * *",
          timezone: pipeline.timezone ?? "Asia/Kolkata",
        };
      }),
    [pipes, statusQueries],
  );

  const filtered = rows.filter((row) =>
    !search ? true : row.dag_id.toLowerCase().includes(search.toLowerCase()),
  );

  const managingRow = rows.find((row) => row.name === managingName) ?? null;

  const openManage = (row: PipelineRow) => {
    setManagingName(row.name);
    setEditState(buildEditState(row));
    setManagingTab("configure");
    setHighlightConfig(false);
    setHighlightTarget(null);
    setHighlightColumn(null);
  };

  const closeManage = () => {
    setManagingName(null);
    setEditState(null);
    setHighlightConfig(false);
    setHighlightTarget(null);
    setHighlightColumn(null);
  };

  const pauseM = useMutation({
    mutationFn: (name: string) => api.patch(`/pipeline/${name}/pause`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pipeline-status"] }),
  });
  const resumeM = useMutation({
    mutationFn: (name: string) => api.patch(`/pipeline/${name}/unpause`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pipeline-status"] }),
  });
  const deleteM = useMutation({
    mutationFn: (name: string) => api.delete(`/delete_pipeline/${name}`),
    onSuccess: (_, name) => {
      setDeleteTarget(null);
      if (managingName === name) closeManage();
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["pipeline-status"] });
    },
  });

  const editM = useMutation({
    mutationFn: ({ name, state }: { name: string; state: EditState }) => {
      // Build payload — only send non-empty string fields, so untouched
      // password fields (left blank) never overwrite the stored secret.
      const payload: Record<string, any> = {
        schedule: buildCron(state.schedule),
        timezone: state.schedule.timezone,
        table_name: state.table_name || null,
        option: state.option,
        after_first_run: state.option === "3" ? (state.after_first_run || null) : null,
        sync_mode: state.sync_mode,
        incremental_column: state.sync_mode === "incremental" ? (state.incremental_column || null) : null,
        folder_path: state.folder_path || null,
        file_path: state.file_path || null,
        sheet_url: state.sheet_url || null,
        api_url: state.api_url || null,
        src_pg_host: state.src_pg_host || null,
        src_pg_db: state.src_pg_db || null,
        src_pg_user: state.src_pg_user || null,
        src_pg_port: state.src_pg_port || null,
        pg_query: state.pg_query || null,
        src_my_host: state.src_my_host || null,
        src_my_db: state.src_my_db || null,
        src_my_user: state.src_my_user || null,
        src_my_port: state.src_my_port || null,
        my_query: state.my_query || null,
        src_ora_host: state.src_ora_host || null,
        src_ora_db: state.src_ora_db || null,
        src_ora_user: state.src_ora_user || null,
        src_ora_port: state.src_ora_port || null,
        ora_query: state.ora_query || null,
        src_mongo_host: state.src_mongo_host || null,
        src_mongo_db: state.src_mongo_db || null,
        src_mongo_user: state.src_mongo_user || null,
        src_mongo_port: state.src_mongo_port || null,
        src_mongo_connection_string: state.src_mongo_connection_string || null,
        mongo_collection: state.mongo_collection || null,
        mongo_query: state.mongo_query || null,
        s3_bucket: state.s3_bucket || null,
        s3_key: state.s3_key || null,
        s3_file_type: state.s3_file_type || null,
        sf_account: state.sf_account || null,
        sf_user: state.sf_user || null,
        sf_warehouse: state.sf_warehouse || null,
        sf_database: state.sf_database || null,
        sf_schema: state.sf_schema || null,
        sf_role: state.sf_role || null,
        sf_query: state.sf_query || null,
        sf_crm_instance_url: state.sf_crm_instance_url || null,
        sf_crm_login_url: state.sf_crm_login_url || null,
        sf_crm_client_id: state.sf_crm_client_id || null,
        sf_crm_username: state.sf_crm_username || null,
        sf_crm_object_name: state.sf_crm_object_name || null,
        sf_crm_soql_query: state.sf_crm_soql_query || null,
        hs_object_type: state.hs_object_type || null,
        hs_properties: state.hs_properties.trim()
          ? state.hs_properties.split(",").map((p) => p.trim()).filter(Boolean)
          : null,
        zoho_client_id: state.zoho_client_id || null,
        zoho_accounts_url: state.zoho_accounts_url || null,
        zoho_api_domain: state.zoho_api_domain || null,
        zoho_module: state.zoho_module || null,
        zoho_criteria: state.zoho_criteria || null,
        df_quality_config: state.df_quality_config,
        df_quality_on_fail: state.df_quality_on_fail,
        custom_schema: state.custom_schema,
      };
      // Only include secrets if the user actually typed something new — an
      // empty field means "keep what's already stored", same rule as
      // src_pg_password/sf_password below.
      if (state.src_pg_password) payload.src_pg_password = state.src_pg_password;
      if (state.sf_password) payload.sf_password = state.sf_password;
      if (state.src_my_password) payload.src_my_password = state.src_my_password;
      if (state.src_ora_password) payload.src_ora_password = state.src_ora_password;
      if (state.src_mongo_password) payload.src_mongo_password = state.src_mongo_password;
      if (state.sf_crm_access_token) payload.sf_crm_access_token = state.sf_crm_access_token;
      if (state.sf_crm_client_secret) payload.sf_crm_client_secret = state.sf_crm_client_secret;
      if (state.sf_crm_password) payload.sf_crm_password = state.sf_crm_password;
      if (state.sf_crm_security_token) payload.sf_crm_security_token = state.sf_crm_security_token;
      if (state.hs_access_token) payload.hs_access_token = state.hs_access_token;
      if (state.zoho_access_token) payload.zoho_access_token = state.zoho_access_token;
      if (state.zoho_refresh_token) payload.zoho_refresh_token = state.zoho_refresh_token;
      if (state.zoho_client_secret) payload.zoho_client_secret = state.zoho_client_secret;

      return api.patch(`/edit_pipeline/${name}`, payload);
    },
    onSuccess: (_, variables) => {
      if (managingName === variables.name) closeManage();
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["pipeline-status"] });
    },
  });

  const counts = {
    total: rows.length,
    active: rows.filter((row) => row.status === "ACTIVE").length,
    paused: rows.filter((row) => row.status === "PAUSED").length,
  };

  const updateEdit = (patch: Partial<EditState>) =>
    setEditState((current) => (current ? { ...current, ...patch } : current));

  return (
    <div className="flex h-full">
      <main className="min-w-0 flex-1 space-y-5 overflow-y-auto">
        <PageHeader
          icon={ListChecks}
          eyebrow="Build"
          title="Pipelines"
          description="Everything that's set up to run automatically, and what happened last time it ran."
        />

        <div className="grid grid-cols-3 gap-3">
          <StatTile label="Total pipelines" value={counts.total} icon={ListChecks} />
          <StatTile label="Running on schedule" value={counts.active} tone="positive" icon={Play} />
          <StatTile label="Paused" value={counts.paused} tone="warning" icon={Pause} />
        </div>

        <Panel>
          <PanelBar title="Pipelines" count={filtered.length}>
            <PanelSearch
              label="Search pipelines"
              value={search}
              onChange={setSearch}
              placeholder="Search by name…"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => qc.invalidateQueries({ queryKey: ["pipelines"] })}
            >
              <RefreshCw /> Refresh
            </Button>
          </PanelBar>

          {isLoading ? (
            <RowSkeleton rows={4} />
          ) : pipes.length === 0 ? (
            <EmptyState
              icon={ListChecks}
              title="No pipelines yet"
              body="A pipeline automatically brings data in from a source, on a schedule you choose, and saves it into a table. Set up your first one to see it here."
              action={
                <Link to="/app/create">
                  <Button size="sm"><Plus /> Create your first pipeline</Button>
                </Link>
              }
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              icon={Search}
              title="No pipelines match that search"
              body={`Nothing matches "${search}". Clear the search to see all ${pipes.length} pipelines.`}
              action={<Button variant="outline" size="sm" onClick={() => setSearch("")}>Clear search</Button>}
            />
          ) : (
            <div>
              {filtered.map((row) => {
                const connectorType = row.connector_type ?? "";
                const isManaging = managingName === row.name;

                return (
                  <Row
                    key={row.dag_id}
                    state={row.status}
                    className={cn(isManaging && "bg-[hsl(var(--surface-2)/0.6)]")}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate text-[15px] font-semibold text-foreground">
                            {humanizeName(row.name)}
                          </span>
                          <StatusBadge status={row.status} />
                          {connectorType && <span className="chip">{sourceLabel(connectorType)}</span>}
                        </div>

                        <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                          {describePipeline(row)}
                        </p>

                        <div className="mt-2">
                          <Meta
                            items={[
                              ["next run", fdt(row.next_run)],
                              ...(connectorType === "postgres" || connectorType === "snowflake"
                                ? ([[
                                    "reading from",
                                    parseTableFromSimpleSelect(connectorType === "postgres" ? row.pg_query : row.sf_query)
                                      ?? "custom SQL query",
                                  ]] as [string, React.ReactNode][])
                                : []),
                              ["size", row.size_kb ? `${row.size_kb} KB` : "—"],
                            ]}
                          />
                        </div>
                      </div>

                      <div className="flex shrink-0 items-center gap-1.5">
                        {row.status === "ACTIVE" ? (
                          <Button variant="outline" size="sm" onClick={() => pauseM.mutate(row.name)}>
                            <Pause /> Pause
                          </Button>
                        ) : (
                          <Button variant="outline" size="sm" onClick={() => resumeM.mutate(row.name)}>
                            <Play /> Resume
                          </Button>
                        )}
                        <Button
                          variant={isManaging ? "default" : "outline"}
                          size="sm"
                          onClick={() => (isManaging ? closeManage() : openManage(row))}
                        >
                          <Settings2 /> Manage
                        </Button>
                        <OverflowMenu label={`More actions for ${humanizeName(row.name)}`}>
                          {(close) => (
                            <>
                              <MenuItem
                                icon={History}
                                onClick={() => {
                                  setHistoryPipeline(row.name);
                                  close();
                                }}
                              >
                                Version history
                              </MenuItem>
                              <MenuSeparator />
                              <MenuItem
                                icon={Trash2}
                                tone="danger"
                                onClick={() => {
                                  setDeleteTarget(row.name);
                                  close();
                                }}
                              >
                                Delete pipeline
                              </MenuItem>
                            </>
                          )}
                        </OverflowMenu>
                      </div>
                    </div>
                  </Row>
                );
              })}
            </div>
          )}
        </Panel>
      </main>

      {managingRow && editState && (
        <PipelineManagePanel
          row={managingRow}
          editState={editState}
          tab={managingTab}
          onTabChange={(t) => {
            setManagingTab(t);
            setHighlightConfig(false);
            setHighlightTarget(null);
            setHighlightColumn(null);
          }}
          onUpdateEdit={updateEdit}
          onClose={closeManage}
          onSave={() => editM.mutate({ name: managingRow.name, state: editState })}
          saving={editM.isPending}
          onPauseResume={() =>
            managingRow.status === "ACTIVE" ? pauseM.mutate(managingRow.name) : resumeM.mutate(managingRow.name)
          }
          pauseResumePending={pauseM.isPending || resumeM.isPending}
          onOpenHistory={() => setHistoryPipeline(managingRow.name)}
          onDelete={() => setDeleteTarget(managingRow.name)}
          highlightConfig={highlightConfig}
          highlightTarget={highlightTarget}
          highlightColumn={highlightColumn}
          highlightToken={highlightToken}
          onFixInConfig={(target, column) => {
            setManagingTab("configure");
            setHighlightConfig(true);
            setHighlightTarget(target ?? "df_quality");
            setHighlightColumn(column ?? null);
            setHighlightToken((t) => t + 1);
          }}
        />
      )}

      {historyPipeline && (
        <HistoryPanel
          queryKey={["pipeline-history", historyPipeline]}
          fetchHistory={() => fetchPipelineHistory(historyPipeline)}
          restoreVersion={(versionId) => restorePipelineVersion(historyPipeline, versionId)}
          onClose={() => setHistoryPipeline(null)}
          onRestored={() => {
            qc.invalidateQueries({ queryKey: ["pipelines"] });
            qc.invalidateQueries({ queryKey: ["pipeline-status"] });
          }}
        />
      )}

      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="mb-1 flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              <DialogTitle>Delete this pipeline?</DialogTitle>
            </div>
            <DialogDescription>
              {deleteTarget && (
                <>
                  <span className="font-medium text-foreground">{humanizeName(deleteTarget)}</span> will stop
                  running and its schedule will be removed. This can't be undone — but its version history
                  stays intact if you ever need to see what it was set up to do.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Keep pipeline
            </Button>
            <Button
              variant="destructive"
              disabled={deleteM.isPending}
              onClick={() => deleteTarget && deleteM.mutate(deleteTarget)}
            >
              <Trash2 /> {deleteM.isPending ? "Deleting…" : "Yes, delete it"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
