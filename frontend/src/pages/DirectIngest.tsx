import { FormEvent, useState, useEffect, useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { DownloadCloud, Loader2, Link2, Link2Off } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { FolderUpload } from "@/pages/FolderUpload";
import { PageHeader } from "@/components/PageHeader";
import { DataQualityBuilder, BuiltQuality } from "@/components/DataQualityBuilder";
import { SchemaBuilder, BuiltSchema } from "@/components/SchemaBuilder";
import { QualityGateSummary } from "@/components/console/QualityGateSummary";
import { LiveTablePicker } from "@/components/LiveTablePicker";
import { buildSelectQuery } from "@/lib/sourceQuery";

type Connector = "csv" | "excel" | "google_sheets" | "api" | "postgres" | "mysql" | "oracle" | "mongodb" | "s3" | "snowflake" | "salesforce" | "hubspot" | "zoho";

const connectorLabels: Record<Connector, string> = {
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

// ── Destination (where the ingested data gets WRITTEN to) — independent
// of the source `connector` above. Falls back to this list if
// /destinations/types hasn't loaded yet. Labels/fields ideally come from
// the backend (backend/destinations/__init__.py) so adding a 6th engine
// there doesn't require a frontend change too.
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

const DESTINATION_FIELD_DEFAULTS: Record<string, string> = {
  port_postgres: "5432", port_mysql: "3306", port_oracle: "1521", schema: "PUBLIC",
};

// Maps a connector to the `source_type` saved connections are stored under —
// same mapping CreatePipeline uses to filter the "Use Saved Connection" list.
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

const initial = {
  connector: "csv" as Connector,
  table_name: "",
  option: "1",
  sync_mode: "full",
  incremental_column: "",
  file_path: "",
  sheet_url: "",
  url: "",
  api_config: "",
  host: "",
  database: "",
  user: "",
  password: "",
  port: "5432",
  query: "",
  my_host: "",
  my_database: "",
  my_user: "",
  my_password: "",
  my_port: "3306",
  my_query: "",
  ora_host: "",
  ora_database: "",
  ora_user: "",
  ora_password: "",
  ora_port: "1521",
  ora_query: "",
  mongo_host: "",
  mongo_database: "",
  mongo_user: "",
  mongo_password: "",
  mongo_port: "27017",
  mongo_connection_string: "",
  mongo_collection: "",
  mongo_query: "",
  bucket: "",
  key: "",
  file_type: "csv",
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
  // Salesforce CRM
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
  // HubSpot
  hs_access_token: "",
  hs_object_type: "contacts",
  hs_properties: "",
  // Zoho CRM
  zoho_access_token: "",
  zoho_refresh_token: "",
  zoho_client_id: "",
  zoho_client_secret: "",
  zoho_accounts_url: "https://accounts.zoho.com",
  zoho_api_domain: "https://www.zohoapis.com",
  zoho_module: "",
  zoho_criteria: "",
};

export const DirectIngest = () => {
  const [form, setForm] = useState(initial);
  const [quality, setQuality] = useState<BuiltQuality | null>(null);
  const [customSchema, setCustomSchema] = useState<BuiltSchema | null>(null);
  const [result, setResult] = useState<any>(null);
  const [apiConfigError, setApiConfigError] = useState<string>("");

  // ── Saved connection support — same UX as CreatePipeline ──────────────
  const [useExistingConnection, setUseExistingConnection] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");

  // ── Destination (where the data gets WRITTEN to) — separate from the
  // source `connector` above. Same "new vs saved connection" UX. ────────
  const [destinationType, setDestinationType] = useState<string>("postgres");
  const [useSavedDestination, setUseSavedDestination] = useState(false);
  const [selectedDestinationConnectionId, setSelectedDestinationConnectionId] = useState<string>("");
  const [destinationManualConfig, setDestinationManualConfig] = useState<Record<string, string>>({});
  const [destinationError, setDestinationError] = useState<string>("");

  const destinationTypesQuery = useQuery({
    queryKey: ["destination-types"],
    queryFn: async () => (await api.get("/destinations/types")).data.destinations ?? [],
  });
  const destinationTypes = destinationTypesQuery.data?.length ? destinationTypesQuery.data : FALLBACK_DESTINATIONS;
  const activeDestination = destinationTypes.find((d: any) => d.type === destinationType) ?? destinationTypes[0];

  const updateDestinationField = (key: string, value: string) =>
    setDestinationManualConfig((current) => ({ ...current, [key]: value }));

  // Switching engines means the manual fields no longer apply, and any
  // saved-connection pick was for the OLD engine's connections.
  useEffect(() => {
    setDestinationManualConfig({});
    setSelectedDestinationConnectionId("");
    setDestinationError("");
  }, [destinationType]);
  // ── Table-vs-query mode for Postgres — Direct Ingest had no "pick a
  // table" option before; this brings it in line with Create Pipeline. ──
  const [pgMode, setPgMode] = useState<"table" | "query">("table");
  const [pgTableInput, setPgTableInput] = useState("");
  const [connectionError, setConnectionError] = useState<string>("");
  // The folder a saved csv/excel connection resolves to, purely so we can
  // list the files inside it — never submitted to the backend directly.
  const [existingConnFolderPath, setExistingConnFolderPath] = useState<string>("");

  const update = (key: keyof typeof initial, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const connections = useQuery({
    queryKey: ["connections"],
    queryFn: async () => (await api.get("/connections")).data.connections ?? [],
  });

  const filteredConnections = connections.data?.filter(
    (conn: any) => conn.source_type === CONNECTOR_TO_SOURCE_TYPE[form.connector]
  ) ?? [];

  // Same saved_connections list, filtered for the DESTINATION engine
  // instead of the source connector — a saved postgres connection can be
  // reused as either, same as reverse-ETL destinations already do.
  const filteredDestinationConnections = connections.data?.filter(
    (conn: any) => conn.source_type === destinationType
  ) ?? [];

  // Saved-connection dropdown values are display-only (passwords/secrets
  // come back masked as "********") — the real credentials are resolved
  // server-side via connection_id at ingest/preview time. Here we only
  // pull the non-secret bits needed to drive the UI (e.g. which folder to
  // browse for csv/excel).
  const populateFromConnection = (connId: string) => {
    if (!connId) {
      setExistingConnFolderPath("");
      return;
    }
    const conn = filteredConnections.find((c: any) => String(c.id) === connId);
    if (conn?.config && ["csv", "excel"].includes(form.connector)) {
      setExistingConnFolderPath(conn.config.base_path || "");
    } else {
      setExistingConnFolderPath("");
    }
  };

  useEffect(() => {
    setUseExistingConnection(false);
    setSelectedConnectionId("");
    setConnectionError("");
    setExistingConnFolderPath("");
  }, [form.connector]);

  // A different saved connection means a different folder — the
  // previously-picked file no longer applies. Note: this only resets the
  // FILE pick, not the folder itself — populateFromConnection already sets
  // the new folder in the same event. (Bug fixed here: this effect used to
  // also clear the folder, and since it runs right after
  // populateFromConnection's setExistingConnFolderPath in the same render
  // cycle, it was wiping out the folder immediately — so the saved-connection
  // file picker for csv/excel, and therefore its preview, never appeared.)
  useEffect(() => {
    update("file_path", "");
  }, [selectedConnectionId]);

  // ── Files inside a saved csv/excel connection's folder — pick one to
  // ingest and to preview/build quality checks against. ────────────────
  const savedFolderFiles = useQuery({
    queryKey: ["saved-connection-files", existingConnFolderPath],
    enabled: useExistingConnection && ["csv", "excel"].includes(form.connector) && !!existingConnFolderPath,
    queryFn: async () => (await api.get("/list_folder_files", {
      params: { folder_path: existingConnFolderPath },
    })).data as { folder_path: string; files: string[] },
  });

  // ── What to preview / build quality checks against, for whichever
  // connector + connection mode is currently selected. `null` means we
  // don't have enough info yet, so DataQualityBuilder renders nothing. ──
  const previewParams = useMemo<Record<string, unknown> | null>(() => {
    const connId = useExistingConnection && selectedConnectionId ? parseInt(selectedConnectionId, 10) : undefined;

    if (["csv", "excel"].includes(form.connector)) {
      return form.file_path ? { file_path: form.file_path } : null;
    }

    if (form.connector === "postgres") {
      const resolvedQuery = pgMode === "table" ? buildSelectQuery(pgTableInput) : form.query;
      if (!resolvedQuery.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, pg_query: resolvedQuery } : null;
      if (!form.host || !form.database || !form.user) return null;
      return {
        src_pg_host: form.host, src_pg_db: form.database, src_pg_user: form.user,
        src_pg_password: form.password, src_pg_port: form.port, pg_query: resolvedQuery,
      };
    }

    if (form.connector === "mysql") {
      if (!form.my_query.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, my_query: form.my_query } : null;
      if (!form.my_host || !form.my_database || !form.my_user) return null;
      return {
        src_my_host: form.my_host, src_my_db: form.my_database, src_my_user: form.my_user,
        src_my_password: form.my_password, src_my_port: form.my_port, my_query: form.my_query,
      };
    }

    if (form.connector === "oracle") {
      if (!form.ora_query.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, ora_query: form.ora_query } : null;
      if (!form.ora_host || !form.ora_database || !form.ora_user) return null;
      return {
        src_ora_host: form.ora_host, src_ora_db: form.ora_database, src_ora_user: form.ora_user,
        src_ora_password: form.ora_password, src_ora_port: form.ora_port, ora_query: form.ora_query,
      };
    }

    if (form.connector === "mongodb") {
      if (!form.mongo_collection.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, mongo_collection: form.mongo_collection, mongo_query: form.mongo_query } : null;
      if (!form.mongo_connection_string && (!form.mongo_host || !form.mongo_database)) return null;
      if (form.mongo_connection_string && !form.mongo_database) return null;
      return {
        src_mongo_host: form.mongo_host, src_mongo_db: form.mongo_database,
        src_mongo_user: form.mongo_user, src_mongo_password: form.mongo_password,
        src_mongo_port: form.mongo_port, src_mongo_connection_string: form.mongo_connection_string,
        mongo_collection: form.mongo_collection, mongo_query: form.mongo_query,
      };
    }

    if (form.connector === "snowflake") {
      if (!form.sf_query.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, sf_query: form.sf_query } : null;
      if (!form.sf_account || !form.sf_user || !form.sf_warehouse || !form.sf_database) return null;
      return {
        sf_account: form.sf_account, sf_user: form.sf_user, sf_password: form.sf_password,
        sf_warehouse: form.sf_warehouse, sf_database: form.sf_database, sf_schema: form.sf_schema,
        sf_role: form.sf_role, sf_query: form.sf_query,
      };
    }

    if (form.connector === "s3") {
      if (useExistingConnection) return connId ? { connection_id: connId } : null;
      if (!form.bucket || !form.key) return null;
      return {
        s3_bucket: form.bucket, s3_key: form.key, s3_file_type: form.file_type,
        s3_access_key: form.s3_access_key, s3_secret_key: form.s3_secret_key,
      };
    }

    if (form.connector === "salesforce") {
      if (useExistingConnection) {
        if (!connId) return null;
        if (!form.sf_crm_object_name.trim() && !form.sf_crm_soql_query.trim()) return null;
        return { connection_id: connId, sf_crm_object_name: form.sf_crm_object_name, sf_crm_soql_query: form.sf_crm_soql_query };
      }
      const hasAuth = (form.sf_crm_access_token && form.sf_crm_instance_url) ||
        (form.sf_crm_client_id && form.sf_crm_client_secret && form.sf_crm_username && form.sf_crm_password);
      if (!hasAuth) return null;
      if (!form.sf_crm_object_name.trim() && !form.sf_crm_soql_query.trim()) return null;
      return {
        sf_crm_access_token: form.sf_crm_access_token, sf_crm_instance_url: form.sf_crm_instance_url,
        sf_crm_login_url: form.sf_crm_login_url, sf_crm_client_id: form.sf_crm_client_id,
        sf_crm_client_secret: form.sf_crm_client_secret, sf_crm_username: form.sf_crm_username,
        sf_crm_password: form.sf_crm_password, sf_crm_security_token: form.sf_crm_security_token,
        sf_crm_object_name: form.sf_crm_object_name, sf_crm_soql_query: form.sf_crm_soql_query,
      };
    }

    if (form.connector === "hubspot") {
      if (useExistingConnection) return connId ? { connection_id: connId, hs_object_type: form.hs_object_type } : null;
      if (!form.hs_access_token.trim()) return null;
      return { hs_access_token: form.hs_access_token, hs_object_type: form.hs_object_type };
    }

    if (form.connector === "zoho") {
      if (useExistingConnection) return connId && form.zoho_module.trim() ? { connection_id: connId, zoho_module: form.zoho_module, zoho_criteria: form.zoho_criteria } : null;
      const hasAuth = form.zoho_access_token || (form.zoho_refresh_token && form.zoho_client_id && form.zoho_client_secret);
      if (!hasAuth || !form.zoho_module.trim()) return null;
      return {
        zoho_access_token: form.zoho_access_token, zoho_refresh_token: form.zoho_refresh_token,
        zoho_client_id: form.zoho_client_id, zoho_client_secret: form.zoho_client_secret,
        zoho_accounts_url: form.zoho_accounts_url, zoho_api_domain: form.zoho_api_domain,
        zoho_module: form.zoho_module, zoho_criteria: form.zoho_criteria,
      };
    }

    if (form.connector === "google_sheets") {
      if (useExistingConnection) return connId ? { connection_id: connId } : null;
      return form.sheet_url.trim() ? { sheet_url: form.sheet_url } : null;
    }

    if (form.connector === "api") {
      if (useExistingConnection) return connId ? { connection_id: connId } : null;
      if (!form.url.trim()) return null;
      if (!form.api_config.trim()) return { api_url: form.url };
      try {
        return { api_url: form.url, api_config: JSON.parse(form.api_config) };
      } catch {
        return null;
      }
    }

    return null;
  }, [
    form.connector, form.file_path,
    useExistingConnection, selectedConnectionId,
    pgMode, pgTableInput,
    form.query, form.host, form.database, form.user, form.password, form.port,
    form.my_query, form.my_host, form.my_database, form.my_user, form.my_password, form.my_port,
    form.ora_query, form.ora_host, form.ora_database, form.ora_user, form.ora_password, form.ora_port,
    form.mongo_collection, form.mongo_query, form.mongo_host, form.mongo_database, form.mongo_user,
    form.mongo_password, form.mongo_port, form.mongo_connection_string,
    form.sf_query, form.sf_account, form.sf_user, form.sf_password, form.sf_warehouse, form.sf_database, form.sf_schema, form.sf_role,
    form.bucket, form.key, form.file_type, form.s3_access_key, form.s3_secret_key,
    form.sheet_url, form.url, form.api_config,
    form.sf_crm_access_token, form.sf_crm_instance_url, form.sf_crm_login_url, form.sf_crm_client_id,
    form.sf_crm_client_secret, form.sf_crm_username, form.sf_crm_password, form.sf_crm_security_token,
    form.sf_crm_object_name, form.sf_crm_soql_query,
    form.hs_access_token, form.hs_object_type,
    form.zoho_access_token, form.zoho_refresh_token, form.zoho_client_id, form.zoho_client_secret,
    form.zoho_accounts_url, form.zoho_api_domain, form.zoho_module, form.zoho_criteria,
  ]);

  const ingest = useMutation({
    mutationFn: async () => {
      if (useExistingConnection && !selectedConnectionId) {
        setConnectionError("Please select a saved connection");
        throw new Error("No connection selected");
      }
      if (!useExistingConnection && ["csv", "excel"].includes(form.connector) && !form.file_path.trim()) {
        setConnectionError("Please select a file — click it in the list below, or upload one first.");
        throw new Error("No file selected");
      }
      if (useSavedDestination && !selectedDestinationConnectionId) {
        setDestinationError("Please select a saved destination connection");
        throw new Error("No destination connection selected");
      }

      const connectionId = useExistingConnection ? parseInt(selectedConnectionId, 10) : null;

      // ── Destination — where load_to_db() writes to. Either a saved
      // connection id, or an inline manual config — never both at once.
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

      // Quality checks now work for every connector, not just csv/excel —
      // the friendly builder just needs a preview of the data first,
      // which /preview_source provides for any source type.
      const dfQualityFields = quality?.hasAnyCheck
        ? { df_quality_config: quality.config, df_quality_on_fail: quality.on_fail }
        : {};

      // Optional user-defined schema — {"column": "integer"|"float"|"boolean"|"date"|"timestamp"|"text"|"json"}.
      // Enforced (with best-effort casting) instead of the auto-detected types. See utils/schema_applier.py.
      const customSchemaFields = customSchema?.hasAnyCustomType
        ? { custom_schema: customSchema.schema }
        : {};

      const common = {
        option: form.option,
        table_name: form.table_name,
        sync_mode: form.sync_mode,
        incremental_column: form.sync_mode === "incremental" ? form.incremental_column : null,
        connection_id: connectionId,
        ...dfQualityFields,
        ...customSchemaFields,
        ...destinationFields,
      };

      let parsedApiConfig: Record<string, unknown> = {};
      if (form.connector === "api" && !useExistingConnection && form.api_config.trim()) {
        try {
          parsedApiConfig = JSON.parse(form.api_config);
        } catch (e) {
          setApiConfigError("Invalid JSON — please check the syntax.");
          throw new Error("Invalid api_config JSON");
        }
      }

      // ── Force-resolve the final Postgres query at submit time — never
      // rely on onChange having fired correctly. ──
      const finalPgQuery = form.connector === "postgres"
        ? (pgMode === "table" ? buildSelectQuery(pgTableInput) : form.query)
        : form.query;

      const payloads = {
        csv: { ...common, file_path: form.file_path },
        excel: { ...common, file_path: form.file_path },
        google_sheets: { ...common, sheet_url: form.sheet_url },
        api: { ...common, url: form.url, ...parsedApiConfig },
        postgres: { ...common, host: form.host, database: form.database, user: form.user, password: form.password, port: form.port, query: finalPgQuery },
        mysql: { ...common, host: form.my_host, database: form.my_database, user: form.my_user, password: form.my_password, port: form.my_port, query: form.my_query },
        oracle: { ...common, host: form.ora_host, database: form.ora_database, user: form.ora_user, password: form.ora_password, port: form.ora_port, query: form.ora_query },
        mongodb: {
          ...common,
          host: form.mongo_host,
          database: form.mongo_database,
          user: form.mongo_user,
          password: form.mongo_password,
          port: form.mongo_port,
          connection_string: form.mongo_connection_string || null,
          collection: form.mongo_collection,
          query: form.mongo_query || null,
        },
        s3: {
          ...common,
          bucket: form.bucket,
          key: form.key,
          file_type: form.file_type,
          access_key: form.s3_access_key || null,
          secret_key: form.s3_secret_key || null,
        },
        snowflake: {
          ...common,
          account: form.sf_account,
          user: form.sf_user,
          password: form.sf_password,
          warehouse: form.sf_warehouse,
          database: form.sf_database,
          schema: form.sf_schema,
          role: form.sf_role || null,
          query: form.sf_query,
        },
        salesforce: {
          ...common,
          access_token: form.sf_crm_access_token || null,
          instance_url: form.sf_crm_instance_url || null,
          login_url: form.sf_crm_login_url || "https://login.salesforce.com",
          client_id: form.sf_crm_client_id || null,
          client_secret: form.sf_crm_client_secret || null,
          username: form.sf_crm_username || null,
          password: form.sf_crm_password || null,
          security_token: form.sf_crm_security_token || null,
          object_name: form.sf_crm_object_name || null,
          soql_query: form.sf_crm_soql_query || null,
        },
        hubspot: {
          ...common,
          access_token: form.hs_access_token || null,
          object_type: form.hs_object_type || "contacts",
          properties: form.hs_properties.trim()
            ? form.hs_properties.split(",").map((p) => p.trim()).filter(Boolean)
            : null,
        },
        zoho: {
          ...common,
          access_token: form.zoho_access_token || null,
          refresh_token: form.zoho_refresh_token || null,
          client_id: form.zoho_client_id || null,
          client_secret: form.zoho_client_secret || null,
          accounts_url: form.zoho_accounts_url || "https://accounts.zoho.com",
          api_domain: form.zoho_api_domain || "https://www.zohoapis.com",
          module: form.zoho_module || null,
          criteria: form.zoho_criteria || null,
        },
      };
      const endpoints = {
        csv: "/ingest_csv",
        excel: "/ingest_excel",
        google_sheets: "/ingest_google_sheet",
        api: "/ingest_api",
        postgres: "/ingest_postgres",
        mysql: "/ingest_mysql",
        oracle: "/ingest_oracle",
        mongodb: "/ingest_mongodb",
        s3: "/ingest_s3",
        snowflake: "/ingest_snowflake",
        salesforce: "/ingest_salesforce",
        hubspot: "/ingest_hubspot",
        zoho: "/ingest_zoho",
      };
      const response = await api.post(endpoints[form.connector], payloads[form.connector]);
      return response.data;
    },
    onSuccess: setResult,
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setConnectionError("");
    setApiConfigError("");
    setDestinationError("");
    setResult(null);
    ingest.mutate();
  };

  return (
    <div className="space-y-5">
      <PageHeader
        icon={DownloadCloud}
        eyebrow="Data"
        title="Direct Ingest"
        description="Load a file or endpoint straight into a table without building a pipeline."
      />
      <Card className="bg-card border-border">
        <CardHeader><CardTitle className="text-sm text-foreground">Run One-Time Ingestion</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <label className="space-y-1 text-sm font-medium text-foreground">
                Connector
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground dark:bg-background dark:text-foreground" value={form.connector} onChange={(e) => update("connector", e.target.value as Connector)}>
                  {Object.entries(connectorLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium text-foreground">Target table<Input value={form.table_name} onChange={(e) => update("table_name", e.target.value)} required /></label>
              <label className="space-y-1 text-sm font-medium text-foreground">
                Load option
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground dark:bg-background dark:text-foreground" value={form.option} onChange={(e) => update("option", e.target.value)}>
                  <option value="1">Append</option>
                  <option value="2">Overwrite</option>
                  <option value="3">Create new</option>
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium text-foreground">
                Sync mode
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground dark:bg-background dark:text-foreground" value={form.sync_mode} onChange={(e) => update("sync_mode", e.target.value)}>
                  <option value="full">Full</option>
                  <option value="incremental">Incremental</option>
                </select>
              </label>
            </div>

            {form.sync_mode === "incremental" && (
              <label className="block max-w-md space-y-1 text-sm font-medium text-foreground">Incremental column<Input value={form.incremental_column} onChange={(e) => update("incremental_column", e.target.value)} /></label>
            )}

            {/* ── New Connection / Use Saved Connection toggle — same UX as CreatePipeline ── */}
            <div className="rounded-md border border-border bg-card p-4 dark:border-border dark:bg-card">
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <input
                    type="radio"
                    name="directConnectionMode"
                    checked={!useExistingConnection}
                    onChange={() => {
                      setUseExistingConnection(false);
                      setSelectedConnectionId("");
                      setConnectionError("");
                      setExistingConnFolderPath("");
                    }}
                  />
                  <Link2Off className="h-4 w-4" />
                  New Connection
                </label>
                <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <input
                    type="radio"
                    name="directConnectionMode"
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

                  {/* ── Saved csv/excel connection → pick the exact file to ingest ── */}
                  {["csv", "excel"].includes(form.connector) && selectedConnectionId && existingConnFolderPath && (
                    <div className="mt-3 rounded-md border border-border bg-muted/50 p-3">
                      <p className="mb-2 text-xs font-medium text-muted-foreground">
                        Pick a file from this connection's folder to ingest and to preview & build quality checks.
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
                          value={form.file_path}
                          onChange={(e) => update("file_path", e.target.value)}
                        >
                          <option value="">Select a file</option>
                          {savedFolderFiles.data!.files.map((fname) => (
                            <option key={fname} value={`${existingConnFolderPath}/${fname}`}>{fname}</option>
                          ))}
                        </select>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {!useExistingConnection && (
              <>
                {["csv", "excel"].includes(form.connector) && (
                  <div className="space-y-3">
                    <label className="block space-y-1 text-sm font-medium text-foreground">
                      File path
                      <Input value={form.file_path} onChange={(e) => update("file_path", e.target.value)} placeholder="Type a path OR pick a folder below and upload" />
                    </label>
                    <FolderUpload
                      connectorType={form.connector as "csv" | "excel"}
                      onFolderResolved={() => {}}
                      onFileResolved={(filePath) => update("file_path", filePath)}
                    />
                  </div>
                )}
                {form.connector === "google_sheets" && (
                  <label className="block space-y-1 text-sm font-medium text-foreground">Sheet URL<Input value={form.sheet_url} onChange={(e) => update("sheet_url", e.target.value)} required /></label>
                )}
                {form.connector === "api" && (
                  <div className="space-y-2">
                    <label className="block space-y-1 text-sm font-medium text-foreground">API URL<Input value={form.url} onChange={(e) => update("url", e.target.value)} required /></label>
                    <label className="space-y-1 text-sm font-medium block text-foreground">
                      Advanced Config (optional JSON — method, auth_type, body, pagination, etc.)
                      <textarea
                        className="min-h-40 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs text-foreground dark:bg-background dark:text-foreground"
                        placeholder='{"method": "POST", "auth_type": "bearer", "bearer_token": "...", "pagination_type": "page"}'
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
                {form.connector === "postgres" && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <Input placeholder="Host" value={form.host} onChange={(e) => update("host", e.target.value)} required />
                    <Input placeholder="Database" value={form.database} onChange={(e) => update("database", e.target.value)} required />
                    <Input placeholder="User" value={form.user} onChange={(e) => update("user", e.target.value)} required />
                    <Input placeholder="Password" type="password" value={form.password} onChange={(e) => update("password", e.target.value)} required />
                    <Input placeholder="Port" value={form.port} onChange={(e) => update("port", e.target.value)} />
                  </div>
                )}
                {form.connector === "mysql" && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <Input placeholder="Host" value={form.my_host} onChange={(e) => update("my_host", e.target.value)} required />
                    <Input placeholder="Database" value={form.my_database} onChange={(e) => update("my_database", e.target.value)} required />
                    <Input placeholder="User" value={form.my_user} onChange={(e) => update("my_user", e.target.value)} required />
                    <Input placeholder="Password" type="password" value={form.my_password} onChange={(e) => update("my_password", e.target.value)} required />
                    <Input placeholder="Port" value={form.my_port} onChange={(e) => update("my_port", e.target.value)} />
                  </div>
                )}
                {form.connector === "oracle" && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <Input placeholder="Host" value={form.ora_host} onChange={(e) => update("ora_host", e.target.value)} required />
                    <Input placeholder="Service name" value={form.ora_database} onChange={(e) => update("ora_database", e.target.value)} required />
                    <Input placeholder="User" value={form.ora_user} onChange={(e) => update("ora_user", e.target.value)} required />
                    <Input placeholder="Password" type="password" value={form.ora_password} onChange={(e) => update("ora_password", e.target.value)} required />
                    <Input placeholder="Port" value={form.ora_port} onChange={(e) => update("ora_port", e.target.value)} />
                  </div>
                )}
                {form.connector === "mongodb" && (
                  <div className="space-y-3">
                    <Input
                      placeholder="Connection string (mongodb:// or mongodb+srv://) — optional, overrides host/user/password"
                      value={form.mongo_connection_string}
                      onChange={(e) => update("mongo_connection_string", e.target.value)}
                    />
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                      <Input placeholder="Host" value={form.mongo_host} onChange={(e) => update("mongo_host", e.target.value)} disabled={!!form.mongo_connection_string} />
                      <Input placeholder="Database" value={form.mongo_database} onChange={(e) => update("mongo_database", e.target.value)} required />
                      <Input placeholder="User (optional)" value={form.mongo_user} onChange={(e) => update("mongo_user", e.target.value)} disabled={!!form.mongo_connection_string} />
                      <Input placeholder="Password (optional)" type="password" value={form.mongo_password} onChange={(e) => update("mongo_password", e.target.value)} disabled={!!form.mongo_connection_string} />
                      <Input placeholder="Port" value={form.mongo_port} onChange={(e) => update("mongo_port", e.target.value)} disabled={!!form.mongo_connection_string} />
                    </div>
                  </div>
                )}
                {form.connector === "s3" && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <Input placeholder="Bucket" value={form.bucket} onChange={(e) => update("bucket", e.target.value)} required />
                    <Input placeholder="Key" value={form.key} onChange={(e) => update("key", e.target.value)} required />
                    <Input placeholder="File type" value={form.file_type} onChange={(e) => update("file_type", e.target.value)} />
                    <Input placeholder="Access key ID" value={form.s3_access_key} onChange={(e) => update("s3_access_key", e.target.value)} />
                    <Input placeholder="Secret access key" type="password" value={form.s3_secret_key} onChange={(e) => update("s3_secret_key", e.target.value)} />
                  </div>
                )}
                {form.connector === "snowflake" && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <Input placeholder="Account (e.g. XROJPNQ-RO43084)" value={form.sf_account} onChange={(e) => update("sf_account", e.target.value)} required />
                    <Input placeholder="User" value={form.sf_user} onChange={(e) => update("sf_user", e.target.value)} required />
                    <Input placeholder="Password" type="password" value={form.sf_password} onChange={(e) => update("sf_password", e.target.value)} required />
                    <Input placeholder="Warehouse" value={form.sf_warehouse} onChange={(e) => update("sf_warehouse", e.target.value)} required />
                    <Input placeholder="Database" value={form.sf_database} onChange={(e) => update("sf_database", e.target.value)} required />
                    <Input placeholder="Schema (default PUBLIC)" value={form.sf_schema} onChange={(e) => update("sf_schema", e.target.value)} />
                    <Input placeholder="Role (optional)" value={form.sf_role} onChange={(e) => update("sf_role", e.target.value)} />
                  </div>
                )}
                {form.connector === "salesforce" && (
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
                {form.connector === "hubspot" && (
                  <div className="space-y-3">
                    <p className="text-xs text-muted-foreground">HubSpot Private App access tokens don't expire, so this is the only credential needed.</p>
                    <Input placeholder="Private App access token" type="password" value={form.hs_access_token} onChange={(e) => update("hs_access_token", e.target.value)} required />
                  </div>
                )}
                {form.connector === "zoho" && (
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

            {/* ── Query fields — always shown regardless of new vs saved connection,
                 same as CreatePipeline's Postgres/Snowflake table/query toggle area. ── */}
            {form.connector === "postgres" && (
              <LiveTablePicker
                fieldKey="direct-ingest-postgres"
                mode={pgMode}
                onModeChange={setPgMode}
                tableInput={pgTableInput}
                onTableInputChange={setPgTableInput}
                queryValue={form.query}
                onQueryChange={(v) => update("query", v)}
                buildQuery={buildSelectQuery}
                canFetch={
                  useExistingConnection
                    ? !!selectedConnectionId
                    : !!(form.host && form.database && form.user)
                }
                buildPayload={() =>
                  useExistingConnection && selectedConnectionId
                    ? { connector_type: "postgres", connection_id: parseInt(selectedConnectionId, 10) }
                    : {
                        connector_type: "postgres",
                        src_pg_host: form.host,
                        src_pg_db: form.database,
                        src_pg_user: form.user,
                        src_pg_password: form.password,
                        src_pg_port: form.port,
                      }
                }
              />
            )}
            {form.connector === "mysql" && (
              <textarea className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:bg-background dark:text-foreground" placeholder="SQL query" value={form.my_query} onChange={(e) => update("my_query", e.target.value)} required />
            )}
            {form.connector === "oracle" && (
              <textarea className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:bg-background dark:text-foreground" placeholder="SQL query" value={form.ora_query} onChange={(e) => update("ora_query", e.target.value)} required />
            )}
            {form.connector === "mongodb" && (
              <div className="space-y-2">
                <Input placeholder="Collection" value={form.mongo_collection} onChange={(e) => update("mongo_collection", e.target.value)} required />
                <textarea
                  className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:bg-background dark:text-foreground"
                  placeholder='Filter (optional JSON), e.g. {"status": "active"} — leave blank to match all documents'
                  value={form.mongo_query}
                  onChange={(e) => update("mongo_query", e.target.value)}
                />
              </div>
            )}
            {form.connector === "snowflake" && (
              <textarea className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:bg-background dark:text-foreground" placeholder="SQL query" value={form.sf_query} onChange={(e) => update("sf_query", e.target.value)} required />
            )}
            {form.connector === "salesforce" && (
              <div className="space-y-2">
                <Input placeholder="Object name, e.g. Account, Contact, Lead, Opportunity" value={form.sf_crm_object_name} onChange={(e) => update("sf_crm_object_name", e.target.value)} />
                <p className="text-xs text-muted-foreground">Or provide an explicit SOQL query below — it overrides the object name entirely.</p>
                <textarea
                  className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:bg-background dark:text-foreground"
                  placeholder="SOQL query (optional), e.g. SELECT Id, Name FROM Account"
                  value={form.sf_crm_soql_query}
                  onChange={(e) => update("sf_crm_soql_query", e.target.value)}
                />
              </div>
            )}
            {form.connector === "hubspot" && (
              <div className="space-y-2">
                <Input placeholder="Object type (default contacts)" value={form.hs_object_type} onChange={(e) => update("hs_object_type", e.target.value)} />
                <Input placeholder="Properties (comma-separated, optional — default set returned if omitted)" value={form.hs_properties} onChange={(e) => update("hs_properties", e.target.value)} />
              </div>
            )}
            {form.connector === "zoho" && (
              <div className="space-y-2">
                <Input placeholder="Module, e.g. Leads, Contacts, Deals, Accounts" value={form.zoho_module} onChange={(e) => update("zoho_module", e.target.value)} required />
                <Input placeholder="Search criteria (optional), e.g. (Email:equals:a@b.com)" value={form.zoho_criteria} onChange={(e) => update("zoho_criteria", e.target.value)} />
              </div>
            )}

            {/* ── Destination — where the data gets WRITTEN to. Separate
                 from the source `connector` above. Postgres / MySQL /
                 Oracle / MongoDB / Snowflake, either via a saved
                 connection or a manual config, driven by /destinations/types
                 so a new engine added on the backend shows up here too. ── */}
            <div className="rounded-md border border-border bg-card p-4 dark:border-border dark:bg-card space-y-3">
              <div className="text-sm font-medium text-foreground">Destination</div>
              <label className="block max-w-xs space-y-1 text-sm font-medium text-foreground">
                Write to
                <select
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground dark:bg-background dark:text-foreground"
                  value={destinationType}
                  onChange={(e) => setDestinationType(e.target.value)}
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
                    name="destinationMode"
                    checked={!useSavedDestination}
                    onChange={() => { setUseSavedDestination(false); setSelectedDestinationConnectionId(""); setDestinationError(""); }}
                  />
                  <Link2Off className="h-4 w-4" /> New connection
                </label>
                <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <input
                    type="radio"
                    name="destinationMode"
                    checked={useSavedDestination}
                    onChange={() => { setUseSavedDestination(true); setDestinationError(""); }}
                  />
                  <Link2 className="h-4 w-4" /> Use saved connection
                </label>
              </div>

              {useSavedDestination ? (
                <div className="space-y-1">
                  <select
                    className="h-9 w-full max-w-md rounded-md border border-input bg-background px-3 text-sm text-foreground dark:bg-background dark:text-foreground"
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
                      value={destinationManualConfig[field] ?? DESTINATION_FIELD_DEFAULTS[`${field}_${destinationType}`] ?? DESTINATION_FIELD_DEFAULTS[field] ?? ""}
                      onChange={(e) => updateDestinationField(field, e.target.value)}
                      required={field !== "role" && field !== "connection_string"}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* ── Friendly data preview + quality checks — works for every
                 connector, and for both a brand-new and a saved connection,
                 via /preview_source. ── */}
            <DataQualityBuilder
              connector={form.connector}
              params={previewParams}
              auto={["csv", "excel"].includes(form.connector)}
              onChange={setQuality}
            />

            {/* ── Optional user-defined schema — works for every connector,
                 any file/source type, via the same /preview_source data. ── */}
            <SchemaBuilder
              connector={form.connector}
              params={previewParams}
              auto={["csv", "excel"].includes(form.connector)}
              onChange={setCustomSchema}
            />

            <Button type="submit" disabled={ingest.isPending}>
              {ingest.isPending ? <Loader2 className="animate-spin" /> : <DownloadCloud />} Run Ingest
            </Button>
          </form>
        </CardContent>
      </Card>

      {(result || ingest.error) && (
        <Card className={ingest.error ? "border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950" : "border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950"}>
          <CardContent className="p-4 space-y-3">
            {result?.status === "FAILED" && (
              <div className="text-sm font-medium text-rose-700 dark:text-rose-400">
                Ingest failed{result?.error ? `: ${result.error}` : "."}
              </div>
            )}
            <QualityGateSummary
              title="Pre-ingest data quality"
              gate={result?.df_quality}
              connectionId={useExistingConnection && selectedConnectionId ? parseInt(selectedConnectionId, 10) : undefined}
            />
            <QualityGateSummary
              title="Post-load data quality"
              gate={result?.quality}
              connectionId={useExistingConnection && selectedConnectionId ? parseInt(selectedConnectionId, 10) : undefined}
            />
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer select-none">Raw response</summary>
              <pre className="mt-2 max-h-80 overflow-auto text-xs text-foreground">{JSON.stringify(result ?? (ingest.error as any)?.response?.data ?? (ingest.error as Error).message, null, 2)}</pre>
            </details>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
