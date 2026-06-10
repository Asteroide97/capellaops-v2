import { useEffect, useMemo, useRef, useState } from "react";
import { Building2, ImagePlus, Trash2 } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";

import {
  deleteCompanyLogo,
  getCompanyProfile,
  updateCompanyProfile,
  uploadCompanyLogo,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import {
  ActionButton,
  DataCard,
  Field,
  FormGrid,
  PageHeader,
  safeDisplayText,
} from "./inventory/shared";


const MAX_LOGO_SIZE_BYTES = 5 * 1024 * 1024;
const ALLOWED_LOGO_TYPES = ["image/png", "image/jpeg", "image/webp"];

const defaultProfile = {
  id: "",
  name: "",
  slug: "",
  nombre_comercial: "",
  razon_social: "",
  rfc: "",
  email_contacto: "",
  telefono: "",
  sitio_web: "",
  direccion: "",
  ciudad: "",
  estado: "",
  pais: "",
  codigo_postal: "",
  logo_url: "",
};


function normalizeProfileForm(payload) {
  return {
    ...defaultProfile,
    ...payload,
    nombre_comercial: payload?.nombre_comercial ?? payload?.name ?? "",
    razon_social: payload?.razon_social ?? "",
    rfc: payload?.rfc ?? "",
    email_contacto: payload?.email_contacto ?? "",
    telefono: payload?.telefono ?? "",
    sitio_web: payload?.sitio_web ?? "",
    direccion: payload?.direccion ?? "",
    ciudad: payload?.ciudad ?? "",
    estado: payload?.estado ?? "",
    pais: payload?.pais ?? "",
    codigo_postal: payload?.codigo_postal ?? "",
    logo_url: payload?.logo_url ?? "",
  };
}


export default function CompanyProfilePage() {
  const fileInputRef = useRef(null);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { empresaId, membership, refreshSession, token, user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [removingLogo, setRemovingLogo] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [profile, setProfile] = useState(defaultProfile);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState("");

  const canEdit = useMemo(() => {
    const role = String(membership?.role ?? "").toLowerCase();
    return Boolean(user?.is_superadmin || role === "owner" || role === "admin");
  }, [membership?.role, user?.is_superadmin]);

  const showOnboardingBanner = searchParams.get("onboarding") === "1";

  useEffect(() => {
    let isMounted = true;

    async function loadProfile() {
      if (!token || !empresaId) {
        return;
      }

      setLoading(true);
      setError("");
      try {
        const response = await getCompanyProfile({ token, empresaId });
        if (!isMounted) {
          return;
        }
        const normalized = normalizeProfileForm(response);
        setProfile(normalized);
        setLogoPreviewUrl(normalized.logo_url || "");
      } catch (requestError) {
        if (!isMounted) {
          return;
        }
        setError(requestError.message || "No se pudo cargar la informacion de la empresa.");
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadProfile();

    return () => {
      isMounted = false;
    };
  }, [token, empresaId]);

  function handleFieldChange(key, value) {
    setProfile((current) => ({ ...current, [key]: value }));
  }

  async function handleSave(event) {
    event.preventDefault();
    if (!canEdit) {
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const response = await updateCompanyProfile({
        token,
        empresaId,
        payload: {
          nombre_comercial: profile.nombre_comercial || null,
          razon_social: profile.razon_social || null,
          rfc: profile.rfc || null,
          email_contacto: profile.email_contacto || null,
          telefono: profile.telefono || null,
          sitio_web: profile.sitio_web || null,
          direccion: profile.direccion || null,
          ciudad: profile.ciudad || null,
          estado: profile.estado || null,
          pais: profile.pais || null,
          codigo_postal: profile.codigo_postal || null,
        },
      });
      const normalized = normalizeProfileForm(response);
      setProfile(normalized);
      setSuccess("Datos de empresa actualizados correctamente.");
      await refreshSession();
    } catch (requestError) {
      setError(requestError.message || "No se pudieron guardar los datos de la empresa.");
    } finally {
      setSaving(false);
    }
  }

  async function handleLogoSelected(event) {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) {
      return;
    }

    if (!ALLOWED_LOGO_TYPES.includes(file.type)) {
      setError("Selecciona una imagen PNG, JPG o WEBP.");
      setSuccess("");
      return;
    }

    if (file.size > MAX_LOGO_SIZE_BYTES) {
      setError("La imagen excede el tamaño máximo de 5 MB.");
      setSuccess("");
      return;
    }

    const previousPreview = logoPreviewUrl;
    const objectUrl = URL.createObjectURL(file);
    setLogoPreviewUrl(objectUrl);
    setUploadingLogo(true);
    setError("");
    setSuccess("");

    try {
      const response = await uploadCompanyLogo({ token, empresaId, file });
      setProfile((current) => ({ ...current, logo_url: response.logo_url }));
      setLogoPreviewUrl(response.logo_url);
      setSuccess("Logo actualizado correctamente.");
      await refreshSession();
    } catch (requestError) {
      setLogoPreviewUrl(previousPreview);
      setError(requestError.message || "No se pudo actualizar el logo.");
    } finally {
      URL.revokeObjectURL(objectUrl);
      setUploadingLogo(false);
    }
  }

  async function handleRemoveLogo() {
    if (!canEdit || removingLogo) {
      return;
    }

    setRemovingLogo(true);
    setError("");
    setSuccess("");
    try {
      await deleteCompanyLogo({ token, empresaId });
      setProfile((current) => ({ ...current, logo_url: "" }));
      setLogoPreviewUrl("");
      setSuccess("Logo eliminado correctamente.");
      await refreshSession();
    } catch (requestError) {
      setError(requestError.message || "No se pudo eliminar el logo.");
    } finally {
      setRemovingLogo(false);
    }
  }

  if (loading) {
    return <div className="screen-center">Cargando perfil de empresa...</div>;
  }

  return (
    <div className="inventory-shell inventory-screen company-profile-screen">
      <PageHeader
        eyebrow="Empresa"
        subtitle="Estos datos se usarán en tickets, estimaciones, órdenes de compra y documentos comerciales."
        title="Perfil"
      >
        {showOnboardingBanner ? (
          <div className="inventory-form-note inventory-form-note-warning company-profile-onboarding">
            <strong>Agrega el logo de tu empresa</strong>
            <p>
              Estos datos se usarán en tickets, estimaciones, órdenes de compra y documentos comerciales.
            </p>
            <div className="inventory-actions inventory-actions-wrap">
              <ActionButton onClick={() => navigate("/")} size="sm" type="button">
                Continuar sin logo
              </ActionButton>
            </div>
          </div>
        ) : null}
      </PageHeader>

      {error ? (
        <div className="inventory-form-note inventory-form-note-danger">
          <strong>Error operativo</strong>
          <p>{error}</p>
        </div>
      ) : null}
      {success ? (
        <div className="inventory-form-note inventory-form-note-success">
          <strong>Operación completada</strong>
          <p>{success}</p>
        </div>
      ) : null}
      {!canEdit ? (
        <div className="inventory-form-note">
          <strong>Solo lectura</strong>
          <p>Puedes consultar los datos de la empresa, pero no tienes permiso para editarlos.</p>
        </div>
      ) : null}

      <div className="company-profile-grid">
        <DataCard
          className="company-profile-logo-card"
          subtitle="Sube el logo que se usará en documentos operativos."
          title="Logo empresarial"
        >
          <div className="company-logo-preview-shell">
            {logoPreviewUrl ? (
              <img alt="Logo de la empresa" className="company-logo-preview" src={logoPreviewUrl} />
            ) : (
              <div className="company-logo-placeholder">
                <Building2 size={28} />
                <span>{safeDisplayText(profile.nombre_comercial || profile.name, "Empresa")}</span>
              </div>
            )}
          </div>

          <input
            accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
            className="company-logo-input"
            disabled={!canEdit || uploadingLogo}
            onChange={handleLogoSelected}
            ref={fileInputRef}
            type="file"
          />

          <div className="inventory-actions inventory-actions-wrap">
            <ActionButton
              disabled={!canEdit || uploadingLogo}
              icon={<ImagePlus size={16} />}
              onClick={() => fileInputRef.current?.click()}
              tone="primary"
              type="button"
            >
              {uploadingLogo ? "Subiendo..." : profile.logo_url ? "Cambiar logo" : "Subir logo"}
            </ActionButton>
            <ActionButton
              disabled={!canEdit || removingLogo || !profile.logo_url}
              icon={<Trash2 size={16} />}
              onClick={handleRemoveLogo}
              type="button"
            >
              {removingLogo ? "Quitando..." : "Quitar logo"}
            </ActionButton>
          </div>

          <p className="table-note">Formatos permitidos: PNG, JPG y WEBP. Tamaño máximo: 5 MB.</p>
        </DataCard>

        <DataCard
          className="company-profile-data-card"
          subtitle="Información comercial y fiscal básica para documentos operativos."
          title="Datos de empresa"
        >
          <form className="inventory-modal-form" onSubmit={handleSave}>
            <FormGrid>
              <Field label="Nombre comercial">
                <input
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("nombre_comercial", event.target.value)}
                  type="text"
                  value={profile.nombre_comercial}
                />
              </Field>
              <Field hint="Solo lectura en esta fase." label="Nombre de la empresa">
                <input disabled type="text" value={profile.name} />
              </Field>
              <Field label="Razón social">
                <input
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("razon_social", event.target.value)}
                  type="text"
                  value={profile.razon_social}
                />
              </Field>
              <Field label="RFC">
                <input
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("rfc", event.target.value.toUpperCase())}
                  type="text"
                  value={profile.rfc}
                />
              </Field>
              <Field label="Email de contacto">
                <input
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("email_contacto", event.target.value)}
                  type="email"
                  value={profile.email_contacto}
                />
              </Field>
              <Field label="Teléfono">
                <input
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("telefono", event.target.value)}
                  type="text"
                  value={profile.telefono}
                />
              </Field>
              <Field label="Sitio web">
                <input
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("sitio_web", event.target.value)}
                  type="text"
                  value={profile.sitio_web}
                />
              </Field>
              <Field label="Código postal">
                <input
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("codigo_postal", event.target.value)}
                  type="text"
                  value={profile.codigo_postal}
                />
              </Field>
              <Field label="Dirección" span={2}>
                <textarea
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("direccion", event.target.value)}
                  rows={3}
                  value={profile.direccion}
                />
              </Field>
              <Field label="Ciudad">
                <input
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("ciudad", event.target.value)}
                  type="text"
                  value={profile.ciudad}
                />
              </Field>
              <Field label="Estado">
                <input
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("estado", event.target.value)}
                  type="text"
                  value={profile.estado}
                />
              </Field>
              <Field label="País">
                <input
                  disabled={!canEdit || saving}
                  onChange={(event) => handleFieldChange("pais", event.target.value)}
                  type="text"
                  value={profile.pais}
                />
              </Field>
              <Field hint="Solo lectura." label="Slug">
                <input disabled type="text" value={profile.slug} />
              </Field>
            </FormGrid>

            {canEdit ? (
              <div className="inventory-actions inventory-actions-wrap">
                <ActionButton disabled={saving} tone="primary" type="submit">
                  {saving ? "Guardando..." : "Guardar cambios"}
                </ActionButton>
                {showOnboardingBanner ? (
                  <ActionButton onClick={() => navigate("/")} type="button">
                    Continuar sin logo
                  </ActionButton>
                ) : null}
              </div>
            ) : null}
          </form>
        </DataCard>
      </div>
    </div>
  );
}
