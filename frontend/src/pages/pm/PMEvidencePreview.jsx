import { useEffect, useState } from "react";

import { getPmEvidenceBlob } from "../../api/client";

export default function PMEvidencePreview({ evidenceId, token, empresaId, alt }) {
  const [preview, setPreview] = useState({ url: "", loading: true, failed: false });

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    setPreview({ url: "", loading: true, failed: false });

    getPmEvidenceBlob({ evidenceId, token, empresaId })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (active) {
          setPreview({ url: objectUrl, loading: false, failed: false });
        } else {
          URL.revokeObjectURL(objectUrl);
        }
      })
      .catch(() => {
        if (active) setPreview({ url: "", loading: false, failed: true });
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [evidenceId, empresaId, token]);

  if (preview.url) return <img alt={alt || "Evidencia del trabajo"} src={preview.url} />;

  return (
    <span className="pm-evidence-preview-state" role="status">
      {preview.loading ? "Cargando fotografía…" : preview.failed ? "No se pudo cargar la fotografía." : ""}
    </span>
  );
}
