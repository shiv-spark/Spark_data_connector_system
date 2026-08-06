import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";

/** Gates the console. Unauthenticated visitors land on sign in and return here after. */
export function RequireAuth() {
  const { user, ready } = useAuth();
  const location = useLocation();

  // Hold the route until the stored session has been read, so a refresh inside
  // the console doesn't bounce the user out to sign in.
  if (!ready) {
    return <div className="h-full" aria-busy="true" />;
  }

  if (!user) {
    return <Navigate to="/signin" state={{ from: location.pathname + location.search }} replace />;
  }

  return <Outlet />;
}
