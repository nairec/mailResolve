# Estructura del proyecto mailResolve

Documentación de módulos, interacciones y decisiones de diseño.

## Visión general

mailResolve automatiza el triage de Gmail mediante reglas deterministas con fallback a Groq LLM. La arquitectura es multi-tenant desde el inicio (todas las tablas llevan `user_id`), aunque v1 es uso personal con una sola cuenta.

```
Gmail watch → Pub/Sub → FastAPI webhook → Celery worker → Clasificación → Acciones Gmail
```

## Estructura de carpetas

```
mailResolve/
├── src/
│   ├── api/           # FastAPI REST API
│   ├── cli/           # Typer CLI
│   ├── core/          # Config y seguridad
│   ├── gmail/         # Cliente Gmail API
│   ├── classifier/    # Motor de reglas + Groq
│   ├── worker/        # Celery tasks
│   ├── models/        # SQLAlchemy ORM
│   └── schemas/       # Pydantic DTOs
├── alembic/           # Migraciones DB
├── tests/
├── docker-compose.yml # Postgres + Redis local
└── pyproject.toml
```

## Módulos y responsabilidades

### `src/core/`

| Archivo | Propósito |
|---------|-----------|
| `config.py` | Settings vía `pydantic-settings`; lee `.env` |
| `security.py` | Cifrado Fernet de `refresh_token` OAuth |

**Decisión**: `SECRET_KEY` debe ser una clave Fernet válida (32 bytes base64). Se genera una vez en setup.

### `src/models/`

| Modelo | Tabla | Descripción |
|--------|-------|-------------|
| `User` | `users` | Cuenta Gmail vinculada, tokens cifrados, `history_id`, `watch_expires_at` |
| `Rule` | `rules` | Reglas de clasificación con `conditions` y `actions` JSONB |
| `ClassificationLog` | `classification_logs` | Auditoría de cada decisión (rule/llm) |
| `SnoozedMessage` | `snoozed_messages` | Emails en snooze con `wake_at` |
| `ProcessedMessage` | `processed_messages` | Deduplicación por `(user_id, gmail_message_id)` |

**Decisión**: Todos los modelos usan UUID como PK. `processed_messages` usa clave compuesta para dedup eficiente.

`database.py` expone `engine`, `SessionLocal` y `get_db()` para inyección en FastAPI.

### `src/schemas/`

DTOs Pydantic para request/response de la API. Separados de los modelos ORM para no acoplar la capa HTTP a la DB.

### `src/api/`

| Archivo | Endpoint(s) | Estado |
|---------|-------------|--------|
| `main.py` | App FastAPI + router central | ✅ Scaffold |
| `deps.py` | `get_database`, `verify_api_key` | ✅ Scaffold |
| `routes/health.py` | `GET /health` | ✅ Funcional |
| `routes/auth.py` | `GET /auth/login`, `/auth/callback` | ✅ OAuth + persist User |
| `routes/webhooks.py` | `POST /webhooks/gmail` → encola `process_history` |
| `routes/rules.py` | CRUD `/rules` + `POST /rules/test` | ✅ Funcional |
| `routes/sync.py` | `POST /sync` → encola `process_history` manual |

**Autenticación API v1**: header `X-API-Key` comparado con `API_KEY` en env.

### `src/cli/`

| Archivo | Propósito |
|---------|-----------|
| `main.py` | Entry point Typer; comandos auth, sync, watch, logs, rules |
| `rules_prompt.py` | Wizard interactivo para crear reglas paso a paso |

CLI Typer con entry point `mailresolve`. Comandos implementados: `auth login/status`, `sync [--classify | --classify-in-process]`, `watch`, `logs --last N`, `rules list/add/delete/test`. `rules add` acepta `--file` (YAML) o modo interactivo (`--interactive` / sin `--file`).

### `src/worker/`

| Archivo | Propósito |
|---------|-----------|
| `celery_app.py` | Config Celery + Redis; beat schedule para `renew_watch` y `wake_snoozed` |
| `tasks.py` | `process_history`, `renew_watch` (Beat), `wake_snoozed` stub |

### `src/gmail/`

| Archivo | Propósito |
|---------|-----------|
| `oauth.py` | Factory `Flow` OAuth, validación de `state`, redirect URI desde settings |
| `client.py` | Wrapper Gmail API |
| `sync.py` | `history.list` incremental, dedup con `processed_messages` |
| `watch.py` | `users.watch()` / renovación |
| `actions.py` | `apply_actions`, archive, mark read, `ensure_label` |

### `src/classifier/`

| Archivo | Propósito |
|---------|-----------|
| `features.py` | `EmailFeatures` + `extract_features()` |
| `rules_engine.py` | Evalúa reglas JSON por prioridad, devuelve `RuleMatch` |
| `rule_validation.py` | Valida `conditions`/`actions` al crear o editar reglas |
| `seed_rules.py` | Reglas por defecto; seed idempotente en OAuth callback |
| `groq_classifier.py` | Fallback Groq con JSON schema + umbral 0.75 |
| `pipeline.py` | Orquestador rules → Groq → actions → `classification_logs` |

## Infraestructura local

### Docker Compose

- **postgres**: puerto 5432, user/pass/db `mailresolve`
- **redis**: puerto 6379

### Alembic

Migración inicial `001_initial_schema.py` crea las 5 tablas del modelo de datos.

```bash
alembic upgrade head
```

### Despliegue (Heroku)

| Archivo | Propósito |
|---------|-----------|
| `Procfile` | `release` (Alembic), `web`, `worker`, `beat` |
| `.python-version` | Versión de Python para Heroku/uv (3.13.0) |
| `uv.lock` | Lockfile de dependencias (Heroku: `uv sync --locked`) |
| `app.json` | Plantilla Heroku: add-ons Postgres/Redis y formation |

**Decisión**: Heroku usa **solo uv** (`pyproject.toml` + `uv.lock` + `.python-version`). No commitear `requirements.txt` a la vez que `uv.lock`.

**Decisión**: Heroku Postgres expone `DATABASE_URL` como `postgres://`; `settings.sqlalchemy_database_url` la normaliza a `postgresql://` para SQLAlchemy.

Tras el deploy: escalar `web=1 worker=1 beat=1`, OAuth en `/auth/login`, Pub/Sub push a `/webhooks/gmail`.

| `railway.toml` | Railway alternativo |

## Flujo de datos (futuro)

1. **OAuth** (`cli auth login`) → guarda `User` con token cifrado → activa `watch`
2. **Push** (`POST /webhooks/gmail`) → decodifica Pub/Sub → encola `process_history`
3. **Worker** → `history.list` incremental → por cada mensaje nuevo → `classifier.pipeline`
4. **Pipeline** → reglas (conf ≥ 0.9) o Groq (conf ≥ 0.75) → `gmail.actions` → `classification_log`
5. **Beat** → renueva `watch` cada 6 días; despierta snoozed cada minuto

## Variables de entorno

Ver `.env.example`. Mínimo para desarrollo local:

- `DATABASE_URL` → apunta a Docker Compose Postgres
- `REDIS_URL` → apunta a Docker Compose Redis
- `SECRET_KEY` → clave Fernet
- `API_KEY` → auth CLI/API

## Fases de implementación

| Fase | Contenido | Estado |
|------|-----------|--------|
| 0–2 | Scaffold, OAuth, sync, clasificación, CLI, reglas | ✅ |
| 3 | Snooze, backfill pending, resync history | Pendiente |
| 3b | Deploy Heroku (artefactos listos) | ✅ |
