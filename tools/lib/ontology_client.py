"""Live reads and writes for the ontology: tag policies, domains, Unity Catalog and workspace tags, and Pages."""

from __future__ import annotations

import json
from urllib.parse import quote

from tools.lib.dbcli import Cli, CliError, is_missing
from tools.lib.ontology import PREFIX, WORKSPACE_TYPES, Context, Live, Node, Ontology

PAGES = "/api/2.0/knowledge/pages"


def _rows(response, key: str) -> list[dict]:
    if isinstance(response, dict):
        return list(response.get(key) or [])
    return list(response or [])


class OntologyClient:
    def __init__(self, cli: Cli):
        self.cli = cli

    # --- reads ---------------------------------------------------------------------------------------------------
    def tag_policies(self) -> dict[str, dict]:
        rows = _rows(self.cli.json(["tag-policies", "list-tag-policies"]), "tag_policies")
        return {r["tag_key"]: r for r in rows if str(r.get("tag_key", "")).startswith(PREFIX)}

    def domains(self) -> dict[str, dict]:
        rows = _rows(self.cli.json(["domains", "list-domains"]), "domains")
        return {r["tag_key"]: r for r in rows if str(r.get("tag_key", "")).startswith(PREFIX)}

    def pages(self, domain_names: set[str]) -> dict[str, dict]:
        """Every Page in the given domains, with its body. The list API has no domain filter, so page through all."""
        found, token = {}, None
        while True:
            path = f"{PAGES}?page_size=100" + (f"&page_token={quote(token, safe='')}" if token else "")
            response = self.cli.api("get", path) or {}
            for row in response.get("pages") or []:
                if row.get("domain") in domain_names:
                    found[row["name"]] = self.cli.api("get", f"/api/2.0/knowledge/{row['name']}")
            token = response.get("next_page_token")
            if not token:
                return found

    def uc_tags(self, full_name: str) -> set[str] | None:
        try:
            rows = _rows(self.cli.json(["entity-tag-assignments", "list", "tables", full_name]), "tag_assignments")
        except CliError as error:
            if is_missing(error):
                return None
            raise
        return {r["tag_key"] for r in rows}

    def ws_tags(self, entity_type: str, entity_id: str) -> set[str]:
        rows = _rows(self.cli.json(["workspace-entity-tag-assignments", "list-tag-assignments", entity_type,
                                    entity_id]), "tag_assignments")
        return {r["tag_key"] for r in rows}

    def gather(self, ontology: Ontology, ctx: Context) -> Live:
        tag_keys = {n.tag_key for n in ontology.nodes}
        domains = self.domains()
        ours = {d["name"] for k, d in domains.items() if k in tag_keys}
        uc: dict[str, set[str] | None] = {}
        for node in ontology.subdomains:
            for asset in node.assets:
                if asset.kind == "uc" and asset.uc_name(ctx.names) not in uc:
                    uc[asset.uc_name(ctx.names)] = self.uc_tags(asset.uc_name(ctx.names))
        ws = {a.ref: self.ws_tags(WORKSPACE_TYPES[a.kind], ctx.workspace_ids[a.ref])
              for n in ontology.subdomains for a in n.assets if a.ref in ctx.workspace_ids}
        return Live(tag_policies=self.tag_policies(), domains=domains, pages=self.pages(ours) if ours else {},
                    uc_tags=uc, ws_tags=ws)

    # --- writes (the Executor protocol in tools.lib.ontology) ----------------------------------------------------
    def create_tag_policy(self, tag_key: str, description: str) -> dict:
        return self.cli.json(["tag-policies", "create-tag-policy", tag_key, "--description", description])

    def create_domain(self, node: Node, parent_id: str | None) -> dict:
        args = ["domains", "create-domain", node.tag_key, "--subtitle", node.subtitle, "--description",
                node.description, "--draft"]
        if parent_id:
            args += ["--parent-domain-id", parent_id]
        return self.cli.json(args)

    def update_domain(self, name: str, node: Node, parent_id: str | None, fields: list[str]) -> dict:
        body = {"tag_key": node.tag_key, "subtitle": node.subtitle, "description": node.description}
        if parent_id:
            body["parent_domain_id"] = parent_id
        return self.cli.json(["domains", "update-domain", name, ",".join(fields), "--json", json.dumps(body)])

    def publish_domain(self, name: str, node: Node) -> dict:
        return self.cli.json(["domains", "update-domain", name, "draft", "--json",
                              json.dumps({"tag_key": node.tag_key, "draft": False})])

    def tag_uc(self, full_name: str, tag_key: str) -> None:
        self.cli.json(["entity-tag-assignments", "create", full_name, tag_key, "tables"])

    def tag_workspace(self, entity_type: str, entity_id: str, ref: str, tag_key: str) -> None:
        self.cli.json(["workspace-entity-tag-assignments", "create-tag-assignment", entity_type, entity_id, tag_key])

    def create_page(self, payload: dict) -> dict:
        return self.cli.api("post", PAGES, payload)

    def update_page(self, name: str, payload: dict, fields: list[str]) -> dict:
        return self.cli.api("patch", f"/api/2.0/knowledge/{name}?update_mask={','.join(fields)}",
                            {k: payload[k] for k in fields})

    def publish_page(self, name: str) -> dict:
        return self.cli.api("patch", f"/api/2.0/knowledge/{name}?update_mask=state", {"state": "PUBLISHED"})
