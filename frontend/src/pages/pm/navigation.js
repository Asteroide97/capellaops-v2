import { BarChart3, FolderKanban, LayoutDashboard } from "lucide-react";


export const pmModuleIcon = FolderKanban;


export const pmNavItems = [
  {
    key: "projects",
    label: "Proyectos",
    path: "/pm/projects",
    icon: FolderKanban,
  },
  {
    key: "dashboard",
    label: "Dashboard PM",
    path: "/pm",
    icon: LayoutDashboard,
  },
  {
    key: "executive",
    label: "Reporte ejecutivo",
    path: "/pm/reports/executive",
    icon: BarChart3,
  },
];


export function isPmPath(pathname = "") {
  return pathname === "/pm" || pathname.startsWith("/pm/");
}


export function resolvePmNavKey(pathname = "") {
  if (!isPmPath(pathname)) {
    return "";
  }

  if (pathname.startsWith("/pm/reports/executive")) {
    return "executive";
  }

  if (pathname.startsWith("/pm/projects/")) {
    return "projects";
  }

  if (pathname === "/pm/projects") {
    return "projects";
  }

  if (pathname === "/pm" || pathname.startsWith("/pm/dashboard")) {
    return "dashboard";
  }

  return "projects";
}
