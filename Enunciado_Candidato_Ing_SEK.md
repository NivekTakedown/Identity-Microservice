# Prueba Técnica – Ingeniero de Desarrollo (Identidades Digitales)

## Objetivo
Construir un microservicio que permita validar competencias en:
1. Diseño y construcción de un **microservicio seguro**.  
2. Integración con **IAM** mediante **REST/SCIM/OAuth2/OIDC**.  
3. Aplicación de **ABAC** y principio de **mínimo privilegio**.  
4. **Documentación** clara y completa.

## Tecnologías permitidas
- Lenguaje: **Python (FastAPI)** o **Node.js (Express)**.  
- Almacenamiento: **in-memory**, archivo JSON o SQLite.  
- IdP/Directorio: **mock** (no real).  
- Ejecución: obligatorio con **Docker**.

## Requerimientos funcionales

### 1. SCIM 2.0 (subset mínimo)
- `POST /scim/v2/Users` – Crea usuario con atributos:  
  `userName`, `name.givenName`, `name.familyName`, `active`, `emails[primary]`, `groups` (opcional).  
- `GET /scim/v2/Users/{id}` – Lee usuario.  
- `PATCH /scim/v2/Users/{id}` – Cambia estado (`active`) o atributos básicos.  
- `GET /scim/v2/Users?filter=userName eq "..."` – Búsqueda exacta por `userName`.  
- (**Opcional +5 pts**) `POST /scim/v2/Groups` y asignación de miembros.

### 2. Emisión y validación de tokens (OAuth2/OIDC-like)
- `POST /auth/token` – Recibe credenciales mock (`client_id/client_secret` o `username/password`) y devuelve un **JWT** con claims:  
  `sub`, `scope`, `groups`, `dept`, `riskScore`, `exp`.  
- `GET /auth/me` – Valida token y retorna claims.  
- Firma de JWT: **HS256 o RS256** (clave/llave desde variable de entorno).

### 3. Evaluador ABAC
- `POST /authz/evaluate` – Entrada ejemplo:  
  ```json
  {
    "subject": {"dept":"HR","groups":["HR_READERS"],"riskScore":20},
    "resource": {"type":"payroll","env":"prod"},
    "context": {"geo":"CL","deviceTrusted":true,"timeOfDay":"10:30"}
  }
  ```
- Políticas en archivo `policies.json|yaml`, por ejemplo:
  - **HR-Payroll-01**: Permit si `dept=="HR"` y `type=="payroll"` y `deviceTrusted==true`.  
  - **Risk-StepUp-01**: Challenge si `riskScore >= 70` o `geo` fuera de `["CL","CO"]`.  
  - **Admins-NonProd-01**: Permit si `groups` incluye `"ADMINS"` y `env!="prod"`. Si `env=="prod"`, Challenge.

- Respuesta:
  ```json
  {
    "decision": "Permit|Deny|Challenge",
    "reasons": ["ruleId: HR-Payroll-01"]
  }
  ```

### 4. Documentación
- **OpenAPI/Swagger** de todos los endpoints.  
- **README** con:  
  - Pre-requisitos.  
  - Variables de entorno.  
  - Cómo ejecutar (Docker).  
  - Ejemplos `curl` o colección Postman.  
  - Supuestos y un diagrama simple de los flujos (SCIM, token, ABAC).

## Datos de prueba
Usuarios iniciales (cargar al iniciar el servicio):  
- `jdoe` → HR, groups: `["HR_READERS"]`, activo, riesgo 20.  
- `agonzalez` → Finance, groups: `["FIN_APPROVERS"]`, activo, riesgo 30.  
- `mrios` → IT, groups: `["ADMINS"]`, inactivo, riesgo 15.  

Políticas iniciales: al menos las 3 de los ejemplos anteriores.

## Entregables
- Código + Dockerfile + docker-compose.  
- README + OpenAPI + diagrama.  
- Postman/cURL con pruebas funcionales.  

Tiempo estimado: 6 horas efectivas (48 horas de ventana de entrega).