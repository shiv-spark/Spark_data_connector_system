import { Link } from "react-router-dom";
import { currentUser, getUserInitials, type User } from "@/lib/user";

interface UserMenuProps {
  user?: User;
}

export function UserMenu({ user = currentUser }: UserMenuProps) {
  const initials = getUserInitials(user.name);

  return (
    <div className="flex items-center gap-2 rounded-md px-1.5 py-1">
      <span className="grid h-6 w-6 place-items-center rounded-full bg-gradient-to-br from-emerald-500 via-teal-500 to-emerald-700 text-[10px] font-bold text-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.12)]">
        {initials}
      </span>
      <div className="flex flex-col items-start leading-tight">
        <span className="text-[11.5px] font-semibold text-slate-800 dark:text-slate-200">
          {user.name}
        </span>
        <span className="text-[10px] text-slate-500 dark:text-slate-400">
          {user.role}
        </span>
      </div>
    </div>
  );
}