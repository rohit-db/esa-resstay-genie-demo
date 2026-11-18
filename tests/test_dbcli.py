import json
import subprocess

import pytest

from tools.lib.dbcli import Cli, CliError, GuardError, assert_host, is_missing, scrubbed_env


def runner_returning(stdout="", returncode=0, stderr="", seen=None):
    def run(argv, env, timeout, cwd):
        if seen is not None:
            seen.append((argv, env))
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)
    return run


def test_profile_is_always_explicit_and_env_is_scrubbed(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "https://wrong.example.com")
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", "/tmp/cfg")
    seen = []
    cli = Cli("esa-resstay-demo", runner=runner_returning('{"a": 1}', seen=seen))
    assert cli.json(["catalogs", "get", "dev_gold"]) == {"a": 1}
    argv, env = seen[0]
    assert argv == ["databricks", "catalogs", "get", "dev_gold", "--output", "json", "--profile", "esa-resstay-demo"]
    assert "DATABRICKS_HOST" not in env and env["DATABRICKS_CONFIG_FILE"] == "/tmp/cfg"
    assert "DATABRICKS_TOKEN" not in scrubbed_env({"DATABRICKS_TOKEN": "x", "PATH": "/bin"})


def test_overriding_the_profile_or_host_is_refused():
    cli = Cli("esa-resstay-demo", runner=runner_returning())
    for bad in (["--profile", "other"], ["-p", "x"], ["--host=https://x"], ["--token", "y"]):
        with pytest.raises(ValueError, match="not allowed"):
            cli.run(["catalogs", "list", *bad])
    with pytest.raises(ValueError, match="invalid profile"):
        Cli("bad profile")


def test_errors_and_absence_are_distinguished():
    cli = Cli("p", runner=runner_returning(returncode=1, stderr="Error: Catalog 'dev_gold' does not exist."))
    with pytest.raises(CliError) as error:
        cli.run(["catalogs", "get", "dev_gold"])
    assert is_missing(error.value)
    denied = CliError(["x"], 1, "PERMISSION_DENIED: not found or permission denied")
    assert not is_missing(denied)


def test_host_guard():
    cli = Cli("p", runner=runner_returning('{"details": {"host": "https://a.cloud.databricks.com/"}}'))
    assert assert_host(cli, "https://A.cloud.databricks.com") == "https://a.cloud.databricks.com"
    with pytest.raises(GuardError, match="expects"):
        assert_host(cli, "https://b.cloud.databricks.com")


EXPIRED_OAUTH_DESCRIBE = json.dumps({   # what `databricks auth describe --output json` prints (exit 0) for a dead OAuth login
    "status": "error", "error": {},
    "details": {"auth_type": "databricks-cli", "host": "https://fe-sandbox-esa-resstay-demo.cloud.databricks.com"},
})


def test_host_refuses_a_profile_whose_login_has_expired():
    cli = Cli("esa-resstay-demo", runner=runner_returning(EXPIRED_OAUTH_DESCRIBE))
    with pytest.raises(GuardError, match="databricks auth login --host https://fe-sandbox-esa-resstay-demo.cloud.databricks.com "
                                         "--profile esa-resstay-demo"):
        cli.host()
