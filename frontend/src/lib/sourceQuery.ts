// Shared between CreatePipeline and the Pipelines edit form, so "table
// name" mode always builds/reads the exact same query shape in both
// places — one source of truth instead of two copies drifting apart.

// For Postgres — respects exact case as typed (Postgres folds unquoted
// identifiers to lowercase by default, so typing lowercase "orders" and
// quoting it as "orders" matches what Postgres actually stored).
export const buildSelectQuery = (tableRef: string) => {
  const t = tableRef.trim();
  if (!t) return "";
  return /["'.]/.test(t) ? `SELECT * FROM ${t}` : `SELECT * FROM "${t}"`;
};

// For Snowflake — unquoted identifiers default to UPPERCASE storage, so
// auto-uppercase the typed table name unless the user already quoted it
// or used a schema-qualified reference (contains a dot or quote char).
export const buildSnowflakeSelectQuery = (tableRef: string) => {
  const t = tableRef.trim();
  if (!t) return "";
  if (/["'.]/.test(t)) return `SELECT * FROM ${t}`;
  return `SELECT * FROM "${t.toUpperCase()}"`;
};

// For MySQL — identifiers are quoted with backticks, not double quotes,
// and MySQL doesn't fold case the way Postgres/Snowflake do.
export const buildMysqlSelectQuery = (tableRef: string) => {
  const t = tableRef.trim();
  if (!t) return "";
  return /[`'.]/.test(t) ? `SELECT * FROM ${t}` : `SELECT * FROM \`${t}\``;
};

// For Oracle — unquoted identifiers default to UPPERCASE storage, same
// rule as Snowflake.
export const buildOracleSelectQuery = (tableRef: string) => {
  const t = tableRef.trim();
  if (!t) return "";
  if (/["'.]/.test(t)) return `SELECT * FROM ${t}`;
  return `SELECT * FROM "${t.toUpperCase()}"`;
};

// The inverse — if a query is exactly "SELECT * FROM <table>" (optionally
// quoted, optional trailing semicolon), return the bare table name so the
// edit UI can preselect it in a dropdown and show a friendly "reading
// from <table>" label. Anything more complex (joins, WHERE, columns list)
// returns null, meaning "this is a custom query, not a plain table read".
export const parseTableFromSimpleSelect = (query: string | null | undefined): string | null => {
  if (!query) return null;
  const match = query.trim().match(/^SELECT\s+\*\s+FROM\s+"?([A-Za-z0-9_.]+)"?\s*;?\s*$/i);
  return match ? match[1] : null;
};
