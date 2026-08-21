---
id: wordpress-plugin-development
title: WordPress Plugin Development — Structure, Bootstrap, and Tooling
type: framework
tags: [wordpress, php, plugin, wp-admin, hooks, bootstrap, wp-cli, wp-env, phpunit, phpcs, static-analysis]
summary: How a WordPress plugin is structured, headered, and loaded — the bootstrap/hook order that matters for security, the full entry-point taxonomy, the single-option role-storage model, and the dev/test/lint tooling for exercising and auditing one.
related:
  - {slug: wordpress-plugin-auth, rel: relates-to}
  - {slug: secure-coding-and-injection, rel: see-also}
created: 2026-07-25
---

# WordPress Plugin Development — Structure, Bootstrap, and Tooling

A WordPress plugin is a directory under `wp-content/plugins/` containing at least one PHP file with a
header comment block; WordPress core parses that header, loads the file on every request (subject to the
guards described below), and the plugin registers itself into core's request lifecycle purely through
**hooks** (actions and filters) — there is no routing layer, no framework-level middleware, and no
built-in request/response object. Everything a plugin does — rendering an admin page, handling a form
submission, exposing a REST route — is "run this callback when this named hook fires."

## The plugin header block

A minimal, valid header (top of the main plugin file, inside a `/* ... */` comment):

```php
/**
 * Plugin Name: Example Plugin
 * Plugin URI:  (your plugin's homepage or repository URL)
 * Description: One-line description shown in wp-admin → Plugins.
 * Version:     1.0.0
 * Requires PHP: 7.4
 * Requires at least: 6.0
 * Author:      Example Author
 * License:     GPL v2 or later
 * Text Domain: example-plugin
 */
```

`Requires PHP` and `Requires at least` (minimum WP version) are enforced by core itself since WP 5.2/5.3 —
an incompatible plugin is blocked from activating rather than fataling at runtime. There is no build step
or manifest beyond this comment block; WordPress discovers plugins by scanning `wp-content/plugins/*.php`
(one level deep) for a file containing this header.

## Bootstrap / load order — the fact that matters most for security

The order in which WordPress core loads a request is, abbreviated to the parts a plugin author/auditor
needs:

1. **Plugin files are `require`d** (`wp-settings.php`) — top-level code in every active plugin's main file
   runs immediately, including any `add_action()`/`add_filter()` calls made at file scope (not inside a
   hook callback). Anything a plugin does *outside* a hook registration — e.g. reading `$_REQUEST` and
   emitting a `header()` redirect directly in the file body — runs on **every** request, unauthenticated,
   before any of the hooks below fire.
2. **`plugins_loaded`** fires — the first hook available to a plugin; used for cross-plugin dependency
   checks (has plugin X registered its constant/class yet).
3. **`init`** fires — the hook most plugins use to register custom post types, taxonomies, shortcodes, and
   (frequently, and dangerously) to read `$_GET`/`$_POST` and act on it directly.
4. Only **after** `init`, for an admin-area (`/wp-admin/*`) request, does `wp-admin/admin.php` call
   `auth_redirect()` — the function that actually checks for a logged-in session and redirects to
   `wp-login.php` if there isn't one.

**The consequence:** an `init`-hooked callback that lives inside a file that is otherwise only loaded for
admin-area requests is *not* protected by "this only loads in wp-admin, so the user must be logged in" —
`init` fires *before* the login check that URL space implies. A plugin's own settings-save handler that
processes `$_POST` on `init` and trusts the request purely because it targets an admin-looking URL, with no
`current_user_can()`/nonce check of its own, is unauthenticated in practice regardless of which directory
the request "looks like" it belongs to. This exact shape — an `init` handler reading `$_POST` on an
admin-looking page, with no authorization or CSRF check, writing an attacker-chosen option name — is the
root cause of a well-documented, recurring critical-severity WordPress plugin vulnerability class (see
[[wordpress-plugin-auth]] for the authorization/CSRF axes and the historical CVE pattern this maps to).

## `is_admin()` does not mean "an administrator"

`is_admin()` returns `true` whenever the *current request* is for the admin area — including
`/wp-admin/admin-ajax.php` — **regardless of whether anyone is logged in, and regardless of what role they
hold**. It is a request-context check ("does this URL belong to wp-admin"), not an authentication or
authorization check. Code gated only by `if (is_admin()) { ... }` runs for an anonymous visitor who simply
requests an admin-area URL; `is_admin()` must never be treated as a substitute for
`is_user_logged_in()`/`current_user_can()`.

## Entry-point taxonomy

Every mechanism below is a way an HTTP request (or a cron tick) reaches plugin PHP code. "Default
reachability" is what WordPress core itself enforces before the callback runs — not what a well-written
plugin should additionally add.

| Mechanism | Registration | Default reachability (core-enforced) |
|---|---|---|
| AJAX, logged-in | `add_action('wp_ajax_{action}', $cb)` | Requires *some* logged-in session — no capability implied; any authenticated role (including the lowest, e.g. Subscriber) reaches it |
| AJAX, public | `add_action('wp_ajax_nopriv_{action}', $cb)` | Fires for logged-out users only — functionally the same dispatch as above but with zero auth requirement |
| `admin-post.php`, logged-in / public | `add_action('admin_post_{action}', $cb)` / `admin_post_nopriv_{action}` | Same split as AJAX |
| REST route | `register_rest_route($ns, $route, $args)` on `rest_api_init` | **Only** what `permission_callback` returns. If omitted, core has called `_doing_it_wrong()` since 5.5.0 — a logged notice, not a block — and the route behaves as fully public either way; `__return_true` is the explicit, silent form of the same thing |
| Admin menu page | `add_menu_page()` / `add_submenu_page()` with a `$capability` argument | Gates the specific page-render callback: core only attaches the callback to its hook if `current_user_can($capability)` passes **at registration time, per request**. A user who fails the check gets a blank admin frame, not a hidden-but-reachable page — but this protects *only* that render callback, not any separate handler wired to process the page's form submission |
| `admin_init` | `add_action('admin_init', $cb)` | Fires on every `wp-admin` request (including AJAX/admin-post loads) for any logged-in user of any role — no capability gating by core at all |
| `init` reading request data | `add_action('init', $cb)` | Fires on every request, front-end and admin, logged in or not — the earliest hook most plugins reach for, and the one with zero auth/authz by default |
| Shortcode | `add_shortcode($tag, $cb)` | Reachable by whoever can view the page/post containing it — for public content, that's any unauthenticated visitor |
| `template_redirect` | `add_action('template_redirect', $cb)` | Front-end, post-query-parsing; no auth by default |
| `parse_request` + custom query vars | `add_filter('query_vars', ...)` + `add_action('parse_request', $cb)` | Public front-end "virtual endpoint" mechanism; no auth by default |
| WP-Cron | `wp_schedule_event()` + `add_action($hook, $cb)` | Indirect, but `wp-cron.php` is itself a public URL that any page load can trigger via loopback by default (unless `DISABLE_WP_CRON` is set); treat cron-hooked handlers that consume request-influenced state as in-scope |

A plugin is responsible for its own authorization/CSRF checks inside every one of these callbacks unless
the table says core already gates it — see [[wordpress-plugin-auth]] for the primitives and the
classification rubric.

## The single option that holds all role definitions

WordPress stores **every** role definition — Administrator, Editor, Author, Contributor, Subscriber, and
any custom roles — in one serialized site option, `{$wpdb->prefix}user_roles` (`wp_user_roles` on a
default single-site prefix). There is no per-role table and no per-capability row. This has an outsized
security consequence: any code path that can write an arbitrary option **name** — a settings-save handler
that iterates a prefix allow-list but never actually applies the check, for instance — is a direct
authorization-system rewrite the moment that name happens to be the roles option, not merely a generic
"arbitrary settings write." See [[wordpress-plugin-auth]] for why a plugin's own escalation guard (if it
has one) usually only covers its intended write path through the `WP_Role` API and not a direct
`update_option()` on the same underlying data.

## Local dev / test environments

Options, fastest-to-disposable first:

1. **`@wordpress/env` (`wp-env`, official, Docker-based)** — zero-config, purpose-built for a single
   plugin/theme working directory:
   ```bash
   npm -g install @wordpress/env
   cd /path/to/plugin              # or a scratch dir with .wp-env.json
   wp-env start                    # → http://localhost:8888/wp-admin (admin / password)
   wp-env run cli wp plugin activate my-plugin
   wp-env destroy                  # tears down completely, no residue
   ```
   A minimal `.wp-env.json` to mount an arbitrary plugin path: `{ "plugins": ["/path/to/plugin"] }`.
2. **LocalWP** — GUI desktop app, one-click sites with built-in WP-CLI/SSH; good for a non-CLI operator,
   harder to script/tear down reproducibly than `wp-env`.
3. **`docker compose` with the official `wordpress` image + `wp-cli`** — for cases needing more control
   than `wp-env` exposes (custom PHP version, xdebug, multisite); mount the plugin directory as a volume,
   `docker compose exec wordpress wp core install ...`, tear down with `docker compose down -v`.
4. **VVV (Varying Vagrant Vagrants)** — Vagrant/VirtualBox-based, oriented at long-lived multi-site
   core-contributor setups; heavier than needed for a single-plugin throwaway.

Treat all of these as disposable and local-only — never point one at a real domain or reuse production
credentials.

## PHPUnit integration testing

WordPress core's own test scaffolding provides `WP_UnitTestCase`, factory helpers, and a bootstrap that
spins up a full throwaway WP install + DB per test run:

```bash
wp scaffold plugin-tests my-plugin              # generates phpunit.xml.dist, tests/bootstrap.php
bin/install-wp-tests.sh wordpress_test root '' localhost latest   # installs throwaway core + test DB
phpunit
```

Testing capability gating directly — mint a low-privilege user and assert the handler rejects it:

```php
class Test_Role_Endpoint extends WP_UnitTestCase {
    public function test_subscriber_cannot_change_roles() {
        $subscriber_id = self::factory()->user->create( array( 'role' => 'subscriber' ) );
        wp_set_current_user( $subscriber_id );

        $request = new WP_REST_Request( 'POST', '/my-plugin/v1/roles' );
        $request->set_param( 'user_id', 2 );
        $request->set_param( 'role', 'administrator' );
        $response = rest_get_server()->dispatch( $request );

        $this->assertSame( 403, $response->get_status() );
    }
}
```

`wp_set_current_user($id)` swaps the "current user" for the rest of the test with no real login flow;
`self::factory()->user->create(['role' => 'subscriber'])` mints the low-privilege test user. For
AJAX/admin-post handlers instead of REST, call the registered `add_action` callback directly after
`wp_set_current_user()` and assert it either `wp_die()`s or that the side effect (e.g. a role change) did
**not** occur.

## Exercising an endpoint by hand

`wp eval` is the fastest way to mint a valid nonce for a given session context without scraping HTML for a
hidden field: `wp eval 'echo wp_create_nonce("my_action");'`. Combine with a cookie jar from
`wp-login.php` (or, simpler for scripted low-privilege testing, an **Application Password** — WP 5.6+,
HTTP Basic Auth over HTTPS for a specifically-created test user) to call `admin-ajax.php`,
`admin-post.php`, or a REST route as a given role and confirm the classification independently of reading
the source. REST cookie auth additionally requires the `wp_rest` nonce sent via the `X-WP-Nonce` header —
without it, the API treats the request as user ID `0` (unauthenticated) even if a valid session cookie is
present.

## Static analysis tooling

| Tool | What it catches | Coverage gap |
|---|---|---|
| **PHPCS + WordPress-Coding-Standards** | `WordPress.Security.NonceVerification.*` — flags superglobal access (`$_POST`/`$_GET`/`$_REQUEST`) with no preceding nonce check in scope; `WordPress.Security.ValidatedSanitizedInput` — unsanitized/unvalidated superglobal use | No equivalent sniff for a *missing capability check* — CSRF presence is checked, authorization presence is not |
| **PHPStan + `szepeviktor/phpstan-wordpress`** (or Psalm) | Type-correctness across WP core APIs; can surface a capability-check return value that is computed but never branched on, at a strict enough level | General type-safety net, not an authz/CSRF-specific rule |
| **Semgrep with WordPress-focused rule packs** | Custom rules can directly pattern-match "AJAX/REST callback body lacking a `current_user_can()`/`check_ajax_referer()` call" | Most flexible option for exactly this gap, but no such rule ships universally out of the box — it has to be authored |

**Practical implication:** PHPCS's nonce sniff is the closest thing to an automated CSRF-axis check and is
worth running as a first pass, but the authorization axis has no equivalent off-the-shelf static check —
that gap is exactly why a manual/semantic review of every entry point (see [[wordpress-plugin-auth]]) is
needed rather than relying on lint output alone.

> Source: https://developer.wordpress.org/plugins/ · https://developer.wordpress.org/plugins/javascript/ajax/ · https://developer.wordpress.org/reference/functions/register_rest_route/ · https://developer.wordpress.org/reference/functions/add_menu_page/ · https://developer.wordpress.org/block-editor/getting-started/devenv/get-started-with-wp-env/ · https://make.wordpress.org/cli/handbook/how-to/plugin-unit-tests/ · https://make.wordpress.org/core/handbook/testing/automated-testing/phpcs/ · promoted by docs (curate) · 2026-07-25
