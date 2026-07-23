"""Retrieval core: markdown chunker, hash-incremental FTS5 index builder, and the kb_search cascade
(FTS5 → ripgrep). Probes are called module-qualified (`probes.fts5_available()`) so test patches reach
here; path helpers come from lib.config.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

from lib import probes
from lib.config import db_path, vault_dir

PROJECT_DB = Path(".devx/index/mdvault-project.sqlite")
MIN_LOCAL_RESULTS = 3          # short-circuit threshold (matches the proven mdvault default)
SNIPPET_TOKENS = 18
GRAPH_TOP_HITS = 3             # F3: expand outgoing links for only the top-N ranked hits
GRAPH_MAX_NEIGHBORS = 5        # F3: cap appended graph neighbors so the result stays focused
# durable .devx files worth indexing (relative to .devx/); research/ globs added at runtime.
# learnings-index.md is the DISTILLED patterns file (docs `distill` mode) — indexing it makes a
# generalized pattern rank for the next agent, not just the raw one-off entries in learnings.md.
PROJECT_TOP = ("decisions.md", "learnings.md", "learnings-index.md", "architecture.md", "project.md")

SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
    id   INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks(
    id         INTEGER PRIMARY KEY,
    file_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    breadcrumb TEXT NOT NULL,
    body       TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    breadcrumb, body, content='chunks', content_rowid='id');
CREATE TABLE IF NOT EXISTS links(
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    target  TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_links_file ON links(file_id);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target);
CREATE TABLE IF NOT EXISTS meta(
    file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    title   TEXT,
    doc_id  TEXT,
    tags    TEXT,
    summary TEXT);
CREATE INDEX IF NOT EXISTS idx_meta_title  ON meta(title);
CREATE INDEX IF NOT EXISTS idx_meta_doc_id ON meta(doc_id);
"""


_WIKILINK_RE = re.compile(r"\[\[\s*([^\]|]+?)\s*(?:\|[^\]]*)?\]\]")


def _frontmatter(text: str) -> str:
    """Raw YAML-ish frontmatter (between leading --- fences), or ''. Stdlib-only — no yaml dependency."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def _fm_field(fm: str, key: str):
    """A scalar frontmatter field (best-effort, single line) or None."""
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", fm, re.M)
    return (m.group(1).strip().strip('"').strip("'") or None) if m else None


def _extract_links(text: str) -> set:
    """Internal references this doc makes: frontmatter `related:` slugs + inline [[wikilinks]]. Tolerant
    /stdlib — dangling links are only warnings downstream, so loose parsing is acceptable."""
    targets = set()
    fm = _frontmatter(text)
    rel = re.search(r"^related:\s*\n((?:[ \t]+.*\n?)*)", fm, re.M)         # indented block under `related:`
    block = rel.group(1) if rel else ""
    inline = re.search(r"^related:\s*\[(.*?)\]", fm, re.M)                 # or inline list `related: [a, b]`
    if inline:
        block += "\n" + "\n".join("- " + s for s in inline.group(1).split(","))
    targets |= set(re.findall(r"slug:\s*([A-Za-z0-9][\w./-]+)", block))           # `- {slug: x, rel: y}`
    targets |= set(re.findall(r"^\s*-\s*([A-Za-z0-9][\w./-]+)\s*$", block, re.M))  # bare `- slug`
    targets |= {m.group(1).strip() for m in _WIKILINK_RE.finditer(text)}          # inline [[wikilinks]]
    return {t for t in targets if t and t not in ("rel", "slug")}


def norm_title(s: str) -> str:
    """Shared title normalizer (validate._norm_title delegates here): lowercase, collapse any
    run of non-alphanumerics to a single space. Used for dedup + meta-title lookups so the index
    and the file-scan fallback agree on what 'the same title' means."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _doc_title(text: str, rel: str):
    """Frontmatter `title:` else the first `# H1` else None (mirrors validate's dedup title logic)."""
    t = _fm_field(_frontmatter(text), "title")
    if not t:
        m = re.search(r"^#\s+(.*)", text, re.MULTILINE)
        t = m.group(1).strip() if m else None
    return t or None


def _doc_summary(text: str) -> str:
    """First non-blank, non-heading, non-frontmatter, non-blockquote paragraph line — a cheap
    summary for graph/semantic snippets. Stdlib-only, best-effort."""
    body = text
    fm = re.match(r"^---\n.*?\n---\n", text, re.S)
    if fm:
        body = text[fm.end():]
    for ln in body.splitlines():
        s = ln.strip()
        if s and not s.startswith("#") and not s.startswith(">"):
            return s[:280]
    return ""


def _doc_meta(text: str, rel: str) -> tuple:
    """(title, doc_id, tags, summary) for the `meta` table.
    title  = frontmatter title: else first H1 else None
    doc_id = frontmatter id:    else the filename stem
    tags   = frontmatter tags:  (raw scalar/list line) else ''
    summary= frontmatter summary: else the first body paragraph line."""
    fm = _frontmatter(text)
    title = _doc_title(text, rel)
    doc_id = _fm_field(fm, "id") or Path(rel).stem
    tags = _fm_field(fm, "tags") or ""
    summary = _fm_field(fm, "summary") or _doc_summary(text)
    return title, doc_id, tags, summary


def meta_titles(db: Path) -> dict:
    """{normalized_title: relpath} from the `meta` table — index-backed replacement for the
    per-validate file scan in validate._vault_titles(). Empty dict if the DB/table is absent."""
    if not Path(db).exists():
        return {}
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT f.path, m.title FROM meta m JOIN files f ON f.id = m.file_id").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    return {norm_title(t): rel for rel, t in rows if t}


def meta_slugs(db: Path) -> set:
    """Resolvable ids for every indexed doc: `meta.doc_id` (frontmatter id else stem) + the filename
    stem — index-backed replacement for validate._vault_slugs(). Empty set if absent."""
    if not Path(db).exists():
        return set()
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT f.path, m.doc_id FROM meta m JOIN files f ON f.id = m.file_id").fetchall()
    except sqlite3.OperationalError:
        return set()
    finally:
        conn.close()
    slugs = set()
    for rel, doc_id in rows:
        slugs.add(Path(rel).stem)
        if doc_id:
            slugs.add(doc_id)
    return slugs


def doc_body(db: Path, relpath: str) -> str:
    """All indexed chunk bodies + the title for one doc (by relpath), lowercased — used by the
    near-duplicate overlap gate to test which candidate terms co-occur in a hit. '' if absent."""
    if not Path(db).exists():
        return ""
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            """SELECT c.body, m.title FROM chunks c
                 JOIN files f ON f.id = c.file_id
            LEFT JOIN meta  m ON m.file_id = f.id
                WHERE f.path = ?""", (relpath,)).fetchall()
    except sqlite3.OperationalError:
        return ""
    finally:
        conn.close()
    parts = []
    for body, title in rows:
        parts.append(body or "")
        if title:
            parts.append(title)
    return " ".join(parts).lower()


def _graph_neighbors(db: Path, hit_paths, exclude: set, limit: int):
    """F3: for the given (top) hit relpaths, resolve their outgoing `links` targets to vault docs and
    return neighbor result rows NOT already in `exclude`. A target resolves to a doc whose `meta.doc_id`
    OR filename stem equals it. Each neighbor: {path, section:None, snippet:<summary|first chunk>,
    tier:"graph", via:<the hit that linked to it>}. Capped at `limit`. [] if the DB/tables are absent."""
    if not Path(db).exists() or not hit_paths:
        return []
    conn = sqlite3.connect(db)
    try:
        # build target -> relpath resolution from meta (doc_id) + filename stems
        rows = conn.execute(
            "SELECT f.path, m.doc_id, m.summary FROM files f LEFT JOIN meta m ON m.file_id = f.id"
        ).fetchall()
        resolve, summaries = {}, {}
        for path, doc_id, summary in rows:
            resolve.setdefault(Path(path).stem, path)
            if doc_id:
                resolve.setdefault(doc_id, path)
            summaries[path] = summary
        out, taken = [], set()
        for hp in hit_paths:
            trow = conn.execute(
                "SELECT l.target FROM links l JOIN files f ON f.id = l.file_id WHERE f.path = ?",
                (hp,)).fetchall()
            for (target,) in trow:
                npath = resolve.get(target) or resolve.get(target.rsplit("/", 1)[-1])  # accept [[category/slug]]
                if not npath or npath in exclude or npath in taken or npath == hp:
                    continue
                snippet = summaries.get(npath) or ""
                if not snippet:
                    fc = conn.execute(
                        """SELECT c.body FROM chunks c JOIN files f ON f.id = c.file_id
                            WHERE f.path = ? ORDER BY c.id LIMIT 1""", (npath,)).fetchone()
                    snippet = (fc[0] if fc else "")[:200]
                taken.add(npath)
                out.append({"path": npath, "section": None, "snippet": snippet,
                            "tier": "graph", "via": hp})
                if len(out) >= limit:
                    return out
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return out


def _chunk_markdown(rel: str, text: str):
    """Split markdown at headings into (breadcrumb, body) chunks.
    breadcrumb = 'relpath > H1 > H2 ...' so every hit carries its location."""
    stack: dict[int, str] = {}
    cur_depth = 0
    buf: list[str] = []
    out: list[tuple[str, str]] = []

    def crumb() -> str:
        return " > ".join([rel] + [stack[d] for d in sorted(stack) if d <= cur_depth])

    def flush():
        body = "\n".join(buf).strip()
        if body:
            out.append((crumb(), body))

    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush()
            buf.clear()
            cur_depth = len(m.group(1))
            stack[cur_depth] = m.group(2).strip()
            for d in [d for d in stack if d > cur_depth]:
                del stack[d]
        else:
            buf.append(line)
    flush()
    return out or [(rel, text.strip())]


def _build_index(db: Path, items) -> dict:
    """items: iterable of (relpath, Path). Rebuild-on-demand, incremental by hash."""
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")   # so ON DELETE CASCADE actually fires
    conn.executescript(SCHEMA)
    seen, changed = set(), 0
    for rel, f in items:
        seen.add(rel)
        text = f.read_text(encoding="utf-8", errors="replace")
        h = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
        row = conn.execute("SELECT id, hash FROM files WHERE path=?", (rel,)).fetchone()
        if row and row[1] == h:
            continue
        changed += 1
        if row:
            fid = row[0]
            conn.execute("DELETE FROM chunks WHERE file_id=?", (fid,))
            conn.execute("DELETE FROM links WHERE file_id=?", (fid,))
            conn.execute("DELETE FROM meta WHERE file_id=?", (fid,))
            conn.execute("UPDATE files SET hash=? WHERE id=?", (h, fid))
        else:
            fid = conn.execute("INSERT INTO files(path, hash) VALUES(?,?)", (rel, h)).lastrowid
        for crumb, body in _chunk_markdown(rel, text):
            conn.execute("INSERT INTO chunks(file_id, breadcrumb, body) VALUES(?,?,?)",
                         (fid, crumb, body))
        for target in _extract_links(text):                      # the [[wikilink]]/`related:` graph
            conn.execute("INSERT INTO links(file_id, target) VALUES(?,?)", (fid, target))
        title, doc_id, tags, summary = _doc_meta(text, rel)      # index-backed dedup/slug metadata
        conn.execute("INSERT INTO meta(file_id, title, doc_id, tags, summary) VALUES(?,?,?,?,?)",
                     (fid, title, doc_id, tags, summary))
    # prune deleted files AND their chunks explicitly (do not rely on cascade alone — a freed
    # rowid can be reused by a new file, misattributing the old file's stale chunks to it).
    for fid, rel in conn.execute("SELECT id, path FROM files").fetchall():
        if rel not in seen:
            conn.execute("DELETE FROM chunks WHERE file_id=?", (fid,))
            conn.execute("DELETE FROM links WHERE file_id=?", (fid,))
            conn.execute("DELETE FROM meta WHERE file_id=?", (fid,))
            conn.execute("DELETE FROM files WHERE id=?", (fid,))
            changed += 1
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    conn.commit()
    stats = {"db": str(db),
             "files": conn.execute("SELECT COUNT(*) FROM files").fetchone()[0],
             "chunks": conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
             "links": conn.execute("SELECT COUNT(*) FROM links").fetchone()[0],
             "meta": conn.execute("SELECT COUNT(*) FROM meta").fetchone()[0],
             "changed": changed}
    conn.close()
    return stats


# Navigation/meta files that live in the vault tree but are NOT knowledge entries — excluded from the
# index so they never surface in kb_search or act as dedup targets. README documents the vault;
# _index.md files are category stubs.
_VAULT_SKIP = {"README.md", "_index.md"}


def _vault_items():
    v = vault_dir()
    v.mkdir(parents=True, exist_ok=True)
    return [(f.relative_to(v).as_posix(), f)
            for f in sorted(v.rglob("*.md")) if f.name not in _VAULT_SKIP]


def _project_items():
    base = Path(".devx")
    files = [base / n for n in PROJECT_TOP if (base / n).exists()]
    if (base / "research").exists():
        files += sorted((base / "research").rglob("*.md"))
    if (base / "workstreams").exists():
        files += sorted((base / "workstreams").glob("*/research/*.md"))
        # per-phase research + phase summaries (JIT phase loop) — so a phase's findings + summary
        # RANK for the next phase's planner/implementer via kb_search --scope project (compounding).
        files += sorted((base / "workstreams").glob("*/phases/*/research/*.md"))
        files += sorted((base / "workstreams").glob("*/phases/*/summary.md"))
    return [(f.relative_to(base).as_posix(), f) for f in files]


def cmd_index(args) -> dict:
    if not probes.fts5_available():
        return {"ok": False, "error": "no such module fts5",
                "note": "kb_search will fall back to ripgrep; no index to build."}
    out = {"ok": True}
    if args.scope in ("vault", "all"):
        out["vault"] = _build_index(db_path(), _vault_items())
    if args.scope in ("project", "all"):
        out["project"] = _build_index(PROJECT_DB, _project_items())
    return out


def _sanitize(query: str, op: str = "AND") -> str:
    """Free text -> quoted FTS5 tokens. Prevents FTS5 syntax errors from hyphens, CVE IDs, slashes,
    or operator-looking words in user queries. op="AND" (default) joins implicitly (every term must
    match — the precise keyword tier); op="OR" joins with `OR` (any term — the loose, fuzzy tier used
    for near-duplicate detection where a near-twin shares only some words)."""
    toks = [f'"{t}"' for t in re.findall(r"[A-Za-z0-9_]+", query)]
    return (" OR ".join(toks) if op == "OR" else " ".join(toks))


def _fts_search(query: str, limit: int, db: Path, tier: str, op: str = "AND"):
    """Ranked hits from an FTS5 index, or None to signal 'fall back to ripgrep'.
    op controls term combination (see _sanitize): "AND" for precise keyword search, "OR" for fuzzy."""
    if not probes.fts5_available() or not Path(db).exists():
        return None
    match = _sanitize(query, op)
    if not match:
        return []
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            """SELECT f.path, c.breadcrumb,
                      snippet(chunks_fts, 1, '«', '»', ' … ', ?) AS snip,
                      bm25(chunks_fts, 2.0, 1.0) AS rank      -- breadcrumb weighted 2x body
                 FROM chunks_fts
                 JOIN chunks c ON c.id = chunks_fts.rowid
                 JOIN files  f ON f.id = c.file_id
                WHERE chunks_fts MATCH ?
             ORDER BY rank                                    -- ASC: more negative = better
                LIMIT ?""",
            (SNIPPET_TOKENS, match, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    return [{"path": r[0], "section": r[1], "snippet": r[2],
             "score": round(r[3], 3), "tier": tier} for r in rows]


def _rel_to_roots(p: str, roots) -> str:
    """Make a ripgrep-emitted path relative to whichever **directory** root contains it, so the
    fallback tier's paths match the FTS tier's vault/project-relative form (enabling cross-tier dedup).
    Only directory roots are relativized — callers that pass individual files keep their paths unchanged.
    Falls back to the raw path if it isn't under any dir root."""
    pp = Path(p).resolve()
    for root in roots:
        rp = Path(root).resolve()
        if rp.is_dir():
            try:
                return pp.relative_to(rp).as_posix()
            except ValueError:
                continue
    return p


def _rg_search(query: str, paths, limit: int, tier: str):
    """Always-fresh, never-stale fallback / project ripgrep tier."""
    terms = re.findall(r"[A-Za-z0-9_]+", query)
    rg = shutil.which("rg")
    roots = [Path(p) for p in paths if Path(p).exists()]
    paths = [str(p) for p in roots]
    if not terms or not rg or not paths:
        return []
    # -w (whole word): the fallback searches markdown KNOWLEDGE, so substring noise
    # ("rate" inside "Curated") hurts more than missing a stem. Source code uses native Grep.
    # -H forces the filename column even for a single-file search (else "path:line:body" parsing breaks)
    args = [rg, "-i", "-w", "-H", "--no-heading", "-n", "-m", "3", "-g", "!index/**", "-g", "!cache/**"]
    for skip in _VAULT_SKIP:                       # same nav/meta exclusion as the FTS tier (README, _index.md)
        args += ["-g", f"!{skip}"]
    for t in terms:
        args += ["-e", t]
    args += paths
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return []
    res = []
    for line in out.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3:
            res.append({"path": _rel_to_roots(parts[0], roots), "line": parts[1],
                        "snippet": parts[2].strip()[:200], "tier": tier})
        if len(res) >= limit:
            break
    return res


def cmd_kb_search(args) -> dict:
    results, tiers = [], []
    if args.scope in ("vault", "all"):
        fts = _fts_search(args.query, args.limit, db_path(), "fts5:vault")
        if fts is None:
            tiers.append("ripgrep:vault(no-fts5-or-db)")
            results += _rg_search(args.query, [vault_dir()], args.limit, "ripgrep:vault")
        else:
            tiers.append("fts5:vault")
            results += fts
            if len([r for r in results if r.get("tier", "").startswith("fts5")]) < MIN_LOCAL_RESULTS:
                tiers.append("ripgrep:vault")
                results += _rg_search(args.query, [vault_dir()], args.limit, "ripgrep:vault")
    if args.scope in ("project", "all"):
        pf = _fts_search(args.query, args.limit, PROJECT_DB, "fts5:project")
        if pf is None or len(pf) < MIN_LOCAL_RESULTS:
            tiers.append("ripgrep:project")
            results += (pf or [])
            results += _rg_search(args.query, [Path(".devx")], args.limit, "ripgrep:project")
        else:
            tiers.append("fts5:project")
            results += pf
    # Rank the FTS keyword tier ahead of the unranked ripgrep fallback. Stable sort PRESERVES the
    # upstream order within the ranked bucket — so the bm25 order of vault + project hits survives.
    results.sort(key=lambda r: 0 if r.get("tier", "").startswith("fts5") else 1)
    # de-dup while preserving order. The ranked FTS tier keeps DISTINCT sections of a doc; the unranked
    # ripgrep fallback collapses to ONE row per doc and never repeats a doc the FTS tier already returned
    # (the fallback paths are now vault/project-relative, so this matches across tiers).
    seen, seen_paths, dedup = set(), set(), []
    for r in results:
        p = r.get("path")
        if r.get("tier", "").startswith("fts5"):
            key = (p, r.get("line") or r.get("section"))
            if key in seen:
                continue
            seen.add(key)
        elif p in seen_paths:                       # fallback row for a doc already present → drop
            continue
        seen_paths.add(p)
        dedup.append(r)
    # needs_web reflects PRIMARY retrieval depth (computed before graph neighbors are appended, so a
    # walked neighbor never masks a thin keyword result).
    needs_web = len(dedup) < MIN_LOCAL_RESULTS
    # F3: graph-walk. Expand the top vault hits' outgoing [[link]]/`related:` targets (the `links`
    # graph) into resolved vault neighbors and APPEND them (tier:"graph", via:<hit>) — never reordering
    # the primary ranking. Vault scope + FTS index only; capped at GRAPH_MAX_NEIGHBORS.
    if args.scope in ("vault", "all") and db_path().exists():
        present = {r.get("path") for r in dedup}
        seeds = [r["path"] for r in dedup
                 if r.get("tier", "").startswith("fts5") and r.get("path")][:GRAPH_TOP_HITS]
        for n in _graph_neighbors(db_path(), seeds, present, GRAPH_MAX_NEIGHBORS):
            if n["path"] not in present:
                present.add(n["path"])
                dedup.append(n)
                if "graph:vault" not in tiers:
                    tiers.append("graph:vault")
    return {"query": args.query, "scope": args.scope, "tiers": tiers,
            "count": len(dedup), "needs_web": needs_web,
            "results": dedup[: args.limit]}
