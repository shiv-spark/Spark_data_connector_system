import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fdt } from "@/lib/format";

export const AuditLog = () => {
  const logs = useQuery({
    queryKey: ["audit_log"],
    queryFn: async () => (await api.get("/audit_log", { params: { limit: 100 } })).data,
  });

  return (
    <Card>
      <CardHeader><CardTitle>Audit Log</CardTitle></CardHeader>
      <CardContent>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="py-2">Time</th>
              <th>User</th>
              <th>Action</th>
              <th>Resource</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {(logs.data?.logs ?? []).map((log: any) => (
              <tr key={log.id} className="border-b">
                <td className="py-2">{fdt(log.created_at)}</td>
                <td>{log.username}</td>
                <td>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs">{log.action}</span>
                </td>
                <td>{log.resource_type}: {log.resource_id}</td>
                <td className="text-xs text-muted-foreground">
                  {JSON.stringify(log.details)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
};