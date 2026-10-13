
# Project File and Code Registry

## Project

Enterprise Autonomous IT Operations & Incident Resolution Agent

## Version

0.3.0

## Current Stage

Stage 7 - Audit Logging and Transaction Safety

## Application Files

| File | Responsibility | Status |
|---|---|---|
| app/main.py | FastAPI application, middleware, routing, request IDs | Implemented |
| app/core/config.py | Environment and database configuration | Implemented |
| app/core/logging_config.py | Structured JSON logging | Implemented |
| app/core/security.py | Password hashing and JWT security | Implemented |
| app/core/dependencies.py | Authentication and role-based access control | Implemented |
| app/api/routes/health.py | Health endpoints | Implemented |
| app/api/routes/auth.py | Login, current-user endpoint, login audit | Implemented |
| app/api/routes/incidents.py | Authenticated incident API and audit logging | Implemented |
| app/db/models.py | User, incident, event, and audit models | Implemented |
| app/db/session.py | SQLAlchemy engine and database sessions | Implemented |
| app/schemas/auth.py | Authentication and user schemas | Implemented |
| app/schemas/incident.py | Incident request and response schemas | Implemented |
| app/services/auth_service.py | User authentication and token issuance | Implemented |
| app/services/audit_service.py | Audit event persistence | Implemented |
| app/services/incident_service.py | Incident lifecycle and transaction operations | Implemented |
| alembic.ini | Database migration configuration | Implemented |
| migrations/env.py | Alembic migration environment | Implemented |
| migrations/script.py.mako | Migration template | Implemented |
| migrations/versions/ | Versioned schema migrations | Implemented |
| .env.example | Environment configuration template | Updated |
| requirements.txt | Python dependencies | Updated |
| docs/PROJECT_REGISTRY.md | Project inventory and development record | Updated |

## API Endpoints

### Health

- GET /
- GET /health
- GET /ready

### Authentication

- POST /api/v1/auth/login
- GET /api/v1/auth/me

### Incidents

- POST /api/v1/incidents
- GET /api/v1/incidents
- GET /api/v1/incidents/{incident_id}
- PATCH /api/v1/incidents/{incident_id}/status

## Authentication and Authorization

- Password hashing and verification.
- JWT access tokens.
- Active-user validation.
- Role-based access control.
- Incident reads require authentication.
- Incident creation and status changes require admin or operator roles.

## Incident Lifecycle

- open -> investigating
- open -> closed
- investigating -> open
- investigating -> resolved
- resolved -> investigating
- resolved -> closed

A resolved incident requires a root cause and resolution description.

## Data Model

- users: user accounts, roles, and password hashes
- incidents: incident records and current status
- incident_events: incident creation and status-change history
- audit_logs: security and operational audit events

## Audit Logging

- Successful and failed login attempts are audited.
- Incident creation is audited.
- Incident status changes are audited.
- Audit records include actor, action, resource, timestamp, and request metadata where available.
- Incident mutations and their audit records share a database transaction.

## Tests

| File | Coverage |
|---|---|
| tests/test_health.py | Health and configuration tests |
| tests/test_auth_service.py | Authentication service tests |
| tests/test_auth_api.py | Authentication API and authorization tests |
| tests/test_incidents.py | Incident API and lifecycle tests |
| tests/test_incident_transactions.py | Incident transaction behavior |
| tests/test_audit_service.py | Audit service persistence |
| tests/test_login_audit.py | Successful and failed login auditing |
| tests/test_incident_audit.py | Incident audit records and rollback behavior |

## Safety and Deployment Notes

- Production remediation is not enabled.
- Production audit immutability requires additional database permissions and controls.
- Audit persistence failures during login are currently handled without failing the login response; production deployments should add monitoring and alerting.
- Database migrations must be reviewed and tested before deployment.
- Dependency health checks and operational monitoring require further work.
- SQLite is currently used for development; production database configuration and deployment hardening remain future work.

## Validation Status

- Focused incident and audit tests: reported passed.
- Full test suite: awaiting recorded final test summary.
- Database migrations: implemented; migration verification should be repeated as part of deployment validation.
