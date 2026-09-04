
import { FormEvent, useState, useEffect, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, PlusCircle, Link2, Link2Off, Check, ChevronLeft, ChevronRight, CheckCircle2, XCircle } from "lucide-react";
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
import { buildSelectQuery, buildSnowflakeSelectQuery, buildMysqlSelectQuery, buildOracleSelectQuery } from "@/lib/sourceQuery";
import { LiveTablePicker } from "@/components/LiveTablePicker";

type Connector = "csv" | "excel" | "google_sheets" | "api" | "postgres" | "mysql" | "oracle" | "mongodb" | "s3" | "snowflake" | "salesforce" | "hubspot" | "zoho";

const CONNECTOR_TO_SOURCE_TYPE: Record<Connector, string> = {
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

const CONNECTOR_LABELS: Record<Connector, string> = {
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

const SUPPORTS_CONNECTIONS: Connector[] = ["csv", "excel", "google_sheets", "api", "postgres", "mysql", "oracle", "mongodb", "s3", "snowflake", "salesforce", "hubspot", "zoho"];

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
  s3_bucket: "",
  s3_key: "",
  s3_file_type: "csv",
  s3_access_key: "",
  s3_secret_key: "",
  sf_account: "",
  sf_user: "",
  sf_password: "",
  sf_warehouse: "",
  sf_database: "",
  sf_schema: "PUBLIC",
  sf_role: "",
  sf_query: "",
  // ── Salesforce CRM ──
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
  // ── HubSpot ──
  hs_access_token: "",
  hs_object_type: "contacts",
  hs_properties: "",
  // ── Zoho CRM ──
  zoho_access_token: "",
  zoho_refresh_token: "",
  zoho_client_id: "",
  zoho_client_secret: "",
  zoho_accounts_url: "https://accounts.zoho.com",
  zoho_api_domain: "https://www.zohoapis.com",
  zoho_module: "",
  zoho_criteria: "",
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

  // ── Table-vs-query mode for Postgres / Snowflake / MySQL / Oracle ─────
  const [pgMode, setPgMode] = useState<"table" | "query">("table");
  const [pgTableInput, setPgTableInput] = useState("");
  const [sfMode, setSfMode] = useState<"table" | "query">("table");
  const [sfTableInput, setSfTableInput] = useState("");
  const [myMode, setMyMode] = useState<"table" | "query">("table");
  const [myTableInput, setMyTableInput] = useState("");
  const [oraMode, setOraMode] = useState<"table" | "query">("table");
  const [oraTableInput, setOraTableInput] = useState("");

  // ── Data-quality checks — friendly preview + column checks, for every connector ──
  const [quality, setQuality] = useState<BuiltQuality | null>(null);
  // ── Optional user-defined schema override, same preview data as above ──
  const [customSchema, setCustomSchema] = useState<BuiltSchema | null>(null);
  // Which file the user picked to preview/build checks against, when a
  // saved csv/excel connection resolves to a whole folder (form.folder_path)
  // rather than a single file.
  const [existingConnFilePath, setExistingConnFilePath] = useState<string>("");

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
      } else if (form.connector_type === "mysql") {
        update("src_my_host", cfg.host || "");
        update("src_my_db", cfg.database || "");
        update("src_my_user", cfg.user || "");
        update("src_my_password", cfg.password || "");
        update("src_my_port", cfg.port || "3306");
      } else if (form.connector_type === "oracle") {
        update("src_ora_host", cfg.host || "");
        update("src_ora_db", cfg.database || "");
        update("src_ora_user", cfg.user || "");
        update("src_ora_password", cfg.password || "");
        update("src_ora_port", cfg.port || "1521");
      } else if (form.connector_type === "mongodb") {
        update("src_mongo_host", cfg.host || "");
        update("src_mongo_db", cfg.database || "");
        update("src_mongo_user", cfg.user || "");
        update("src_mongo_password", cfg.password || "");
        update("src_mongo_port", cfg.port || "27017");
        update("src_mongo_connection_string", cfg.connection_string || "");
        update("mongo_collection", cfg.collection || "");
      } else if (form.connector_type === "s3") {
        update("s3_bucket", cfg.bucket || "");
        update("s3_key", cfg.prefix || "");
        update("s3_file_type", cfg.file_type || "csv");
        update("s3_access_key", "");
        update("s3_secret_key", "");
      } else if (form.connector_type === "snowflake") {
        update("sf_account", cfg.account || "");
        update("sf_user", cfg.user || "");
        update("sf_password", cfg.password || "");
        update("sf_warehouse", cfg.warehouse || "");
        update("sf_database", cfg.database || "");
        update("sf_schema", cfg.schema || "PUBLIC");
        update("sf_role", cfg.role || "");
      } else if (form.connector_type === "salesforce") {
        update("sf_crm_login_url", cfg.login_url || "https://login.salesforce.com");
        update("sf_crm_instance_url", cfg.instance_url || "");
      } else if (form.connector_type === "hubspot") {
      } else if (form.connector_type === "zoho") {
        update("zoho_accounts_url", cfg.accounts_url || "https://accounts.zoho.com");
        update("zoho_api_domain", cfg.api_domain || "https://www.zohoapis.com");
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
    setPgMode("table");
    setPgTableInput("");
    setSfMode("table");
    setSfTableInput("");
    setExistingConnFilePath("");
  }, [form.connector_type]);

  // A different saved connection means a different folder — the
  // previously-picked file no longer applies.
  useEffect(() => {
    setExistingConnFilePath("");
  }, [selectedConnectionId]);

  const resolvedPgQuery = pgMode === "table" ? buildSelectQuery(pgTableInput) : form.pg_query;
  const resolvedSfQuery = sfMode === "table" ? buildSnowflakeSelectQuery(sfTableInput) : form.sf_query;
  const resolvedMyQuery = myMode === "table" ? buildMysqlSelectQuery(myTableInput) : form.my_query;
  const resolvedOraQuery = oraMode === "table" ? buildOracleSelectQuery(oraTableInput) : form.ora_query;

  // ── Files inside a saved csv/excel connection's folder — lets the user
  // pick one to preview/build quality checks against, the same way
  // FolderUpload lets them pick one for a brand-new connection. ──────────
  const savedFolderFiles = useQuery({
    queryKey: ["saved-connection-files", form.folder_path],
    enabled: useExistingConnection && ["csv", "excel"].includes(form.connector_type) && !!form.folder_path,
    queryFn: async () => (await api.get("/list_folder_files", {
      params: { folder_path: form.folder_path },
    })).data as { folder_path: string; files: string[] },
  });

  // ── What to preview / build quality checks against, for whichever
  // connector + connection mode is currently selected. `null` means we
  // don't have enough info yet, so DataQualityBuilder renders nothing. ──
  const previewParams = useMemo<Record<string, unknown> | null>(() => {
    const connId = useExistingConnection && selectedConnectionId ? parseInt(selectedConnectionId, 10) : undefined;

    if (["csv", "excel"].includes(form.connector_type)) {
      const path = useExistingConnection ? existingConnFilePath : form.file_path;
      if (path) return { file_path: path };
      // No single file picked yet — if a whole folder is set (either typed
      // directly, or resolved from a saved connection's base_path), fall
      // back to it so the preview/schema builders still render, same as
      // the backend's /preview_source folder fallback expects.
      if (form.folder_path) return { folder_path: form.folder_path };
      return null;
    }

    if (form.connector_type === "postgres") {
      if (!resolvedPgQuery.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, pg_query: resolvedPgQuery } : null;
      if (!form.src_pg_host || !form.src_pg_db || !form.src_pg_user) return null;
      return {
        src_pg_host: form.src_pg_host, src_pg_db: form.src_pg_db, src_pg_user: form.src_pg_user,
        src_pg_password: form.src_pg_password, src_pg_port: form.src_pg_port, pg_query: resolvedPgQuery,
      };
    }

    if (form.connector_type === "mysql") {
      if (!resolvedMyQuery.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, my_query: resolvedMyQuery } : null;
      if (!form.src_my_host || !form.src_my_db || !form.src_my_user) return null;
      return {
        src_my_host: form.src_my_host, src_my_db: form.src_my_db, src_my_user: form.src_my_user,
        src_my_password: form.src_my_password, src_my_port: form.src_my_port, my_query: resolvedMyQuery,
      };
    }

    if (form.connector_type === "oracle") {
      if (!resolvedOraQuery.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, ora_query: resolvedOraQuery } : null;
      if (!form.src_ora_host || !form.src_ora_db || !form.src_ora_user) return null;
      return {
        src_ora_host: form.src_ora_host, src_ora_db: form.src_ora_db, src_ora_user: form.src_ora_user,
        src_ora_password: form.src_ora_password, src_ora_port: form.src_ora_port, ora_query: resolvedOraQuery,
      };
    }

    if (form.connector_type === "mongodb") {
      if (!form.mongo_collection.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, mongo_collection: form.mongo_collection, mongo_query: form.mongo_query } : null;
      if (!form.src_mongo_connection_string && (!form.src_mongo_host || !form.src_mongo_db)) return null;
      if (form.src_mongo_connection_string && !form.src_mongo_db) return null;
      return {
        src_mongo_host: form.src_mongo_host, src_mongo_db: form.src_mongo_db,
        src_mongo_user: form.src_mongo_user, src_mongo_password: form.src_mongo_password,
        src_mongo_port: form.src_mongo_port, src_mongo_connection_string: form.src_mongo_connection_string,
        mongo_collection: form.mongo_collection, mongo_query: form.mongo_query,
      };
    }

    if (form.connector_type === "snowflake") {
      if (!resolvedSfQuery.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, sf_query: resolvedSfQuery } : null;
      if (!form.sf_account || !form.sf_user || !form.sf_warehouse || !form.sf_database) return null;
      return {
        sf_account: form.sf_account, sf_user: form.sf_user, sf_password: form.sf_password,
        sf_warehouse: form.sf_warehouse, sf_database: form.sf_database, sf_schema: form.sf_schema,
        sf_role: form.sf_role, sf_query: resolvedSfQuery,
      };
    }

    if (form.connector_type === "s3") {
      if (useExistingConnection) return connId ? { connection_id: connId } : null;
      if (!form.s3_bucket || !form.s3_key) return null;
      return {
        s3_bucket: form.s3_bucket, s3_key: form.s3_key, s3_file_type: form.s3_file_type,
        s3_access_key: form.s3_access_key, s3_secret_key: form.s3_secret_key,
      };
    }

    if (form.connector_type === "salesforce") {
      if (!form.sf_crm_object_name.trim() && !form.sf_crm_soql_query.trim()) return null;
      if (useExistingConnection) {
        return connId ? { connection_id: connId, sf_crm_object_name: form.sf_crm_object_name, sf_crm_soql_query: form.sf_crm_soql_query } : null;
      }
      const hasAuth = (form.sf_crm_access_token && form.sf_crm_instance_url) ||
        (form.sf_crm_client_id && form.sf_crm_client_secret && form.sf_crm_username && form.sf_crm_password);
      if (!hasAuth) return null;
      return {
        sf_crm_access_token: form.sf_crm_access_token, sf_crm_instance_url: form.sf_crm_instance_url,
        sf_crm_login_url: form.sf_crm_login_url, sf_crm_client_id: form.sf_crm_client_id,
        sf_crm_client_secret: form.sf_crm_client_secret, sf_crm_username: form.sf_crm_username,
        sf_crm_password: form.sf_crm_password, sf_crm_security_token: form.sf_crm_security_token,
        sf_crm_object_name: form.sf_crm_object_name, sf_crm_soql_query: form.sf_crm_soql_query,
      };
    }

    if (form.connector_type === "hubspot") {
      if (useExistingConnection) return connId ? { connection_id: connId, hs_object_type: form.hs_object_type } : null;
      if (!form.hs_access_token.trim()) return null;
      return { hs_access_token: form.hs_access_token, hs_object_type: form.hs_object_type };
    }

    if (form.connector_type === "zoho") {
      if (!form.zoho_module.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, zoho_module: form.zoho_module, zoho_criteria: form.zoho_criteria } : null;
      const hasAuth = form.zoho_access_token || (form.zoho_refresh_token && form.zoho_client_id && form.zoho_client_secret);
      if (!hasAuth) return null;
      return {
        zoho_access_token: form.zoho_access_token, zoho_refresh_token: form.zoho_refresh_token,
        zoho_client_id: form.zoho_client_id, zoho_client_secret: form.zoho_client_secret,
        zoho_accounts_url: form.zoho_accounts_url, zoho_api_domain: form.zoho_api_domain,
        zoho_module: form.zoho_module, zoho_criteria: form.zoho_criteria,
      };
    }

    if (form.connector_type === "google_sheets") {
      if (useExistingConnection) return connId ? { connection_id: connId } : null;
      return form.sheet_url.trim() ? { sheet_url: form.sheet_url } : null;
    }

    if (form.connector_type === "api") {
      if (useExistingConnection) return connId ? { connection_id: connId } : null;
      if (!form.api_url.trim()) return null;
      if (!form.api_config.trim()) return { api_url: form.api_url };
      try {
        return { api_url: form.api_url, api_config: JSON.parse(form.api_config) };
      } catch {
        return null;
      }
    }

    return null;
  }, [
    form.connector_type, form.file_path, existingConnFilePath,
    useExistingConnection, selectedConnectionId,
    resolvedPgQuery, form.src_pg_host, form.src_pg_db, form.src_pg_user, form.src_pg_password, form.src_pg_port,
    resolvedMyQuery, form.src_my_host, form.src_my_db, form.src_my_user, form.src_my_password, form.src_my_port,
    resolvedOraQuery, form.src_ora_host, form.src_ora_db, form.src_ora_user, form.src_ora_password, form.src_ora_port,
    form.mongo_collection, form.mongo_query, form.src_mongo_host, form.src_mongo_db, form.src_mongo_user,
    form.src_mongo_password, form.src_mongo_port, form.src_mongo_connection_string,
    resolvedSfQuery, form.sf_account, form.sf_user, form.sf_password, form.sf_warehouse, form.sf_database, form.sf_schema, form.sf_role,
    form.s3_bucket, form.s3_key, form.s3_file_type, form.s3_access_key, form.s3_secret_key,
    form.sheet_url, form.api_url, form.api_config,
    form.sf_crm_access_token, form.sf_crm_instance_url, form.sf_crm_login_url, form.sf_crm_client_id,
    form.sf_crm_client_secret, form.sf_crm_username, form.sf_crm_password, form.sf_crm_security_token,
    form.sf_crm_object_name, form.sf_crm_soql_query,
    form.hs_access_token, form.hs_object_type,
    form.zoho_access_token, form.zoho_refresh_token, form.zoho_client_id, form.zoho_client_secret,
    form.zoho_accounts_url, form.zoho_api_domain, form.zoho_module, form.zoho_criteria,
  ]);

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

      // ── Force-resolve the final query at submit time — never rely on
      // onChange having fired correctly, this guarantees correctness even
      // if a stale value from a previous session survived in `form`. ──
      const finalPgQuery =
        form.connector_type === "postgres"
          ? (pgMode === "table" ? buildSelectQuery(pgTableInput) : form.pg_query)
          : form.pg_query;

      const finalSfQuery =
        form.connector_type === "snowflake"
          ? (sfMode === "table" ? buildSnowflakeSelectQuery(sfTableInput) : form.sf_query)
          : form.sf_query;

      const finalMyQuery =
        form.connector_type === "mysql"
          ? (myMode === "table" ? buildMysqlSelectQuery(myTableInput) : form.my_query)
          : form.my_query;

      const finalOraQuery =
        form.connector_type === "oracle"
          ? (oraMode === "table" ? buildOracleSelectQuery(oraTableInput) : form.ora_query)
          : form.ora_query;

      // Quality checks now work for every connector, not just csv/excel —
      // the friendly builder just needs a preview of the data first,
      // which /preview_source now provides for any source type.
      const dfQualityFields = quality?.hasAnyCheck
        ? { df_quality_config: quality.config, df_quality_on_fail: quality.on_fail }
        : {};

      // Optional user-defined schema — {"column": "integer"|"float"|"boolean"|"date"|"timestamp"|"text"|"json"}.
      const customSchemaFields = customSchema?.hasAnyCustomType
        ? { custom_schema: customSchema.schema }
        : {};

      const payload = {
        ...form,
        pg_query: finalPgQuery,
        sf_query: finalSfQuery,
        my_query: finalMyQuery,
        ora_query: finalOraQuery,
        api_config: parsedApiConfig,
        hs_properties: form.hs_properties.trim()
          ? form.hs_properties.split(",").map((p) => p.trim()).filter(Boolean)
          : null,
        schedule: buildCron(schedule),
        timezone: schedule.timezone,
        incremental_column: form.sync_mode === "incremental" ? form.incremental_column : null,
        after_first_run: form.option === "3" ? form.after_first_run || null : null,
        connection_id: useExistingConnection ? parseInt(selectedConnectionId) : null,
        ...dfQualityFields,
        ...customSchemaFields,
      };
      const response = await api.post("/create_pipeline", payload);
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
      setForm(base);
      setSchedule(defaultSchedule);
      setUseExistingConnection(false);
      setSelectedConnectionId("");
      setConnectionError("");
      setApiConfigError("");
      setStepError("");
      setCurrentStep(1);
      setPgMode("table");
      setPgTableInput("");
      setSfMode("table");
      setSfTableInput("");
      setQuality(null);
      setCustomSchema(null);
      setExistingConnFilePath("");
    },
  });

  // ── Step validation — checked before allowing "Next" ─────────────────
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
        if (form.connector_type === "postgres" && (!form.src_pg_host || !form.src_pg_db || !form.src_pg_user)) {
          return "Host, database, and user are required for Postgres.";
        }
        if (form.connector_type === "mysql" && (!form.src_my_host || !form.src_my_db || !form.src_my_user)) {
          return "Host, database, and user are required for MySQL.";
        }
        if (form.connector_type === "oracle" && (!form.src_ora_host || !form.src_ora_db || !form.src_ora_user)) {
          return "Host, service name, and user are required for Oracle.";
        }
        if (form.connector_type === "mongodb") {
          if (!form.src_mongo_connection_string && (!form.src_mongo_host || !form.src_mongo_db)) {
            return "Host and database (or a connection string) are required for MongoDB.";
          }
          if (form.src_mongo_connection_string && !form.src_mongo_db) {
            return "Database is required for MongoDB.";
          }
        }
        if (form.connector_type === "s3" && (!form.s3_bucket || !form.s3_key)) return "Bucket and key are required for S3.";
        if (form.connector_type === "s3" && (!form.s3_access_key || !form.s3_secret_key)) return "Access key and secret key are required for a new S3 connection.";
        if (form.connector_type === "snowflake" && (!form.sf_account || !form.sf_user || !form.sf_warehouse || !form.sf_database)) {
          return "Account, user, warehouse, and database are required for Snowflake.";
        }
        if (form.connector_type === "salesforce") {
          const hasAuth = (form.sf_crm_access_token && form.sf_crm_instance_url) ||
            (form.sf_crm_client_id && form.sf_crm_client_secret && form.sf_crm_username && form.sf_crm_password);
          if (!hasAuth) return "Salesforce needs an access token + instance URL, or client id/secret + username/password.";
        }
        if (form.connector_type === "hubspot" && !form.hs_access_token.trim()) return "HubSpot access token is required.";
        if (form.connector_type === "zoho") {
          const hasAuth = form.zoho_access_token.trim() ||
            (form.zoho_refresh_token.trim() && form.zoho_client_id.trim() && form.zoho_client_secret.trim());
          if (!hasAuth) return "Zoho needs an access token, or refresh token + client id/secret.";
        }
      }
      // Table/query validation applies regardless of new vs. saved connection.
      if (form.connector_type === "postgres") {
        if (pgMode === "table" && !pgTableInput.trim()) return "Table name is required for Postgres.";
        if (pgMode === "query" && !form.pg_query.trim()) return "SQL query is required for Postgres.";
      }
      if (form.connector_type === "mysql") {
        if (myMode === "table" && !myTableInput.trim()) return "Table name is required for MySQL.";
        if (myMode === "query" && !form.my_query.trim()) return "SQL query is required for MySQL.";
      }
      if (form.connector_type === "oracle") {
        if (oraMode === "table" && !oraTableInput.trim()) return "Table name is required for Oracle.";
        if (oraMode === "query" && !form.ora_query.trim()) return "SQL query is required for Oracle.";
      }
      if (form.connector_type === "mongodb" && !form.mongo_collection.trim()) return "Collection is required for MongoDB.";
      if (form.connector_type === "snowflake") {
        if (sfMode === "table" && !sfTableInput.trim()) return "Table name is required for Snowflake.";
        if (sfMode === "query" && !form.sf_query.trim()) return "SQL query is required for Snowflake.";
      }
      if (form.connector_type === "api" && form.api_config.trim()) {
        try {
          JSON.parse(form.api_config);
        } catch {
          return "Advanced Config has invalid JSON.";
        }
      }
      if (form.connector_type === "salesforce" && !form.sf_crm_object_name.trim() && !form.sf_crm_soql_query.trim()) {
        return "Object name or SOQL query is required for Salesforce.";
      }
      if (form.connector_type === "zoho" && !form.zoho_module.trim()) return "Module is required for Zoho.";
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
    // Only allow jumping backward, or forward if all steps in between are valid
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
      <PageHeader
        icon={PlusCircle}
        eyebrow="Build"
        title="Create Pipeline"
        description="Pick a source, shape the data, and set when it runs."
      />

      {/* ── Stepper ─────────────────────────────────────────────────── */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center">
            {STEPS.map((step, idx) => (
              <div key={step.id} className="flex flex-1 items-center last:flex-none">
                <button
                  type="button"
                  onClick={() => goToStep(step.id)}
                  className="flex items-center gap-2 group"
                >
                  <span
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-medium transition-colors ${
                      step.id === currentStep
                        ? "border-emerald-600 bg-emerald-600 text-white dark:border-emerald-500 dark:bg-emerald-500"
                        : step.id < currentStep
                        ? "border-emerald-600 bg-emerald-50 text-emerald-600 dark:border-emerald-500 dark:bg-emerald-950 dark:text-emerald-400"
                        : "border-border bg-card text-muted-foreground group-hover:border-muted-foreground dark:border-border dark:bg-card dark:text-muted-foreground"
                    }`}
                  >
                    {step.id < currentStep ? <Check className="h-4 w-4" /> : step.id}
                  </span>
                  <span
                    className={`hidden text-sm font-medium sm:block ${
                      step.id === currentStep
                        ? "text-foreground"
                        : step.id < currentStep
                        ? "text-emerald-700 dark:text-emerald-400"
                        : "text-muted-foreground"
                    }`}
                  >
                    {step.label}
                  </span>
                </button>
                {idx < STEPS.length - 1 && (
                  <div className={`mx-3 h-0.5 flex-1 ${step.id < currentStep ? "bg-emerald-600 dark:bg-emerald-500" : "bg-border"}`} />
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-foreground">
            Step {currentStep} of {STEPS.length}: {STEPS[currentStep - 1].label}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">

            {/* ══════════════════ STEP 1 — BASIC INFO ══════════════════ */}
            {currentStep === 1 && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <label className="space-y-1 text-sm font-medium text-foreground">
                    Pipeline name
                    <Input value={form.pipeline_name} onChange={(e) => update("pipeline_name", e.target.value)} placeholder="e.g. daily_sales_sync" required />
                  </label>
                  <label className="space-y-1 text-sm font-medium text-foreground">
                    Connector
                    <select className="select-control" value={form.connector_type} onChange={(e) => update("connector_type", e.target.value as Connector)}>
                      {(Object.keys(CONNECTOR_LABELS) as Connector[]).map((c) => (
                        <option key={c} value={c}>{CONNECTOR_LABELS[c]}</option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-sm font-medium text-foreground">
                    Target table
                    <Input value={form.table_name} onChange={(e) => update("table_name", e.target.value)} placeholder="e.g. sales_data" required />
                  </label>
                  <label className="space-y-1 text-sm font-medium text-foreground">
                    Load option
                    <select className="select-control" value={form.option} onChange={(e) => update("option", e.target.value)}>
                      <option value="1">Append</option>
                      <option value="2">Overwrite</option>
                      <option value="3">Create new</option>
                    </select>
                  </label>
                  <label className="space-y-1 text-sm font-medium text-foreground">
                    Sync mode
                    <select className="select-control" value={form.sync_mode} onChange={(e) => update("sync_mode", e.target.value)}>
                      <option value="full">Full</option>
                      <option value="incremental">Incremental</option>
                    </select>
                  </label>
                </div>

                {form.option === "3" && (
                  <label className="block max-w-md space-y-1 text-sm font-medium text-foreground">
                    After first run
                    <select className="select-control" value={form.after_first_run} onChange={(e) => update("after_first_run", e.target.value)}>
                      <option value="">Select...</option>
                      <option value="1">Then append</option>
                      <option value="2">Then overwrite</option>
                    </select>
                  </label>
                )}
                {form.sync_mode === "incremental" && (
                  <label className="block max-w-md space-y-1 text-sm font-medium text-foreground">
                    Incremental column
                    <Input value={form.incremental_column} onChange={(e) => update("incremental_column", e.target.value)} placeholder="e.g. updated_at" />
                  </label>
                )}
              </div>
            )}

            {/* ══════════════════ STEP 2 — SOURCE CONFIG ══════════════════ */}
            {currentStep === 2 && (
              <div className="space-y-4">
                {SUPPORTS_CONNECTIONS.includes(form.connector_type) && (
                  <div className="rounded-md border border-border bg-card p-4 dark:border-border dark:bg-card">
                    <div className="flex items-center gap-4">
                      <label className="flex items-center gap-2 text-sm font-medium text-foreground">
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
                      <label className="flex items-center gap-2 text-sm font-medium text-foreground">
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
                          <p className="text-sm text-red-500 dark:text-red-400">No saved connections for this connector type. Please create a new connection.</p>
                        ) : (
                          <select
                            className="select-control"
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
                        {connectionError && <p className="mt-2 text-sm text-red-500 dark:text-red-400">{connectionError}</p>}

                        {/* ── Saved csv/excel connection → pick a file from its
                             folder to preview & build quality checks against,
                             the same way FolderUpload does for a brand-new
                             connection below. ── */}
                        {["csv", "excel"].includes(form.connector_type) && selectedConnectionId && form.folder_path && (
                          <div className="mt-3 rounded-md border border-border bg-muted/50 p-3">
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
                                value={existingConnFilePath}
                                onChange={(e) => setExistingConnFilePath(e.target.value)}
                              >
                                <option value="">Select a file to preview</option>
                                {savedFolderFiles.data!.files.map((fname) => (
                                  <option key={fname} value={`${form.folder_path}/${fname}`}>{fname}</option>
                                ))}
                              </select>
                            )}
                          </div>
                        )}
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
                        <label className="space-y-1 text-sm font-medium block text-foreground">
                          Advanced Config (optional JSON — method, auth_type, body, pagination, etc.)
                          <textarea
                            className="min-h-40 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs text-foreground"
                            placeholder={`{\n  "method": "GET",\n  "records_path": "products"\n}`}
                            value={form.api_config}
                            onChange={(e) => {
                              update("api_config", e.target.value);
                              setApiConfigError("");
                            }}
                          />
                        </label>
                        {apiConfigError && <p className="text-sm text-red-500 dark:text-red-400">{apiConfigError}</p>}
                      </div>
                    )}

                    {/* ── Postgres credentials — shown only for a brand-new connection.
                         For a saved connection, host/user/password already live on the
                         saved_connections row and are resolved server-side. ── */}
                    {form.connector_type === "postgres" && (
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <Input placeholder="Host" value={form.src_pg_host} onChange={(e) => update("src_pg_host", e.target.value)} />
                        <Input placeholder="Database" value={form.src_pg_db} onChange={(e) => update("src_pg_db", e.target.value)} />
                        <Input placeholder="User" value={form.src_pg_user} onChange={(e) => update("src_pg_user", e.target.value)} />
                        <Input placeholder="Password" type="password" value={form.src_pg_password} onChange={(e) => update("src_pg_password", e.target.value)} />
                        <Input placeholder="Port" value={form.src_pg_port} onChange={(e) => update("src_pg_port", e.target.value)} />
                      </div>
                    )}

                    {form.connector_type === "mysql" && (
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <Input placeholder="Host" value={form.src_my_host} onChange={(e) => update("src_my_host", e.target.value)} />
                        <Input placeholder="Database" value={form.src_my_db} onChange={(e) => update("src_my_db", e.target.value)} />
                        <Input placeholder="User" value={form.src_my_user} onChange={(e) => update("src_my_user", e.target.value)} />
                        <Input placeholder="Password" type="password" value={form.src_my_password} onChange={(e) => update("src_my_password", e.target.value)} />
                        <Input placeholder="Port" value={form.src_my_port} onChange={(e) => update("src_my_port", e.target.value)} />
                      </div>
                    )}

                    {form.connector_type === "oracle" && (
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <Input placeholder="Host" value={form.src_ora_host} onChange={(e) => update("src_ora_host", e.target.value)} />
                        <Input placeholder="Service name" value={form.src_ora_db} onChange={(e) => update("src_ora_db", e.target.value)} />
                        <Input placeholder="User" value={form.src_ora_user} onChange={(e) => update("src_ora_user", e.target.value)} />
                        <Input placeholder="Password" type="password" value={form.src_ora_password} onChange={(e) => update("src_ora_password", e.target.value)} />
                        <Input placeholder="Port" value={form.src_ora_port} onChange={(e) => update("src_ora_port", e.target.value)} />
                      </div>
                    )}

                    {form.connector_type === "mongodb" && (
                      <div className="space-y-3">
                        <Input
                          placeholder="Connection string (mongodb:// or mongodb+srv://) — optional"
                          value={form.src_mongo_connection_string}
                          onChange={(e) => update("src_mongo_connection_string", e.target.value)}
                        />
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                          <Input placeholder="Host" value={form.src_mongo_host} onChange={(e) => update("src_mongo_host", e.target.value)} disabled={!!form.src_mongo_connection_string} />
                          <Input placeholder="Database" value={form.src_mongo_db} onChange={(e) => update("src_mongo_db", e.target.value)} />
                          <Input placeholder="User (optional)" value={form.src_mongo_user} onChange={(e) => update("src_mongo_user", e.target.value)} disabled={!!form.src_mongo_connection_string} />
                          <Input placeholder="Password (optional)" type="password" value={form.src_mongo_password} onChange={(e) => update("src_mongo_password", e.target.value)} disabled={!!form.src_mongo_connection_string} />
                          <Input placeholder="Port" value={form.src_mongo_port} onChange={(e) => update("src_mongo_port", e.target.value)} disabled={!!form.src_mongo_connection_string} />
                        </div>
                      </div>
                    )}

                    {form.connector_type === "s3" && (
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                        <Input placeholder="Bucket" value={form.s3_bucket} onChange={(e) => update("s3_bucket", e.target.value)} />
                        <Input placeholder="Key" value={form.s3_key} onChange={(e) => update("s3_key", e.target.value)} />
                        <Input placeholder="File type" value={form.s3_file_type} onChange={(e) => update("s3_file_type", e.target.value)} />
                        <Input placeholder="Access key ID" value={form.s3_access_key} onChange={(e) => update("s3_access_key", e.target.value)} />
                        <Input placeholder="Secret access key" type="password" value={form.s3_secret_key} onChange={(e) => update("s3_secret_key", e.target.value)} />
                      </div>
                    )}

                    {/* ── Snowflake credentials — same rule as Postgres above ── */}
                    {form.connector_type === "snowflake" && (
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <Input placeholder="Account (e.g. XROJPNQ-RO43084)" value={form.sf_account} onChange={(e) => update("sf_account", e.target.value)} />
                        <Input placeholder="User" value={form.sf_user} onChange={(e) => update("sf_user", e.target.value)} />
                        <Input placeholder="Password" type="password" value={form.sf_password} onChange={(e) => update("sf_password", e.target.value)} />
                        <Input placeholder="Warehouse" value={form.sf_warehouse} onChange={(e) => update("sf_warehouse", e.target.value)} />
                        <Input placeholder="Database" value={form.sf_database} onChange={(e) => update("sf_database", e.target.value)} />
                        <Input placeholder="Schema (default PUBLIC)" value={form.sf_schema} onChange={(e) => update("sf_schema", e.target.value)} />
                        <Input placeholder="Role (optional)" value={form.sf_role} onChange={(e) => update("sf_role", e.target.value)} />
                      </div>
                    )}

                    {/* ── Salesforce CRM credentials — same rule as Postgres above ── */}
                    {form.connector_type === "salesforce" && (
                      <div className="space-y-3">
                        <p className="text-xs text-muted-foreground">
                          Either paste a ready access token + instance URL, or fill in client id/secret + username/password to log in fresh on every run.
                        </p>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                          <Input placeholder="Access token (optional)" type="password" value={form.sf_crm_access_token} onChange={(e) => update("sf_crm_access_token", e.target.value)} />
                          <Input placeholder="Instance URL (optional)" value={form.sf_crm_instance_url} onChange={(e) => update("sf_crm_instance_url", e.target.value)} />
                        </div>
                        <Input placeholder="Login URL (default https://login.salesforce.com)" value={form.sf_crm_login_url} onChange={(e) => update("sf_crm_login_url", e.target.value)} />
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                          <Input placeholder="Client ID" value={form.sf_crm_client_id} onChange={(e) => update("sf_crm_client_id", e.target.value)} />
                          <Input placeholder="Client secret" type="password" value={form.sf_crm_client_secret} onChange={(e) => update("sf_crm_client_secret", e.target.value)} />
                          <Input placeholder="Username" value={form.sf_crm_username} onChange={(e) => update("sf_crm_username", e.target.value)} />
                          <Input placeholder="Password" type="password" value={form.sf_crm_password} onChange={(e) => update("sf_crm_password", e.target.value)} />
                        </div>
                        <Input placeholder="Security token (optional)" type="password" value={form.sf_crm_security_token} onChange={(e) => update("sf_crm_security_token", e.target.value)} />
                      </div>
                    )}

                    {form.connector_type === "hubspot" && (
                      <div className="space-y-3">
                        <p className="text-xs text-muted-foreground">HubSpot Private App access tokens don't expire, so this is the only credential needed.</p>
                        <Input placeholder="Private App access token" type="password" value={form.hs_access_token} onChange={(e) => update("hs_access_token", e.target.value)} />
                      </div>
                    )}

                    {form.connector_type === "zoho" && (
                      <div className="space-y-3">
                        <p className="text-xs text-muted-foreground">
                          Either paste a ready access token, or fill in refresh token + client id/secret to mint a fresh one every run (Zoho tokens expire hourly).
                        </p>
                        <Input placeholder="Access token (optional)" type="password" value={form.zoho_access_token} onChange={(e) => update("zoho_access_token", e.target.value)} />
                        <Input placeholder="Refresh token (optional)" type="password" value={form.zoho_refresh_token} onChange={(e) => update("zoho_refresh_token", e.target.value)} />
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                          <Input placeholder="Client ID" value={form.zoho_client_id} onChange={(e) => update("zoho_client_id", e.target.value)} />
                          <Input placeholder="Client secret" type="password" value={form.zoho_client_secret} onChange={(e) => update("zoho_client_secret", e.target.value)} />
                        </div>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                          <Input placeholder="Accounts URL (region, default .com)" value={form.zoho_accounts_url} onChange={(e) => update("zoho_accounts_url", e.target.value)} />
                          <Input placeholder="API domain (region, default .com)" value={form.zoho_api_domain} onChange={(e) => update("zoho_api_domain", e.target.value)} />
                        </div>
                      </div>
                    )}
                  </>
                )}

                {/* ── Postgres — Table name / Custom SQL query toggle ──
                     Always shown when connector is Postgres, regardless of
                     whether credentials come from a new or saved connection.
                     "Pick a table" connects live (using whatever's currently
                     in the form, or the saved connection) and lists real
                     table names instead of making someone type one blind. ── */}
                {form.connector_type === "postgres" && (
                  <LiveTablePicker
                    fieldKey="create-postgres"
                    mode={pgMode}
                    onModeChange={setPgMode}
                    tableInput={pgTableInput}
                    onTableInputChange={setPgTableInput}
                    queryValue={form.pg_query}
                    onQueryChange={(v) => update("pg_query", v)}
                    buildQuery={buildSelectQuery}
                    canFetch={
                      useExistingConnection
                        ? !!selectedConnectionId
                        : !!(form.src_pg_host && form.src_pg_db && form.src_pg_user)
                    }
                    buildPayload={() =>
                      useExistingConnection && selectedConnectionId
                        ? { connector_type: "postgres", connection_id: parseInt(selectedConnectionId, 10) }
                        : {
                            connector_type: "postgres",
                            src_pg_host: form.src_pg_host,
                            src_pg_db: form.src_pg_db,
                            src_pg_user: form.src_pg_user,
                            src_pg_password: form.src_pg_password,
                            src_pg_port: form.src_pg_port,
                          }
                    }
                  />
                )}

                {form.connector_type === "mysql" && (
                  <LiveTablePicker
                    fieldKey="create-mysql"
                    mode={myMode}
                    onModeChange={setMyMode}
                    tableInput={myTableInput}
                    onTableInputChange={setMyTableInput}
                    queryValue={form.my_query}
                    onQueryChange={(v) => update("my_query", v)}
                    buildQuery={buildMysqlSelectQuery}
                    canFetch={
                      useExistingConnection
                        ? !!selectedConnectionId
                        : !!(form.src_my_host && form.src_my_db && form.src_my_user)
                    }
                    buildPayload={() =>
                      useExistingConnection && selectedConnectionId
                        ? { connector_type: "mysql", connection_id: parseInt(selectedConnectionId, 10) }
                        : {
                            connector_type: "mysql",
                            src_my_host: form.src_my_host,
                            src_my_db: form.src_my_db,
                            src_my_user: form.src_my_user,
                            src_my_password: form.src_my_password,
                            src_my_port: form.src_my_port,
                          }
                    }
                  />
                )}

                {form.connector_type === "oracle" && (
                  <LiveTablePicker
                    fieldKey="create-oracle"
                    mode={oraMode}
                    onModeChange={setOraMode}
                    tableInput={oraTableInput}
                    onTableInputChange={setOraTableInput}
                    queryValue={form.ora_query}
                    onQueryChange={(v) => update("ora_query", v)}
                    buildQuery={buildOracleSelectQuery}
                    canFetch={
                      useExistingConnection
                        ? !!selectedConnectionId
                        : !!(form.src_ora_host && form.src_ora_user)
                    }
                    buildPayload={() =>
                      useExistingConnection && selectedConnectionId
                        ? { connector_type: "oracle", connection_id: parseInt(selectedConnectionId, 10) }
                        : {
                            connector_type: "oracle",
                            src_ora_host: form.src_ora_host,
                            src_ora_db: form.src_ora_db,
                            src_ora_user: form.src_ora_user,
                            src_ora_password: form.src_ora_password,
                            src_ora_port: form.src_ora_port,
                          }
                    }
                  />
                )}

                {form.connector_type === "mongodb" && (
                  <div className="space-y-2">
                    <Input placeholder="Collection" value={form.mongo_collection} onChange={(e) => update("mongo_collection", e.target.value)} />
                    <textarea
                      className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                      placeholder='Filter (optional JSON), e.g. {"status": "active"} — leave blank to match all documents'
                      value={form.mongo_query}
                      onChange={(e) => update("mongo_query", e.target.value)}
                    />
                  </div>
                )}

                {/* ── Snowflake — Table name / Custom SQL query toggle ──
                     Always shown when connector is Snowflake, regardless of
                     whether credentials come from a new or saved connection. ── */}
                {form.connector_type === "snowflake" && (
                  <LiveTablePicker
                    fieldKey="create-snowflake"
                    mode={sfMode}
                    onModeChange={setSfMode}
                    tableInput={sfTableInput}
                    onTableInputChange={setSfTableInput}
                    queryValue={form.sf_query}
                    onQueryChange={(v) => update("sf_query", v)}
                    buildQuery={buildSnowflakeSelectQuery}
                    canFetch={
                      useExistingConnection
                        ? !!selectedConnectionId
                        : !!(form.sf_account && form.sf_user && form.sf_database)
                    }
                    buildPayload={() =>
                      useExistingConnection && selectedConnectionId
                        ? { connector_type: "snowflake", connection_id: parseInt(selectedConnectionId, 10) }
                        : {
                            connector_type: "snowflake",
                            sf_account: form.sf_account,
                            sf_user: form.sf_user,
                            sf_password: form.sf_password,
                            sf_warehouse: form.sf_warehouse,
                            sf_database: form.sf_database,
                            sf_schema: form.sf_schema,
                            sf_role: form.sf_role,
                          }
                    }
                  />
                )}

                {/* ── Salesforce CRM — object name / SOQL, always shown
                     regardless of new vs saved connection ── */}
                {form.connector_type === "salesforce" && (
                  <div className="space-y-2">
                    <Input placeholder="Object name, e.g. Account, Contact, Lead, Opportunity" value={form.sf_crm_object_name} onChange={(e) => update("sf_crm_object_name", e.target.value)} />
                    <p className="text-xs text-muted-foreground">Or provide an explicit SOQL query below — it overrides the object name entirely.</p>
                    <textarea
                      className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                      placeholder="SOQL query (optional), e.g. SELECT Id, Name FROM Account"
                      value={form.sf_crm_soql_query}
                      onChange={(e) => update("sf_crm_soql_query", e.target.value)}
                    />
                  </div>
                )}

                {form.connector_type === "hubspot" && (
                  <div className="space-y-2">
                    <label className="block max-w-md space-y-1 text-sm font-medium text-foreground">
                      Object type
                      <select className="select-control" value={form.hs_object_type} onChange={(e) => update("hs_object_type", e.target.value)}>
                        <option value="contacts">Contacts</option>
                        <option value="companies">Companies</option>
                        <option value="deals">Deals</option>
                        <option value="tickets">Tickets</option>
                        <option value="products">Products</option>
                        <option value="line_items">Line items</option>
                      </select>
                    </label>
                    <Input placeholder="Properties (comma-separated, optional — default set returned if omitted)" value={form.hs_properties} onChange={(e) => update("hs_properties", e.target.value)} />
                  </div>
                )}

                {form.connector_type === "zoho" && (
                  <div className="space-y-2">
                    <Input placeholder="Module, e.g. Leads, Contacts, Deals, Accounts" value={form.zoho_module} onChange={(e) => update("zoho_module", e.target.value)} />
                    <Input placeholder="Search criteria (optional), e.g. (Email:equals:a@b.com)" value={form.zoho_criteria} onChange={(e) => update("zoho_criteria", e.target.value)} />
                  </div>
                )}

                {/* ── Friendly data preview + quality checks — works for every
                     connector, and for both a brand-new and a saved
                     connection, via /preview_source. ── */}
                <DataQualityBuilder
                  connector={form.connector_type}
                  params={previewParams}
                  auto={["csv", "excel"].includes(form.connector_type)}
                  onChange={setQuality}
                />

                {/* ── Optional user-defined schema — any connector, any source shape. ── */}
                <SchemaBuilder
                  connector={form.connector_type}
                  params={previewParams}
                  auto={["csv", "excel"].includes(form.connector_type)}
                  onChange={setCustomSchema}
                />
              </div>
            )}

            {/* ══════════════════ STEP 3 — SCHEDULE ══════════════════ */}
            {currentStep === 3 && (
              <div className="space-y-4">
                <SchedulerFields value={schedule} onChange={setSchedule} />
              </div>
            )}

            {/* ══════════════════ STEP 4 — REVIEW & CREATE ══════════════════ */}
            {currentStep === 4 && (
              <div className="space-y-4">
                <div className="rounded-md border border-border bg-card p-4 text-sm dark:border-border dark:bg-card">
                  <h3 className="mb-3 font-semibold text-foreground">Review your pipeline</h3>
                  <dl className="grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2">
                    <div><dt className="text-muted-foreground">Pipeline name</dt><dd className="font-medium text-foreground">{form.pipeline_name || "—"}</dd></div>
                    <div><dt className="text-muted-foreground">Connector</dt><dd className="font-medium text-foreground">{CONNECTOR_LABELS[form.connector_type]}</dd></div>
                    <div><dt className="text-muted-foreground">Target table</dt><dd className="font-medium text-foreground">{form.table_name || "—"}</dd></div>
                    <div><dt className="text-muted-foreground">Load option</dt><dd className="font-medium text-foreground">{{ "1": "Append", "2": "Overwrite", "3": "Create new" }[form.option]}</dd></div>
                    <div><dt className="text-muted-foreground">Sync mode</dt><dd className="font-medium text-foreground capitalize">{form.sync_mode}</dd></div>
                    <div><dt className="text-muted-foreground">Schedule</dt><dd className="font-medium text-foreground">{buildCron(schedule)} ({schedule.timezone})</dd></div>
                    <div>
                      <dt className="text-muted-foreground">Data quality checks</dt>
                      <dd className="font-medium text-foreground">
                        {quality?.hasAnyCheck
                          ? `On — ${quality.on_fail === "block" ? "won't save if a check fails" : "warns only, still saves"}`
                          : "Off"}
                      </dd>
                    </div>
                    {form.connector_type === "postgres" && (
                      <div className="md:col-span-2">
                        <dt className="text-muted-foreground">Postgres query</dt>
                        <dd className="font-medium text-foreground font-mono text-xs break-all">
                          {(pgMode === "table" ? buildSelectQuery(pgTableInput) : form.pg_query) || "—"}
                        </dd>
                      </div>
                    )}
                    {form.connector_type === "mysql" && (
                      <div className="md:col-span-2">
                        <dt className="text-muted-foreground">MySQL query</dt>
                        <dd className="font-medium text-foreground font-mono text-xs break-all">
                          {(myMode === "table" ? buildMysqlSelectQuery(myTableInput) : form.my_query) || "—"}
                        </dd>
                      </div>
                    )}
                    {form.connector_type === "oracle" && (
                      <div className="md:col-span-2">
                        <dt className="text-muted-foreground">Oracle query</dt>
                        <dd className="font-medium text-foreground font-mono text-xs break-all">
                          {(oraMode === "table" ? buildOracleSelectQuery(oraTableInput) : form.ora_query) || "—"}
                        </dd>
                      </div>
                    )}
                    {form.connector_type === "mongodb" && (
                      <div className="md:col-span-2">
                        <dt className="text-muted-foreground">MongoDB collection / filter</dt>
                        <dd className="font-medium text-foreground font-mono text-xs break-all">
                          {form.mongo_collection || "—"}{form.mongo_query ? ` — ${form.mongo_query}` : ""}
                        </dd>
                      </div>
                    )}
                    {form.connector_type === "snowflake" && (
                      <div className="md:col-span-2">
                        <dt className="text-muted-foreground">Snowflake query</dt>
                        <dd className="font-medium text-foreground font-mono text-xs break-all">
                          {(sfMode === "table" ? buildSnowflakeSelectQuery(sfTableInput) : form.sf_query) || "—"}
                        </dd>
                      </div>
                    )}
                    {form.connector_type === "salesforce" && (
                      <div className="md:col-span-2">
                        <dt className="text-muted-foreground">Salesforce object / SOQL</dt>
                        <dd className="font-medium text-foreground font-mono text-xs break-all">
                          {form.sf_crm_soql_query || form.sf_crm_object_name || "—"}
                        </dd>
                      </div>
                    )}
                    {form.connector_type === "hubspot" && (
                      <div className="md:col-span-2">
                        <dt className="text-muted-foreground">HubSpot object type</dt>
                        <dd className="font-medium text-foreground">{form.hs_object_type || "—"}</dd>
                      </div>
                    )}
                    {form.connector_type === "zoho" && (
                      <div className="md:col-span-2">
                        <dt className="text-muted-foreground">Zoho module / criteria</dt>
                        <dd className="font-medium text-foreground font-mono text-xs break-all">
                          {form.zoho_module || "—"}{form.zoho_criteria ? ` — ${form.zoho_criteria}` : ""}
                        </dd>
                      </div>
                    )}
                    <div className="md:col-span-2">
                      <dt className="text-muted-foreground">Source</dt>
                      <dd className="font-medium text-foreground">
                        {useExistingConnection
                          ? `Saved connection: ${filteredConnections.find((c: any) => String(c.id) === selectedConnectionId)?.name || selectedConnectionId}`
                          : form.file_path || form.folder_path || form.sheet_url || form.api_url
                            || form.src_pg_host || form.src_my_host || form.src_ora_host
                            || form.src_mongo_host || form.src_mongo_connection_string
                            || form.s3_bucket || form.sf_account
                            || form.sf_crm_instance_url || form.zoho_api_domain || "—"}
                      </dd>
                    </div>
                  </dl>
                </div>

                <p className="text-sm text-muted-foreground">
                  Everything look right? Click <span className="font-medium text-foreground">Create Pipeline</span> below to finish.
                </p>
              </div>
            )}

            {stepError && <p className="text-sm text-red-500 dark:text-red-400">{stepError}</p>}

            {/* ══════════════════ NAVIGATION ══════════════════ */}
            <div className="flex items-center justify-between border-t border-border pt-4 dark:border-border">
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
        <Card className="border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950">
          <CardContent className="flex items-start gap-3 p-4">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <div className="space-y-1">
              <p className="font-medium text-emerald-900 dark:text-emerald-200">Pipeline created successfully</p>
              <p className="text-sm text-emerald-800 dark:text-emerald-300">
                <span className="font-medium">{result.dag_id}</span> is set up and will start running on schedule.
              </p>
              {result.message && <p className="text-xs text-emerald-700 dark:text-emerald-400">{result.message}</p>}
            </div>
          </CardContent>
        </Card>
      )}

      {create.error && (
        <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950">
          <CardContent className="flex items-start gap-3 p-4">
            <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600 dark:text-rose-400" />
            <div className="space-y-1">
              <p className="font-medium text-rose-900 dark:text-rose-200">Couldn't create pipeline</p>
              <p className="text-sm text-rose-800 dark:text-rose-300">
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
