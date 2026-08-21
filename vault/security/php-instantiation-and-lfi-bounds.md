---
id: php-instantiation-and-lfi-bounds
title: Bounding PHP Object-Instantiation and File-Inclusion Findings
type: security
tags: [php, object-injection, lfi, autoloader, path-traversal, severity, unsafe-reflection, cwe-470, cwe-98]
summary: Empirically established limits on how far `new $userControlled()` and `include("prefix.$userControlled")` findings actually reach in PHP — PHP refuses to autoload invalid identifiers (killing autoloader-traversal RCE), while a fixed string prefix does not block `../` traversal because PHP normalises lexically. Plus the gadget-availability question that decides whether object instantiation is DoS or RCE.
related:
  - {slug: secure-coding-and-injection, rel: relates-to}
  - {slug: wordpress-plugin-auth, rel: relates-to}
  - {slug: owasp-top-10-quickref, rel: see-also}
created: 2026-07-25
---

# Bounding PHP Object-Instantiation and File-Inclusion Findings

> Source: https://www.php.net/manual/en/language.oop5.autoload.php · auto-promoted by devx-orchestrator · 2026-07-25

Primary references: [PHP autoloading](https://www.php.net/manual/en/language.oop5.autoload.php) ·
[`include`](https://www.php.net/manual/en/function.include.php) ·
[CWE-470 Unsafe Reflection](https://cwe.mitre.org/data/definitions/470.html) ·
[CWE-98 PHP Remote File Inclusion](https://cwe.mitre.org/data/definitions/98.html) ·
[OWASP PHP Object Injection](https://owasp.org/www-community/vulnerabilities/PHP_Object_Injection).
The measured results below were established empirically on PHP 8.1.29 during a plugin audit;
each was tested against a control rather than inferred.

Two sink shapes recur in PHP audits and are routinely mis-scored in both directions:

```php
$c = new $v(...);                        // arbitrary class instantiation (CWE-470)
include("fixed.prefix." . $x . ".php");  // prefixed inclusion (CWE-98)
```

Both look like immediate RCE and usually are not. The four facts below decide the real severity.
All were established by testing on PHP 8.1, each against a control — not by reasoning.

## 1. PHP does not autoload class names containing invalid identifier characters

This is the single most useful bound, because it kills the most attractive escalation story.

A common pattern is an autoloader that builds a path from the class name with no sanitisation:

```php
$file = $base_dir . str_replace('\\', '/', $relative_class) . '.php';
if ( file_exists($file) ) { require $file; }   // looks like arbitrary require
```

It reads as arbitrary local file inclusion via `new "Ns\..\..\..\tmp\evil"`. **It is not
reachable.** PHP only invokes registered autoloaders for names that are well-formed
identifiers (alphanumerics, `_`, and `\` namespace separators). A name containing `.`, `/`, or
a space is rejected before any autoloader runs.

Measured, with a probe autoloader that echoes whatever it receives:

| class name passed to `new` | autoloader invoked? |
|---|---|
| `PlainMissingClass` | yes |
| `Foo\Bar\Baz` | yes |
| `Ns\ASP\..\..\tmp\x` | **no** |
| `../../tmp/x` | **no** |
| `Has Space` | **no** |

Confirmed end-to-end: a planted `/tmp/payload.php` was never included, verified by a
file-write side channel.

**Consequence.** Do not report "unsanitised autoloader → arbitrary `require` → RCE". The
unsanitised path build is a real latent defect worth fixing, but it is not attacker-reachable
through `new $v()`. Check whether any *other* caller passes an arbitrary string to
`class_exists()`, `spl_autoload_call()`, or the autoloader directly — those are not subject to
the identifier restriction.

## 2. A fixed string prefix does NOT block `../` traversal

The mirror-image error, in the opposite direction:

```php
include("asp.shortcode." . $field . ".php");
```

It is tempting to conclude that the glued `asp.shortcode.` prefix forces the first path
component to be `asp.shortcode.<attacker>`, which would have to exist as a real directory for
`..` to pop it — and therefore that traversal fails.

**Wrong.** PHP normalises `..` lexically when resolving an include path; the intermediate
component need not exist. `asp.shortcode../../../../tmp/payload.php` resolves to
`/tmp/payload.php` and executes.

Verified: an unauthenticated request with `field = general|../../../../../../../../tmp/aspoc`
executed a planted file as the web-server uid.

**Consequence.** A prefixed `include`/`require` with a request-influenced component is a real
LFI. Never dismiss one on prefix grounds without testing it. (If two auditors disagree on a
sink of this shape, this is why — and it is one command to settle.)

## 3. Distinguish read from inclusion — and check which is actually worse

| | `file_get_contents` (LFR) | `include`/`require` (LFI) |
|---|---|---|
| Yields | file **contents** as data | file **executed** as PHP |
| `.php` target | source disclosed verbatim | source never seen, only side effects |
| Needs a plantable `.php`? | no | yes, to be useful |

Counter-intuitively the **read** is often the more severe of the two. Against a config file
holding credentials and session-signing secrets, `include` does nothing useful (already
loaded, produces no output) while `file_get_contents` hands over the secrets — frequently a
full authentication bypass with no code execution needed.

So: when both sinks exist, score them independently and do not assume the inclusion outranks
the read.

## 4. Instantiation is only RCE if a gadget exists — enumerate, don't assume

`new $v($fixed, $fixed, $controlled)` gives an attacker constructor execution, plus
`__destruct` at shutdown (which still fires when a later method call fatals). It does **not**
give `__wakeup` — that is deserialization-only.

Enumerate the actual gadget pool in the running application rather than asserting RCE:

```php
foreach (get_declared_classes() as $c) {
    $r = new ReflectionClass($c);
    if (!$r->isAbstract() && $r->hasMethod('__destruct')) {
        try { new $c(/* the exact arg shape the sink supplies */); echo "BUILT: $c\n"; }
        catch (Throwable $e) { echo "blocked: $c -> " . get_class($e) . "\n"; }
    }
}
```

A minimal stack often yields nothing usable — constructors that throw before the object is
created never reach `__destruct`. But the pool scales with installed extensions, plugins, and
libraries, and **any autoloadable class is reachable, not just already-loaded ones** (subject
to fact 1). Score on that basis: "arbitrary object instantiation, RCE-capable given a gadget"
is the honest phrasing when no gadget is named.

Note also that a sink wrapped in `ob_start()` swallows any `echo` from the instantiated code —
use a file-write or network side channel to prove execution, not printed output.

## Review checklist

- [ ] Sink identified as read vs inclusion vs instantiation — scored independently.
- [ ] For a prefixed include: traversal **tested**, not reasoned about (fact 2).
- [ ] For instantiation: autoloader-traversal escalation ruled out (fact 1).
- [ ] For instantiation: gadget pool enumerated against the sink's real argument shape (fact 4).
- [ ] For inclusion claimed as RCE: an attacker-influenceable `.php` write path **named**. No
      upload handler and hardcoded write extensions means LFI, not RCE.
- [ ] Execution proven via side channel if the sink is inside an output buffer.
