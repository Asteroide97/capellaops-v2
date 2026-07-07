import {
  BarChart3,
  CalendarRange,
  ClipboardList,
  FolderKanban,
  LayoutDashboard,
  Rows3,
} from "lucide-react";


export const pmModuleIcon = FolderKanban;


export const pmNavItems = [
  {
    key: "schedule",
    label: "Cronograma",
    path: "/pm",
    icon: CalendarRange,
  },
  {
    key: "dashboard",
    label: "Resumen",
    path: "/pm/dashboard",
    icon: LayoutDashboard,
  },
  {
    key: "work_progress",
    label: "Avance de trabajos",
    path: "/pm/work-progress",
    icon: ClipboardList,
  },
  {
    key: "projects",
    label: "Lista de trabajos",
    path: "/pm/projects",
    icon: Rows3,
  },
  {
    key: "executive",
    label: "Reporte de trabajos",
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

  if (pathname.startsWith("/pm/work-progress")) {
    return "work_progress";
  }

  if (pathname.startsWith("/pm/projects/")) {
    return "projects";
  }

  if (pathname === "/pm/projects") {
    return "projects";
  }

  if (pathname.startsWith("/pm/dashboard")) {
    return "dashboard";
  }

  if (pathname === "/pm") {
    return "schedule";
  }

  return "schedule";
}
