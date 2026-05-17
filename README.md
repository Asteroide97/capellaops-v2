# Capella Ops V2

Monorepo inicial para un SaaS multiempresa con Azure SQL, FastAPI y React + Vite.

## Stack

- Frontend: React + Vite
- Backend: FastAPI
- Base de datos objetivo: Azure SQL
- ORM: SQLAlchemy
- Migraciones: Alembic
- Auth: JWT propio
- Verificacion de telefono: Twilio Verify SMS
- Antibot: reCAPTCHA validado en backend

## Estructura

```text
CapellaOpsV2/
  frontend/
  backend/
  docs/
  database/
```

## Requisitos

- Node.js 18+
- Python 3.11+
- ODBC Driver 18 for SQL Server

## Backend

1. Crear entorno virtual:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configurar variables:

```powershell
Copy-Item .env.example .env
```

3. Ejecutar migraciones:

```powershell
alembic upgrade head
```

4. Sembrar planes:

```powershell
python -m app.seed
```

5. Inspeccionar la base configurada:

```powershell
python -m app.debug_db
```

6. Levantar API:

```powershell
uvicorn app.main:app --reload
```

### Endpoints incluidos

- `GET /health`
- `POST /auth/register/start`
- `POST /auth/register/verify`
- `POST /auth/login`
- `GET /me`
- `GET /modules`

### Flujo de registro

1. `POST /auth/register/start`
   Valida reCAPTCHA, verifica que el correo y el telefono no existan todavia, crea o actualiza `PendingRegistration` y envia un codigo por SMS con Twilio Verify.
2. `POST /auth/register/verify`
   Verifica el codigo de 6 digitos por SMS y solo entonces crea `Empresa`, `Usuario`, `EmpresaUsuario`, `EmpresaModulo` y `AuditLog`.

### Variables relevantes

- `DATABASE_URL`
- `AZURE_SQL_SERVER`
- `AZURE_SQL_DATABASE`
- `AZURE_SQL_USERNAME`
- `AZURE_SQL_PASSWORD`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_VERIFY_SERVICE_SID`
- `TWILIO_VERIFY_CHANNEL`
- `VERIFY_DEV_MODE`
- `VERIFY_DEV_CODE`
- `RECAPTCHA_SECRET_KEY`
- `RECAPTCHA_MIN_SCORE`
- `RECAPTCHA_ENABLED`

## Frontend

1. Instalar dependencias:

```powershell
cd frontend
npm install
```

2. Configurar entorno:

```powershell
Copy-Item .env.example .env
```

3. Levantar Vite:

```powershell
npm run dev
```

### Variables relevantes

- `VITE_API_URL`
- `VITE_RECAPTCHA_SITE_KEY`

## Base de datos

- Produccion: usar Azure SQL mediante `DATABASE_URL` o variables `AZURE_SQL_*`.
- Alembic toma la URL resuelta desde `backend/.env`, sin depender del directorio desde donde se ejecute el comando.
- Si no se configura Azure SQL, el backend cae en SQLite local solo para smoke tests rapidos.

## Reglas implementadas

- Cada empresa tiene `plan_code`: `basico`, `pro` o `total`.
- Cada empresa tiene `access_status`: `trial`, `active`, `past_due`, `suspended`, `cancelled`.
- Toda empresa nueva inicia con trial de 15 dias.
- El contexto de empresa se valida desde backend mediante token y/o `X-Empresa-Id`.
- La funcion central `can_access_module(user, empresa, module_name)` gobierna acceso por plan, estado y rol.
- Facturacion existe solo como modulo pendiente y bloqueado para clientes.
- No se crea empresa hasta verificar el SMS.
- No se permiten mas de 5 intentos por codigo.
- No se permite reenviar codigo antes de 60 segundos.

## Notas

- No se usa Base44 ni SDKs relacionados.
- No se implementa `factura.com`.
- No se implementa timbrado CFDI.
- No se implementa CSD.
- Twilio Verify SMS requiere un Verify Service con canal `sms` habilitado y una cuenta/configuracion valida para envio de SMS.
