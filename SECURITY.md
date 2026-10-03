# Security policy

## Before pushing or deploying

Run the test suite and inspect the staged files:

```powershell
python test_backend.py
git diff --cached --check
git diff --cached --name-only
```

Never stage environment files, service-account JSON, private keys, databases,
logs, or generated archives. `.gitignore` and `.dockerignore` provide a safety
net; they do not replace reviewing what is staged.

## Required production configuration

- Store `GEMINI_API_KEY`, `ADMIN_API_KEY`, and any service-account credential in
  the deployment platform's secret manager, never in source control or a Docker
  image.
- Set `ADMIN_API_KEY` to a long random secret. Operational mutation, insurance,
  and billable AI briefing endpoints reject requests without it.
- Set `ALLOWED_ORIGINS` to exact, HTTPS frontend origins.
- Enforce rate limits and authentication at the load balancer/API gateway as
  well as in the application.

## Historical credential incident

A Google service-account credential was previously committed under
`HACKATHON/api/gee-credentials.json`. Assume it is compromised even if it no
longer appears in the working tree:

1. Revoke/delete the exposed Google service-account key and review audit logs.
2. Remove the path from every Git ref using `git filter-repo` (or equivalent).
3. Force-push rewritten refs and ask every collaborator to re-clone.
4. Treat forks, caches, artifacts, and past clones as possible copies.

Do not rewrite shared Git history until collaborators have been notified.
