from tools.demo_links import links


def test_links_come_from_the_manifest():
    manifest = {"host": "https://h/", "catalog": {"name": "dev_gold"},
                "bundle": {"dashboards": {"resstay": "d1"}, "genie_spaces": {"resstay_revenue": "g1"}},
                "ontology": {"pages": {"resstay--adr": {"name": "pages/p1"}}}}
    out = dict(links(manifest))
    assert out["ResStay Dashboard"] == "https://h/sql/dashboardsv3/d1/published"
    assert out["Genie: ESA ResStay Revenue"] == "https://h/genie/rooms/g1"
    assert out["Page resstay--adr"] == "https://h/one/discover/pages/p1"
