"""Auto-promote validation gate. Before a finding is written into the SHARED curated vault, it is
validated so the compounding loop compounds knowledge, not rot: dead source links (stale references),
missing/old provenance, duplicates of existing entries, and un-generalized project specifics are all
caught here. With --promote-to the promotion is GATED BY THIS CODE — the agent cannot write to the
vault except through a passing validation (and the target is clamped inside the vault boundary).
"""
from __future__ import annotations

import datetime
import re
import urllib.error
import urllib.request
from pathlib import Path

from lib import probes, retrieval
from lib.config import _within, db_path, vault_dir
from lib.retrieval import _build_index, _extract_links, _fm_field, _frontmatter, _vault_items, norm_title

PROMOTE_MAX_AGE_DAYS = 365     # promoted knowledge older than this is flagged (warn) for re-verification
URL_RE = re.compile(r'https?://[^\s<>()\[\]"`]+')

# F2: fuzzy near-duplicate WARNING thresholds (never a hard fail — near-dup is a judgment call, so we
# warn and let the curator --update or keep). The candidate's title+summary is OR-searched against the
# vault; a hit must clear BOTH gates to be flagged:
#   1. NEAR_DUP_BM25_MAX — bm25() cutoff (more-negative = stronger). bm25 is strictly ordered within a
#      result set but its ABSOLUTE magnitude varies by SQLite build, so this is a loose floor (any
#      genuine match clears it); the real discriminator is the overlap gate below. Documented per brief.
#   2. NEAR_DUP_MIN_OVERLAP — fraction of the candidate's DISTINCT content terms that also appear in the
#      hit's chunk. Portable across SQLite builds and what actually separates a near-twin (shares most
#      terms) from an incidental one-word match.
NEAR_DUP_BM25_MAX = -0.0          # bm25 is negative for any match; this admits all, overlap decides
NEAR_DUP_MIN_OVERLAP = 0.5        # >= half the candidate's content terms must co-occur in the hit
NEAR_DUP_LIMIT = 5                # how many FTS hits to scan for a near-twin


def _norm_title(s: str) -> str:
    return norm_title(s)        # shared normalizer (retrieval.norm_title) — index + file-scan agree


def _index_ready() -> bool:
    """The vault FTS index exists and is usable → read dedup metadata from it instead of re-parsing
    every file. Module-qualified probe call so a test patch on probes.fts5_available reaches here."""
    return probes.fts5_available() and db_path().exists()


def _extract_urls(text: str) -> list[str]:
    seen, out = set(), []
    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip('.,;:)*"\'')
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _parse_iso_date(text: str):
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _check_url_live(url: str, timeout: int = 15):
    """('live'|'dead'|'unknown', detail). 'dead' = definitively gone (404/410) → a stale
    reference. 'unknown' = transient/auth/network (401/403/5xx/timeout) → never fails a
    promotion (offline or a flaky host must not poison the verdict)."""
    hdrs = {"User-Agent": "Mozilla/5.0 (devx)"}
    try:
        req = urllib.request.Request(url, method="HEAD", headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return ("live", getattr(r, "status", 200))
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return ("dead", e.code)
        if e.code in (403, 405, 501):           # HEAD refused — retry with GET
            try:
                req = urllib.request.Request(url, headers=hdrs)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return ("live", getattr(r, "status", 200))
            except urllib.error.HTTPError as e2:
                return ("dead", e2.code) if e2.code in (404, 410) else ("unknown", e2.code)
            except Exception as e2:
                return ("unknown", str(e2))
        return ("unknown", e.code)
    except Exception as e:
        return ("unknown", str(e))


def _vault_titles() -> dict:
    """Normalized title -> relpath for every vault doc (frontmatter `title:`, else H1) — for dedup.
    Reads from the FTS `meta` table when the index is ready; else falls back to the file scan."""
    if _index_ready():
        titles = retrieval.meta_titles(db_path())
        if titles:
            return titles
    return _vault_titles_scan()


def _vault_titles_scan() -> dict:
    """File-scan fallback for _vault_titles() (opens + parses every vault .md) — used when no index."""
    titles = {}
    for rel, f in _vault_items():
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        t = _fm_field(_frontmatter(text), "title")
        if not t:
            m = re.search(r"^#\s+(.*)", text, re.MULTILINE)
            t = m.group(1) if m else None
        if t:
            titles[_norm_title(t)] = rel
    return titles


def _vault_slugs() -> set:
    """Resolvable ids for every vault doc: frontmatter `id:` + filename stem — for [[link]] resolution.
    Reads from the FTS `meta` table when the index is ready; else falls back to the file scan."""
    if _index_ready():
        slugs = retrieval.meta_slugs(db_path())
        if slugs:
            return slugs
    return _vault_slugs_scan()


def _vault_slugs_scan() -> set:
    """File-scan fallback for _vault_slugs() — used when no index is available."""
    slugs = set()
    for rel, f in _vault_items():
        slugs.add(Path(rel).stem)
        try:
            idv = _fm_field(_frontmatter(f.read_text(encoding="utf-8", errors="replace")), "id")
        except Exception:
            idv = None
        if idv:
            slugs.add(idv)
    return slugs


def validate_promotion(text: str, *, url_checker=None, today=None,
                       max_age_days: int = PROMOTE_MAX_AGE_DAYS,
                       vault_titles=None, vault_slugs=None, target_rel=None) -> dict:
    """Pure, injectable validator (the CLI and the tests share it). Verdict is 'pass'
    only when every blocking check passes; soft signals are warnings, not failures."""
    url_checker = url_checker or _check_url_live
    today = today or datetime.date.today()
    checks, warnings, stale_refs = [], [], []

    # 1. Provenance (auditability + pruning) and its date
    src = next((ln for ln in text.splitlines() if ln.strip().lower().startswith("> source:")), None)
    if not src:
        checks.append({"check": "provenance", "ok": False,
                       "detail": "missing '> Source: {url} · auto-promoted by {who} · {date}' line"})
    else:
        d = _parse_iso_date(src)
        if not d:
            checks.append({"check": "provenance", "ok": False,
                           "detail": "Source line present but has no ISO date (YYYY-MM-DD)"})
        else:
            checks.append({"check": "provenance", "ok": True, "detail": src.strip()})
            age = (today - d).days
            if age > max_age_days:
                warnings.append({"warn": "stale-by-age",
                                 "detail": f"source dated {d} is {age}d old (>{max_age_days}d) — re-verify"})

    # 2. Stale references — dead source links are the headline check
    urls = _extract_urls(text)
    url_status = []
    for u in urls:
        state, detail = url_checker(u)
        url_status.append({"url": u, "state": state, "detail": detail})
        if state == "dead":
            stale_refs.append(u)
        elif state == "unknown":
            warnings.append({"warn": "url-unreachable", "detail": f"{u} ({detail}) — could not verify"})
    checks.append({"check": "links", "ok": not stale_refs,
                   "detail": (f"{len(urls)} url(s); {len(stale_refs)} dead" if urls else "no urls cited")})
    if not urls:
        warnings.append({"warn": "no-citations", "detail": "no source URLs — promoted knowledge should cite"})

    # 3. Dedup — same title (frontmatter `title:`, else H1) or same target filename already in the vault
    if vault_titles is None:
        vault_titles = _vault_titles()
    cand_title = _fm_field(_frontmatter(text), "title")
    if not cand_title:
        m = re.search(r"^#\s+(.*)", text, re.MULTILINE)
        cand_title = m.group(1) if m else None
    cand = _norm_title(cand_title) if cand_title else None
    dup = vault_titles.get(cand) if cand else None
    if not dup and target_rel:
        dup = next((p for p in vault_titles.values() if Path(p).name == Path(target_rel).name), None)
    checks.append({"check": "dedup", "ok": dup is None,
                   "detail": (f"a vault entry already covers this: {dup} — update it (use --update)"
                              if dup else "no title/filename collision")})

    # 3b. Fuzzy near-duplicate — only when there's NO exact dup and the FTS index is live. An FTS
    #     self-search of the candidate's title+summary against the vault catches near-twins (same
    #     topic, different title) that the exact check misses. A strong top hit → WARNING (not a
    #     fail): near-dup is a judgment call, so the curator decides (--update or keep). Cutoff is
    #     NEAR_DUP_BM25_MAX (more-negative = stronger).
    near_dups: list[str] = []
    if dup is None and probes.fts5_available() and db_path().exists():
        _, _, _, cand_summary = retrieval._doc_meta(text, target_rel or "candidate.md")
        probe = " ".join(p for p in (cand_title, cand_summary) if p).strip()
        cand_terms = {t for t in re.findall(r"[a-z0-9]+", probe.lower()) if len(t) > 2}
        self_name = Path(target_rel).name if target_rel else None
        cand_links = {l.rsplit("/", 1)[-1] for l in _extract_links(text)}   # the candidate's own cross-links
        if probe and cand_terms:
            # OR semantics: a near-twin shares SOME words, not all — an AND query would miss it.
            hits = retrieval._fts_search(probe, NEAR_DUP_LIMIT, db_path(), "fts5:vault", op="OR") or []
            for h in hits:
                hp = h.get("path")
                # exclude an exact-title self-match and the candidate's own target file
                if cand and vault_titles.get(cand) == hp:
                    continue
                if self_name and Path(hp).name == self_name:
                    continue
                if Path(hp).stem in cand_links:    # candidate deliberately cross-links it → complementary, not a twin
                    continue
                if h.get("score", 0.0) > NEAR_DUP_BM25_MAX:          # bm25 floor (every match is < 0)
                    continue
                hit_body = retrieval.doc_body(db_path(), hp)
                overlap = sum(1 for t in cand_terms if t in hit_body) / len(cand_terms)
                if overlap >= NEAR_DUP_MIN_OVERLAP and hp not in near_dups:
                    near_dups.append(hp)
        if near_dups:
            warnings.append({"warn": "thematic-overlap",
                             "detail": "strong thematic overlap with: " + ", ".join(near_dups[:3])
                                       + " — confirm it's complementary (cross-link it in `related:`), not a"
                                       + " duplicate; use --update only if it's truly the same entry"})

    # 4. Generalized — an absolute project path is an un-stripped leak into a SHARED vault
    cwd = str(Path.cwd())
    if cwd in text:
        checks.append({"check": "generalized", "ok": False,
                       "detail": f"contains the absolute project path {cwd} — strip project specifics"})
    else:
        checks.append({"check": "generalized", "ok": True, "detail": "no absolute project path"})
        if re.search(r"(^|[\s/`])\.devx/", text):
            warnings.append({"warn": "project-specifics",
                             "detail": "references .devx/ — confirm this is generalized, not project-local"})

    # 5. Internal links — `related:`/[[wikilink]] targets should resolve; dangling = WARNING, not failure
    #    (the target may simply be promoted next — we nudge, we don't block).
    if vault_slugs is None:
        vault_slugs = _vault_slugs()
    known = set(vault_slugs) | {Path(p).stem for p in vault_titles.values()}

    def _resolves(t: str) -> bool:
        base = t.rsplit("/", 1)[-1]                      # accept [[category/slug]] → bare slug
        return (t in known or base in known
                or _norm_title(t) in vault_titles or _norm_title(base) in vault_titles)

    dangling = sorted(t for t in _extract_links(text) if not _resolves(t))
    if dangling:
        warnings.append({"warn": "dangling-links",
                         "detail": "internal link target(s) not in the vault: "
                                   + ", ".join(dangling[:5]) + " — add them or fix the slug"})

    verdict = "pass" if all(c["ok"] for c in checks) else "fail"
    return {"verdict": verdict, "checks": checks, "stale_refs": stale_refs,
            "duplicate": dup, "near_duplicates": near_dups, "warnings": warnings,
            "urls": url_status, "dangling_links": dangling}


def cmd_validate(args) -> dict:
    f = Path(args.file)
    if not f.exists():
        return {"ok": False, "verdict": "fail", "error": f"candidate not found: {args.file}"}
    text = f.read_text(encoding="utf-8", errors="replace")
    checker = (lambda u: ("unknown", "offline")) if args.offline else _check_url_live
    res = validate_promotion(text, url_checker=checker, max_age_days=args.max_age_days,
                             target_rel=args.promote_to)
    res["candidate"] = str(f)
    res["ok"] = res["verdict"] == "pass"
    if args.promote_to:
        # --update waives ONLY the dedup check (deliberate overwrite); nothing else.
        blocking = [c for c in res["checks"] if not c["ok"]
                    and not (c["check"] == "dedup" and args.update)]
        if not blocking:
            dest = vault_dir() / args.promote_to
            if not _within(dest, vault_dir()):     # H-02: no `../`, absolute, or symlink escape
                res["promoted"] = False
                res["verdict"] = "fail"
                res["ok"] = False
                res["error"] = f"--promote-to escapes the vault boundary: {args.promote_to}"
                return res
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            res["promoted"] = True
            res["promoted_to"] = str(dest)
            res["reindexed"] = bool(probes.fts5_available()) and bool(_build_index(db_path(), _vault_items()))
            res["verdict"] = "pass"
            res["ok"] = True
        else:
            res["promoted"] = False
    return res
