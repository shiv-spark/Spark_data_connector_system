import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const UserManagement = () => {
  const qc = useQueryClient();
  const users = useQuery({
    queryKey: ["users"],
    queryFn: async () => (await api.get("/auth/users")).data,
  });

  const updateRole = useMutation({
    mutationFn: ({ id, role }: { id: number; role: string }) =>
      api.patch(`/auth/users/${id}/role?role=${role}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const deactivate = useMutation({
    mutationFn: (id: number) => api.patch(`/auth/users/${id}/deactivate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const activate = useMutation({
    mutationFn: (id: number) => api.patch(`/auth/users/${id}/activate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <Card>
      <CardHeader><CardTitle>User Management</CardTitle></CardHeader>
      <CardContent>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left">
              <th>Username</th><th>Email</th><th>Role</th><th>Status</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {(users.data ?? []).map((u: any) => (
              <tr key={u.id} className="border-t">
                <td>{u.username}</td>
                <td>{u.email}</td>
                <td>
                  <select
                    value={u.role}
                    onChange={(e) => updateRole.mutate({ id: u.id, role: e.target.value })}
                  >
                    <option value="admin">admin</option>
                    <option value="editor">editor</option>
                    <option value="viewer">viewer</option>
                  </select>
                </td>
                <td>{u.is_active ? "Active" : "Deactivated"}</td>
                <td>
                  {u.is_active ? (
                    <Button variant="outline" size="sm" onClick={() => deactivate.mutate(u.id)}>
                      Deactivate
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" onClick={() => activate.mutate(u.id)}>
                      Activate
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
};
