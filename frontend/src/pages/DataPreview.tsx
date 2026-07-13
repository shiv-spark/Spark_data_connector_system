import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Table2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export const DataPreview = () => {
  const [table, setTable] = useState("");
  const [activeTable, setActiveTable] = useState("");
  const [filterCol, setFilterCol] = useState("");
  const [filterVal, setFilterVal] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isFetching, error } = useQuery({
    queryKey: ["table-preview", activeTable, filterCol, filterVal, offset],
    enabled: !!activeTable,
    queryFn: async () => {
      const response = await api.get(`/table/${activeTable}`, {
        params: { limit, offset, filter_col: filterCol || undefined, filter_val: filterVal || undefined },
      });
      return response.data;
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setOffset(0);
    setActiveTable(table.trim());
  };

  const rows = data?.data ?? [];
  const columns: string[] = data?.columns ?? (rows[0] ? Object.keys(rows[0]) : []);

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><Table2 className="h-5 w-5" /> Data Preview</h2>
      <Card>
        <CardHeader><CardTitle className="text-sm">Table Browser</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_220px_220px_auto]">
            <Input placeholder="Table name" value={table} onChange={(e) => setTable(e.target.value)} required />
            <Input placeholder="Filter column" value={filterCol} onChange={(e) => setFilterCol(e.target.value)} />
            <Input placeholder="Filter value" value={filterVal} onChange={(e) => setFilterVal(e.target.value)} />
            <Button type="submit"><Search /> Load</Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950"><CardContent className="p-4 text-sm text-rose-700 dark:text-rose-400">{(error as any)?.response?.data?.detail ?? (error as Error).message}</CardContent></Card>
      )}

      {activeTable && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{activeTable} {data?.pagination ? `(${data.pagination.total} rows)` : ""}</CardTitle>
          </CardHeader>
          <CardContent>
            {isFetching ? <p className="text-sm text-muted-foreground">Loading rows...</p> : rows.length ? (
              <>
                <div className="overflow-auto rounded-md border border-border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted">
                      <tr>{columns.map((column) => <th key={column} className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">{column}</th>)}</tr>
                    </thead>
                    <tbody>
                      {rows.map((row: any, index: number) => (
                        <tr key={index} className="border-t border-border">
                          {columns.map((column) => <td key={column} className="max-w-72 truncate px-3 py-2 text-foreground">{String(row[column] ?? "")}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <Button variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Previous</Button>
                  <span className="text-sm text-muted-foreground">Page {data.pagination.page} of {data.pagination.pages}</span>
                  <Button variant="outline" disabled={!data.pagination.has_more} onClick={() => setOffset(offset + limit)}>Next</Button>
                </div>
              </>
            ) : <p className="text-sm text-muted-foreground">No rows found.</p>}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
