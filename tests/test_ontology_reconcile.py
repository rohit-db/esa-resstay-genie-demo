import copy
import itertools

import pytest

from tools.lib.ontology import CollisionError, Context, Live, plan, reconcile
from tests.test_ontology_model import AGENT_PAGE, PAGE, write
from tools.lib.ontology import load_ontology

NAMES = {"catalog": "dev_gold", "mart": "mart", "common": "common", "semantic": "semantic"}
STAY, METRICS = "dev_gold.mart.fact_actual_stay", "dev_gold.semantic.resstay_metrics"


class FakeAccount:
    """In-memory governed tags, domains, tags, and Pages; implements both the reads and the writes."""

    def __init__(self):
        self.ids = itertools.count(1)
        self.tag_policies, self.domains, self.pages = {}, {}, {}
        self.uc_tags = {STAY: set()}          # resstay_metrics does not exist yet
        self.ws_tags = {}
        self.writes = []

    def live(self, workspace_ids=()):
        return Live(tag_policies=copy.deepcopy(self.tag_policies), domains=copy.deepcopy(self.domains),
                    pages=copy.deepcopy(self.pages), uc_tags=copy.deepcopy(self.uc_tags),
                    ws_tags={ref: set(self.ws_tags.get(ref, set())) for ref in workspace_ids})

    def create_tag_policy(self, tag_key, description):
        self.writes.append(("create_tag_policy", tag_key))
        record = self.tag_policies[tag_key] = {"id": str(next(self.ids)), "tag_key": tag_key}
        return record

    def create_domain(self, node, parent_id):
        assert node.tag_key in self.tag_policies, "domains need their governed tag first"
        self.writes.append(("create_domain", node.tag_key, parent_id))
        domain_id = f"d{next(self.ids)}"
        record = {"domain_id": domain_id, "name": f"domains/{domain_id}", "tag_key": node.tag_key,
                  "subtitle": node.subtitle, "description": node.description, "draft": True, "effective_draft": True}
        if parent_id:
            record["parent_domain_id"] = parent_id
        self.domains[node.tag_key] = record
        return record

    def update_domain(self, name, node, parent_id, fields):
        self.writes.append(("update_domain", node.tag_key, tuple(fields)))
        record = self.domains[node.tag_key]
        record.update(subtitle=node.subtitle, description=node.description)

    def publish_domain(self, name, node):
        self.writes.append(("publish_domain", node.tag_key))
        self.domains[node.tag_key].update(draft=False, effective_draft=False)

    def tag_uc(self, full_name, tag_key):
        self.writes.append(("tag_uc", full_name, tag_key))
        self.uc_tags[full_name].add(tag_key)

    def tag_workspace(self, entity_type, entity_id, ref, tag_key):
        self.writes.append(("tag_workspace", entity_type, entity_id, tag_key))
        self.ws_tags.setdefault(ref, set()).add(tag_key)

    def create_page(self, payload):
        self.writes.append(("create_page", payload["display_name"]))
        name = f"pages/p{next(self.ids)}"
        # Live behaviour: the Pages API stores synonyms sorted.
        record = self.pages[name] = dict(payload, name=name, state="DRAFT", synonyms=sorted(payload["synonyms"]))
        return record

    def update_page(self, name, payload, fields):
        self.writes.append(("update_page", payload["display_name"], tuple(fields)))
        self.pages[name].update({k: payload[k] for k in fields})

    def publish_page(self, name):
        self.writes.append(("publish_page", self.pages[name]["display_name"]))
        self.pages[name]["state"] = "PUBLISHED"


@pytest.fixture
def ontology(tmp_path):
    return load_ontology(*write(tmp_path, pages={"resstay--adr.md": PAGE, "resstay--agent.md": AGENT_PAGE}))


def context(**workspace_ids):
    refs = {f"genie:{k}": v for k, v in workspace_ids.items()}
    return Context(names=NAMES, workspace_ids=refs, urls={r: f"https://host/genie/rooms/{v}" for r, v in refs.items()})


def test_first_apply_creates_everything_in_order_and_records_ids(ontology):
    account, records, saves = FakeAccount(), {}, []
    result = reconcile(ontology, account.live(), records, context(), account, save=lambda: saves.append(1))
    ops = [w[0] for w in account.writes]
    assert ops == ["create_tag_policy", "create_tag_policy", "create_domain", "create_domain", "tag_uc",
                   "create_page", "publish_page", "publish_domain", "publish_domain"]
    parent_id = records["domains"]["revenue"]["domain_id"]
    assert account.writes[3] == ("create_domain", "ESA Revenue Management/ResStay", parent_id)
    assert account.writes[-2:] == [("publish_domain", "ESA Revenue Management/ResStay"),
                                   ("publish_domain", "ESA Revenue Management")]
    assert set(records["pages"]) == {"resstay--adr"} and len(saves) >= 5
    assert any("semantic.resstay_metrics" in p for p in result.pending)
    assert any("ResStay Revenue Q&A" in p and "genie:resstay_revenue" in p for p in result.pending)
    assert not result.problems


def test_second_run_changes_nothing(ontology):
    account, records = FakeAccount(), {}
    reconcile(ontology, account.live(), records, context(), account)
    account.writes.clear()
    result = reconcile(ontology, account.live(), records, context(), account)
    assert account.writes == [] and result.actions == []


def test_plan_reports_actions_without_writing_or_recording(ontology):
    account, records = FakeAccount(), {}
    result = plan(ontology, account.live(), records, context())
    assert account.writes == [] and records == {}
    assert [a.op for a in result.actions][:4] == ["create_tag_policy", "create_tag_policy", "create_domain",
                                                  "create_domain"]
    assert ("create_page", "Average Daily Rate (ADR)") in [(a.op, a.target) for a in result.actions]


@pytest.mark.parametrize("seed", ["tag_policy", "domain", "page"])
def test_refuses_to_adopt_objects_it_did_not_create(ontology, seed):
    account, records = FakeAccount(), {}
    reconcile(ontology, account.live(), records, context(), account)
    stranger = FakeAccount()
    if seed == "tag_policy":
        stranger.tag_policies = copy.deepcopy(account.tag_policies)
        stranger_records = {}
    elif seed == "domain":
        stranger.tag_policies, stranger.domains = copy.deepcopy(account.tag_policies), copy.deepcopy(account.domains)
        stranger_records = {"tag_policies": copy.deepcopy(records["tag_policies"])}
    else:
        stranger.tag_policies, stranger.domains = copy.deepcopy(account.tag_policies), copy.deepcopy(account.domains)
        stranger.pages = copy.deepcopy(account.pages)
        stranger_records = {k: copy.deepcopy(records[k]) for k in ("tag_policies", "domains")}
    with pytest.raises(CollisionError, match="did not create"):
        reconcile(ontology, stranger.live(), stranger_records, context(), stranger)
    assert [w for w in stranger.writes if w[0].startswith("create")] == []


def test_workspace_assets_and_their_pages_follow_once_deployed(ontology):
    account, records = FakeAccount(), {}
    reconcile(ontology, account.live(), records, context(), account)
    account.writes.clear()
    ctx = context(resstay_revenue="space1")
    result = reconcile(ontology, account.live(ctx.workspace_ids), records, ctx, account)
    assert ("tag_workspace", "geniespaces", "space1", "ESA Revenue Management/ResStay") in account.writes
    assert ("create_page", "ResStay Revenue Q&A") in account.writes
    agent = next(p for p in account.pages.values() if p["display_name"] == "ResStay Revenue Q&A")
    assert "https://host/genie/rooms/space1" in agent["body"] and agent["state"] == "PUBLISHED"
    assert not any("genie:resstay_revenue" in p for p in result.pending)


def test_changes_to_domains_and_pages_become_updates(ontology, tmp_path):
    account, records = FakeAccount(), {}
    reconcile(ontology, account.live(), records, context(), account)
    account.writes.clear()
    account.domains["ESA Revenue Management"]["subtitle"] = "edited in the UI"
    name = records["pages"]["resstay--adr"]["name"]
    account.pages[name]["body"] = "edited in the UI"
    reconcile(ontology, account.live(), records, context(), account)
    assert account.writes == [("update_domain", "ESA Revenue Management", ("subtitle",)),
                              ("update_page", "Average Daily Rate (ADR)", ("body",))]


def test_missing_mart_tables_are_problems_and_missing_metric_views_are_pending(ontology):
    account, records = FakeAccount(), {}
    account.uc_tags = {}
    result = reconcile(ontology, account.live(), records, context(), account)
    assert any(STAY in p for p in result.problems)
    assert any(METRICS in p for p in result.pending)
