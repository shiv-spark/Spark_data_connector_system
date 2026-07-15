export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  avatar?: string;
}

export const currentUser: User = {
  id: "1",
  name: "Gaurav",
  email: "gaurav@sparkbrains.com",
  role: "Owner",
};

export const getUserInitials = (name: string): string => {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
};