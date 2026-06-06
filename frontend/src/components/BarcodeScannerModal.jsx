import { BrowserMultiFormatReader } from "@zxing/browser";
import { useEffect, useRef, useState } from "react";

import { ActionButton, Field, ModalShell } from "../pages/inventory/shared";


function canUseCameraScanner() {
  if (typeof window === "undefined") {
    return false;
  }

  const hostname = window.location.hostname;
  const isSingleLabelHost = Boolean(hostname) && !hostname.includes(".") && !hostname.includes(":");
  const ipv4Parts = hostname.split(".");
  const isLoopbackIpv4 =
    ipv4Parts.length === 4 &&
    ipv4Parts.every((part) => /^\d+$/.test(part)) &&
    Number(ipv4Parts[0]) === 127 &&
    ipv4Parts.every((part) => Number(part) >= 0 && Number(part) <= 255);
  const isLoopbackIpv6 = hostname === "::1";
  return Boolean(window.isSecureContext || isSingleLabelHost || isLoopbackIpv4 || isLoopbackIpv6);
}


function getCameraErrorMessage(error) {
  const errorName = error?.name || "";
  if (errorName === "NotAllowedError" || errorName === "PermissionDeniedError") {
    return "No se pudo acceder a la cámara. Revisa permisos del navegador.";
  }
  if (errorName === "NotFoundError" || errorName === "DevicesNotFoundError") {
    return "No se encontró una cámara disponible en este dispositivo.";
  }
  if (errorName === "NotReadableError" || errorName === "TrackStartError") {
    return "La cámara está en uso por otra aplicación o no pudo iniciarse.";
  }
  return "No se pudo iniciar el escáner de cámara. Puedes escribir o pegar el código manualmente.";
}


export default function BarcodeScannerModal({
  open,
  onClose,
  onDetected,
  title = "Escanear código",
  helperText = "Apunta la cámara al código de barras o QR.",
}) {
  const videoRef = useRef(null);
  const controlsRef = useRef(null);
  const readerRef = useRef(null);
  const detectedRef = useRef(false);

  const [manualCode, setManualCode] = useState("");
  const [detectedCode, setDetectedCode] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  function stopScanner() {
    detectedRef.current = false;

    try {
      controlsRef.current?.stop?.();
    } catch {
      // No action required.
    }
    controlsRef.current = null;

    try {
      readerRef.current?.reset?.();
    } catch {
      // No action required.
    }
    readerRef.current = null;

    const videoElement = videoRef.current;
    const stream = videoElement?.srcObject;
    if (stream && typeof stream.getTracks === "function") {
      stream.getTracks().forEach((track) => track.stop());
    }
    if (videoElement) {
      videoElement.srcObject = null;
    }
  }

  function closeModal() {
    stopScanner();
    setManualCode("");
    setDetectedCode("");
    setError("");
    setStatus("");
    onClose();
  }

  function useDetectedCode(value = manualCode || detectedCode) {
    const normalized = String(value || "").trim();
    if (!normalized) {
      setError("Escribe o escanea un código para continuar.");
      return;
    }

    onDetected(normalized);
    closeModal();
  }

  useEffect(() => {
    if (!open) {
      stopScanner();
      return undefined;
    }

    setManualCode("");
    setDetectedCode("");
    setError("");
    setStatus("");

    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Este navegador no soporta acceso a cámara. Puedes escribir o pegar el código manualmente.");
      return undefined;
    }

    if (!canUseCameraScanner()) {
      setError("La cámara requiere HTTPS o permisos del navegador. Puedes escribir o pegar el código manualmente.");
      return undefined;
    }

    let cancelled = false;

    async function startScanner() {
      setStatus("Iniciando cámara...");
      const reader = new BrowserMultiFormatReader();
      readerRef.current = reader;

      try {
        const controls = await reader.decodeFromVideoDevice(undefined, videoRef.current, (result) => {
          if (!result || cancelled || detectedRef.current) {
            return;
          }

          const code = String(result.getText?.() ?? result.text ?? "").trim();
          if (!code) {
            return;
          }

          detectedRef.current = true;
          setDetectedCode(code);
          setManualCode(code);
          setStatus(`Código detectado: ${code}`);
          setError("");
          stopScanner();
        });

        if (cancelled) {
          controls?.stop?.();
          return;
        }

        controlsRef.current = controls;
        setStatus("Apunta la cámara al código de barras o QR.");
      } catch (requestError) {
        if (!cancelled) {
          setError(getCameraErrorMessage(requestError));
          setStatus("");
        }
      }
    }

    startScanner();

    return () => {
      cancelled = true;
      stopScanner();
    };
  }, [open]);

  return (
    <ModalShell onClose={closeModal} open={open} size="medium" subtitle={helperText} title={title}>
      <div className="barcode-scanner-stack">
        <div className="barcode-scanner-preview">
          <video className="barcode-scanner-video" muted playsInline ref={videoRef} />
          {!detectedCode ? (
            <div className="barcode-scanner-overlay">Coloca el código dentro del cuadro de la cámara.</div>
          ) : null}
        </div>

        {status ? <p className="feature-note">{status}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}

        <Field hint="Si la cámara no está disponible, escribe o pega el código." label="Escribir código manualmente">
          <input
            autoFocus
            onChange={(event) => setManualCode(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                useDetectedCode(event.currentTarget.value);
              }
            }}
            placeholder="SKU, código de barras o QR"
            type="text"
            value={manualCode}
          />
        </Field>

        <div className="inventory-actions inventory-actions-end">
          <ActionButton onClick={() => useDetectedCode()} tone="primary" type="button">
            Usar código
          </ActionButton>
          <ActionButton onClick={closeModal} type="button">
            Cerrar
          </ActionButton>
        </div>
      </div>
    </ModalShell>
  );
}
