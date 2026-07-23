---
id: secure-coding-and-injection
title: Secure Coding Against Injection and Input-Based Attacks
type: security
tags: [security, injection, sql-injection, command-injection, ssrf, path-traversal, deserialization, input-validation, xss, output-encoding]
summary: How to prevent injection attacks (SQL, command, template, SSRF, path traversal, deserialization) — the mechanisms behind each defence, not just a checklist.
related:
  - {slug: owasp-top-10-quickref, rel: relates-to}
  - {slug: auth-and-secrets, rel: relates-to}
created: 2026-06-21
---

# Secure Coding Against Injection and Input-Based Attacks

Injection vulnerabilities share a root cause: user-controlled data is interpreted as code or instructions by an interpreter (database, shell, template engine, HTTP client, filesystem). Prevention is not about filtering dangerous characters — it is about structurally separating data from code so that the interpreter never treats input as instructions, regardless of what the input contains. This entry explains the mechanism behind each defence; see [[owasp-top-10-quickref]] for the fast-scan checklist.

## Input Validation and Allowlisting

Validate at the trust boundary — the moment data enters your system from any untrusted source (HTTP request, file upload, queue message, webhook). The correct posture is **allowlisting** (reject everything not explicitly permitted) rather than denylisting (trying to strip known-bad characters).

- Define the expected format precisely: type, length, character set, range.
- Reject or return an error on anything that does not match — do not silently strip and continue, because the downstream consumer may still misparse the stripped value.
- Allowlisting alone is not sufficient for SQL or command contexts; it is a second layer, not a substitute for parameterization.
- For complex free-text fields where allowlisting is impractical, rely on parameterization plus output encoding — not on attempting to sanitize the input.

Source: OWASP Injection Prevention Cheat Sheet — "Allow-List Input Validation" section.

## SQL Injection

**Root cause**: user input is string-concatenated into a SQL statement, allowing an attacker to alter the query's structure.

**Primary defence — parameterized queries (prepared statements)**: The SQL template is sent to the database engine first; parameters are bound separately. The engine therefore always distinguishes code from data, regardless of what the parameter contains. An attacker who injects `' OR '1'='1` into a bound parameter will have that entire string matched literally against the column value — the query structure cannot change.

```sql
-- WRONG: string concatenation
SELECT balance FROM accounts WHERE user = '" + userInput + "'

-- RIGHT: parameterized (JDBC syntax)
SELECT balance FROM accounts WHERE user = ?
-- then: pstmt.setString(1, userInput)
```

**ORMs help but do not fully protect**: ORMs like Hibernate (HQL), SQLAlchemy, and ActiveRecord use parameterization by default, but every ORM exposes a raw/native query escape hatch. Those raw calls are just as vulnerable as hand-written JDBC. Treat any `session.execute(raw_sql)`, `.raw()`, or `.from_statement()` call as a finding that requires review.

**Stored procedures**: Safe when they are implemented without internal dynamic SQL generation. They are NOT automatically safe — a stored procedure that calls `EXEC(@dynamic_sql)` or `sp_executesql` with concatenated input is still injectable. Additionally, stored procedures often require elevated DB roles (`EXECUTE` permission), so a breach may give the attacker more database access than a least-privilege read/write account would have.

**Allow-list for dynamic identifiers**: Table names, column names, and sort directions cannot be parameterized. If user input must influence these, map the input to a hardcoded safe value via a switch/enum — never pass user input directly into the identifier position even after escaping.

Source: OWASP SQL Injection Prevention Cheat Sheet (https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html).

## Command Injection

**Root cause**: user input reaches a shell interpreter that evaluates metacharacters (`;`, `|`, `&&`, backticks, `$()`) as control flow, allowing arbitrary command execution.

**Primary defence — avoid OS commands entirely**: Use language-native library functions. `os.makedirs()` instead of `system("mkdir ...")`. `shutil.copy()` instead of `subprocess("cp ...")`. Library functions cannot be hijacked via shell metacharacters because they never invoke a shell.

**When a subprocess call is unavoidable — pass an argv array, never a shell string**:

```python
# WRONG — shell=True with any interpolated input
subprocess.run(f"convert {user_file} output.png", shell=True)

# RIGHT — argv list, no shell
subprocess.run(["convert", user_file, "output.png"])
```

In Java, `ProcessBuilder` with arguments as separate list elements is safe; `Runtime.exec(String)` that concatenates a command string is not (though Java does not invoke `/bin/sh`, metacharacters become literal arguments rather than shell operators — the real risk is argument injection into the target command's own option parser).

**Allowlist the command and arguments**: If user input must select which command to run, map allowed values to hardcoded command strings. If user input supplies arguments, validate against a strict allowlist regex (e.g., `^[a-z0-9]{3,10}$`) and reject anything containing shell metacharacters: `| ; $ \` ! ( )`.

**Argument injection** is a sub-class: even if the command itself is fixed, user-controlled arguments can invoke flags that change the command's behavior (e.g., `curl --output /etc/crontab`). Use `--` as an argument terminator where the command supports it (POSIX Guideline 10): `curl -- $url` causes any leading `-` in `$url` to be treated as an operand, not an option.

Source: OWASP OS Command Injection Defense Cheat Sheet (https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html).

## Template and Expression Injection

**Root cause**: user-controlled data is rendered by a template engine (Jinja2, Twig, Freemarker, Pebble, Velocity) or expression evaluator (OGNL, SpEL, EL) without escaping, allowing the engine to evaluate the input as template syntax.

**Primary defence — auto-escaping on by default**: Modern template engines (Jinja2 with `autoescape=True`, Django templates, Rails ERB) HTML-escape output automatically. Never disable this globally.

**Treat every "safe" bypass as a security review gate**: Functions like `| safe` (Jinja2), `mark_safe()` (Django), `raw` (Twig), `SafeHtmlString` (.NET) bypass escaping. Each use must be code-reviewed and justified — user-controlled data must never flow into these calls.

**Server-side template injection (SSTI)** is the critical case: if user input is passed as the *template string itself* (e.g., `Template(user_input).render()`), arbitrary code execution is typically achievable. Never compile user input as a template. Render user input as *data into* a fixed template.

**Expression language injection**: Java EE EL, Spring SpEL, and OGNL (Struts) have been the source of numerous critical RCEs. Never evaluate user-controlled strings as expressions. Use the framework's built-in variable binding rather than dynamic expression construction.

## Server-Side Request Forgery (SSRF)

**Root cause**: the application fetches a URL or makes a network request to a destination controlled (fully or partially) by the user, allowing an attacker to pivot to internal services, cloud metadata endpoints (e.g., `http://169.254.169.254/`), or other infrastructure not intended to be reachable from the internet.

**Primary defence — allowlist, not denylist**: Denylisting private IP ranges is bypassable through encoding tricks (octal IP notation, IPv6 forms, DNS rebinding, redirect chains). The robust defence is to define an explicit allowlist of permitted destination hosts/IPs and reject everything else.

**Two OWASP-defined cases**:

1. **Known internal targets** (application proxies to a fixed set of internal services): Build a strict allowlist of expected IP addresses and domain names. Validate the parsed IP/domain against the allowlist before issuing the request. Use a library for IP parsing (e.g., Apache Commons `InetAddressValidator` in Java, `IPAddress.TryParse` in .NET) to prevent bypass via hex/octal encoding.

2. **Arbitrary external destinations** (webhook receivers, URL-fetch features): No allowlist is feasible. Apply network-layer controls — run the outbound HTTP client from a dedicated egress proxy or network segment that blocks RFC 1918 ranges, loopback, link-local (`169.254.0.0/16`), and the cloud metadata endpoint. On AWS, enforce IMDSv2 (token-based) to raise the bar for metadata theft even if SSRF occurs.

**Additional controls**:
- Disable automatic HTTP redirect following in your HTTP client, or re-validate the destination after each redirect.
- Reject URLs with non-HTTP(S) schemes (`file://`, `gopher://`, `dict://`, `ftp://`) at the application layer.
- Do not return raw response bodies from internal services to external users — this limits exfiltration even if SSRF occurs.

Source: OWASP SSRF Prevention Cheat Sheet (https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).

## Path Traversal

**Root cause**: user input containing `../` sequences (or URL/unicode-encoded equivalents) is joined to a base filesystem path, allowing an attacker to escape the intended directory and read or write arbitrary files.

**Primary defence — canonicalize, then perform a component-aware containment check**:

```python
from pathlib import Path

BASE_DIR = Path("/var/app/uploads").resolve()

def safe_path(user_filename: str) -> Path:
    resolved = (BASE_DIR / user_filename).resolve()
    try:
        resolved.relative_to(BASE_DIR)
    except ValueError:
        raise ValueError("Path traversal detected")
    return resolved
```

`Path.relative_to` compares path components, avoiding string-prefix mistakes such as treating
`/var/app/uploads-evil` as a child of `/var/app/uploads`. Other languages should use their
component-aware path/containment API after canonicalization, not a raw string prefix.

**Canonicalization is not enough in attacker-writable trees.** A symlink can change after validation
(TOCTOU). For hostile upload directories, open relative to a trusted directory descriptor/handle with
no-follow semantics where the platform supports it, reject symlink components, and apply least-privilege
filesystem permissions.

**Never join user input to filesystem paths naively**: decode once at the trust boundary, validate the
expected filename/path grammar, canonicalize, then check containment.

**Allowlist filenames where possible**: if the expected inputs are a known set (e.g., report templates, asset names), maintain a server-side list and reject any filename not in it, bypassing the path logic entirely.

## Insecure Deserialization

**Root cause**: deserializing untrusted data with a rich-object format (Python `pickle`, PHP `unserialize`, Java native serialization, Ruby `Marshal`, PyYAML `yaml.load`) allows an attacker to supply a crafted byte stream that triggers arbitrary code execution during the deserialization process itself — before any application logic validates the object.

**Primary defence — never deserialize untrusted data into rich objects**: The only safe approach is to not use these formats for untrusted data. There is no reliable way to sanitize a pickle or Java serialized stream; the attack surface is in the deserializer itself.

**Prefer JSON with schema validation**:
- Standard JSON has no object-construction tags, which gives it a smaller default attack surface than
  native object serialization. Custom revivers/decoders, unsafe extensions, and downstream object
  binding can still execute behavior or enable mass assignment.
- Validate the parsed JSON against a strict schema (jsonschema, Pydantic, Zod) to enforce expected shape, types, and value ranges.
- This guards against mass-assignment and unexpected field injection as well as injection via nested values.

**If rich deserialization cannot be avoided**:
- Java: use a `SerialKiller`-style deserialization filter (JEP 290 / `ObjectInputFilter`) to allowlist permitted classes; reject any class not on the list.
- YAML: for untrusted input, use `yaml.safe_load()` (PyYAML) or explicitly select `SafeLoader`, then
  validate the resulting data shape and resource limits.
- Do not call a general-purpose `yaml.load` on untrusted data. Loader defaults and behavior vary by
  library/version; choose the safe loader explicitly.

**Cryptographic signing is not a substitute**: signing a serialized blob prevents tampering, but if the signing key is compromised or the verification is skipped on a code path, the attack is still possible. Prefer safe formats over signed unsafe ones.

## Output Encoding

Output encoding is the complementary defence to input validation — it ensures that data passed to an interpreter is never mistaken for code by that interpreter. The encoding must match the context.

| Output context | Required encoding | Examples |
|---|---|---|
| HTML body / attributes | HTML entity encoding | `&lt;` for `<`, `&amp;` for `&` |
| HTML attribute (unquoted) | Do not use unquoted attributes | n/a — always quote |
| JavaScript string literal | Framework/JSON serializer with script-safe escaping | `\u003C` for `<` where required |
| URL query parameter | Percent-encoding | `%3C` for `<` |
| CSS property value | CSS hex escaping | rarely user-controlled |
| Shell argument | Not applicable — use argv arrays | see Command Injection |

**Framework auto-escaping handles most cases** for HTML (see Template Injection section above). The residual risk is **JavaScript contexts**: interpolating server data directly into a `<script>` block or an event handler attribute requires JavaScript-specific escaping even when HTML auto-escaping is enabled, because the HTML parser defers to the JS parser inside `<script>` tags.

**Defense-in-depth**: Output encoding is not a primary injection defence for SQL or commands — use parameterization there. For HTML/XSS, output encoding is the primary structural defence, and Content Security Policy (CSP) is the defense-in-depth layer that limits impact if encoding is missed.

> Source: https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html · https://owasp.org/www-community/attacks/Path_Traversal · reviewed 2026-07-23
