

import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, PlusCircle, Link2, Link2Off, Check, ChevronLeft, ChevronRight, CheckCircle2, XCircle, Network, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SchedulerFields } from "@/components/SchedulerFields";
import { FolderUpload } from "@/pages/FolderUpload";
import { buildCron, defaultSchedule } from "@/lib/schedule";
import { PageHeader } from "@/components/PageHeader";
import { DataQualityBuilder, BuiltQuality } from "@/components/DataQualityBuilder";
import { SchemaBuilder, BuiltSchema } from "@/components/SchemaBuilder";
import { LiveTablePicker } from "@/components/LiveTablePicker";

const splitList = (value: string): string[] =>
  value.split(",").map((v) => v.trim()).filter(Boolean);

// ── Safely turn any backend error shape into a plain string for rendering.
// FastAPI's own validation errors (422) return `detail` as an ARRAY of
// {loc, msg, type} objects, not a string — handing that array straight to
// React as a child throws "Objects are not valid as a React child" and
// blanks the whole page (no error boundary catches it). Everything else
// (HTTPException(detail="...") or detail={"error": "..."}) still works too. ──
const formatApiError = (error: unknown): string => {
  const detail = (error as any)?.response?.data?.detail;

  if (Array.isArray(detail)) {
    return detail
      .map((d: any) => {
        if (typeof d === "string") return d;
        const field = Array.isArray(d?.loc) ? d.loc.filter((p: any) => p !== "body").join(".") : null;
        return field ? `${field}: ${d?.msg ?? "invalid value"}` : (d?.msg ?? JSON.stringify(d));
      })
      .join("; ");
  }
  if (detail && typeof detail === "object") {
    return detail.error ?? JSON.stringify(detail);
  }
  if (typeof detail === "string" && detail) {
    return detail;
  }
  return (error as Error)?.message ?? "Something went wrong.";
};

// ── Destination (where all sources load into) — see DirectIngest.tsx for
// the same constants; kept in sync deliberately. ──────────────────────
const FALLBACK_DESTINATIONS: { type: string; label: string; fields: string[] }[] = [
  { type: "postgres", label: "PostgreSQL", fields: ["host", "port", "database", "user", "password"] },
  { type: "mysql", label: "MySQL", fields: ["host", "port", "database", "user", "password"] },
  { type: "oracle", label: "Oracle", fields: ["host", "port", "database", "user", "password"] },
  { type: "mongodb", label: "MongoDB", fields: ["connection_string"] },
  { type: "snowflake", label: "Snowflake", fields: ["account", "user", "password", "warehouse", "database", "schema", "role"] },
];

const DESTINATION_FIELD_LABELS: Record<string, string> = {
  host: "Host", port: "Port", database: "Database", user: "User", password: "Password",
  connection_string: "Connection string (mongodb:// or mongodb+srv://)",
  account: "Account", warehouse: "Warehouse", schema: "Schema", role: "Role (optional)",
};

const CONNECTOR_TO_SOURCE_TYPE: Record<string, string> = {
  csv: "local_folder",
  excel: "local_folder",
  google_sheets: "google_sheet",
  api: "api",
  postgres: "postgres",
  mysql: "mysql",
  oracle: "oracle",
  mongodb: "mongodb",
  s3: "s3",
  snowflake: "snowflake",
  salesforce: "salesforce",
  hubspot: "hubspot",
  zoho: "zoho",
};

const CONNECTOR_LABELS: Record<string, string> = {
  csv: "CSV",
  excel: "Excel",
  google_sheets: "Google Sheets",
  api: "API",
  postgres: "Postgres",
  mysql: "MySQL",
  oracle: "Oracle",
  mongodb: "MongoDB",
  s3: "S3",
  snowflake: "Snowflake",
  salesforce: "Salesforce",
  hubspot: "HubSpot",
  zoho: "Zoho CRM",
};

const SUPPORTS_CONNECTIONS = ["csv", "excel", "google_sheets", "api", "postgres", "mysql", "oracle", "mongodb", "s3", "snowflake", "salesforce", "hubspot", "zoho"];

const SECRET_FIELDS: Array<keyof Source> = ["src_pg_password", "src_my_password", "src_ora_password", "src_mongo_password", "sf_password", "s3_secret_key", "sf_crm_access_token", "sf_crm_client_secret", "sf_crm_password", "sf_crm_security_token", "hs_access_token", "zoho_access_token", "zoho_refresh_token", "zoho_client_secret"];
const STEPS = [
  { id: 1, label: "Basic Info" },
  { id: 2, label: "Sources" },
  { id: 3, label: "Schedule" },
  { id: 4, label: "Review & Create" },
];

// For Postgres — respects exact case as typed (Postgres folds unquoted
// identifiers to lowercase by default).
const buildSelectQuery = (tableRef: string) => {
  const t = tableRef.trim();
  if (!t) return "";
  return /["'.]/.test(t) ? `SELECT * FROM ${t}` : `SELECT * FROM "${t}"`;
};

// For Snowflake — unquoted identifiers default to UPPERCASE storage, so
// auto-uppercase the typed table name unless the user already quoted it
// or used a schema-qualified reference.
const buildSnowflakeSelectQuery = (tableRef: string) => {
  const t = tableRef.trim();
  if (!t) return "";
  if (/["'.]/.test(t)) return `SELECT * FROM ${t}`;
  return `SELECT * FROM "${t.toUpperCase()}"`;
};

type Source = {
  connector_type: string;
  connection_id: number | null;
  file_path: string;
  folder_path: string;
  sheet_url: string;
  api_url: string;
  api_config: string;
  s3_bucket: string;
  s3_key: string;
  s3_file_type: string;
  s3_access_key: string;
  s3_secret_key: string;
  src_pg_host: string;
  src_pg_db: string;
  src_pg_user: string;
  src_pg_password: string;
  src_pg_port: string;
  pg_query: string;
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
  sf_account: string;
  sf_user: string;
  sf_password: string;
  sf_warehouse: string;
  sf_database: string;
  sf_schema: string;
  sf_query: string;
  sf_role: string;
  // ── Salesforce CRM ──
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
  // ── HubSpot ──
  hs_access_token: string;
  hs_object_type: string;
  hs_properties: string;
  // ── Zoho CRM ──
  zoho_access_token: string;
  zoho_refresh_token: string;
  zoho_client_id: string;
  zoho_client_secret: string;
  zoho_accounts_url: string;
  zoho_api_domain: string;
  zoho_module: string;
  zoho_criteria: string;
  // ── table-name-vs-custom-SQL mode ──
  pg_query_mode: "table" | "custom";
  pg_source_table: string;
  sf_query_mode: "table" | "custom";
  sf_source_table: string;
};

const blankSource = (): Source => ({
  connector_type: "csv",
  connection_id: null,
  file_path: "",
  folder_path: "",
  sheet_url: "",
  api_url: "",
  api_config: "",
  s3_bucket: "",
  s3_key: "",
  s3_file_type: "csv",
  s3_access_key: "",
  s3_secret_key: "",
  src_pg_host: "",
  src_pg_db: "",
  src_pg_user: "",
  src_pg_password: "",
  src_pg_port: "5432",
  pg_query: "",
  src_my_host: "",
  src_my_db: "",
  src_my_user: "",
  src_my_password: "",
  src_my_port: "3306",
  my_query: "",
  src_ora_host: "",
  src_ora_db: "",
  src_ora_user: "",
  src_ora_password: "",
  src_ora_port: "1521",
  ora_query: "",
  src_mongo_host: "",
  src_mongo_db: "",
  src_mongo_user: "",
  src_mongo_password: "",
  src_mongo_port: "27017",
  src_mongo_connection_string: "",
  mongo_collection: "",
  mongo_query: "",
  sf_account: "",
  sf_user: "",
  sf_password: "",
  sf_warehouse: "",
  sf_database: "",
  sf_schema: "PUBLIC",
  sf_query: "",
  sf_role: "",
  sf_crm_access_token: "",
  sf_crm_instance_url: "",
  sf_crm_login_url: "https://login.salesforce.com",
  sf_crm_client_id: "",
  sf_crm_client_secret: "",
  sf_crm_username: "",
  sf_crm_password: "",
  sf_crm_security_token: "",
  sf_crm_object_name: "",
  sf_crm_soql_query: "",
  hs_access_token: "",
  hs_object_type: "contacts",
  hs_properties: "",
  zoho_access_token: "",
  zoho_refresh_token: "",
  zoho_client_id: "",
  zoho_client_secret: "",
  zoho_accounts_url: "https://accounts.zoho.com",
  zoho_api_domain: "https://www.zohoapis.com",
  zoho_module: "",
  zoho_criteria: "",
  pg_query_mode: "table",
  pg_source_table: "",
  sf_query_mode: "table",
  sf_source_table: "",
});

type SourceConnectionState = {
  useExisting: boolean;
  selectedConnectionId: string;
  connectionError: string;
};

export const MultiSource = () => {
  const qc = useQueryClient();
  const [pipelineName, setPipelineName] = useState("");
  const [tableName, setTableName] = useState("");
  const [schedule, setSchedule] = useState(defaultSchedule);
  const [option, setOption] = useState("1");
  const [sources, setSources] = useState<Source[]>([blankSource()]);
  const [sourceConnectionStates, setSourceConnectionStates] = useState<Record<number, SourceConnectionState>>({});
  const [apiConfigErrors, setApiConfigErrors] = useState<Record<number, string>>({});
  const [result, setResult] = useState<any>(null);

  // ── Pre-ingest DataFrame quality gate — one BuiltQuality per source
  // index, filled in by <DataQualityBuilder>, same shape/behavior as
  // CreatePipeline.tsx / DirectIngest.tsx. ──────────────────────────────
  const [sourceQualities, setSourceQualities] = useState<Record<number, BuiltQuality | null>>({});
  // ── Optional user-defined schema override — one per source index, same
  // idea as sourceQualities above. ──────────────────────────────────────
  const [sourceSchemas, setSourceSchemas] = useState<Record<number, BuiltSchema | null>>({});
  // Which file the user picked to preview/build checks against, when a
  // saved csv/excel connection resolves to a whole folder rather than a
  // single file — one per source index, same idea as CreatePipeline's
  // existingConnFilePath but keyed per-source since there can be several.
  const [existingConnFilePaths, setExistingConnFilePaths] = useState<Record<number, string>>({});

  const [currentStep, setCurrentStep] = useState(1);
  const [stepError, setStepError] = useState("");
  const [activeSourceTab, setActiveSourceTab] = useState(0);

  // ── Destination (where ALL sources load into — one table, one
  // destination for the whole pipeline). Same "new vs saved connection"
  // UX as the source connections below. ──────────────────────────────
  const [destinationType, setDestinationType] = useState<string>("postgres");
  const [useSavedDestination, setUseSavedDestination] = useState(false);
  const [selectedDestinationConnectionId, setSelectedDestinationConnectionId] = useState<string>("");
  const [destinationManualConfig, setDestinationManualConfig] = useState<Record<string, string>>({});
  const [destinationError, setDestinationError] = useState<string>("");

  const destinationTypesQuery = useQuery({
    queryKey: ["destination-types"],
    queryFn: async () => (await api.get("/destinations/types")).data.destinations ?? [],
  });

  const connections = useQuery({
    queryKey: ["connections"],
    queryFn: async () => (await api.get("/connections")).data.connections ?? [],
  });

  const destinationTypes = destinationTypesQuery.data?.length ? destinationTypesQuery.data : FALLBACK_DESTINATIONS;
  const activeDestination = destinationTypes.find((d: any) => d.type === destinationType) ?? destinationTypes[0];
  const filteredDestinationConnections = connections.data?.filter(
    (conn: any) => conn.source_type === destinationType
  ) ?? [];
  const updateDestinationField = (key: string, value: string) =>
    setDestinationManualConfig((current) => ({ ...current, [key]: value }));

  const getFilteredConnections = (connectorType: string) => {
    const sourceType = CONNECTOR_TO_SOURCE_TYPE[connectorType];
    return connections.data?.filter((conn: any) => conn.source_type === sourceType) ?? [];
  };

  const updateSource = (index: number, key: keyof Source, value: string | number | boolean | null) =>
    setSources((current) => current.map((source, i) => i === index ? { ...source, [key]: value } : source));

  const setExistingConnFilePath = (index: number, value: string) =>
    setExistingConnFilePaths((current) => ({ ...current, [index]: value }));

  // ── What to preview / build pre-ingest quality checks against, for one
  // source's currently selected connector + connection mode. `null` means
  // we don't have enough info yet, so DataQualityBuilder renders nothing.
  // Mirrors CreatePipeline.tsx's previewParams, generalized per source. ──
  const getPreviewParams = (
    source: Source,
    connState: SourceConnectionState,
    existingFilePath: string,
  ): Record<string, unknown> | null => {
    const connId = connState.useExisting && connState.selectedConnectionId
      ? parseInt(connState.selectedConnectionId, 10)
      : undefined;

    if (["csv", "excel"].includes(source.connector_type)) {
      const path = connState.useExisting ? existingFilePath : source.file_path;
      if (path) return { file_path: path };
      // No single file picked yet — fall back to the whole folder, same as
      // CreatePipeline.tsx/Pipelines.tsx, so folder-based sources still get
      // a working preview/schema builder instead of always rendering nothing.
      if (source.folder_path) return { folder_path: source.folder_path };
      return null;
    }

    if (source.connector_type === "postgres") {
      const resolvedQuery = source.pg_query_mode === "table" ? buildSelectQuery(source.pg_source_table) : source.pg_query;
      if (!resolvedQuery.trim()) return null;
      if (connState.useExisting) return connId ? { connection_id: connId, pg_query: resolvedQuery } : null;
      if (!source.src_pg_host || !source.src_pg_db || !source.src_pg_user) return null;
      return {
        src_pg_host: source.src_pg_host, src_pg_db: source.src_pg_db, src_pg_user: source.src_pg_user,
        src_pg_password: source.src_pg_password, src_pg_port: source.src_pg_port, pg_query: resolvedQuery,
      };
    }

    if (source.connector_type === "mysql") {
      if (!source.my_query.trim()) return null;
      if (connState.useExisting) return connId ? { connection_id: connId, my_query: source.my_query } : null;
      if (!source.src_my_host || !source.src_my_db || !source.src_my_user) return null;
      return {
        src_my_host: source.src_my_host, src_my_db: source.src_my_db, src_my_user: source.src_my_user,
        src_my_password: source.src_my_password, src_my_port: source.src_my_port, my_query: source.my_query,
      };
    }

    if (source.connector_type === "oracle") {
      if (!source.ora_query.trim()) return null;
      if (connState.useExisting) return connId ? { connection_id: connId, ora_query: source.ora_query } : null;
      if (!source.src_ora_host || !source.src_ora_db || !source.src_ora_user) return null;
      return {
        src_ora_host: source.src_ora_host, src_ora_db: source.src_ora_db, src_ora_user: source.src_ora_user,
        src_ora_password: source.src_ora_password, src_ora_port: source.src_ora_port, ora_query: source.ora_query,
      };
    }

    if (source.connector_type === "mongodb") {
      if (!source.mongo_collection.trim()) return null;
      if (connState.useExisting) return connId ? { connection_id: connId, mongo_collection: source.mongo_collection, mongo_query: source.mongo_query } : null;
      if (!source.src_mongo_connection_string && (!source.src_mongo_host || !source.src_mongo_db)) return null;
      if (source.src_mongo_connection_string && !source.src_mongo_db) return null;
      return {
        src_mongo_host: source.src_mongo_host, src_mongo_db: source.src_mongo_db,
        src_mongo_user: source.src_mongo_user, src_mongo_password: source.src_mongo_password,
        src_mongo_port: source.src_mongo_port, src_mongo_connection_string: source.src_mongo_connection_string,
        mongo_collection: source.mongo_collection, mongo_query: source.mongo_query,
      };
    }

    if (source.connector_type === "snowflake") {
      const resolvedQuery = source.sf_query_mode === "table" ? buildSnowflakeSelectQuery(source.sf_source_table) : source.sf_query;
      if (!resolvedQuery.trim()) return null;
      if (connState.useExisting) return connId ? { connection_id: connId, sf_query: resolvedQuery } : null;
      if (!source.sf_account || !source.sf_user || !source.sf_warehouse || !source.sf_database) return null;
      return {
        sf_account: source.sf_account, sf_user: source.sf_user, sf_password: source.sf_password,
        sf_warehouse: source.sf_warehouse, sf_database: source.sf_database, sf_schema: source.sf_schema,
        sf_role: source.sf_role, sf_query: resolvedQuery,
      };
    }

    if (source.connector_type === "s3") {
      if (connState.useExisting) return connId ? { connection_id: connId } : null;
      if (!source.s3_bucket || !source.s3_key) return null;
      return {
        s3_bucket: source.s3_bucket, s3_key: source.s3_key, s3_file_type: source.s3_file_type,
        s3_access_key: source.s3_access_key, s3_secret_key: source.s3_secret_key,
      };
    }

    if (source.connector_type === "salesforce") {
      if (!source.sf_crm_object_name.trim() && !source.sf_crm_soql_query.trim()) return null;
      if (connState.useExisting) {
        return connId ? { connection_id: connId, sf_crm_object_name: source.sf_crm_object_name, sf_crm_soql_query: source.sf_crm_soql_query } : null;
      }
      const hasAuth = (source.sf_crm_access_token && source.sf_crm_instance_url) ||
        (source.sf_crm_client_id && source.sf_crm_client_secret && source.sf_crm_username && source.sf_crm_password);
      if (!hasAuth) return null;
      return {
        sf_crm_access_token: source.sf_crm_access_token, sf_crm_instance_url: source.sf_crm_instance_url,
        sf_crm_login_url: source.sf_crm_login_url, sf_crm_client_id: source.sf_crm_client_id,
        sf_crm_client_secret: source.sf_crm_client_secret, sf_crm_username: source.sf_crm_username,
        sf_crm_password: source.sf_crm_password, sf_crm_security_token: source.sf_crm_security_token,
        sf_crm_object_name: source.sf_crm_object_name, sf_crm_soql_query: source.sf_crm_soql_query,
      };
    }

    if (source.connector_type === "hubspot") {
      if (connState.useExisting) return connId ? { connection_id: connId, hs_object_type: source.hs_object_type } : null;
      if (!source.hs_access_token.trim()) return null;
      return { hs_access_token: source.hs_access_token, hs_object_type: source.hs_object_type };
    }

    if (source.connector_type === "zoho") {
      if (!source.zoho_module.trim()) return null;
      if (connState.useExisting) return connId ? { connection_id: connId, zoho_module: source.zoho_module, zoho_criteria: source.zoho_criteria } : null;
      const hasAuth = source.zoho_access_token || (source.zoho_refresh_token && source.zoho_client_id && source.zoho_client_secret);
      if (!hasAuth) return null;
      return {
        zoho_access_token: source.zoho_access_token, zoho_refresh_token: source.zoho_refresh_token,
        zoho_client_id: source.zoho_client_id, zoho_client_secret: source.zoho_client_secret,
        zoho_accounts_url: source.zoho_accounts_url, zoho_api_domain: source.zoho_api_domain,
        zoho_module: source.zoho_module, zoho_criteria: source.zoho_criteria,
      };
    }

    if (source.connector_type === "google_sheets") {
      if (connState.useExisting) return connId ? { connection_id: connId } : null;
      return source.sheet_url.trim() ? { sheet_url: source.sheet_url } : null;
    }

    if (source.connector_type === "api") {
      if (connState.useExisting) return connId ? { connection_id: connId } : null;
      if (!source.api_url.trim()) return null;
      if (!source.api_config.trim()) return { api_url: source.api_url };
      try {
        return { api_url: source.api_url, api_config: JSON.parse(source.api_config) };
      } catch {
        return null;
      }
    }

    return null;
  };

  const updateConnectionState = (index: number, key: keyof SourceConnectionState, value: string | boolean) => {
    setSourceConnectionStates((current) => {
      const existingState = current[index] ?? { useExisting: false, selectedConnectionId: "", connectionError: "" };
      return { ...current, [index]: { ...existingState, [key]: value } };
    });
    // A different saved connection (or leaving/entering "use existing")
    // means a different folder/query — the previously-picked preview file
    // no longer applies, same as CreatePipeline.tsx.
    if (key === "selectedConnectionId" || key === "useExisting") {
      setExistingConnFilePath(index, "");
    }
  };

  const populateFromConnection = (index: number, connId: string) => {
    const conn = getFilteredConnections(sources[index].connector_type).find((c: any) => String(c.id) === connId);
    if (conn?.config) {
      const cfg = conn.config;
      const connectorType = sources[index].connector_type;

      if (connectorType === "postgres") {
        updateSource(index, "src_pg_host", cfg.host || "");
        updateSource(index, "src_pg_db", cfg.database || "");
        updateSource(index, "src_pg_user", cfg.user || "");
        updateSource(index, "src_pg_password", "");
        updateSource(index, "src_pg_port", cfg.port || "5432");
      } else if (connectorType === "mysql") {
        updateSource(index, "src_my_host", cfg.host || "");
        updateSource(index, "src_my_db", cfg.database || "");
        updateSource(index, "src_my_user", cfg.user || "");
        updateSource(index, "src_my_password", "");
        updateSource(index, "src_my_port", cfg.port || "3306");
      } else if (connectorType === "oracle") {
        updateSource(index, "src_ora_host", cfg.host || "");
        updateSource(index, "src_ora_db", cfg.database || "");
        updateSource(index, "src_ora_user", cfg.user || "");
        updateSource(index, "src_ora_password", "");
        updateSource(index, "src_ora_port", cfg.port || "1521");
      } else if (connectorType === "mongodb") {
        updateSource(index, "src_mongo_host", cfg.host || "");
        updateSource(index, "src_mongo_db", cfg.database || "");
        updateSource(index, "src_mongo_user", cfg.user || "");
        updateSource(index, "src_mongo_password", "");
        updateSource(index, "src_mongo_port", cfg.port || "27017");
        updateSource(index, "src_mongo_connection_string", "");
        updateSource(index, "mongo_collection", cfg.collection || "");
      } else if (connectorType === "s3") {
        updateSource(index, "s3_bucket", cfg.bucket || "");
        updateSource(index, "s3_key", cfg.prefix || "");
        updateSource(index, "s3_file_type", cfg.file_type || "csv");
        updateSource(index, "s3_access_key", "");
        updateSource(index, "s3_secret_key", "");
      } else if (connectorType === "snowflake") {
        updateSource(index, "sf_account", cfg.account || "");
        updateSource(index, "sf_user", cfg.user || "");
        updateSource(index, "sf_password", "");
        updateSource(index, "sf_warehouse", cfg.warehouse || "");
        updateSource(index, "sf_database", cfg.database || "");
        updateSource(index, "sf_schema", cfg.schema || "PUBLIC");
        updateSource(index, "sf_role", cfg.role || "");
      } else if (connectorType === "salesforce") {
        updateSource(index, "sf_crm_login_url", cfg.login_url || "https://login.salesforce.com");
        updateSource(index, "sf_crm_instance_url", cfg.instance_url || "");
      } else if (connectorType === "zoho") {
        updateSource(index, "zoho_accounts_url", cfg.accounts_url || "https://accounts.zoho.com");
        updateSource(index, "zoho_api_domain", cfg.api_domain || "https://www.zohoapis.com");
      } else if (connectorType === "api") {
        updateSource(index, "api_url", cfg.base_url || "");
      } else if (connectorType === "google_sheets") {
        updateSource(index, "sheet_url", cfg.sheet_url || "");
      } else if (connectorType === "csv" || connectorType === "excel") {
        updateSource(index, "folder_path", cfg.base_path || "");
        updateSource(index, "file_path", "");
        updateSource(index, "s3_file_type", cfg.file_type || "csv");
      }
    }
  };

  const handleConnectorTypeChange = (index: number, newType: string) => {
    updateSource(index, "connector_type", newType);
    setSourceConnectionStates((current) => ({
      ...current,
      [index]: { useExisting: false, selectedConnectionId: "", connectionError: "" },
    }));
    updateSource(index, "connection_id", null);
    updateSource(index, "file_path", "");
    updateSource(index, "folder_path", "");
    updateSource(index, "sheet_url", "");
    updateSource(index, "api_url", "");
    updateSource(index, "api_config", "");
    updateSource(index, "s3_bucket", "");
    updateSource(index, "s3_key", "");
    updateSource(index, "s3_file_type", "csv");
    updateSource(index, "s3_access_key", "");
    updateSource(index, "s3_secret_key", "");
    updateSource(index, "src_pg_host", "");
    updateSource(index, "src_pg_db", "");
    updateSource(index, "src_pg_user", "");
    updateSource(index, "src_pg_password", "");
    updateSource(index, "src_pg_port", "5432");
    updateSource(index, "pg_query", "");
    updateSource(index, "pg_query_mode", "table");
    updateSource(index, "pg_source_table", "");
    updateSource(index, "src_my_host", "");
    updateSource(index, "src_my_db", "");
    updateSource(index, "src_my_user", "");
    updateSource(index, "src_my_password", "");
    updateSource(index, "src_my_port", "3306");
    updateSource(index, "my_query", "");
    updateSource(index, "src_ora_host", "");
    updateSource(index, "src_ora_db", "");
    updateSource(index, "src_ora_user", "");
    updateSource(index, "src_ora_password", "");
    updateSource(index, "src_ora_port", "1521");
    updateSource(index, "ora_query", "");
    updateSource(index, "src_mongo_host", "");
    updateSource(index, "src_mongo_db", "");
    updateSource(index, "src_mongo_user", "");
    updateSource(index, "src_mongo_password", "");
    updateSource(index, "src_mongo_port", "27017");
    updateSource(index, "src_mongo_connection_string", "");
    updateSource(index, "mongo_collection", "");
    updateSource(index, "mongo_query", "");
    updateSource(index, "sf_account", "");
    updateSource(index, "sf_user", "");
    updateSource(index, "sf_password", "");
    updateSource(index, "sf_warehouse", "");
    updateSource(index, "sf_database", "");
    updateSource(index, "sf_schema", "PUBLIC");
    updateSource(index, "sf_query", "");
    updateSource(index, "sf_role", "");
    updateSource(index, "sf_query_mode", "table");
    updateSource(index, "sf_source_table", "");
    updateSource(index, "sf_crm_access_token", "");
    updateSource(index, "sf_crm_instance_url", "");
    updateSource(index, "sf_crm_login_url", "https://login.salesforce.com");
    updateSource(index, "sf_crm_client_id", "");
    updateSource(index, "sf_crm_client_secret", "");
    updateSource(index, "sf_crm_username", "");
    updateSource(index, "sf_crm_password", "");
    updateSource(index, "sf_crm_security_token", "");
    updateSource(index, "sf_crm_object_name", "");
    updateSource(index, "sf_crm_soql_query", "");
    updateSource(index, "hs_access_token", "");
    updateSource(index, "hs_object_type", "contacts");
    updateSource(index, "hs_properties", "");
    updateSource(index, "zoho_access_token", "");
    updateSource(index, "zoho_refresh_token", "");
    updateSource(index, "zoho_client_id", "");
    updateSource(index, "zoho_client_secret", "");
    updateSource(index, "zoho_accounts_url", "https://accounts.zoho.com");
    updateSource(index, "zoho_api_domain", "https://www.zohoapis.com");
    updateSource(index, "zoho_module", "");
    updateSource(index, "zoho_criteria", "");
    setExistingConnFilePath(index, "");
    setSourceQualities((current) => ({ ...current, [index]: null }));
    setSourceSchemas((current) => ({ ...current, [index]: null }));
  };

  const addSource = () => {
    setSources((current) => [...current, blankSource()]);
    setActiveSourceTab(sources.length); // jump to the new tab
  };

  const removeSource = (index: number) => {
    setSources((current) => current.filter((_, i) => i !== index));
    setSourceConnectionStates((current) => {
      const next: Record<number, SourceConnectionState> = {};
      Object.entries(current).forEach(([key, val]) => {
        const i = Number(key);
        if (i < index) next[i] = val;
        else if (i > index) next[i - 1] = val;
      });
      return next;
    });
    setSourceQualities((current) => {
      const next: Record<number, BuiltQuality | null> = {};
      Object.entries(current).forEach(([key, val]) => {
        const i = Number(key);
        if (i < index) next[i] = val;
        else if (i > index) next[i - 1] = val;
      });
      return next;
    });
    setSourceSchemas((current) => {
      const next: Record<number, BuiltSchema | null> = {};
      Object.entries(current).forEach(([key, val]) => {
        const i = Number(key);
        if (i < index) next[i] = val;
        else if (i > index) next[i - 1] = val;
      });
      return next;
    });
    setExistingConnFilePaths((current) => {
      const next: Record<number, string> = {};
      Object.entries(current).forEach(([key, val]) => {
        const i = Number(key);
        if (i < index) next[i] = val;
        else if (i > index) next[i - 1] = val;
      });
      return next;
    });
    setActiveSourceTab((current) => Math.max(0, current >= index ? current - 1 : current));
  };

  const create = useMutation({
    mutationFn: async () => {
      if (useSavedDestination && !selectedDestinationConnectionId) {
        setDestinationError("Please select a saved destination connection");
        throw new Error("No destination connection selected");
      }

      const destinationFields = useSavedDestination
        ? {
            destination_type: destinationType,
            destination_connection_id: parseInt(selectedDestinationConnectionId, 10),
            destination_config: null,
          }
        : {
            destination_type: destinationType,
            destination_connection_id: null,
            destination_config: destinationManualConfig,
          };

      const sourcesWithConnectionId = sources.map((source, index) => {
        const connState = sourceConnectionStates[index];
        const connectionId = connState?.useExisting && connState?.selectedConnectionId
          ? parseInt(connState.selectedConnectionId)
          : null;

        let parsedApiConfig: Record<string, unknown> | null = null;
        if (source.connector_type === "api" && source.api_config.trim()) {
          try {
            parsedApiConfig = JSON.parse(source.api_config);
          } catch (e) {
            throw new Error(`Source ${index + 1}: Invalid JSON in Advanced Config`);
          }
        }

        const cleaned: any = { ...source, connection_id: connectionId, api_config: parsedApiConfig };

        // ── Force-resolve final pg_query / sf_query at submit time — never
        // rely on onChange having fired correctly. ──
        if (source.connector_type === "postgres") {
          cleaned.pg_query = source.pg_query_mode === "table"
            ? buildSelectQuery(source.pg_source_table)
            : source.pg_query;
        }
        if (source.connector_type === "snowflake") {
          cleaned.sf_query = source.sf_query_mode === "table"
            ? buildSnowflakeSelectQuery(source.sf_source_table)
            : source.sf_query;
        }
        // Every source carries hs_properties (only meaningful for HubSpot),
        // but the backend model expects Optional[List[str]] — a raw ""
        // string fails validation. Normalize it for ALL source types, not
        // just HubSpot, so non-HubSpot sources send null instead of "".
        cleaned.hs_properties = source.connector_type === "hubspot"
          ? (splitList(source.hs_properties).length ? splitList(source.hs_properties) : null)
          : null;

        if (connectionId) {
          for (const field of SECRET_FIELDS) {
            cleaned[field] = "";
          }
        }

        // ── Post-load quality gate removed from this form — always send
        // "off" values so the backend's optional fields fall back to
        // their defaults. ──
        cleaned.quality_connection_id = null;
        cleaned.quality_config = null;
        cleaned.quality_on_fail = "warn";

        // ── Pre-ingest DataFrame gate — runs before THIS source's load —
        // built by <DataQualityBuilder> from a friendly preview, just like
        // CreatePipeline.tsx / DirectIngest.tsx. ──
        const dfQuality = sourceQualities[index];
        cleaned.df_quality_config = dfQuality?.hasAnyCheck ? dfQuality.config : null;
        cleaned.df_quality_on_fail = dfQuality?.on_fail ?? "warn";

        // ── Optional user-defined schema override for this source — built
        // by <SchemaBuilder> from the same preview data. ──
        const schemaBuilt = sourceSchemas[index];
        cleaned.custom_schema = schemaBuilt?.hasAnyCustomType ? schemaBuilt.schema : null;

        return cleaned;
      });

      const response = await api.post("/create_multi_pipeline", {
        pipeline_name: pipelineName,
        table_name: tableName,
        option,
        schedule: buildCron(schedule),
        timezone: schedule.timezone,
        sync_mode: "full",
        sources: sourcesWithConnectionId,
        ...destinationFields,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });

      // Reset the whole form so the user can immediately create another
      // pipeline without manually going Back through every step, and
      // without accidentally resubmitting the same pipeline_name (which
      // the backend rejects as "already exists").
      setPipelineName("");
      setTableName("");
      setSchedule(defaultSchedule);
      setOption("1");
      setSources([blankSource()]);
      setSourceConnectionStates({});
      setApiConfigErrors({});
      setSourceQualities({});
      setSourceSchemas({});
      setExistingConnFilePaths({});
      setStepError("");
      setCurrentStep(1);
      setActiveSourceTab(0);
    },
  });

  // ── Step + per-source validation ──────────────────────────────────────
  const validateSource = (index: number): string => {
    const source = sources[index];
    const connState = sourceConnectionStates[index];
    const label = `Source ${index + 1}`;

    if (SUPPORTS_CONNECTIONS.includes(source.connector_type) && connState?.useExisting) {
      if (!connState.selectedConnectionId) return `${label}: select a saved connection, or switch to New Connection.`;
      // still fall through to table/query validation below
    }

    if (["csv", "excel"].includes(source.connector_type) && !source.file_path && !source.folder_path) {
      return `${label}: provide a file path or folder path.`;
    }
    if (source.connector_type === "google_sheets" && !source.sheet_url.trim()) return `${label}: sheet URL is required.`;
    if (source.connector_type === "api" && !source.api_url.trim()) return `${label}: API URL is required.`;
    if (source.connector_type === "api" && source.api_config.trim()) {
      try { JSON.parse(source.api_config); } catch { return `${label}: Advanced Config has invalid JSON.`; }
    }
    if (source.connector_type === "postgres") {
      if (!connState?.useExisting && (!source.src_pg_host || !source.src_pg_db || !source.src_pg_user)) {
        return `${label}: host, database, and user are required.`;
      }
      const hasQuery = source.pg_query_mode === "table" ? source.pg_source_table.trim() : source.pg_query.trim();
      if (!hasQuery) return `${label}: table name or SQL query is required.`;
    }
    if (source.connector_type === "mysql") {
      if (!connState?.useExisting && (!source.src_my_host || !source.src_my_db || !source.src_my_user)) {
        return `${label}: host, database, and user are required.`;
      }
      if (!source.my_query.trim()) return `${label}: SQL query is required.`;
    }
    if (source.connector_type === "oracle") {
      if (!connState?.useExisting && (!source.src_ora_host || !source.src_ora_db || !source.src_ora_user)) {
        return `${label}: host, service name, and user are required.`;
      }
      if (!source.ora_query.trim()) return `${label}: SQL query is required.`;
    }
    if (source.connector_type === "mongodb") {
      if (!connState?.useExisting) {
        if (!source.src_mongo_connection_string && (!source.src_mongo_host || !source.src_mongo_db)) {
          return `${label}: host and database (or a connection string) are required.`;
        }
        if (source.src_mongo_connection_string && !source.src_mongo_db) {
          return `${label}: database is required.`;
        }
      }
      if (!source.mongo_collection.trim()) return `${label}: collection is required.`;
    }
    if (source.connector_type === "s3" && (!source.s3_bucket || !source.s3_key)) return `${label}: bucket and key are required.`;
    if (source.connector_type === "snowflake") {
      if (!connState?.useExisting && (!source.sf_account || !source.sf_user || !source.sf_warehouse || !source.sf_database)) {
        return `${label}: account, user, warehouse, and database are required.`;
      }
      const hasQuery = source.sf_query_mode === "table" ? source.sf_source_table.trim() : source.sf_query.trim();
      if (!hasQuery) return `${label}: table name or SQL query is required.`;
    }
    if (source.connector_type === "salesforce") {
      if (!connState?.useExisting) {
        const hasAuth = (source.sf_crm_access_token && source.sf_crm_instance_url) ||
          (source.sf_crm_client_id && source.sf_crm_client_secret && source.sf_crm_username && source.sf_crm_password);
        if (!hasAuth) return `${label}: Salesforce needs an access token + instance URL, or client id/secret + username/password.`;
      }
      if (!source.sf_crm_object_name.trim() && !source.sf_crm_soql_query.trim()) {
        return `${label}: object name or SOQL query is required for Salesforce.`;
      }
    }
    if (source.connector_type === "hubspot") {
      if (!connState?.useExisting && !source.hs_access_token.trim()) return `${label}: HubSpot access token is required.`;
    }
    if (source.connector_type === "zoho") {
      if (!connState?.useExisting) {
        const hasAuth = source.zoho_access_token.trim() ||
          (source.zoho_refresh_token.trim() && source.zoho_client_id.trim() && source.zoho_client_secret.trim());
        if (!hasAuth) return `${label}: Zoho needs an access token, or refresh token + client id/secret.`;
      }
      if (!source.zoho_module.trim()) return `${label}: module is required for Zoho.`;
    }
    return "";
  };

  const validateStep = (step: number): string => {
    if (step === 1) {
      if (!pipelineName.trim()) return "Pipeline name is required.";
      if (!tableName.trim()) return "Target table is required.";
      return "";
    }
    if (step === 2) {
      if (sources.length === 0) return "At least one source is required.";
      for (let i = 0; i < sources.length; i++) {
        const err = validateSource(i);
        if (err) {
          setActiveSourceTab(i);
          return err;
        }
      }
      return "";
    }
    return "";
  };

  const goNext = () => {
    const err = validateStep(currentStep);
    if (err) { setStepError(err); return; }
    setStepError("");
    setCurrentStep((s) => Math.min(s + 1, STEPS.length));
  };

  const goBack = () => {
    setStepError("");
    setCurrentStep((s) => Math.max(s - 1, 1));
  };

  const goToStep = (step: number) => {
    if (step < currentStep) { setStepError(""); setCurrentStep(step); return; }
    for (let s = currentStep; s < step; s++) {
      const err = validateStep(s);
      if (err) { setStepError(err); return; }
    }
    setStepError("");
    setCurrentStep(step);
  };

  // ── Saved csv/excel connection → files in its folder, for the active
  // source tab only (a single top-level hook call, same as
  // CreatePipeline.tsx's savedFolderFiles — safe under rules-of-hooks
  // regardless of how many sources exist). ──────────────────────────────
  const activeSource: Source | undefined = sources[activeSourceTab];
  const activeConnState: SourceConnectionState =
    sourceConnectionStates[activeSourceTab] ?? { useExisting: false, selectedConnectionId: "", connectionError: "" };

  const savedFolderFiles = useQuery({
    queryKey: ["saved-connection-files", activeSourceTab, activeSource?.folder_path],
    enabled: activeConnState.useExisting
      && ["csv", "excel"].includes(activeSource?.connector_type ?? "")
      && !!activeSource?.folder_path,
    queryFn: async () => (await api.get("/list_folder_files", {
      params: { folder_path: activeSource!.folder_path },
    })).data as { folder_path: string; files: string[] },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setResult(null);
    setStepError("");

    const err = validateStep(2);
    if (err) {
      setStepError(err);
      setCurrentStep(2);
      return;
    }

    create.mutate();
  };

  return (
    <div className="space-y-5">
      <PageHeader
        icon={Network}
        eyebrow="Build"
        title="Multi-Source Pipeline"
        description="Join tables that live in different systems into a single pipeline."
      />

      {/* ── Stepper ─────────────────────────────────────────────────── */}
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
                         ? "border-emerald-600 bg-emerald-50 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400"
                         : "border-border bg-background text-muted-foreground group-hover:border-muted-foreground"
                     }`}
                   >
                     {step.id < currentStep ? <Check className="h-4 w-4" /> : step.id}
                   </span>
                   <span className={`hidden text-sm font-medium sm:block ${step.id === currentStep ? "text-foreground" : step.id < currentStep ? "text-emerald-700 dark:text-emerald-400" : "text-muted-foreground"}`}>
                     {step.label}
                   </span>
                 </button>
                 {idx < STEPS.length - 1 && <div className={`mx-3 h-0.5 flex-1 ${step.id < currentStep ? "bg-emerald-600" : "bg-border"}`} />}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Step {currentStep} of {STEPS.length}: {STEPS[currentStep - 1].label}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">

            {/* ══════════════════ STEP 1 — BASIC INFO ══════════════════ */}
            {currentStep === 1 && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <label className="space-y-1 text-sm font-medium">
                  Pipeline name
                  <Input value={pipelineName} onChange={(e) => setPipelineName(e.target.value)} placeholder="e.g. combined_sales_pipeline" required />
                </label>
                <label className="space-y-1 text-sm font-medium">
                  Target table
                  <Input value={tableName} onChange={(e) => setTableName(e.target.value)} placeholder="e.g. combined_sales" required />
                </label>
                <label className="space-y-1 text-sm font-medium">
                  Load option (first source)
                  <select className="select-control" value={option} onChange={(e) => setOption(e.target.value)}>
                    <option value="1">Append</option>
                    <option value="2">Overwrite</option>
                    <option value="3">Create new</option>
                  </select>
                </label>
                <p className="text-xs text-muted-foreground md:col-span-3">
                  Note: only the first source uses this load option. Every subsequent source always appends, so it can't overwrite rows from earlier sources.
                </p>

                {/* ── Destination — one table, one destination for the
                     whole pipeline, applies to every source above. ── */}
                <div className="md:col-span-3 rounded-md border border-border bg-card p-4 space-y-3">
                  <div className="text-sm font-medium text-foreground">Destination</div>
                  <label className="block max-w-xs space-y-1 text-sm font-medium text-foreground">
                    Write to
                    <select
                      className="select-control"
                      value={destinationType}
                      onChange={(e) => { setDestinationType(e.target.value); setDestinationManualConfig({}); setSelectedDestinationConnectionId(""); setDestinationError(""); }}
                    >
                      {destinationTypes.map((d: any) => (
                        <option key={d.type} value={d.type}>{d.label}</option>
                      ))}
                    </select>
                  </label>

                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                      <input
                        type="radio"
                        name="multiDestinationMode"
                        checked={!useSavedDestination}
                        onChange={() => { setUseSavedDestination(false); setSelectedDestinationConnectionId(""); setDestinationError(""); }}
                      />
                      <Link2Off className="h-4 w-4" /> New connection
                    </label>
                    <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                      <input
                        type="radio"
                        name="multiDestinationMode"
                        checked={useSavedDestination}
                        onChange={() => { setUseSavedDestination(true); setDestinationError(""); }}
                      />
                      <Link2 className="h-4 w-4" /> Use saved connection
                    </label>
                  </div>

                  {useSavedDestination ? (
                    <div className="space-y-1">
                      <select
                        className="select-control max-w-md"
                        value={selectedDestinationConnectionId}
                        onChange={(e) => setSelectedDestinationConnectionId(e.target.value)}
                      >
                        <option value="">Select a saved {activeDestination?.label ?? destinationType} connection…</option>
                        {filteredDestinationConnections.map((c: any) => (
                          <option key={c.id} value={String(c.id)}>{c.name}</option>
                        ))}
                      </select>
                      {filteredDestinationConnections.length === 0 && (
                        <p className="text-xs text-muted-foreground">
                          No saved {activeDestination?.label ?? destinationType} connections yet — add one on the Connections page, or use "New connection" instead.
                        </p>
                      )}
                      {destinationError && <p className="text-xs text-rose-600 dark:text-rose-400">{destinationError}</p>}
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                      {(activeDestination?.fields ?? []).map((field: string) => (
                        <Input
                          key={field}
                          type={field === "password" ? "password" : "text"}
                          placeholder={DESTINATION_FIELD_LABELS[field] ?? field}
                          value={destinationManualConfig[field] ?? (field === "schema" ? "PUBLIC" : "")}
                          onChange={(e) => updateDestinationField(field, e.target.value)}
                          required={field !== "role" && field !== "connection_string"}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ══════════════════ STEP 2 — SOURCES (tabs) ══════════════════ */}
            {currentStep === 2 && (
              <div className="space-y-4">
                {/* Tab bar */}
                <div className="flex flex-wrap items-center gap-2 border-b border-border pb-2">
                   {sources.map((source, index) => (
                     <button
                       key={index}
                       type="button"
                       onClick={() => setActiveSourceTab(index)}
                       className={`flex items-center gap-2 rounded-t-md px-3 py-1.5 text-sm font-medium transition-colors ${
                         activeSourceTab === index
                           ? "bg-muted text-foreground"
                           : "text-muted-foreground hover:bg-muted/50"
                       }`}
                     >
                       Source {index + 1}
                       <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{CONNECTOR_LABELS[source.connector_type]}</span>
                      {sources.length > 1 && (
                        <Trash2
                          className="h-3 w-3 text-muted-foreground hover:text-destructive"
                          onClick={(e) => { e.stopPropagation(); removeSource(index); }}
                        />
                      )}
                    </button>
                  ))}
                  <Button type="button" variant="outline" size="sm" onClick={addSource}>
                    <Plus className="h-3.5 w-3.5" /> Add Source
                  </Button>
                </div>

                {/* Active source's config panel */}
                {sources.map((source, index) => {
                  if (index !== activeSourceTab) return null;
                  const connState = sourceConnectionStates[index] || { useExisting: false, selectedConnectionId: "", connectionError: "" };
                  const filteredConnections = getFilteredConnections(source.connector_type);
                  const fieldsRequired = !connState.useExisting;

                  return (
                    <div key={index} className="space-y-4">
                      <label className="space-y-1 text-sm font-medium block max-w-xs">
                        Connector type
                        <select
                          className="select-control"
                          value={source.connector_type}
                          onChange={(e) => handleConnectorTypeChange(index, e.target.value)}
                        >
                          {Object.keys(CONNECTOR_LABELS).map((c) => (
                            <option key={c} value={c}>{CONNECTOR_LABELS[c]}</option>
                          ))}
                        </select>
                      </label>

                      {SUPPORTS_CONNECTIONS.includes(source.connector_type) && (
                         <div className="rounded-md border border-border bg-muted/50 p-3">
                          <div className="flex items-center gap-4">
                            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                              <input
                                type="radio"
                                name={`connectionMode-${index}`}
                                checked={!connState.useExisting}
                                onChange={() => {
                                  updateConnectionState(index, "useExisting", false);
                                  updateConnectionState(index, "selectedConnectionId", "");
                                  updateConnectionState(index, "connectionError", "");
                                  updateSource(index, "connection_id", null);
                                }}
                              />
                              <Link2Off className="h-4 w-4" /> New Connection
                            </label>
                            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                              <input
                                type="radio"
                                name={`connectionMode-${index}`}
                                checked={connState.useExisting}
                                onChange={() => updateConnectionState(index, "useExisting", true)}
                              />
                              <Link2 className="h-4 w-4" /> Use Saved Connection
                            </label>
                          </div>
                          {connState.useExisting && (
                            <div className="mt-3">
                              {connections.isLoading ? (
                                <p className="text-sm text-muted-foreground">Loading connections...</p>
                              ) : filteredConnections.length === 0 ? (
                                <p className="text-sm text-destructive">No saved connections for this connector type. Please create a new connection.</p>
                              ) : (
                                <select
                                  className="select-control"
                                  value={connState.selectedConnectionId}
                                  onChange={(e) => {
                                    updateConnectionState(index, "selectedConnectionId", e.target.value);
                                    updateConnectionState(index, "connectionError", "");
                                    populateFromConnection(index, e.target.value);
                                  }}
                                >
                                  <option value="">Select a connection</option>
                                  {filteredConnections.map((conn: any) => (
                                    <option key={conn.id} value={conn.id}>{conn.name}</option>
                                  ))}
                                </select>
                              )}
                              {connState.connectionError && <p className="mt-2 text-sm text-destructive">{connState.connectionError}</p>}
                            </div>
                          )}
                        </div>
                      )}

                      {["csv", "excel"].includes(source.connector_type) && (
                        connState.useExisting ? (
                          <div className="space-y-3">
                            <Input placeholder="Folder path (from saved connection)" value={source.folder_path} readOnly disabled />
                            {/* ── Saved csv/excel connection → pick a file from its
                                 folder to preview & build quality checks against,
                                 the same way FolderUpload does for a brand-new
                                 connection below. ── */}
                            {source.folder_path && (
                              <div className="rounded-md border border-border bg-muted/50 p-3">
                                <p className="mb-2 text-xs font-medium text-muted-foreground">
                                  Pick a file from this connection's folder to preview & build quality checks. Every matching file in the folder is still ingested — checks apply to all of them.
                                </p>
                                {savedFolderFiles.isLoading ? (
                                  <p className="text-sm text-muted-foreground">Loading files…</p>
                                ) : savedFolderFiles.isError ? (
                                  <p className="text-sm text-rose-600 dark:text-rose-400">
                                    {(savedFolderFiles.error as any)?.response?.data?.detail ?? "Couldn't list files in this folder."}
                                  </p>
                                ) : (savedFolderFiles.data?.files.length ?? 0) === 0 ? (
                                  <p className="text-sm text-muted-foreground">No files found in this connection's folder.</p>
                                ) : (
                                  <select
                                    className="select-control"
                                    value={existingConnFilePaths[index] ?? ""}
                                    onChange={(e) => setExistingConnFilePath(index, e.target.value)}
                                  >
                                    <option value="">Select a file to preview</option>
                                    {savedFolderFiles.data?.files.map((f) => (
                                      <option key={f} value={`${source.folder_path}/${f}`}>{f}</option>
                                    ))}
                                  </select>
                                )}
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="space-y-3">
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                              <Input placeholder="File path" value={source.file_path} onChange={(e) => updateSource(index, "file_path", e.target.value)} />
                              <Input placeholder="Folder path (all files in it)" value={source.folder_path} onChange={(e) => updateSource(index, "folder_path", e.target.value)} />
                            </div>
                            <FolderUpload
                              connectorType={source.connector_type as "csv" | "excel"}
                              onFolderResolved={(folderPath) => { updateSource(index, "folder_path", folderPath); updateSource(index, "file_path", ""); }}
                              onFileResolved={(filePath) => { updateSource(index, "file_path", filePath); updateSource(index, "folder_path", ""); }}
                            />
                          </div>
                        )
                      )}
                      {source.connector_type === "google_sheets" && (
                        <Input placeholder="Sheet URL" value={source.sheet_url} onChange={(e) => updateSource(index, "sheet_url", e.target.value)} required={fieldsRequired} />
                      )}
                      {source.connector_type === "api" && (
                        <div className="space-y-2">
                          <Input placeholder="API URL" value={source.api_url} onChange={(e) => updateSource(index, "api_url", e.target.value)} required={fieldsRequired} />
                          <label className="space-y-1 text-sm font-medium block">
                            Advanced Config (optional JSON)
                            <textarea
                              className="min-h-32 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                              placeholder='{"method": "GET", "records_path": "products"}'
                              value={source.api_config}
                              onChange={(e) => {
                                updateSource(index, "api_config", e.target.value);
                                setApiConfigErrors((current) => ({ ...current, [index]: "" }));
                              }}
                            />
                          </label>
                           {apiConfigErrors[index] && <p className="text-sm text-destructive">{apiConfigErrors[index]}</p>}
                        </div>
                      )}
                      {source.connector_type === "s3" && (
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                          <Input placeholder="Bucket" value={source.s3_bucket} onChange={(e) => updateSource(index, "s3_bucket", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input placeholder="Key" value={source.s3_key} onChange={(e) => updateSource(index, "s3_key", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input placeholder="File type" value={source.s3_file_type} onChange={(e) => updateSource(index, "s3_file_type", e.target.value)} />
                          <Input
                            placeholder="Access key ID"
                            value={source.s3_access_key}
                            onChange={(e) => updateSource(index, "s3_access_key", e.target.value)}
                            required={fieldsRequired}
                            disabled={connState.useExisting}
                          />
                          <Input
                            type="password"
                            placeholder={connState.useExisting ? "(using saved connection)" : "Secret access key"}
                            value={connState.useExisting ? "" : source.s3_secret_key}
                            onChange={(e) => updateSource(index, "s3_secret_key", e.target.value)}
                            required={fieldsRequired}
                            disabled={connState.useExisting}
                          />
                        </div>
                      )}

                      {/* ── Postgres — credentials (new connection only) + table/query toggle ── */}
                      {source.connector_type === "postgres" && (
                        <div className="space-y-4">
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <Input placeholder="Host" value={source.src_pg_host} onChange={(e) => updateSource(index, "src_pg_host", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input placeholder="Database" value={source.src_pg_db} onChange={(e) => updateSource(index, "src_pg_db", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input placeholder="User" value={source.src_pg_user} onChange={(e) => updateSource(index, "src_pg_user", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input
                              type="password"
                              placeholder={connState.useExisting ? "(using saved connection)" : "Password"}
                              value={connState.useExisting ? "" : source.src_pg_password}
                              onChange={(e) => updateSource(index, "src_pg_password", e.target.value)}
                              required={fieldsRequired}
                              disabled={connState.useExisting}
                            />
                            <Input placeholder="Port" value={source.src_pg_port} onChange={(e) => updateSource(index, "src_pg_port", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          </div>

                          <LiveTablePicker
                            fieldKey={`multisource-postgres-${index}`}
                            mode={source.pg_query_mode === "table" ? "table" : "query"}
                            onModeChange={(m) => updateSource(index, "pg_query_mode", m === "table" ? "table" : "custom")}
                            tableInput={source.pg_source_table}
                            onTableInputChange={(v) => updateSource(index, "pg_source_table", v)}
                            queryValue={source.pg_query}
                            onQueryChange={(v) => updateSource(index, "pg_query", v)}
                            buildQuery={buildSelectQuery}
                            canFetch={
                              connState.useExisting
                                ? !!connState.selectedConnectionId
                                : !!(source.src_pg_host && source.src_pg_db && source.src_pg_user)
                            }
                            buildPayload={() =>
                              connState.useExisting && connState.selectedConnectionId
                                ? { connector_type: "postgres", connection_id: parseInt(connState.selectedConnectionId, 10) }
                                : {
                                    connector_type: "postgres",
                                    src_pg_host: source.src_pg_host,
                                    src_pg_db: source.src_pg_db,
                                    src_pg_user: source.src_pg_user,
                                    src_pg_password: source.src_pg_password,
                                    src_pg_port: source.src_pg_port,
                                  }
                            }
                          />
                        </div>
                      )}

                      {/* ── MySQL — credentials (new connection only) + SQL query ── */}
                      {source.connector_type === "mysql" && (
                        <div className="space-y-4">
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <Input placeholder="Host" value={source.src_my_host} onChange={(e) => updateSource(index, "src_my_host", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input placeholder="Database" value={source.src_my_db} onChange={(e) => updateSource(index, "src_my_db", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input placeholder="User" value={source.src_my_user} onChange={(e) => updateSource(index, "src_my_user", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input
                              type="password"
                              placeholder={connState.useExisting ? "(using saved connection)" : "Password"}
                              value={connState.useExisting ? "" : source.src_my_password}
                              onChange={(e) => updateSource(index, "src_my_password", e.target.value)}
                              required={fieldsRequired}
                              disabled={connState.useExisting}
                            />
                            <Input placeholder="Port" value={source.src_my_port} onChange={(e) => updateSource(index, "src_my_port", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          </div>
                          <textarea
                            className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            placeholder="SQL query"
                            value={source.my_query}
                            onChange={(e) => updateSource(index, "my_query", e.target.value)}
                          />
                        </div>
                      )}

                      {/* ── Oracle — credentials (new connection only) + SQL query ── */}
                      {source.connector_type === "oracle" && (
                        <div className="space-y-4">
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <Input placeholder="Host" value={source.src_ora_host} onChange={(e) => updateSource(index, "src_ora_host", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input placeholder="Service name" value={source.src_ora_db} onChange={(e) => updateSource(index, "src_ora_db", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input placeholder="User" value={source.src_ora_user} onChange={(e) => updateSource(index, "src_ora_user", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input
                              type="password"
                              placeholder={connState.useExisting ? "(using saved connection)" : "Password"}
                              value={connState.useExisting ? "" : source.src_ora_password}
                              onChange={(e) => updateSource(index, "src_ora_password", e.target.value)}
                              required={fieldsRequired}
                              disabled={connState.useExisting}
                            />
                            <Input placeholder="Port" value={source.src_ora_port} onChange={(e) => updateSource(index, "src_ora_port", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          </div>
                          <textarea
                            className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            placeholder="SQL query"
                            value={source.ora_query}
                            onChange={(e) => updateSource(index, "ora_query", e.target.value)}
                          />
                        </div>
                      )}

                      {/* ── MongoDB — credentials (new connection only) + collection/filter ── */}
                      {source.connector_type === "mongodb" && (
                        <div className="space-y-4">
                          <div className="space-y-3">
                            <Input
                              placeholder="Connection string (mongodb:// or mongodb+srv://) — optional"
                              value={source.src_mongo_connection_string}
                              onChange={(e) => updateSource(index, "src_mongo_connection_string", e.target.value)}
                              disabled={connState.useExisting}
                            />
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                              <Input placeholder="Host" value={source.src_mongo_host} onChange={(e) => updateSource(index, "src_mongo_host", e.target.value)} disabled={connState.useExisting || !!source.src_mongo_connection_string} />
                              <Input placeholder="Database" value={source.src_mongo_db} onChange={(e) => updateSource(index, "src_mongo_db", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                              <Input placeholder="User (optional)" value={source.src_mongo_user} onChange={(e) => updateSource(index, "src_mongo_user", e.target.value)} disabled={connState.useExisting || !!source.src_mongo_connection_string} />
                              <Input
                                type="password"
                                placeholder={connState.useExisting ? "(using saved connection)" : "Password (optional)"}
                                value={connState.useExisting ? "" : source.src_mongo_password}
                                onChange={(e) => updateSource(index, "src_mongo_password", e.target.value)}
                                disabled={connState.useExisting || !!source.src_mongo_connection_string}
                              />
                              <Input placeholder="Port" value={source.src_mongo_port} onChange={(e) => updateSource(index, "src_mongo_port", e.target.value)} disabled={connState.useExisting || !!source.src_mongo_connection_string} />
                            </div>
                          </div>
                          <Input placeholder="Collection" value={source.mongo_collection} onChange={(e) => updateSource(index, "mongo_collection", e.target.value)} required={fieldsRequired} />
                          <textarea
                            className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            placeholder='Filter (optional JSON), e.g. {"status": "active"} — leave blank to match all documents'
                            value={source.mongo_query}
                            onChange={(e) => updateSource(index, "mongo_query", e.target.value)}
                          />
                        </div>
                      )}

                      {/* ── Snowflake — credentials (new connection only) + table/query toggle ── */}
                      {source.connector_type === "snowflake" && (
                        <div className="space-y-4">
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <Input placeholder="Account" value={source.sf_account} onChange={(e) => updateSource(index, "sf_account", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input placeholder="User" value={source.sf_user} onChange={(e) => updateSource(index, "sf_user", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input
                              type="password"
                              placeholder={connState.useExisting ? "(using saved connection)" : "Password"}
                              value={connState.useExisting ? "" : source.sf_password}
                              onChange={(e) => updateSource(index, "sf_password", e.target.value)}
                              required={fieldsRequired}
                              disabled={connState.useExisting}
                            />
                            <Input placeholder="Warehouse" value={source.sf_warehouse} onChange={(e) => updateSource(index, "sf_warehouse", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input placeholder="Database" value={source.sf_database} onChange={(e) => updateSource(index, "sf_database", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input placeholder="Schema" value={source.sf_schema} onChange={(e) => updateSource(index, "sf_schema", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                            <Input placeholder="Role (optional)" value={source.sf_role} onChange={(e) => updateSource(index, "sf_role", e.target.value)} disabled={connState.useExisting} />
                          </div>

                          <LiveTablePicker
                            fieldKey={`multisource-snowflake-${index}`}
                            mode={source.sf_query_mode === "table" ? "table" : "query"}
                            onModeChange={(m) => updateSource(index, "sf_query_mode", m === "table" ? "table" : "custom")}
                            tableInput={source.sf_source_table}
                            onTableInputChange={(v) => updateSource(index, "sf_source_table", v)}
                            queryValue={source.sf_query}
                            onQueryChange={(v) => updateSource(index, "sf_query", v)}
                            buildQuery={buildSnowflakeSelectQuery}
                            canFetch={
                              connState.useExisting
                                ? !!connState.selectedConnectionId
                                : !!(source.sf_account && source.sf_user && source.sf_database)
                            }
                            buildPayload={() =>
                              connState.useExisting && connState.selectedConnectionId
                                ? { connector_type: "snowflake", connection_id: parseInt(connState.selectedConnectionId, 10) }
                                : {
                                    connector_type: "snowflake",
                                    sf_account: source.sf_account,
                                    sf_user: source.sf_user,
                                    sf_password: source.sf_password,
                                    sf_warehouse: source.sf_warehouse,
                                    sf_database: source.sf_database,
                                    sf_schema: source.sf_schema,
                                    sf_role: source.sf_role,
                                  }
                            }
                          />
                        </div>
                      )}

                      {/* ── Salesforce CRM — credentials (new connection only) + object/SOQL ── */}
                      {source.connector_type === "salesforce" && (
                        <div className="space-y-4">
                          {!connState.useExisting && (
                            <div className="space-y-3">
                              <p className="text-xs text-muted-foreground">
                                Either paste a ready access token + instance URL, or fill in client id/secret + username/password to log in fresh on every run.
                              </p>
                              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                                <Input placeholder="Access token (optional)" type="password" value={source.sf_crm_access_token} onChange={(e) => updateSource(index, "sf_crm_access_token", e.target.value)} required={fieldsRequired} />
                                <Input placeholder="Instance URL (optional)" value={source.sf_crm_instance_url} onChange={(e) => updateSource(index, "sf_crm_instance_url", e.target.value)} />
                              </div>
                              <Input placeholder="Login URL (default https://login.salesforce.com)" value={source.sf_crm_login_url} onChange={(e) => updateSource(index, "sf_crm_login_url", e.target.value)} disabled={connState.useExisting} />
                              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                                <Input placeholder="Client ID" value={source.sf_crm_client_id} onChange={(e) => updateSource(index, "sf_crm_client_id", e.target.value)} disabled={connState.useExisting} />
                                <Input placeholder="Client secret" type="password" value={connState.useExisting ? "" : source.sf_crm_client_secret} onChange={(e) => updateSource(index, "sf_crm_client_secret", e.target.value)} disabled={connState.useExisting} />
                                <Input placeholder="Username" value={source.sf_crm_username} onChange={(e) => updateSource(index, "sf_crm_username", e.target.value)} disabled={connState.useExisting} />
                                <Input placeholder="Password" type="password" value={connState.useExisting ? "" : source.sf_crm_password} onChange={(e) => updateSource(index, "sf_crm_password", e.target.value)} disabled={connState.useExisting} />
                              </div>
                              <Input placeholder="Security token (optional)" type="password" value={connState.useExisting ? "" : source.sf_crm_security_token} onChange={(e) => updateSource(index, "sf_crm_security_token", e.target.value)} disabled={connState.useExisting} />
                            </div>
                          )}
                          <div className="space-y-2">
                            <Input placeholder="Object name, e.g. Account, Contact, Lead, Opportunity" value={source.sf_crm_object_name} onChange={(e) => updateSource(index, "sf_crm_object_name", e.target.value)} />
                            <p className="text-xs text-muted-foreground">Or provide an explicit SOQL query below — it overrides the object name entirely.</p>
                            <textarea
                              className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                              placeholder="SOQL query (optional), e.g. SELECT Id, Name FROM Account"
                              value={source.sf_crm_soql_query}
                              onChange={(e) => updateSource(index, "sf_crm_soql_query", e.target.value)}
                            />
                          </div>
                        </div>
                      )}

                      {/* ── HubSpot — access token (new connection only) + object type ── */}
                      {source.connector_type === "hubspot" && (
                        <div className="space-y-4">
                          {!connState.useExisting && (
                            <div className="space-y-3">
                              <p className="text-xs text-muted-foreground">HubSpot Private App access tokens don't expire, so this is the only credential needed.</p>
                              <Input placeholder="Private App access token" type="password" value={source.hs_access_token} onChange={(e) => updateSource(index, "hs_access_token", e.target.value)} required={fieldsRequired} />
                            </div>
                          )}
                          <div className="space-y-2">
                            <label className="block max-w-xs space-y-1 text-sm font-medium">
                              Object type
                              <select className="select-control" value={source.hs_object_type} onChange={(e) => updateSource(index, "hs_object_type", e.target.value)}>
                                <option value="contacts">Contacts</option>
                                <option value="companies">Companies</option>
                                <option value="deals">Deals</option>
                                <option value="tickets">Tickets</option>
                                <option value="products">Products</option>
                                <option value="line_items">Line items</option>
                              </select>
                            </label>
                            <Input placeholder="Properties (comma-separated, optional — default set returned if omitted)" value={source.hs_properties} onChange={(e) => updateSource(index, "hs_properties", e.target.value)} />
                          </div>
                        </div>
                      )}

                      {/* ── Zoho CRM — credentials (new connection only) + module/criteria ── */}
                      {source.connector_type === "zoho" && (
                        <div className="space-y-4">
                          {!connState.useExisting && (
                            <div className="space-y-3">
                              <p className="text-xs text-muted-foreground">
                                Either paste a ready access token, or fill in refresh token + client id/secret to mint a fresh one every run (Zoho tokens expire hourly).
                              </p>
                              <Input placeholder="Access token (optional)" type="password" value={source.zoho_access_token} onChange={(e) => updateSource(index, "zoho_access_token", e.target.value)} />
                              <Input placeholder="Refresh token (optional)" type="password" value={source.zoho_refresh_token} onChange={(e) => updateSource(index, "zoho_refresh_token", e.target.value)} />
                              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                                <Input placeholder="Client ID" value={source.zoho_client_id} onChange={(e) => updateSource(index, "zoho_client_id", e.target.value)} />
                                <Input placeholder="Client secret" type="password" value={source.zoho_client_secret} onChange={(e) => updateSource(index, "zoho_client_secret", e.target.value)} />
                              </div>
                              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                                <Input placeholder="Accounts URL (region, default .com)" value={source.zoho_accounts_url} onChange={(e) => updateSource(index, "zoho_accounts_url", e.target.value)} />
                                <Input placeholder="API domain (region, default .com)" value={source.zoho_api_domain} onChange={(e) => updateSource(index, "zoho_api_domain", e.target.value)} />
                              </div>
                            </div>
                          )}
                          <div className="space-y-2">
                            <Input placeholder="Module, e.g. Leads, Contacts, Deals, Accounts" value={source.zoho_module} onChange={(e) => updateSource(index, "zoho_module", e.target.value)} required={fieldsRequired} />
                            <Input placeholder="Search criteria (optional), e.g. (Email:equals:a@b.com)" value={source.zoho_criteria} onChange={(e) => updateSource(index, "zoho_criteria", e.target.value)} />
                          </div>
                        </div>
                      )}

                      {/* ── Friendly pre-ingest data preview + quality checks —
                           works for every connector, and for both a
                           brand-new and a saved connection, via
                           /preview_source. Runs BEFORE this source's load,
                           same as CreatePipeline.tsx / DirectIngest.tsx. ── */}
                      <DataQualityBuilder
                        connector={source.connector_type as any}
                        params={getPreviewParams(source, connState, existingConnFilePaths[index] ?? "")}
                        auto={["csv", "excel"].includes(source.connector_type)}
                        onChange={(built) => setSourceQualities((current) => ({ ...current, [index]: built }))}
                      />

                      {/* ── Optional user-defined schema for this source —
                           any connector, any source shape. ── */}
                      <SchemaBuilder
                        connector={source.connector_type as any}
                        params={getPreviewParams(source, connState, existingConnFilePaths[index] ?? "")}
                        auto={["csv", "excel"].includes(source.connector_type)}
                        onChange={(built) => setSourceSchemas((current) => ({ ...current, [index]: built }))}
                      />
                    </div>
                  );
                })}
              </div>
            )}

            {/* ══════════════════ STEP 3 — SCHEDULE ══════════════════ */}
            {currentStep === 3 && <SchedulerFields value={schedule} onChange={setSchedule} />}

            {/* ══════════════════ STEP 4 — REVIEW ══════════════════ */}
            {currentStep === 4 && (
              <div className="space-y-4">
                 <div className="rounded-md border border-border bg-muted/50 p-4 text-sm">
                   <h3 className="mb-3 font-semibold text-foreground">Pipeline overview</h3>
                  <dl className="grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2">
                    <div><dt className="text-muted-foreground">Pipeline name</dt><dd className="font-medium">{pipelineName || "—"}</dd></div>
                    <div><dt className="text-muted-foreground">Target table</dt><dd className="font-medium">{tableName || "—"}</dd></div>
                    <div><dt className="text-muted-foreground">Load option</dt><dd className="font-medium">{{ "1": "Append", "2": "Overwrite", "3": "Create new" }[option]}</dd></div>
                    <div><dt className="text-muted-foreground">Schedule</dt><dd className="font-medium">{buildCron(schedule)} ({schedule.timezone})</dd></div>
                  </dl>
                </div>

                 <div className="space-y-2">
                   <h3 className="text-sm font-semibold text-foreground">Sources ({sources.length})</h3>
                   {sources.map((source, index) => {
                     const connState = sourceConnectionStates[index];
                     const dfQuality = sourceQualities[index];
                      const querySummary =
                        source.connector_type === "postgres"
                          ? (source.pg_query_mode === "table" ? buildSelectQuery(source.pg_source_table) : source.pg_query)
                          : source.connector_type === "snowflake"
                          ? (source.sf_query_mode === "table" ? buildSnowflakeSelectQuery(source.sf_source_table) : source.sf_query)
                          : source.connector_type === "mysql"
                          ? source.my_query
                          : source.connector_type === "oracle"
                          ? source.ora_query
                          : source.connector_type === "mongodb"
                          ? `${source.mongo_collection}${source.mongo_query ? ` — ${source.mongo_query}` : ""}`
                          : source.connector_type === "salesforce"
                          ? (source.sf_crm_soql_query || source.sf_crm_object_name)
                          : source.connector_type === "hubspot"
                          ? source.hs_object_type
                          : source.connector_type === "zoho"
                          ? `${source.zoho_module}${source.zoho_criteria ? ` — ${source.zoho_criteria}` : ""}`
                          : null;
                     return (
                       <div key={index} className="rounded-md border border-border bg-card p-3 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">Source {index + 1}: {CONNECTOR_LABELS[source.connector_type]}</span>
                          {index === 0 && <span className="text-xs text-muted-foreground">uses pipeline load option</span>}
                        </div>
                        <p className="mt-1 text-muted-foreground">
                          {connState?.useExisting
                            ? `Saved connection: ${getFilteredConnections(source.connector_type).find((c: any) => String(c.id) === connState.selectedConnectionId)?.name || connState.selectedConnectionId}`
                            : source.file_path || source.folder_path || source.sheet_url || source.api_url
                              || source.src_pg_host || source.src_my_host || source.src_ora_host
                              || source.src_mongo_host || source.src_mongo_connection_string
                              || source.s3_bucket || source.sf_account
                              || source.sf_crm_instance_url || source.zoho_api_domain || "—"}
                        </p>
                        {querySummary && (
                          <p className="mt-1 font-mono text-xs text-muted-foreground break-all">{querySummary || "—"}</p>
                        )}
                        {dfQuality?.hasAnyCheck && (
                          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            <span>
                              Pre-ingest gate: {dfQuality.on_fail === "block" ? "blocks before write" : "warns only"}
                            </span>
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {stepError && <p className="text-sm text-destructive">{stepError}</p>}

            {/* ══════════════════ NAVIGATION ══════════════════ */}
            <div className="flex items-center justify-between border-t border-border pt-4">
              <Button type="button" variant="outline" onClick={goBack} disabled={currentStep === 1}>
                <ChevronLeft className="h-4 w-4" /> Back
              </Button>

              {currentStep < STEPS.length ? (
                <Button type="button" onClick={goNext}>
                  Next <ChevronRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button type="submit" disabled={create.isPending}>
                  {create.isPending ? <Loader2 className="animate-spin" /> : <Network />} Create Multi-Source Pipeline
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {result && (
         <Card className="border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950">
           <CardContent className="flex items-start gap-3 p-4">
             <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
             <div className="space-y-1">
               <p className="font-medium text-emerald-900 dark:text-emerald-100">Pipeline created successfully</p>
               <p className="text-sm text-emerald-800 dark:text-emerald-200">
                 <span className="font-medium">{result.dag_id}</span> is set up and will start running on schedule.
               </p>
               {result.message && <p className="text-xs text-emerald-700 dark:text-emerald-300">{result.message}</p>}
             </div>
           </CardContent>
         </Card>
       )}

{create.error && (
         <Card className="border-rose-200 bg-rose-50 dark:border-rose-900 dark:bg-rose-950">
           <CardContent className="flex items-start gap-3 p-4">
             <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600 dark:text-rose-400" />
             <div className="space-y-1">
               <p className="font-medium text-rose-900 dark:text-rose-100">Couldn't create pipeline</p>
               <p className="text-sm text-rose-800 dark:text-rose-200">
                 {formatApiError(create.error)}
               </p>
             </div>
           </CardContent>
         </Card>
       )}
    </div>
  );
};