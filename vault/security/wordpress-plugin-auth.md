---
id: wordpress-plugin-auth
title: WordPress Plugin Authentication, Authorization, and CSRF
type: security
tags: [wordpress, php, authentication, authorization, csrf, nonces, capabilities, roles, privilege-escalation, multisite]
summary: The three orthogonal axes for classifying a WordPress plugin's request handlers (authentication, authorization, CSRF), the two classic mistakes behind most WP plugin CVEs, the role/capability model, multisite super-admin passthrough, and why nonces and auth cookies are only partly offline-forgeable.
related:
  - {slug: wordpress-plugin-development, rel: relates-to}
  - {slug: auth-and-secrets, rel: relates-to}
  - {slug: owasp-top-10-quickref, rel: see-also}
  - {slug: secure-coding-and-injection, rel: see-also}
created: 2026-07-25
---

# WordPress Plugin Authentication, Authorization, and CSRF

WordPress plugin security review requires separating three questions that are easy to conflate because a
single wrong assumption about any one of them is the root cause of most disclosed WordPress plugin
vulnerabilities: **is the requester logged in at all** (authentication), **is this specific requester
allowed to do this specific thing** (authorization), and **did this request actually originate from a page
WordPress rendered to this user** (CSRF protection). A handler can pass one or two of these and still be
exploitable — reviewing "is there a check" is not enough; the check has to be the *right* one for the
threat being defended against.

## Three orthogonal questions, not one

| Primitive | Question it answers | Authorization? | CSRF protection? |
|---|---|---|---|
| `is_user_logged_in()` | Is there a valid session? | No — pure authentication | No |
| `current_user_can($cap[, $object_id])` | Is this user allowed to do X (optionally to object Y)? | **Yes** | No |
| `wp_verify_nonce($nonce, $action)` / `check_admin_referer()` / `check_ajax_referer()` | Did this request originate from a page WordPress itself rendered to this same user within the token lifetime? | No | **Yes — this is CSRF protection only** |

WordPress's own security handbook states this directly and should be treated as authoritative, not a
paraphrase:

> "Nonces should never be relied on for authentication, authorization, or access control. Protect your
> functions using `current_user_can()`, and always assume nonces can be compromised."

A nonce answers "is this the same browser/session that was just shown this form," nothing about *who* that
session belongs to or what they're allowed to do. A logged-out visitor and every logged-in Subscriber can
independently obtain a valid nonce for any action whose token is emitted on a page they can view — nonces
are not secret to the requester, only to a cross-site attacker who can't read the page that embeds them.

## The two classic, opposite mistakes

These two shapes account for the large majority of WordPress plugin privilege-escalation and CSRF
advisories, and they are mirror images of each other:

1. **Nonce-as-access-control (the critical one).** A handler calls `check_ajax_referer()` /
   `check_admin_referer()`, sees it pass, and proceeds to mutate state with **no** `current_user_can()`
   check. Since the nonce check only proves same-origin/same-session, not identity or permission, *any*
   authenticated role that can obtain the nonce — including the lowest-privileged role on the site — can
   invoke the action. When a single nonce action string is reused across several handlers, one leaked or
   guessable token compromises all of them at once. Grep signature: a callback body that calls
   `wp_verify_nonce()`/`check_ajax_referer()`/`check_admin_referer()` and then reaches a write (an
   `update_option`/`add_cap`/`update_user_meta`/DB write) with no `current_user_can()` (or equivalent
   capability check) anywhere in the same call chain.
2. **Capability check with no nonce (CSRF).** A handler correctly calls
   `current_user_can('some_admin_capability')` but has no nonce check at all. An attacker cannot bypass the
   capability requirement directly, but can forge a cross-site request (an auto-submitting form or image tag
   on an attacker-controlled page) that rides the **victim's own authenticated cookies** to the handler's
   URL. The server sees a fully authorized request from that victim — because it genuinely is one, just not
   one the victim intended — and executes it. This is the documented shape behind multiple real-world
   "CSRF leading to privilege escalation" advisories in role/capability-management plugins: a role-writing
   function had a correct capability check but missing or broken nonce validation. Grep signature: a
   callback that calls `current_user_can()` and reaches a state-changing sink with no
   `wp_verify_nonce()`/`check_ajax_referer()`/`check_admin_referer()` anywhere in the same call chain.

**The correct pattern requires both, checked independently**, on the specific action being performed —
`current_user_can()` for authorization *and* a nonce check scoped to that action, not a generic page-load
nonce reused across unrelated writes. A third historically recurring variant worth flagging separately: a
handler checks a **meta** capability (e.g. "can edit this user") against an object ID that defaults to or
is trivially set to the *requester's own* ID, when the intended semantics were "can edit *other* users." A
meta-cap check for editing your own profile/object always passes, so this degrades to "any authenticated
user can perform the action against themselves" — which is a full compromise when the "object" being
edited is the user's own role assignment.

## The review checklist, per entry point

Classify every discovered handler on three orthogonal axes, then derive the weakest privilege that can
successfully complete a round-trip:

- **Auth level** — `unauthenticated` (reachable with zero session) / `authenticated-any-role` (needs
  login, no specific capability enforced in-path) / `authenticated-capability` (needs login **and** a
  specific capability check that passes).
- **Authorization capability** — the exact capability string checked, or "none"; note whether it's a
  primitive or meta capability and, if meta, what object ID it's checked against (flag if that ID is
  attacker-controlled and can trivially equal the requester's own ID for an operation meant to affect
  *other* objects).
- **CSRF protection** — `nonce-verified` (checked and the result actually gates execution) /
  `nonce-present-not-enforced` (checked but the boolean result is discarded — functionally identical to no
  check at all) / `no-nonce`.
- **Sink** — what the handler ultimately writes, and the lowest privilege level that reaches that write.

Record one row per entry point: mechanism, auth level, authorization capability, CSRF status, lowest
privilege that reaches it, and the sink. See [[wordpress-plugin-development]] for the entry-point taxonomy
this rubric applies to (AJAX, admin-post, REST, admin-menu pages, `init`/`admin_init`, shortcodes, cron).

## The capability model

- **Roles** (Administrator, Editor, Author, Contributor, Subscriber, plus Super Admin at the network
  level) are named bundles of **capabilities**.
- **Primitive capabilities** (`edit_posts`, `manage_options`, `edit_users`, `list_users`,
  `promote_users`, `delete_users`) are checked directly against the user's/role's capability array.
- **Meta capabilities** (`edit_post`, `edit_user`, `delete_post`, etc.) are not stored on roles; they are
  resolved at check-time by `map_meta_cap()`, which maps a meta capability + object ID to the primitive
  capability(ies) actually required (e.g. `edit_post` for a given post resolves to `edit_posts` if the
  user owns it, or `edit_others_posts` if they don't). `current_user_can()` is meta-cap aware and delegates
  to this resolution internally.
- **Admin-equivalent capabilities** — a single-site Administrator by default holds all of these; any
  endpoint gated only by one of them should be treated as equivalent to full site compromise:
  - `manage_options` — arbitrary settings/options write; combined with an unvalidated option **name**
    parameter, this becomes a privilege-escalation primitive in its own right (a write target of
    `default_role`, or of whatever option a plugin uses as its authorization source of truth, is a direct
    path to elevated access).
  - `edit_users` — edit **other** users' profiles/roles (distinct from the meta capability `edit_user`,
    which resolves per-object and can be satisfied against the requester's **own** account).
  - `promote_users` — change a user's role; the single most load-bearing capability for any role/capability
    management feature. Gating a "change user role" endpoint with anything weaker than `promote_users` (or
    `edit_users` plus an explicit check that the target isn't already more privileged) is a direct
    privilege-escalation path.
  - `list_users` — enumerate all site users (information-disclosure primitive, often chained with the
    above).
  - `create_users` / `delete_users` — full account lifecycle control.
- Any endpoint that can write one of the following is equivalent to "grants attacker
  Administrator/Super Admin," regardless of what capability nominally gates it, because the write target
  *is* the authorization system: assigning/removing a role or capability for any user; writing the
  underlying roles storage directly; writing `default_role` (new self-registrations get an elevated role
  by default) or toggling self-registration alongside it; creating a user with an attacker-chosen role; or
  importing/restoring a serialized roles/capabilities snapshot (see the deserialization note below).

## Multisite: super admin bypasses every check

`is_super_admin()` is true only for network Super Admins — the multisite analogue of "god mode,"
independent of any single site's Administrator role. **`current_user_can()` returns `true` for a Super
Admin regardless of the capability being checked, unless the check is specifically and explicitly denied.**
The practical consequence: an idiom like `$capability = (is_multisite() && is_super_admin()) ? 'read'
: 'some_admin_cap';` used to select which capability a menu/handler checks does **not** widen access, even
though `'read'` is a capability every Subscriber holds — a Super Admin already passes every
`current_user_can()` check regardless of which string is passed, so the ternary changes nothing for that
user, and a non-Super-Admin never receives the weaker branch. It is dead defensive code, not a
vulnerability — but it is a real, recorded refactoring hazard: drop the `is_super_admin()` conjunct from
that ternary and it becomes a genuine access-control hole. Treat any occurrence of this pattern as worth a
second look during review, not an automatic pass.

Separately, `manage_network_options` / `manage_network_users` are the network-level analogues of
`manage_options`/`edit_users`, scoped to Network Admin screens rather than a single site. A plugin that
performs network-wide role/capability management should be checked for whether its network-scope code
paths verify `manage_network_users`/`is_super_admin()`, or whether they only check a per-site capability —
the latter would let a single-site Administrator (who is not a Super Admin) affect sibling sites in the
network, a cross-site privilege-escalation bug specific to multisite plugins.

## Nonces and auth cookies derive from wp-config salts — but forgery isn't purely offline

WordPress nonces are `wp_hash()`-derived from the site's `NONCE_KEY`/`NONCE_SALT` secrets (defined in
`wp-config.php`), bound to `(action, user ID, session token, time window)`. The logged-in authentication
cookie is derived similarly from `AUTH_KEY`/`AUTH_SALT` and `LOGGED_IN_KEY`/`LOGGED_IN_SALT`. This has a
precise, two-part consequence that should not be collapsed into one blanket statement:

- **If these salts are disclosed** (e.g. via a separate file-read/SSRF/config-leak vulnerability elsewhere
  in the stack), nonce forgery for a chosen action/user becomes computable without any further access to
  the target system — every "the CSRF layer protects this" classification in a review should be understood
  to rest on the premise that the salts are secret.
- **Auth-cookie forgery is a sharper but *not* purely offline attack**, because the logged-in cookie is
  additionally bound to a session token that WordPress stores server-side in the target user's
  `session_tokens` user meta (added in WP 4.0's session-management rework) — an attacker needs that
  DB-resident value as well as the salts, not just the salts alone. Do not state "salt disclosure = full
  auth-cookie forgery" without that qualifier; do state "salt disclosure = the CSRF layer becomes
  forgeable outright" — those are different claims with different evidence requirements, and only the
  first is a pure function of the salts.

This is why the two classic mistakes above matter in that specific order: a nonce-only handler is
compromised the moment *any* authenticated session can obtain the token (no salt disclosure required —
just a leak of the token itself, e.g. via another plugin, an XSS, or a page that renders it), while a
capability-only handler additionally requires forging a request that rides an already-privileged victim's
session — a strictly higher bar. Reviews should record which premise ("salts assumed secret", "token
assumed secret to non-viewers of the page") each "admin-only" classification actually rests on.

## Deserialization in import/restore/update paths

Backup/restore and settings-import features that call PHP's native `unserialize()` (or WordPress's
`maybe_unserialize()`, which internally calls `unserialize()` for any string matching PHP's serialization
format) on attacker-influenced or remotely-sourced data — an uploaded file, a POST field, an option value
round-tripped through export/import, or a remote update-server response — are a recurring PHP Object
Injection surface in exactly this plugin category (backup/migration and importer plugins have repeated,
disclosed instances of this shape). If any class loaded during that request tree defines a magic method
(`__wakeup`, `__destruct`, `__toString`), a crafted serialized payload can trigger a POP-chain gadget for
arbitrary file write/delete or code execution. The fix pattern in every patched instance is uniform: switch
the format to JSON, or pass `['allowed_classes' => false]` as `unserialize()`'s second argument. See
[[secure-coding-and-injection]] for the general insecure-deserialization treatment this instantiates.

## Discovery mechanics: four traps that hide real findings

Conceptual understanding is not enough — each of these caused a live vulnerability to be missed or
misjudged during an actual plugin audit. All are cheap to check and all generalise.

### Hook names are often built dynamically, so a literal grep finds nothing

A registry-style plugin registers handlers like this:

```php
$prefix = $custom ? "ASP_" : "wp_ajax_";
if ($priv)   add_action($prefix . $action,             [$handler, 'handle']);
if ($nopriv) add_action($prefix . 'nopriv_' . $action, [$handler, 'handle']);
```

`grep wp_ajax_nopriv_` over the whole tree returns **zero hits** — yet unauthenticated routes exist.
An audit pass concluded from that zero that the plugin had no public AJAX surface. It had three.

**Rule:** if a search returns zero for a pattern the plugin's behaviour *requires* (a front-end search
feature must be reachable logged-out), the search is broken, not the finding absent. Grep the
registration **mechanism** (`add_action(`, a registry array, a factory) and the **callback**, never the
literal hook name. The authoritative route table is usually one config array in one class.

### `wp_magic_quotes()` is not a mitigation on any path that decodes again

Core runs `addslashes()` over `$_GET`/`$_POST`/`$_COOKIE`/`$_REQUEST`, which is often cited to dismiss
an injection. That only holds if nothing downstream decodes.

`parse_str()` **URL-decodes its input**, and plugins routinely do `parse_str($_POST['blob'], $settings)`.
Send `%255C`: PHP's POST decoding yields the literal text `%5C`, `addslashes` leaves it untouched (no
backslash present yet), and `parse_str` decodes it to a real `\`. Verified end-to-end. The same applies
to any base64 field — the base64 alphabet contains no quote or backslash, so slashing is a no-op and
arbitrary bytes are reconstructed after decoding.

**Rule:** before downgrading on slashing grounds, trace for a second decode — `parse_str`,
`base64_decode`, `urldecode`, `json_decode`, `stripcslashes`.

### WordPress slashes array *values*, never array *keys*

`add_magic_quotes()` recurses into values only. Input shaped `$_POST['opts']['<name>'][]` puts attacker
data in the **key**, which arrives with a raw `'` intact. Code that iterates
`foreach ($opts as $name => $vals)` and interpolates `$name` into SQL is injectable even where the
equivalent value would have been slashed.

**Rule:** treat array keys as a first-class taint source. They are easy to miss precisely because the
value-side equivalent looks safe.

### `strip_tags()` protects a text node, and nothing else

A sanitiser that removes `<` and `>` is context-appropriate for an HTML text node and useless in an
attribute. The same stored value frequently reaches both.

In a real case one sink echoed a `strip_tags`-filtered keyword into `<span>…</span>` — correctly judged
safe — while two widget templates echoed the *same* value into `href='...?s=<value>'`. A payload of
`x' onmouseover='alert(1)` contains no angle bracket, passes `strip_tags` untouched, and breaks out of
the single-quoted attribute. The audit cleared the text-node sink and never enumerated the
attribute-context siblings.

**Rule:** when you clear a sink because of an upstream filter, immediately enumerate **every other sink
fed by the same data** and classify each by output context (body / attribute / JS string / URL / CSS).
Clearing one sink is not clearing the value. See [[secure-coding-and-injection]] for the
context-to-escaper matrix.

> Source: https://developer.wordpress.org/apis/security/nonces/ · https://developer.wordpress.org/reference/functions/check_ajax_referer/ · https://developer.wordpress.org/reference/functions/current_user_can/ · https://developer.wordpress.org/reference/functions/map_meta_cap/ · https://wordpress.org/documentation/article/roles-and-capabilities/ · https://developer.wordpress.org/advanced-administration/multisite/admin/ · https://www.php.net/manual/en/function.parse-str.php · promoted by docs (curate) · 2026-07-25
