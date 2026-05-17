import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";


export default function NotFoundPage() {
  const { token } = useAuth();

  return (
    <div className="screen-center">
      <div className="auth-card">
        <h2>Página no encontrada</h2>
        <p>La ruta solicitada no existe en esta versión inicial.</p>
        <Link className="primary-link" to={token ? "/" : "/login"}>
          Volver al inicio
        </Link>
      </div>
    </div>
  );
}

