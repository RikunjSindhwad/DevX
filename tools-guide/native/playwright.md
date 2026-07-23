# Playwright (browser automation) — generate-a-script workflow

Browser automation for **UI verification and debugging** — and any other real-browser task (DOM/text
extraction, console + network capture, form flows, auth'd journeys, responsive checks, screenshots, PDF,
tracing). DevX does **not** wrap this in a `devx` subcommand: the agent **writes a small Playwright-Python
script (raw `sync_api` — simplest for one-off automation; not the pytest test plugin), runs it under the
operator-provisioned DevX helper runtime, reads the structured result, and cleans up**. Scripts are saved for reuse; transient artifacts
are deleted after they're analyzed.

This is the official Microsoft library (`playwright` on PyPI) driven via Python. The operator owns
`.devx/.venv`; role agents only consume it. No Node, no MCP.

## 1. Runtime preflight (operator-owned)
Check the managed runtime before browser work:
```bash
.devx/.venv/bin/python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); b.close(); p.stop()" 2>/dev/null
```
If the interpreter/import/browser is missing, the browser agent returns `SETUP_REQUIRED` through its
handoff. It must not create or modify `.devx/.venv`, install packages, download Chromium, or use an
ephemeral `uv run --with` fallback. `/devx:devx-init` offers the operator the persistent setup after
confirmation.

Run a saved script: `.devx/.venv/bin/python .devx/browser/scripts/<name>.py [args]`.

Use `chromium.launch(headless=True)` by default. `--no-sandbox` disables a browser security boundary:
use it only in an explicitly trusted, isolated environment where Chromium's sandbox cannot run. For
untrusted pages or crawling, prefer a separate non-root user plus an appropriate container seccomp
profile rather than disabling the sandbox.

## 2. Reuse before you generate (the next agent looks here first)
Reusable scripts live in **`.devx/browser/scripts/*.py`** (committed — durable project assets). **Before
writing a new one, look for an existing one** and reuse/adapt it:
```bash
ls .devx/browser/scripts/ 2>/dev/null
rg -l "<what you need>" .devx/browser/scripts/ 2>/dev/null
```
When you do write one:
- **Parameterize** it (URL / selectors / output path via `sys.argv` or env) so it's reusable, not one-off.
- Start it with a **header comment**: purpose · usage (`python x.py <args>`, required env) · created date.
- Give it a **descriptive filename** (`login-flow-smoke.py`, `capture-console-errors.py`) so a later agent
  finds it by name.

## 3. Output convention
A script prints **one JSON object to stdout** (so the agent parses a result, not log scraping) and writes
any **artifacts to `.devx/cache/browser/`** (git-ignored). Typical fields: `http_status`, `title`,
`final_url`, `console_errors`, `page_errors`, `failed_requests`, extracted data, and artifact paths.

## 4. Storage hygiene — two tiers of screenshot
Screenshots come in **two distinct tiers**; don't conflate them:

- **Transient (cache).** Debugging shots, traces, videos, PDFs, downloads — write to `.devx/cache/browser/`
  (git-ignored) and **delete once analyzed** so storage doesn't grow unbounded:
  ```bash
  rm .devx/cache/browser/<file>          # remove the specific artifact(s) after reading them
  ```
- **Gallery (committed visual record).** ONE sanitized screenshot per meaningful non-sensitive view/state, saved to
  `./.devx/ui-gallery/{phase}/{view}-{state}.png` with a `gallery.md` index — the durable **visual
  acceptance record**. It is committed only after deliberate sensitivity review (see `agents/ui/browser.md` for the per-view
  coverage matrix: first screen, primary workflows, empty/error/busy, long lists, details, settings,
  translated/hardware states).

**Keep the script** (reusable asset) and only sanitized gallery images; **drop the cache artifacts**.
Never commit cache artifacts (the `.devx/cache/` path is already git-ignored — don't relocate artifacts out
of it); do commit the gallery.

## 5. Security (matches agent-guide §9)
- **Credentials come from the environment**, never inline — saved scripts are **committed**, so a hardcoded
  password/token would leak. Use `os.environ["APP_USER"]` / `os.environ["APP_PASS"]`; document the required
  env vars in the header comment. Take them from the shell env, never write them into the script or a log.
- Authentication state files contain live cookies and headers. Store them only under the git-ignored
  cache, restrict access, and delete them immediately after the run.
- Screenshots, traces, video, PDFs, console logs, and network payloads can expose sensitive data.
  Authenticated artifacts stay transient unless a reviewer explicitly redacts and approves a gallery
  image. Never put auth state, secrets, customer data, or private payloads in the gallery.

## 6. Capability recipes (it's not just screenshots)
Headless launch + structured capture (the UI-debug staple):
```python
import json, os, sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
out = {"url": url, "console_errors": [], "page_errors": [], "failed_requests": []}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.on("console", lambda m: m.type in ("error","warning") and out["console_errors"].append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: out["page_errors"].append(str(e)[:200]))
    pg.on("requestfailed", lambda r: out["failed_requests"].append(f"{r.method} {r.url[:80]}"))
    resp = pg.goto(url, wait_until="domcontentloaded", timeout=30000)
    out["http_status"] = resp.status if resp else None
    out["title"] = pg.title()
    out["aria"] = pg.locator("body").aria_snapshot()        # structured DOM/role tree (great for an LLM)
    pg.screenshot(path=".devx/cache/browser/shot.png")      # transient — delete after analysis
    b.close()
print(json.dumps(out))
```
Other features to reach for (use **semantic locators** — see §7):
- **Interact / flows:** `pg.get_by_role("button", name="Save").click()`, `pg.get_by_label("Email").fill(v)`;
  for navigation, click then `pg.wait_for_url("**/next")`.
- **Extract:** `pg.get_by_role("heading").inner_text()`, `pg.locator("body").aria_snapshot()`, `pg.content()`.
- **Auth (env creds):** fill `os.environ["APP_USER"]`/`["APP_PASS"]`, submit, then **save state once** —
  `context.storage_state(path=".devx/cache/browser/auth.json")` — and reuse via
  `browser.new_context(storage_state=".devx/cache/browser/auth.json")`. State holds live cookies → keep it in
  the git-ignored cache only, never commit.
- **Network:** mock with `pg.route("**/api/x", lambda r: r.fulfill(json={...}))`; wait for a real call with
  `pg.expect_response(lambda r: "/api/x" in r.url and r.ok)`.
- **Responsive / device:** `b.new_context(**p.devices["iPhone 13"])` or `viewport={"width":390,"height":844}`.
- **Element shot:** `pg.get_by_role("dialog").screenshot(path=".devx/cache/browser/el.png")`.
- **Heavy (use sparingly, always clean up):** tracing (§8), `pg.pdf(...)`, video.

## 7. Reliability — write scripts that don't flake
Locators auto-wait and re-resolve the DOM before each action, so prefer them over raw selectors and never
pre-sleep. This is the difference between a reliable script and a flaky one.
- **Locator ladder** (most → least preferred): `get_by_role(role, name=…)` → `get_by_label` /
  `get_by_placeholder` → `get_by_text` / `get_by_alt_text` → `get_by_test_id` → `locator("css=…"|"xpath=…")`
  **only** when no semantic handle exists. Don't grab CSS/XPath just because it's the first thing you see.
- **Assert, don't sleep.** Use auto-retrying web-first assertions — `expect(loc).to_be_visible()`,
  `expect(page).to_have_url(re.compile(…))`, `expect(loc).to_have_text(…)` — never `time.sleep()` /
  `wait_for_timeout`. Wait for a *condition*: `pg.wait_for_url("**/x")` for navigation, `pg.expect_response(pred)`
  for a backend call.
- **One element per action.** A locator matching multiple elements failing is a *signal* — narrow it with
  `name=` / `.filter(has_text=…)`, not `.first`. Use `.first` / `.nth()` only when order is the requirement.
- **iframes →** `pg.frame_locator("iframe[title='…']").get_by_role(…)` (plain page locators won't reach inside).
  **Multiple users →** a separate `browser.new_context()` each. **`force=True`** only with a written reason
  (fix the locator/overlay/state first).

## 8. Gotchas
- First `playwright install` downloads a browser (~120 MiB) — slow once, cached after.
- Use `headless=True` for automated runs. Add `--no-sandbox` only for a trusted isolated runtime where
  Chromium cannot otherwise launch; document that exception.
- Set explicit `timeout=`/`wait_until=` on `goto`; live sites are flaky (a real run here saw an intermittent
  HTTP 500), so capture `http_status` and degrade gracefully rather than assuming success.
- **Hard debug:** record a trace — `context.tracing.start(screenshots=True, snapshots=True, sources=True)` …
  `context.tracing.stop(path=".devx/cache/browser/trace.zip")`, view with `playwright show-trace <zip>`, then
  delete it. Best artifact for a stubborn failure (actions + DOM snapshots + console + network).
- **Deeper lookups:** official Playwright Python docs — `https://playwright.dev/python/docs` (locators,
  test-assertions, network, auth, trace-viewer, emulation).

## Desktop GUI — when Playwright doesn't apply

Playwright drives **web** UIs only. For a **desktop** app (Qt/PySide6, Electron, Tkinter, wxPython), use the
offscreen-screenshot recipe in `agents/ui/browser.md` (Desktop GUI path) — `QT_QPA_PLATFORM=offscreen` +
`window.grab()` for Qt, `xvfb-run` + a test entry point for others. Same output convention (JSON to stdout,
PNG artifacts to `.devx/cache/browser/`, clean up after analysis).
