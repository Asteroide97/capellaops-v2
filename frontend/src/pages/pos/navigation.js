import {
  Clock3,
  History,
  ShoppingCart,
  Ticket,
} from "lucide-react";


export const posModuleIcon = ShoppingCart;


export const posNavItems = [
  {
    key: "sell",
    label: "Vender",
    path: "/pos?view=sell",
    view: "sell",
    icon: ShoppingCart,
  },
  {
    key: "history",
    label: "Historial de Ventas",
    path: "/pos?view=history",
    view: "history",
    icon: History,
  },
  {
    key: "tickets",
    label: "Tickets",
    path: "/pos?view=tickets",
    view: "tickets",
    icon: Ticket,
  },
  {
    key: "cash",
    label: "Caja / Turnos",
    path: "/pos?view=cash",
    view: "cash",
    icon: Clock3,
  },
];
