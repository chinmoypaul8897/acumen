"""Config-loader tests -- the sizing guard, before and after OPEN-1.

CONTEXT 9 OPEN-1 said "code takes risk_per_trade as required config; no default". The trader
answered it in Round 3 (25-Jul-2026): risk per trade = 1000 rupees (QUESTIONS.md ROUND-3
RECEIPTS). The committed config now carries that amount, so the repo config RESOLVES to 1000
instead of blocking. The guard that protected real money while OPEN-1 was open is not deleted,
only re-pointed: a NULL value still raises, proved here on a synthetic config
(``test_a_null_risk_per_trade_still_blocks``), so a future config that loses the amount fails
loudly rather than sizing on a guess.

Every test that reads the repository's own config.yaml passes ``include_env=False``: a test
suite has no reason to pull the operator's live credentials into ``os.environ``
(REVIEW_0 finding F4). The one deliberate exception is
``test_env_values_never_reach_the_config_object``, whose whole subject IS the
``include_env=True`` path.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from acumen.config import (
    DEFAULT_CONFIG_PATH,
    Config,
    ConfigError,
    env_value,
    load_config,
    load_env,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_VALID = """
risk_per_trade: null
row_size: 24
paths:
  data_dir: data
"""


def _write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# --- the repository's own config.yaml -------------------------------------------------


def test_repo_config_loads() -> None:
    config = load_config(include_env=False)
    assert isinstance(config, Config)
    assert config.source == DEFAULT_CONFIG_PATH


def test_repo_config_resolves_risk_per_trade_to_the_trader_amount() -> None:
    """OPEN-1 RESOLVED (Round 3): the committed config carries the trader's 1000-rupee risk."""
    assert load_config(include_env=False).risk_per_trade == 1000


def test_repo_config_require_risk_per_trade_returns_the_trader_amount() -> None:
    """The sizing path now gets a real number, not a ConfigError (OPEN-1 resolved)."""
    assert load_config(include_env=False).require_risk_per_trade() == 1000


def test_repo_config_carries_the_context_row_size() -> None:
    """Row Size N comes from config, never a hardcoded constant (CONTEXT 3.3, OPEN-2)."""
    row_size = load_config(include_env=False).row_size
    assert isinstance(row_size, int)
    assert row_size == 24


def test_repo_config_paths_resolve_absolute_under_the_repo() -> None:
    paths = load_config(include_env=False).paths
    assert set(paths) == {"data_dir", "cache_dir", "logs_dir"}
    for name, resolved in paths.items():
        assert resolved.is_absolute(), name
        assert resolved.parent == REPO_ROOT, name


# --- OPEN-1: a null amount still blocks (regression kept after the resolution) ----------


def test_a_null_risk_per_trade_still_blocks(tmp_path: Path) -> None:
    """OPEN-1 is resolved in the repo config, but the GUARD must survive: a null amount
    (a future config that loses the value) still refuses to size, naming OPEN-1."""
    path = _write_config(tmp_path, "risk_per_trade: null\nrow_size: 24\npaths:\n  data_dir: data\n")
    config = load_config(path, include_env=False)
    assert config.risk_per_trade is None
    with pytest.raises(ConfigError) as excinfo:
        config.require_risk_per_trade()
    message = str(excinfo.value)
    assert "OPEN-1" in message
    assert "BLOCKED" in message
    assert "risk_per_trade" in message


def test_require_risk_per_trade_returns_the_amount_once_open_1_is_answered(
    tmp_path: Path,
) -> None:
    path = _write_config(tmp_path, "risk_per_trade: 500\nrow_size: 24\npaths:\n  data_dir: data\n")
    assert load_config(path, include_env=False).require_risk_per_trade() == 500


@pytest.mark.parametrize("value", ["0", "-1", "-0.5"])
def test_non_positive_risk_per_trade_is_rejected(tmp_path: Path, value: str) -> None:
    path = _write_config(
        tmp_path, f"risk_per_trade: {value}\nrow_size: 24\npaths:\n  data_dir: data\n"
    )
    with pytest.raises(ConfigError, match="risk_per_trade"):
        load_config(path, include_env=False)


@pytest.mark.parametrize("value", ["'500'", "true", "[500]"])
def test_non_numeric_risk_per_trade_is_rejected(tmp_path: Path, value: str) -> None:
    path = _write_config(
        tmp_path, f"risk_per_trade: {value}\nrow_size: 24\npaths:\n  data_dir: data\n"
    )
    with pytest.raises(ConfigError, match="risk_per_trade"):
        load_config(path, include_env=False)


# --- structural validation -------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "-3", "'24'", "24.5", "true"])
def test_bad_row_size_is_rejected(tmp_path: Path, value: str) -> None:
    path = _write_config(
        tmp_path, f"risk_per_trade: null\nrow_size: {value}\npaths:\n  data_dir: data\n"
    )
    with pytest.raises(ConfigError, match="row_size"):
        load_config(path, include_env=False)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    """A typo must fail loudly instead of silently falling back to a default."""
    path = _write_config(tmp_path, _VALID + "rowsize: 30\n")
    with pytest.raises(ConfigError, match="Unknown key"):
        load_config(path, include_env=False)


def test_missing_key_is_rejected(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "risk_per_trade: null\npaths:\n  data_dir: data\n")
    with pytest.raises(ConfigError, match="Missing key"):
        load_config(path, include_env=False)


@pytest.mark.parametrize("body", ["", "- 1\n- 2\n", "just a string\n"])
def test_non_mapping_config_is_rejected(tmp_path: Path, body: str) -> None:
    path = _write_config(tmp_path, body)
    with pytest.raises(ConfigError, match="mapping"):
        load_config(path, include_env=False)


def test_malformed_yaml_is_rejected(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "risk_per_trade: [unclosed\n")
    with pytest.raises(ConfigError, match="Could not parse"):
        load_config(path, include_env=False)


def test_missing_config_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml", include_env=False)


@pytest.mark.parametrize("body", ["paths: {}\n", "paths:\n  data_dir: ''\n", "paths: data\n"])
def test_bad_paths_block_is_rejected(tmp_path: Path, body: str) -> None:
    path = _write_config(tmp_path, "risk_per_trade: null\nrow_size: 24\n" + body)
    with pytest.raises(ConfigError, match="paths"):
        load_config(path, include_env=False)


def test_absolute_path_values_are_kept_as_given(tmp_path: Path) -> None:
    absolute = (tmp_path / "store").as_posix()
    path = _write_config(
        tmp_path, f"risk_per_trade: null\nrow_size: 24\npaths:\n  data_dir: {absolute}\n"
    )
    assert load_config(path, include_env=False).path("data_dir") == Path(absolute)


def test_unknown_path_key_raises_a_clear_error() -> None:
    with pytest.raises(ConfigError, match="Unknown path key"):
        load_config(include_env=False).path("nope_dir")


# --- secrets never leak (CLAUDE.md rule 4) ---------------------------------------------


def test_env_values_never_reach_the_config_object(tmp_path: Path) -> None:
    """The loader reads .env into the environment; Config itself must stay secret-free."""
    fake = "fake-token-for-this-test-only"
    env_file = tmp_path / ".env"
    env_file.write_text(f"ACUMEN_TEST_FAKE_TOKEN={fake}\n", encoding="utf-8")
    try:
        assert load_env(env_file) == env_file
        assert os.environ["ACUMEN_TEST_FAKE_TOKEN"] == fake
        config = load_config(_write_config(tmp_path, _VALID), include_env=True)
        assert fake not in repr(config)
        assert fake not in str(vars(config))
    finally:
        os.environ.pop("ACUMEN_TEST_FAKE_TOKEN", None)


def test_load_env_tolerates_a_missing_env_file(tmp_path: Path) -> None:
    assert load_env(tmp_path / ".env") is None


def test_missing_env_variable_error_names_the_variable_only() -> None:
    os.environ.pop("ACUMEN_TEST_ABSENT", None)
    with pytest.raises(ConfigError) as excinfo:
        env_value("ACUMEN_TEST_ABSENT")
    assert "ACUMEN_TEST_ABSENT" in str(excinfo.value)


def test_optional_env_variable_returns_none() -> None:
    os.environ.pop("ACUMEN_TEST_ABSENT", None)
    assert env_value("ACUMEN_TEST_ABSENT", required=False) is None
