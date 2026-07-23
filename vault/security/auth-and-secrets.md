---
id: auth-and-secrets
title: Authentication, Authorization, and Secrets Handling
type: security
tags: [security, authentication, authorization, oauth, oidc, jwt, sessions, rbac, mfa, secrets, kms, credentials]
summary: How to implement authentication (OAuth/OIDC, JWT, sessions, MFA), enforce authorization (RBAC, ABAC, deny-by-default), and handle secrets safely (env, KMS, rotation, never-log).
related:
  - {slug: owasp-top-10-quickref, rel: relates-to}
  - {slug: secure-coding-and-injection, rel: relates-to}
  - {slug: ci-cd-and-deployment, rel: see-also}
created: 2026-06-21
---

# Authentication, Authorization, and Secrets Handling

Authentication (AuthN) proves identity; authorization (AuthZ) controls what that identity may do;
secrets management keeps the keys to both out of adversary hands. Failures in these layers are common
causes of application compromise. This entry is the deep treatment; see [[owasp-top-10-quickref]] for a
fast review checklist.

## Authentication choices

**Use OAuth 2.0 + OIDC** when you need federated identity (social login, enterprise SSO, third-party
API delegation). OIDC layers identity on top of OAuth—the relying party validates the ID Token's
issuer (`iss`), audience (`aud`), signature/key policy, expiration (`exp`), nonce when applicable,
and provider-specific requirements. As of July 2026, OAuth 2.1 is still an Internet-Draft
(`draft-ietf-oauth-v2-1-15`), not an RFC. Use the published OAuth/OIDC RFCs plus the OAuth 2.0 Security
Best Current Practice; apply PKCE to authorization-code clients, do not use the implicit grant, and
follow current refresh-token sender-constraining or rotation guidance.

**Use server-side sessions** for traditional server-rendered web apps. Store a cryptographically random
session ID in an `HttpOnly; Secure` cookie; choose `SameSite=Strict` when flows permit or `Lax` when
legitimate top-level cross-site navigation is required. `SameSite=None` requires `Secure` and explicit
CSRF defenses. Session state lives server-side and can be revoked centrally.

**Use JWTs** when self-contained, signed claims are a deliberate protocol choice and all verifiers can
enforce a consistent policy. Tradeoffs: early revocation requires additional state or short expiry,
payload claims are readable unless encrypted, and claim/key-policy drift across services is dangerous.
Choose access-token lifetime from threat model and operational needs; use refresh tokens only where the
client and authorization-server design supports them safely.

OpenID 2.0 is obsolete; do not implement it. SAML remains in use for enterprise federation but should not be chosen for new systems unless the IdP mandates it.

## JWT security

Four critical rules, in order of importance:

1. **Validate signature AND algorithm.** Explicitly specify the expected algorithm in your verifier; never allow the library to infer it from the token header. Some older libraries accepted `alg: none` as a valid "already verified" signal, letting attackers strip the signature entirely. Always reject tokens with `alg: none`. (Source: OWASP JWT Cheat Sheet — "None Hashing Algorithm" section.)

2. **Reject algorithm confusion.** Pin the accepted algorithm and key type. For HMAC, generate a
high-entropy secret with a CSPRNG sized for the algorithm (for example, at least 256 bits for HS256),
not a human password or a character-count rule. Use asymmetric signatures when separate signing and
verification trust domains are required.

3. **Bounded expiry + revocation design.** Shorter access-token lifetimes reduce replay exposure but
increase renewal load; select a documented risk-based lifetime. When issuing refresh tokens, protect
them as high-value credentials and use rotation or sender-constraining as required by the client model.
If immediate access-token revocation is a requirement, design stateful introspection/denylisting or
short lifetimes explicitly.

4. **Prefer HttpOnly cookies for browser sessions.** `localStorage` and `sessionStorage` are readable by
JavaScript, so XSS can exfiltrate bearer tokens. An `HttpOnly; Secure` cookie reduces that theft path
but requires a deliberate SameSite/CSRF design and still rides with requests during XSS. Avoid
persistent browser bearer-token storage where possible; if JavaScript must hold a token, keep it
in memory with the minimum practical lifetime and harden the application against XSS.

Minimize JWT claims. Do not place confidential data in an ordinary signed JWT because the payload is
encoded, not encrypted; use an appropriate encrypted channel/token design if claim confidentiality is
required. Treat authorization claims as server-validated inputs, not a substitute for object-level checks.

## Password storage

Passwords must be hashed with a **slow, memory-hard KDF**:

- **Argon2id** — OWASP's preferred modern choice when available; use current minimum memory/time/parallelism
  guidance and benchmark it on production-class hardware.
- **bcrypt** — widely supported but has input-length limitations; choose and periodically raise the work
  factor from measured verification latency and current OWASP guidance, not a universal fixed number.
- **scrypt** — acceptable; memory-hard.

Never use MD5, SHA-1, or SHA-256 alone for passwords — they are fast hashes designed for integrity checking, not key derivation. Never store passwords in plaintext.

Additional controls from NIST SP 800-63B-4 and the OWASP Authentication Cheat Sheet:

- Require at least 15 characters when a password is the only authentication factor; a verifier may
  permit a minimum of 8 when the password is used as part of multi-factor authentication.
- Maximum length at least 64 to support passphrases.
- Do not silently truncate passwords.
- Allow all characters including Unicode and whitespace; do not impose composition rules.
- Block commonly used, expected, and compromised passwords using a privacy-preserving blocklist check.
- Do not mandate periodic password rotation; instead, force rotation on confirmed compromise.
- Use timing-safe comparison functions when checking password hashes.

## MFA

Multi-factor authentication materially reduces credential-replay risk, but effectiveness depends on the
factor and recovery path. Phishing-resistant authenticators provide stronger protection than OTPs.

**Prefer in this order:**

1. **FIDO2 / WebAuthn (Passkeys)** — phishing-resistant; authenticates with a public-key challenge
   bound to the relying-party origin. Strongly prefer it for high-value or administrative accounts,
   and require it where the system's threat model or governing policy calls for phishing-resistant MFA.
2. **TOTP (RFC 6238)** — time-based one-time passwords via an authenticator app (e.g., TOTP RFC 6238-compliant apps). Not phishing-resistant but far better than no MFA or SMS.
3. **SMS/PSTN OTP** — vulnerable to SIM-swap, number-porting, and signaling attacks. NIST treats PSTN
   out-of-band authentication as **restricted**, not universally prohibited; use it only with a
   documented risk assessment and safer recovery/fallback controls.

Security questions and "memorable words" are weak; avoid them for high-risk operations.

Use risk-based step-up re-authentication for sensitive operations such as credential or recovery-channel
changes and high-value transactions. Recovery flows need equivalent or stronger assurance rather than
becoming an MFA bypass.

## Authorization patterns

**Deny by default.** An endpoint with no explicit grant must return 403, not 200. Every route must have an access-control decision; "forgot to add the guard" must result in a hard error in development, not silent permission in production. (Source: OWASP Authorization Cheat Sheet — "Deny by Default.")

**Server-side checks on every request.** Authorization in the UI (hiding buttons, disabling routes) is a UX nicety, not a security control. The API server must re-evaluate permissions on every call, regardless of what the client claims.

**RBAC vs ABAC/ReBAC.** Role-Based Access Control is simpler to implement and audit but can become
coarse or role-heavy. Attribute- or relationship-based policies support rules such as "user may edit
documents they own." Choose the smallest model that expresses the domain, centralize enforcement, and
test deny/default and object-level cases.

**Object-level authorization (prevent IDOR).** Every data fetch or mutation must verify that the calling
identity may operate on that specific object, not merely that it is authenticated. Opaque/UUID
identifiers reduce guessability but do not enforce authorization; validate ownership, relationship, or
policy on every lookup.

**Enforce authorization checks on static resources.** Files served from storage (S3, blob storage) need the same access controls as dynamic endpoints — pre-signed URLs with short TTLs or server-side proxy checks.

**Exit safely on failure.** An authorization failure must stop execution and return a generic 403; it must not partially execute the request or leak details about why access was denied.

**Log access-control decisions.** Log denials (user, resource, reason, timestamp) to enable anomaly detection and post-incident forensics. Do not log sensitive payload content.

## Secrets management

**Never hardcode credentials in source.** No API keys, database passwords, signing secrets, or certificates in code, configuration files committed to git, or build artifacts. This is non-negotiable. (Source: OWASP Secrets Management Cheat Sheet.)

**Development vs production:**

- Development: environment variables (`.env` files loaded at process start). The `.env` file must be in `.gitignore` and must never be committed. Use example files (`.env.example`) with placeholder values to document required variables.
- Production: a dedicated secrets manager — AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, HashiCorp Vault, or equivalent. Applications retrieve secrets at startup or via sidecar/agent injection; secrets are never baked into images or config maps in plaintext.

**Dynamic secrets where possible.** A secrets system can issue short-lived, leased credentials to a
workload and revoke/rotate them independently of application releases. Renewal, expiry, clock, and
outage behavior must be designed and tested; short leases reduce but do not eliminate theft impact.

**Never log secrets.** Structured logging pipelines often capture full HTTP request headers and bodies. API keys, Authorization headers, tokens, and passwords must be redacted before any log line is written. Audit your logging middleware. Never log secrets in error messages, stack traces, or debug output.

**Rotate on suspected exposure.** If a credential may have leaked (repository scan finding, employee
departure, incident response), rotate it immediately — do not wait for a scheduled rotation window. For
service credentials, choose the shortest practical TTL supported by renewal reliability and the threat
model; shorter lifetimes reduce the replay window but increase renewal dependencies.

**Least privilege for secrets access.** Not every service or engineer needs every secret. Apply fine-grained IAM policies so each workload can read only the secrets it needs. Audit access logs on the secrets manager.

## Secret scanning and prevention

**Pre-commit hooks.** Install a secret-scanning hook that runs before `git commit`:

- **gitleaks** — open source, fast, pattern-based; integrates as a pre-commit hook or CI step.
- **detect-secrets** — Python-based, supports custom regex patterns and a baseline file for known false positives.

**CI/CD pipeline scanning.** Run secret scanning on every pull request and merge to catch anything that slipped past the local hook.

**Never commit `.env` files with real secrets.** `.env`, `*.pem`, `*_rsa`, `credentials.json`, `serviceaccount.json`, and similar files must be in `.gitignore` globally. Commit only template files with placeholder values.

**If a secret is committed:** treat the git history as compromised. Rotate the credential immediately, then optionally clean the history with `git filter-repo`. Do not rely on history rewriting as a substitute for rotation — forks and cached clones may already have the secret.

**CI/CD secret injection.** See [[ci-cd-and-deployment]] for patterns on injecting secrets into pipelines without exposing them in logs or job definitions.

> Source: https://pages.nist.gov/800-63-4/sp800-63b.html · https://datatracker.ietf.org/doc/draft-ietf-oauth-v2-1/ · https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html · reviewed 2026-07-23
