# Security Policy

Knowledge Atlas is currently a pre-release graduation project and is not intended for production deployment.

## Reporting a security issue

Do not open a public issue containing credentials, private source code, personal data, or a reproducible exploit against a deployed instance. Report the issue privately to the repository owner and include only the minimum information needed to reproduce it safely.

## Sensitive data rules

- Never commit `.env` files, API keys, GitHub tokens, database passwords, or model-provider credentials.
- Use synthetic data in Mock fixtures, screenshots, tests, and documentation.
- Do not upload private repositories or personal notes to third-party model providers without explicit authorization.
- Logs must not contain access tokens, full prompts containing confidential code, or database connection strings.
- Uploaded files must be treated as untrusted input and validated by type, size, and parser behavior.

## Planned deployment safeguards

Before any public or shared deployment, the project should add:

- Authentication and project-level authorization checks.
- File upload limits and parser isolation.
- Secret management and credential rotation procedures.
- Dependency and container vulnerability scanning.
- Database backups and restore verification.
- Audit logging for knowledge confirmation, merge, and deletion operations.
- Rate limits for model-backed and ingestion endpoints.

Security features listed here are requirements, not claims about the current implementation.
