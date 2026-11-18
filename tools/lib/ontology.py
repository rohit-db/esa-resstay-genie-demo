"""Discover ontology as code: governed tags, domains and subdomains, asset tags, and Pages.

`load_ontology` reads ontology/domains.yml and ontology/pages/*.md. `reconcile` compares that desired state with the
live account and applies the difference through an executor; `plan` runs the same logic without writing anything.
Only objects recorded in the manifest are ever changed: a live object with one of our names that the manifest does
not record belongs to someone else, and reconcile stops instead of adopting it.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import yaml

from tools.lib.templates import PLACEHOLDER, TemplateError, render_template

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOMAINS = ROOT / "ontology" / "domains.yml"
DEFAULT_PAGES = ROOT / "ontology" / "pages"
PREFIX = "ESA "
NAME_KEYS = ("catalog", "mart", "common", "semantic")
WORKSPACE_TYPES = {"dashboard": "dashboards", "genie": "geniespaces"}
SUBTITLE_MAX, DESCRIPTION_MAX, PAGE_DESCRIPTION_MAX = 280, 4096, 280
DOMAIN_FIELDS = {"key", "tag_key", "subtitle", "description", "subdomains"}
SUBDOMAIN_FIELDS = {"key", "name", "subtitle", "description", "assets"}
PAGE_FIELDS = {"display_name", "subdomain", "synonyms", "description", "assumption", "mentions", "requires"}
ASSET = re.compile(r"^(?:(mart|common|semantic)\.([A-Za-z_][A-Za-z0-9_]*)|(dashboard|genie):([a-z][a-z0-9_]*))$")
KEY = re.compile(r"^[a-z][a-z0-9_]*$")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
BANNER = ("> **Demo definition — confirm with ESA.** This Page states the working definition used in the demo; "
          "ESA has not confirmed it yet.\n\n")


class OntologyError(ValueError):
    pass


class CollisionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Asset:
    ref: str
    kind: str              # uc | dashboard | genie
    schema: str | None     # logical schema for Unity Catalog objects
    name: str

    @property
    def url_placeholder(self) -> str:
        return f"url_{self.kind}_{self.name}"

    @property
    def body_form(self) -> str:
        """How a mention of this asset is written in a Page template."""
        if self.kind == "uc":
            return f"{{{{catalog}}}}.{{{{{self.schema}}}}}.{self.name}"
        return f"{{{{{self.url_placeholder}}}}}"

    def uc_name(self, names: dict[str, str]) -> str:
        return f"{names['catalog']}.{names[self.schema]}.{self.name}"


def parse_asset(ref: Any) -> Asset:
    match = ASSET.match(str(ref or ""))
    if not match:
        raise OntologyError(f"invalid asset reference {ref!r}; expected <mart|common|semantic>.<name>, "
                            "dashboard:<key>, or genie:<key>")
    if match.group(1):
        return Asset(str(ref), "uc", match.group(1), match.group(2))
    return Asset(str(ref), match.group(3), None, match.group(4))


@dataclass(frozen=True)
class Node:
    """A domain (parent is None) or a subdomain."""
    key: str
    tag_key: str
    subtitle: str
    description: str
    parent: str | None = None
    assets: tuple[Asset, ...] = ()


@dataclass(frozen=True)
class Page:
    slug: str
    display_name: str
    subdomain: str
    synonyms: tuple[str, ...]
    description: str
    assumption: bool
    mentions: tuple[Asset, ...]
    requires: tuple[Asset, ...]
    body: str


@dataclass(frozen=True)
class Ontology:
    nodes: tuple[Node, ...]
    pages: tuple[Page, ...]

    def node(self, key: str) -> Node:
        for node in self.nodes:
            if node.key == key:
                return node
        raise KeyError(key)

    @property
    def subdomains(self) -> tuple[Node, ...]:
        return tuple(n for n in self.nodes if n.parent)


def _text(raw: dict, name: str, limit: int, where: str, problems: list[str]) -> str:
    value = " ".join(str(raw.get(name) or "").split())
    if not value:
        problems.append(f"{where}: {name} is required")
    elif len(value) > limit:
        problems.append(f"{where}: {name} is longer than {limit} characters")
    return value


def load_domains(path: Path = DEFAULT_DOMAINS) -> tuple[Node, ...]:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    problems: list[str] = []
    if raw.get("version") != 1:
        problems.append("version must be 1")
    nodes: list[Node] = []
    for d in raw.get("domains") or []:
        where = f"domain {d.get('key')!r}"
        if set(d) - DOMAIN_FIELDS:
            problems.append(f"{where}: unknown fields {sorted(set(d) - DOMAIN_FIELDS)}")
        tag_key = str(d.get("tag_key") or "")
        if not tag_key.startswith(PREFIX):
            problems.append(f"{where}: tag_key {tag_key!r} must start with {PREFIX!r} (the account is shared)")
        if "/" in tag_key:
            problems.append(f"{where}: tag_key must not contain '/'")
        nodes.append(Node(str(d.get("key")), tag_key, _text(d, "subtitle", SUBTITLE_MAX, where, problems),
                          _text(d, "description", DESCRIPTION_MAX, where, problems)))
        for s in d.get("subdomains") or []:
            sub_where = f"subdomain {s.get('key')!r}"
            if set(s) - SUBDOMAIN_FIELDS:
                problems.append(f"{sub_where}: unknown fields {sorted(set(s) - SUBDOMAIN_FIELDS)}")
            name = str(s.get("name") or "").strip()
            if not name or "/" in name:
                problems.append(f"{sub_where}: name is required and must not contain '/'")
            assets = []
            for ref in s.get("assets") or []:
                try:
                    assets.append(parse_asset(ref))
                except OntologyError as error:
                    problems.append(f"{sub_where}: {error}")
            nodes.append(Node(str(s.get("key")), f"{tag_key}/{name}",
                              _text(s, "subtitle", SUBTITLE_MAX, sub_where, problems),
                              _text(s, "description", DESCRIPTION_MAX, sub_where, problems),
                              parent=str(d.get("key")), assets=tuple(assets)))
    for label, values in (("key", [n.key for n in nodes]), ("tag_key", [n.tag_key for n in nodes])):
        problems += [f"duplicate {label} {v!r}" for v in sorted({v for v in values if values.count(v) > 1})]
    problems += [f"invalid key {n.key!r}" for n in nodes if not KEY.match(n.key)]
    if problems:
        raise OntologyError(f"{path}: " + "; ".join(problems))
    return tuple(nodes)


def _page(path: Path, nodes: tuple[Node, ...]) -> tuple[Page | None, list[str]]:
    where, problems = path.name, []
    match = FRONTMATTER.match(path.read_text())
    if not match:
        return None, [f"{where}: expected YAML frontmatter between '---' lines"]
    meta, body = yaml.safe_load(match.group(1)) or {}, match.group(2).strip() + "\n"
    if PAGE_FIELDS - set(meta):
        problems.append(f"{where}: missing fields {sorted(PAGE_FIELDS - set(meta))}")
    if set(meta) - PAGE_FIELDS:
        problems.append(f"{where}: unknown fields {sorted(set(meta) - PAGE_FIELDS)}")
    subdomain = str(meta.get("subdomain"))
    if subdomain not in {n.key for n in nodes if n.parent}:
        problems.append(f"{where}: {subdomain!r} is not a subdomain key")
    if not path.stem.startswith(f"{subdomain}--"):
        problems.append(f"{where}: file name must start with '{subdomain}--'")
    synonyms = meta.get("synonyms") or []
    if not isinstance(synonyms, list) or not all(isinstance(s, str) and s.strip() for s in synonyms):
        problems.append(f"{where}: synonyms must be a list of strings")
    description = _text(meta, "description", PAGE_DESCRIPTION_MAX, where, problems)
    if "{{" in description:
        problems.append(f"{where}: description must not contain placeholders")
    if not isinstance(meta.get("assumption"), bool):
        problems.append(f"{where}: assumption must be true or false")
    refs: dict[str, tuple[Asset, ...]] = {}
    for name in ("mentions", "requires"):
        try:
            refs[name] = tuple(parse_asset(r) for r in meta.get(name) or [])
        except OntologyError as error:
            problems.append(f"{where}: {error}")
            refs[name] = ()
    if re.search(r"^# ", body, re.M):
        problems.append(f"{where}: the body must not contain an H1; display_name is the title")
    allowed = set(NAME_KEYS) | {a.url_placeholder for a in refs["requires"]}
    used = {m.group(1) for m in PLACEHOLDER.finditer(body)}
    if used - allowed:
        problems.append(f"{where}: placeholders not allowed here: {sorted(used - allowed)}")
    for asset in refs["mentions"]:
        if asset.body_form not in body:
            problems.append(f"{where}: mention {asset.ref} does not appear in the body as {asset.body_form}")
    if problems:
        return None, problems
    return Page(path.stem, " ".join(str(meta["display_name"]).split()), subdomain,
                tuple(s.strip() for s in synonyms), description, meta["assumption"], refs["mentions"],
                refs["requires"], body), []


def load_pages(pages_dir: Path, nodes: tuple[Node, ...]) -> tuple[Page, ...]:
    pages, problems = [], []
    for path in sorted(Path(pages_dir).glob("*.md")):
        page, found = _page(path, nodes)
        problems += found
        if page:
            pages.append(page)
    names = [p.display_name for p in pages]
    problems += [f"duplicate display_name {n!r}" for n in sorted({n for n in names if names.count(n) > 1})]
    if problems:
        raise OntologyError("; ".join(problems))
    return tuple(pages)


def load_ontology(domains_path: Path = DEFAULT_DOMAINS, pages_dir: Path = DEFAULT_PAGES) -> Ontology:
    nodes = load_domains(domains_path)
    return Ontology(nodes, load_pages(pages_dir, nodes))


def check_coverage(nodes: tuple[Node, ...], contract) -> None:
    """Every contract object belongs to at least one subdomain, and every mart/common asset is a contract object."""
    tables = {t.name: t.schema for t in contract.tables}
    assigned = {(a.schema, a.name) for n in nodes for a in n.assets if a.kind == "uc" and a.schema != "semantic"}
    unknown = sorted(f"{s}.{n}" for s, n in assigned if tables.get(n) != s)
    unassigned = sorted(n for n, s in tables.items() if (s, n) not in assigned)
    problems = []
    if unassigned:
        problems.append(f"contract objects not assigned to any subdomain: {', '.join(unassigned)}")
    if unknown:
        problems.append(f"assets that are not contract objects: {', '.join(unknown)}")
    if problems:
        raise OntologyError("; ".join(problems))


def render_body(page: Page, names: dict[str, str], urls: dict[str, str]) -> str:
    context = {k: names[k] for k in NAME_KEYS}
    for asset in page.requires:
        if asset.ref not in urls:
            raise OntologyError(f"Page {page.display_name!r}: no URL for {asset.ref}")
        context[asset.url_placeholder] = urls[asset.ref]
    try:
        body = render_template(page.body, context)
    except TemplateError as error:
        raise OntologyError(f"Page {page.display_name!r}: {error}") from error
    return (BANNER + body) if page.assumption else body


# --- reconcile -------------------------------------------------------------------------------------------------

@dataclass
class Live:
    tag_policies: dict[str, dict]            # tag key -> tag policy
    domains: dict[str, dict]                 # tag key -> domain
    pages: dict[str, dict]                   # page name -> Page, for Pages in our domains
    uc_tags: dict[str, set[str] | None]      # object full name -> tag keys; absent or None when it does not exist
    ws_tags: dict[str, set[str]]             # asset ref -> tag keys, for deployed dashboards and Genie spaces


@dataclass(frozen=True)
class Context:
    names: dict[str, str]                    # catalog, mart, common, semantic for the bundle target
    workspace_ids: dict[str, str] = field(default_factory=dict)   # asset ref -> dashboard or Genie space ID
    urls: dict[str, str] = field(default_factory=dict)            # asset ref -> URL used in Page bodies


@dataclass(frozen=True)
class Action:
    op: str
    target: str
    detail: str = ""

    def describe(self) -> str:
        return f"{self.op:<18} {self.target}" + (f"  ({self.detail})" if self.detail else "")


@dataclass
class Result:
    actions: list[Action] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    unmanaged: list[str] = field(default_factory=list)


class Executor(Protocol):
    def create_tag_policy(self, tag_key: str, description: str) -> dict: ...
    def create_domain(self, node: Node, parent_id: str | None) -> dict: ...
    def update_domain(self, name: str, node: Node, parent_id: str | None, fields: list[str]) -> Any: ...
    def publish_domain(self, name: str, node: Node) -> Any: ...
    def tag_uc(self, full_name: str, tag_key: str) -> Any: ...
    def tag_workspace(self, entity_type: str, entity_id: str, ref: str, tag_key: str) -> Any: ...
    def create_page(self, payload: dict) -> dict: ...
    def update_page(self, name: str, payload: dict, fields: list[str]) -> Any: ...
    def publish_page(self, name: str) -> Any: ...


class DryRun:
    """An executor that writes nothing and hands out placeholder IDs, so `plan` can walk the whole sequence."""

    def create_tag_policy(self, tag_key, description):
        return {"id": f"<new tag {tag_key}>"}

    def create_domain(self, node, parent_id):
        return {"domain_id": f"<new {node.key}>", "name": f"domains/<new {node.key}>", "draft": True}

    def create_page(self, payload):
        return {"name": f"pages/<new {payload['display_name']}>", "state": "DRAFT"}

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return [_norm(v) for v in value]
    return value


def _same(key: str, live_value: Any, wanted: Any) -> bool:
    if key == "synonyms":                    # the Pages API stores synonyms sorted
        return sorted(_norm(live_value or [])) == sorted(_norm(wanted))
    return _norm(live_value) == _norm(wanted)


def reconcile(ontology: Ontology, live: Live, records: dict, ctx: Context, executor: Executor,
              save: Callable[[], None] = lambda: None) -> Result:
    result = Result()
    act = result.actions.append
    tags = records.setdefault("tag_policies", {})
    domains = records.setdefault("domains", {})
    pages = records.setdefault("pages", {})

    for node in ontology.nodes:                                    # 1. governed tags
        found = live.tag_policies.get(node.tag_key)
        if found:
            if str((tags.get(node.tag_key) or {}).get("id")) != str(found.get("id")):
                raise CollisionError(f"governed tag {node.tag_key!r} already exists and this repo did not create it; "
                                     "rename the domain or remove the tag")
            continue
        act(Action("create_tag_policy", node.tag_key))
        tags[node.tag_key] = {"id": str(executor.create_tag_policy(node.tag_key, node.subtitle).get("id"))}
        save()

    drafts: dict[str, bool] = {}
    for node in ontology.nodes:                                    # 2. domains, parents before subdomains
        found = live.domains.get(node.tag_key)
        parent_id = domains[node.parent]["domain_id"] if node.parent else None
        if found:
            if (domains.get(node.key) or {}).get("domain_id") != found.get("domain_id"):
                raise CollisionError(f"domain {node.tag_key!r} already exists and this repo did not create it")
            changed = [f for f in ("subtitle", "description") if _norm(found.get(f) or "") != getattr(node, f)]
            if (found.get("parent_domain_id") or None) != parent_id:
                changed.append("parent_domain_id")
            if changed:
                act(Action("update_domain", node.tag_key, ",".join(changed)))
                executor.update_domain(found["name"], node, parent_id, changed)
            drafts[node.key] = bool(found.get("draft", found.get("effective_draft")))
            continue
        act(Action("create_domain", node.tag_key, f"under {node.parent}" if node.parent else ""))
        created = executor.create_domain(node, parent_id)
        domains[node.key] = {"domain_id": created["domain_id"], "name": created["name"], "tag_key": node.tag_key}
        save()
        drafts[node.key] = True

    for node in ontology.subdomains:                               # 3. asset tags
        for asset in node.assets:
            if asset.kind == "uc":
                full = asset.uc_name(ctx.names)
                present = live.uc_tags.get(full)
                if present is None:
                    message = f"{asset.ref} ({full}) does not exist"
                    (result.pending if asset.schema == "semantic" else result.problems).append(message)
                elif node.tag_key not in present:
                    act(Action("tag_table", full, node.tag_key))
                    executor.tag_uc(full, node.tag_key)
                continue
            entity_id = ctx.workspace_ids.get(asset.ref)
            if not entity_id:
                result.pending.append(f"{asset.ref} is not deployed yet")
            elif node.tag_key not in live.ws_tags.get(asset.ref, set()):
                act(Action("tag_workspace", asset.ref, node.tag_key))
                executor.tag_workspace(WORKSPACE_TYPES[asset.kind], entity_id, asset.ref, node.tag_key)

    managed = set()
    for page in ontology.pages:                                    # 4. Pages
        waiting = [a.ref for a in page.requires if a.ref not in ctx.urls]
        if waiting:
            result.pending.append(f"Page {page.display_name!r} waits for {', '.join(waiting)}")
            continue
        domain = domains[page.subdomain]["name"]
        payload = {"domain": domain, "display_name": page.display_name, "description": page.description,
                   "synonyms": list(page.synonyms), "body": render_body(page, ctx.names, ctx.urls)}
        name = (pages.get(page.slug) or {}).get("name")
        found = live.pages.get(name) if name else None
        if found is None:
            clash = [p for p in live.pages.values()
                     if p.get("domain") == domain and _norm(p.get("display_name")) == page.display_name]
            if clash:
                raise CollisionError(f"Page {page.display_name!r} already exists in {domain} and this repo did not "
                                     "create it")
            act(Action("create_page", page.display_name))
            created = executor.create_page(payload)
            name, state = created["name"], created.get("state")
            pages[page.slug] = {"name": name, "domain": domain}
            save()
        else:
            changed = [k for k, v in payload.items() if not _same(k, found.get(k), v)]
            if changed:
                act(Action("update_page", page.display_name, ",".join(changed)))
                executor.update_page(name, payload, changed)
            state = found.get("state")
        managed.add(name)
        if state != "PUBLISHED":
            act(Action("publish_page", page.display_name))
            executor.publish_page(name)
    our_domains = {d["name"] for d in domains.values()}
    result.unmanaged += sorted(f"Page {p.get('display_name')!r} ({n}) is not in ontology/pages"
                               for n, p in live.pages.items() if n not in managed and p.get("domain") in our_domains)

    order = list(ontology.subdomains) + [n for n in ontology.nodes if not n.parent]
    for node in order:                                             # 5. publish subdomains, then domains
        if drafts.get(node.key):
            act(Action("publish_domain", node.tag_key))
            executor.publish_domain(domains[node.key]["name"], node)
    return result


def plan(ontology: Ontology, live: Live, records: dict, ctx: Context) -> Result:
    """What reconcile would do, without writing to the account or the manifest."""
    return reconcile(ontology, copy.deepcopy(live), copy.deepcopy(records), ctx, DryRun())
