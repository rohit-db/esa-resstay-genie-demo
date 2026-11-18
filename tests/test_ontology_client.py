import json

import pytest

from tools.lib.dbcli import CliError
from tools.lib.ontology import Node
from tools.lib.ontology_client import OntologyClient

SUB = Node("resstay", "ESA Revenue Management/ResStay", "Stays.", "Stay revenue.", parent="revenue")


def test_reads_keep_only_esa_objects_and_page_through_all_pages(fake_cli):
    pages = {
        "/api/2.0/knowledge/pages?page_size=100": {"pages": [{"name": "pages/a", "domain": "domains/ours"},
                                                              {"name": "pages/b", "domain": "domains/theirs"}],
                                                    "next_page_token": "t/1"},
        "/api/2.0/knowledge/pages?page_size=100&page_token=t%2F1": {"pages": [{"name": "pages/c",
                                                                               "domain": "domains/ours"}]},
    }
    cli = fake_cli({
        ("tag-policies", "list-tag-policies"): [{"id": "1", "tag_key": "ESA Revenue Management"},
                                                 {"id": "2", "tag_key": "cesar_budget"}],
        ("domains", "list-domains"): [{"tag_key": "ESA Revenue Management", "name": "domains/ours"},
                                      {"tag_key": "Brickcorp", "name": "domains/theirs"}],
        ("get",): lambda args: pages.get(args[1]) or {"name": args[1].rsplit("/knowledge/", 1)[1], "body": "x"},
    })
    client = OntologyClient(cli)
    assert list(client.tag_policies()) == ["ESA Revenue Management"]
    assert list(client.domains()) == ["ESA Revenue Management"]
    assert sorted(client.pages({"domains/ours"})) == ["pages/a", "pages/c"]
    assert ("api", ("get", "/api/2.0/knowledge/pages/b", "")) not in cli.calls


def test_missing_tables_read_as_none_but_permission_errors_raise(fake_cli):
    def tags(args):
        if args[3].endswith("absent"):
            raise CliError(args, 1, "Error: Table 'dev_gold.semantic.absent' does not exist.")
        if args[3].endswith("locked"):
            raise CliError(args, 1, "Error: PERMISSION_DENIED: User does not have USE SCHEMA")
        return [{"tag_key": "ESA Revenue Management/ResStay"}]
    client = OntologyClient(fake_cli({("entity-tag-assignments", "list"): tags}))
    assert client.uc_tags("dev_gold.mart.fact_actual_stay") == {"ESA Revenue Management/ResStay"}
    assert client.uc_tags("dev_gold.semantic.absent") is None
    with pytest.raises(CliError):
        client.uc_tags("dev_gold.mart.locked")


def test_domain_writes_create_drafts_and_publish_with_an_explicit_false(fake_cli):
    cli = fake_cli({("domains", "create-domain"): {"domain_id": "d2", "name": "domains/d2"},
                    ("domains", "update-domain"): {}})
    client = OntologyClient(cli)
    client.create_domain(SUB, "d1")
    args = cli.calls[-1][1]
    assert args[:3] == ("domains", "create-domain", SUB.tag_key) and "--draft" in args
    assert args[args.index("--parent-domain-id") + 1] == "d1"
    client.publish_domain("domains/d2", SUB)
    args = cli.calls[-1][1]
    assert args[:4] == ("domains", "update-domain", "domains/d2", "draft")
    assert json.loads(args[args.index("--json") + 1]) == {"tag_key": SUB.tag_key, "draft": False}


def test_tag_and_page_writes(fake_cli):
    cli = fake_cli({("entity-tag-assignments", "create"): {}, ("post",): {"name": "pages/new"}, ("patch",): {}})
    client = OntologyClient(cli)
    client.tag_uc("dev_gold.mart.dim_los", SUB.tag_key)
    assert cli.calls[-1][1] == ("entity-tag-assignments", "create", "dev_gold.mart.dim_los", SUB.tag_key, "tables")
    assert client.create_page({"display_name": "ADR"}) == {"name": "pages/new"}
    client.update_page("pages/new", {"display_name": "ADR", "body": "b", "synonyms": []}, ["body"])
    assert cli.calls[-1][1] == ("patch", "/api/2.0/knowledge/pages/new?update_mask=body", json.dumps({"body": "b"}))
