from pathlib import Path

import pytest

from tools.lib.contract import load_contract
from tools.lib.ontology import (BANNER, DEFAULT_DOMAINS, OntologyError, check_coverage, load_domains, load_ontology,
                                load_pages, parse_asset, render_body)

NAMES = {"catalog": "dev_gold", "mart": "mart", "common": "common", "semantic": "semantic"}

DOMAINS = """\
version: 1
domains:
  - key: revenue
    tag_key: ESA Revenue Management
    subtitle: Revenue.
    description: Revenue domain.
    subdomains:
      - key: resstay
        name: ResStay
        subtitle: Stays.
        description: Stay revenue.
        assets: [mart.fact_actual_stay, semantic.resstay_metrics, genie:resstay_revenue]
"""

PAGE = """\
---
display_name: Average Daily Rate (ADR)
subdomain: resstay
synonyms: [average daily rate, ADR]
description: Room revenue per consumed room night.
assumption: true
mentions: [mart.fact_actual_stay]
requires: []
---
## Definition
ADR divides room revenue by room nights in `{{catalog}}.{{mart}}.fact_actual_stay`.
"""

AGENT_PAGE = """\
---
display_name: ResStay Revenue Q&A
subdomain: resstay
synonyms: [revenue agent]
description: Ask revenue questions.
assumption: false
mentions: [genie:resstay_revenue]
requires: [genie:resstay_revenue]
---
## Definition
[Open the agent]({{url_genie_resstay_revenue}}).
"""


def write(tmp_path: Path, domains: str = DOMAINS, pages: dict[str, str] | None = None) -> tuple[Path, Path]:
    (tmp_path / "domains.yml").write_text(domains)
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    for name, text in (pages if pages is not None else {"resstay--adr.md": PAGE}).items():
        (pages_dir / name).write_text(text)
    return tmp_path / "domains.yml", pages_dir


def test_subdomain_tag_keys_join_parent_and_name(tmp_path):
    ontology = load_ontology(*write(tmp_path))
    assert [(n.key, n.tag_key, n.parent) for n in ontology.nodes] == [
        ("revenue", "ESA Revenue Management", None), ("resstay", "ESA Revenue Management/ResStay", "revenue")]
    assert [a.ref for a in ontology.node("resstay").assets] == [
        "mart.fact_actual_stay", "semantic.resstay_metrics", "genie:resstay_revenue"]


@pytest.mark.parametrize("old, new, message", [
    ("tag_key: ESA Revenue Management", "tag_key: Revenue Management", "must start with 'ESA '"),
    ("name: ResStay", "name: Res/Stay", "must not contain '/'"),
    ("assets: [mart.fact_actual_stay,", "assets: [raw.fact_actual_stay,", "invalid asset reference"),
    ("    subtitle: Revenue.", "    subtitle: " + "x" * 281, "subtitle is longer than 280"),
    ("      - key: resstay", "      - key: revenue", "duplicate key"),
    ("        name: ResStay", "        name: ResStay\n        icon: hotel", "unknown fields"),
])
def test_domain_file_problems_are_reported(tmp_path, old, new, message):
    assert old in DOMAINS
    with pytest.raises(OntologyError, match=message):
        load_domains(write(tmp_path, DOMAINS.replace(old, new), pages={})[0])


@pytest.mark.parametrize("old, new, message", [
    ("subdomain: resstay", "subdomain: revenue", "not a subdomain"),
    ("description: Room revenue per consumed room night.", "description: " + "x" * 281, "longer than 280"),
    ("mentions: [mart.fact_actual_stay]", "mentions: [mart.dim_los]", "does not appear in the body"),
    ("assumption: true\n", "", "missing fields"),
    ("## Definition", "# ADR\n## Definition", "H1"),
    ("`{{catalog}}.{{mart}}.fact_actual_stay`.", "`{{catalog}}.{{mart}}.fact_actual_stay` {{url_genie_x}}.",
     "placeholders not allowed"),
])
def test_page_problems_are_reported(tmp_path, old, new, message):
    assert old in PAGE
    domains, pages = write(tmp_path, pages={"resstay--adr.md": PAGE.replace(old, new)})
    with pytest.raises(OntologyError, match=message):
        load_pages(pages, load_domains(domains))


def test_page_file_name_must_start_with_its_subdomain(tmp_path):
    domains, pages = write(tmp_path, pages={"booking--adr.md": PAGE})
    with pytest.raises(OntologyError, match="file name must start with 'resstay--'"):
        load_pages(pages, load_domains(domains))


def test_workspace_mentions_must_be_required(tmp_path):
    text = AGENT_PAGE.replace("requires: [genie:resstay_revenue]", "requires: []")
    domains, pages = write(tmp_path, pages={"resstay--agent.md": text})
    with pytest.raises(OntologyError, match="placeholders not allowed"):
        load_pages(pages, load_domains(domains))


def test_render_body_fills_names_urls_and_the_assumption_banner(tmp_path):
    ontology = load_ontology(*write(tmp_path, pages={"resstay--adr.md": PAGE, "resstay--agent.md": AGENT_PAGE}))
    adr, agent = sorted(ontology.pages, key=lambda p: p.slug)
    body = render_body(adr, NAMES, {})
    assert body.startswith(BANNER) and "`dev_gold.mart.fact_actual_stay`" in body and "{{" not in body
    urls = {"genie:resstay_revenue": "https://host/genie/rooms/abc"}
    assert render_body(agent, NAMES, urls) == "## Definition\n[Open the agent](https://host/genie/rooms/abc).\n"
    with pytest.raises(OntologyError, match="no URL for genie:resstay_revenue"):
        render_body(agent, NAMES, {})


def test_asset_references_parse():
    assert parse_asset("common.dim_date").uc_name(NAMES) == "dev_gold.common.dim_date"
    genie = parse_asset("genie:property_operations")
    assert (genie.kind, genie.name, genie.url_placeholder) == ("genie", "property_operations",
                                                               "url_genie_property_operations")


def test_repo_domains_assign_every_contract_object_once_per_subdomain():
    nodes = load_domains(DEFAULT_DOMAINS)
    check_coverage(nodes, load_contract())
    assert {n.tag_key for n in nodes if n.parent is None} == {"ESA Revenue Management", "ESA Property Operations"}
    assert sorted(n.key for n in nodes if n.parent) == ["booking", "occupancy", "portfolio", "resstay"]


def test_coverage_reports_unassigned_and_unknown_objects(tmp_path):
    nodes = load_domains(write(tmp_path, pages={})[0])
    with pytest.raises(OntologyError, match=r"not assigned to any subdomain: .*dim_los") as error:
        check_coverage(nodes, load_contract())
    assert "fact_actual_stay" not in str(error.value).split("not assigned")[1]


def test_repo_pages_load_and_cover_every_subdomain():
    ontology = load_ontology()
    assert len(ontology.pages) == 28
    assert {p.subdomain for p in ontology.pages} == {n.key for n in ontology.subdomains}
    workspace_pages = {p.slug: [a.ref for a in p.requires] for p in ontology.pages if p.requires}
    assert workspace_pages == {
        "resstay--resstay-dashboard": ["dashboard:resstay"], "resstay--resstay-revenue-agent": ["genie:resstay_revenue"],
        "occupancy--occupancy-trend-dashboard": ["dashboard:occupancy"],
        "occupancy--property-operations-agent": ["genie:property_operations"]}
    for page in ontology.pages:
        assert "dev_gold" not in page.body and "{{" not in render_body(page, NAMES, {
            a.ref: "https://host/x" for a in page.requires})
