import {
  BarChart3,
  BookOpen,
  Box,
  Boxes,
  ClipboardCheck,
  ClipboardList,
  FolderKanban,
  Gauge,
  Repeat2,
  ShoppingCart,
  Truck,
  Warehouse,
  Wrench,
} from "lucide-react";


export const inventoryModuleIcon = Boxes;


export const inventoryNavItems = [
  {
    key: "resumen",
    label: "Resumen",
    path: "/inventario/resumen",
    description: "Vista operativa general, stock y alertas.",
    icon: Gauge,
  },
  {
    key: "almacenes",
    label: "Almacenes",
    path: "/inventario/almacenes",
    description: "Configuración y consulta de almacenes activos.",
    icon: Warehouse,
  },
  {
    key: "materiales",
    label: "Materiales",
    path: "/inventario/materiales",
    description: "Catálogo de materiales y precios base.",
    icon: Box,
  },
  {
    key: "movimientos",
    label: "Movimientos",
    path: "/inventario/movimientos",
    description: "Entradas, salidas y ajustes manuales.",
    icon: Repeat2,
  },
  {
    key: "kardex",
    label: "Kardex",
    path: "/inventario/kardex",
    description: "Historial detallado por material y almacén.",
    icon: BookOpen,
  },
  {
    key: "traspasos",
    label: "Traspasos",
    path: "/inventario/traspasos",
    description: "Transferencias entre almacenes y conteos físicos.",
    icon: Repeat2,
  },
  {
    key: "proveedores",
    label: "Proveedores",
    path: "/inventario/proveedores",
    description: "Directorio base de proveedores.",
    icon: Truck,
  },
  {
    key: "ordenes-compra",
    label: "Órdenes de compra",
    path: "/inventario/ordenes-compra",
    description: "Emisión y recepción de compras.",
    icon: ClipboardList,
  },
  {
    key: "requisiciones",
    label: "Requisiciones",
    path: "/inventario/requisiciones",
    description: "Solicitudes internas de materiales.",
    icon: ShoppingCart,
  },
  {
    key: "proyectos",
    label: "Proyectos",
    path: "/inventario/proyectos",
    description: "Consumos, devoluciones y costo real de materiales por proyecto.",
    icon: FolderKanban,
  },
  {
    key: "equipos",
    label: "Equipos",
    path: "/inventario/equipos",
    description: "Control futuro de equipos y activos.",
    icon: Wrench,
  },
  {
    key: "ordenes-trabajo",
    label: "Órdenes de trabajo",
    path: "/inventario/ordenes-trabajo",
    description: "Consumo y seguimiento operativo futuro.",
    icon: ClipboardCheck,
  },
  {
    key: "reportes",
    label: "Reportes",
    path: "/inventario/reportes",
    description: "Paneles y exportaciones operativas futuras.",
    icon: BarChart3,
  },
];
