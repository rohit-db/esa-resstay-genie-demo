from datetime import date

import pytest

import tools.deploy as deploy_module
from tools.deploy import DeployError, deploy, parse_args
from tools.lib.dbcli import GuardError


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(deploy_module, "ensure_catalog", lambda cli, m, name, user: seen.setdefault("catalog", name))
    monkeypatch.setattr(deploy_module, "render", lambda target: seen.setdefault("rendered", target))
    monkeypatch.setattr(deploy_module, "run_validation", lambda cli, m, cfg: {"status": "pass", "target": "demo", "sections": {}})
    from tools.lib.ontology import Result
    monkeypatch.setattr(deploy_module, "apply_ontology", lambda cli, m, cfg, host: seen.setdefault("ontology", host) and Result())
    return seen


def handlers():
    summary = {"resources": {"sql_warehouses": {"esa_demo_wh": {"id": "wh1"}},
                             "jobs": {"setup": {"id": 11}, "nightly_refresh": {"id": 12}},
                             "genie_spaces": {"resstay_revenue": {"id": "g1"}, "property_operations": {"id": "g2"}},
                             "dashboards": {"resstay": {"id": "d1"}, "occupancy": {"id": "d2"}}}}
    return {("bundle", "deploy"): "", ("bundle", "summary"): summary, ("bundle", "run"): ""}


def test_first_deploy_anchors_stories_and_runs_every_step(stubbed, tmp_path, fake_cli):
    cli = fake_cli(handlers())
    args = parse_args(["--profile", "esa-resstay-demo", "--as-of", "2026-11-16", "--state", str(tmp_path / "m.json")])
    assert deploy(args, cli) == 0
    run_calls = [args for kind, args in cli.calls if kind == "run"]
    assert run_calls[0] == ("bundle", "deploy", "--target", "demo", "--var", "story_anchor_date=2026-11-16",
                            "--var", "nightly_pause_status=PAUSED")
    assert run_calls[1] == ("bundle", "run", "setup", "--target", "demo", "--params", "as_of_date=2026-11-16")
    assert stubbed == {"catalog": "dev_gold", "rendered": "demo",
                       "ontology": "https://fe-sandbox-esa-resstay-demo.cloud.databricks.com"}
    import json
    manifest = json.loads((tmp_path / "m.json").read_text())
    assert manifest["story_anchor_date"] == "2026-11-16" and manifest["bundle"]["warehouse_id"] == "wh1"
    assert manifest["bundle"]["genie_spaces"] == {"resstay_revenue": "g1", "property_operations": "g2"}
    assert manifest["bundle"]["dashboards"] == {"resstay": "d1", "occupancy": "d2"}
    assert manifest["runs"][-1]["status"] == "SUCCESS"


def test_later_deploys_keep_the_original_anchor(stubbed, tmp_path, fake_cli):
    state = str(tmp_path / "m.json")
    deploy(parse_args(["--profile", "esa-resstay-demo", "--as-of", "2026-11-16", "--state", state]), fake_cli(handlers()))
    cli = fake_cli(handlers())
    deploy(parse_args(["--profile", "esa-resstay-demo", "--as-of", "2026-11-20", "--nightly", "on", "--state", state]), cli)
    first = [args for kind, args in cli.calls if kind == "run"][0]
    assert "story_anchor_date=2026-11-16" in first and "nightly_pause_status=UNPAUSED" in first
    with pytest.raises(DeployError, match="before the recorded story anchor"):
        deploy(parse_args(["--profile", "esa-resstay-demo", "--as-of", "2026-11-10", "--state", state]), fake_cli(handlers()))


def test_wrong_workspace_is_refused_before_any_change(stubbed, tmp_path, fake_cli):
    cli = fake_cli(handlers(), host="https://someone-else.cloud.databricks.com")
    with pytest.raises(GuardError):
        deploy(parse_args(["--profile", "esa-resstay-demo", "--state", str(tmp_path / "m.json")]), cli)
    assert not (tmp_path / "m.json").exists() and stubbed == {}


def test_esa_target_is_not_deployable_yet():
    with pytest.raises(SystemExit):
        parse_args(["--profile", "x", "--target", "esa"])


def test_a_deploy_long_after_the_anchor_is_refused(stubbed, tmp_path, fake_cli):
    state = str(tmp_path / "m.json")
    deploy(parse_args(["--profile", "esa-resstay-demo", "--as-of", "2026-11-16", "--state", state]), fake_cli(handlers()))
    with pytest.raises(DeployError, match="more than 30 days after the story anchor"):
        deploy(parse_args(["--profile", "esa-resstay-demo", "--as-of", "2026-12-17", "--state", state]), fake_cli(handlers()))


def test_a_failed_setup_job_is_recorded_and_raised(stubbed, tmp_path, fake_cli):
    from tools.lib.dbcli import CliError

    def failing_run(args):
        raise CliError(list(args), 1, "Task data_checks failed: Data check revenue_rules failed: 3 violation(s)")
    cli = fake_cli({**handlers(), ("bundle", "run"): failing_run})
    with pytest.raises(CliError, match="revenue_rules"):
        deploy(parse_args(["--profile", "esa-resstay-demo", "--as-of", "2026-11-16", "--state", str(tmp_path / "m.json")]), cli)
    import json
    run = json.loads((tmp_path / "m.json").read_text())["runs"][-1]
    assert run["status"] == "FAILED" and "revenue_rules" in run["error"]


def test_an_expired_login_changes_nothing(stubbed, tmp_path):
    """Real Cli, real `auth describe` payload for a dead OAuth login (it exits 0 with status=error)."""
    import subprocess
    from tools.lib.dbcli import Cli
    describe = '{"status": "error", "error": {}, "details": {"host": "https://fe-sandbox-esa-resstay-demo.cloud.databricks.com"}}'
    calls = []

    def runner(argv, env, timeout, cwd):
        calls.append(argv[1:3])
        return subprocess.CompletedProcess(argv, 0, describe, "")
    with pytest.raises(GuardError, match="databricks auth login"):
        deploy(parse_args(["--profile", "esa-resstay-demo", "--state", str(tmp_path / "m.json")]), Cli("esa-resstay-demo", runner=runner))
    assert calls == [["auth", "describe"]] and not (tmp_path / "m.json").exists() and stubbed == {}


def test_a_failed_identity_call_changes_nothing_and_points_at_login(stubbed, tmp_path):
    import subprocess
    from tools.lib.dbcli import Cli
    describe = '{"status": "success", "details": {"host": "https://fe-sandbox-esa-resstay-demo.cloud.databricks.com"}}'

    def runner(argv, env, timeout, cwd):
        if argv[1:3] == ["auth", "describe"]:
            return subprocess.CompletedProcess(argv, 0, describe, "")
        return subprocess.CompletedProcess(argv, 1, "", "Error: Invalid access token. [ReqId: x]")
    with pytest.raises(GuardError, match="Invalid access token.*databricks auth login"):
        deploy(parse_args(["--profile", "esa-resstay-demo", "--state", str(tmp_path / "m.json")]), Cli("esa-resstay-demo", runner=runner))
    assert not (tmp_path / "m.json").exists() and stubbed == {}


def test_missing_bundle_ids_stop_before_the_setup_job(stubbed, tmp_path, fake_cli):
    cli = fake_cli({**handlers(), ("bundle", "summary"): {"resources": {"jobs": {}}}})
    with pytest.raises(DeployError, match="missing the warehouse or job IDs"):
        deploy(parse_args(["--profile", "esa-resstay-demo", "--as-of", "2026-11-16", "--state", str(tmp_path / "m.json")]), cli)
    assert not any(args[:2] == ("bundle", "run") for kind, args in cli.calls)
