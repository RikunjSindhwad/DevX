---
id: owasp-top-10-quickref
title: OWASP-Style Secure-by-Default Checklist
type: security
tags: [security, owasp, review, checklist]
summary: A compact review checklist for common application security failures.
related: []
created: 2026-06-20
---

# OWASP-Style Secure-by-Default Checklist

A review-time checklist for application code. Not exhaustive — a fast pass for the reviewer agent.

## Injection (SQL / command / template)
- Parameterized queries only; never string-concatenate untrusted input into SQL.
- No `shell=True` with interpolated input; pass argv lists.
- Auto-escaping templating; treat any `| safe` / `mark_safe` as a finding to justify.

## Broken access control
- Authorization checked **server-side** on every endpoint, not just the UI.
- Object-level checks (does *this user* own *this id*?) — the classic IDOR gap.
- Deny by default; no "forgot to add the guard" routes.

## Authentication & secrets
- No hardcoded credentials, tokens, or API keys in source or config committed to git.
- Passwords hashed with a slow KDF (argon2/bcrypt/scrypt), never fast hashes.
- Tokens validated for signature **and** algorithm; reject `alg: none`.

## Sensitive data & crypto
- TLS for transport; no homegrown crypto; use vetted libraries.
- PII minimized and not logged.

## Misconfiguration & dependencies
- Pin dependency versions; run an advisory check (npm audit / pip-audit / govulncheck).
- Debug/verbose errors off in production; no stack traces to clients.

## SSRF / deserialization
- Validate and allowlist outbound URLs from user input.
- Never deserialize untrusted data into rich objects (pickle/yaml.load/Java serialization).

> Source: https://owasp.org/www-project-top-ten/ · curated · 2026-06-20
