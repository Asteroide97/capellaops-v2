import {
  BadgeDollarSign,
  BarChart3,
  CheckCheck,
  CircleDollarSign,
  Clock3,
  FileText,
  FolderKanban,
  Lock,
  PackageOpen,
} from "lucide-react";


export const pmModuleIcon = FolderKanban;


export const pmNavItems = [
  {
    key: "projects",
    label: "Proyectos",
    path: "/pm/projects",
    icon: FolderKanban,
  },
  {
    key: "executive",
    label: "Reporte ejecutivo",
    path: "/pm/reports/executive",
    icon: BarChart3,
  },
  {
    key: "estimations",
    label: "Estimaciones",
    path: "/pm/projects?section=estimations",
    section: "estimations",
    icon: CircleDollarSign,
  },
  {
    key: "budgets",
    label: "Presupuestos",
    path: "/pm/projects?section=budgets",
    section: "budgets",
    icon: BadgeDollarSign,
  },
  {
    key: "materials",
    label: "Materiales",
    path: "/pm/projects?section=materials",
    section: "materials",
    icon: PackageOpen,
  },
  {
    key: "time-costs",
    label: "Tiempo y costos",
    path: "/pm/rates",
    icon: Clock3,
  },
  {
    key: "approvals",
    label: "Aprobaciones",
    path: "/pm/projects?section=approvals",
    section: "approvals",
    icon: CheckCheck,
  },
  {
    key: "documents",
    label: "Documentos",
    path: "/pm/projects?section=documents",
    section: "documents",
    icon: FileText,
  },
  {
    key: "portal",
    label: "Portal externo",
    path: "/pm/projects?section=portal",
    section: "portal",
    icon: Lock,
  },
];


export function isPmPath(pathname = "") {
  return pathname === "/pm" || pathname.startsWith("/pm/");
}


export function resolvePmNavKey(pathname = "", search = "") {
  if (!isPmPath(pathname)) {
    return "";
  }

  if (pathname.startsWith("/pm/reports/executive")) {
    return "executive";
  }

  if (pathname.startsWith("/pm/rates")) {
    return "time-costs";
  }

  if (pathname.startsWith("/pm/projects/")) {
    return "projects";
  }

  if (pathname === "/pm/projects") {
    const section = new URLSearchParams(search).get("section");
    if (section) {
      const matchedItem = pmNavItems.find((item) => item.section === section);
      if (matchedItem) {
        return matchedItem.key;
      }
    }
    return "projects";
  }

  return "projects";
}
