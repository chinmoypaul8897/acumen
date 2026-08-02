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
from decimal import Decimal
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

#: Q-18 layer 1 (CLAUDE.md, "Data-store safety"): both store roots must be ABSOLUTE and
#: OUTSIDE the repository tree, so every synthetic config here builds one instead of typing
#: it -- "/acumen-test-data" is ROOTED but NOT absolute on Windows, where a path without a
#: drive letter is drive-relative. Nothing is created on disk: the loader only validates.
_OUTSIDE_ROOT = Path(REPO_ROOT.anchor) / "acumen-test-data"
_PATHS = (
    "paths:\n"
    f"  data_root: {_OUTSIDE_ROOT.as_posix()}\n"
    f"  cache_root: {(_OUTSIDE_ROOT / 'cache').as_posix()}\n"
)

#: The Q-20 pin (QUESTIONS.md, architect 02-Aug-2026) is a REQUIRED top-level key, so every
#: synthetic config below needs one. It rides with the paths block in ``_TAIL`` to keep the
#: twenty-odd one-line bodies below readable; the tests that are ABOUT the pin build their own.
_PIN = "instrument_master: OpenAPIScripMaster_2026-07-31.json\n"

_TAIL = _PIN + _PATHS

_VALID_HEAD = """
risk_per_trade: null
cost_per_trade: 100
initial_capital: 100000
row_size: 24
"""

_VALID = _VALID_HEAD + _TAIL


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


def test_repo_config_paths_resolve_absolute() -> None:
    paths = load_config(include_env=False).paths
    assert set(paths) == {"data_root", "cache_root", "logs_dir"}
    for name, resolved in paths.items():
        assert resolved.is_absolute(), name
    # logs/ is repo-local by design: it holds no store data and is regenerated freely.
    assert paths["logs_dir"].parent == REPO_ROOT


def test_the_repo_config_keeps_both_stores_outside_the_repository_tree() -> None:
    """Q-18 LAYER 1, on the committed config (CLAUDE.md, "Data-store safety").

    The 31-Jul-2026 incident destroyed both stores because they sat INSIDE the repo and
    ``git worktree remove --force`` reached them. Gitignoring them did not help -- every
    ignore rule was in force at the time. This asserts the layer on the config the operator
    actually runs, not just on the loader's ability to refuse a bad one.
    """
    paths = load_config(include_env=False).paths
    for name in ("data_root", "cache_root"):
        root = paths[name].resolve()
        assert not root.is_relative_to(REPO_ROOT), f"{name} is inside the repository tree: {root}"


@pytest.mark.parametrize(
    "root",
    ["store", "./store", "../acumen-data"],
)
def test_a_relative_store_root_is_refused(tmp_path: Path, root: str) -> None:
    """A relative root resolves against the config file's directory -- i.e. the repo. Refused."""
    path = _write_config(
        tmp_path,
        "risk_per_trade: 1000\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n"
        + _PIN
        + f"paths:\n  data_root: {root}\n"
        f"  cache_root: {(_OUTSIDE_ROOT / 'cache').as_posix()}\n",
    )
    with pytest.raises(ConfigError, match="ABSOLUTE|INSIDE the repository tree"):
        load_config(path, include_env=False)


def test_a_store_root_inside_the_repository_tree_is_refused(tmp_path: Path) -> None:
    """The Q-18 shape exactly: an absolute root that still lands under the repo root."""
    inside = (REPO_ROOT / "data").as_posix()
    path = _write_config(
        tmp_path,
        "risk_per_trade: 1000\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n"
        + _PIN
        + f"paths:\n  data_root: {inside}\n"
        f"  cache_root: {(_OUTSIDE_ROOT / 'cache').as_posix()}\n",
    )
    with pytest.raises(ConfigError) as excinfo:
        load_config(path, include_env=False)
    message = str(excinfo.value)
    assert "INSIDE the repository tree" in message
    assert "Q-18 layer 1" in message


def test_a_missing_store_root_is_refused_rather_than_defaulted(tmp_path: Path) -> None:
    """No default: a store nobody declared is a store nobody snapshots (CLAUDE.md rule 1)."""
    path = _write_config(
        tmp_path,
        "risk_per_trade: 1000\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n"
        + _PIN
        + f"paths:\n  cache_root: {(_OUTSIDE_ROOT / 'cache').as_posix()}\n",
    )
    with pytest.raises(ConfigError, match="data_root"):
        load_config(path, include_env=False)


# --- OPEN-1: a null amount still blocks (regression kept after the resolution) ----------


def test_a_null_risk_per_trade_still_blocks(tmp_path: Path) -> None:
    """OPEN-1 is resolved in the repo config, but the GUARD must survive: a null amount
    (a future config that loses the value) still refuses to size, naming OPEN-1."""
    path = _write_config(tmp_path, "risk_per_trade: null\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n" + _TAIL)
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
    path = _write_config(tmp_path, "risk_per_trade: 500\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n" + _TAIL)
    assert load_config(path, include_env=False).require_risk_per_trade() == 500


@pytest.mark.parametrize("value", ["0", "-1", "-0.5"])
def test_non_positive_risk_per_trade_is_rejected(tmp_path: Path, value: str) -> None:
    path = _write_config(
        tmp_path, f"risk_per_trade: {value}\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n" + _TAIL
    )
    with pytest.raises(ConfigError, match="risk_per_trade"):
        load_config(path, include_env=False)


@pytest.mark.parametrize("value", ["'500'", "true", "[500]"])
def test_non_numeric_risk_per_trade_is_rejected(tmp_path: Path, value: str) -> None:
    path = _write_config(
        tmp_path, f"risk_per_trade: {value}\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n" + _TAIL
    )
    with pytest.raises(ConfigError, match="risk_per_trade"):
        load_config(path, include_env=False)


# --- the money amounts in PAISE (chunk 8: the only door into CONTEXT 7-E11's domain) ----


def test_repo_config_carries_the_context_3_5_round_trip_cost() -> None:
    """CONTEXT 3.5 / R1-Q23: 100 rupees flat per round-trip trade, from config -- never a
    literal in the simulator."""
    assert load_config(include_env=False).cost_per_trade == 100


def test_the_repo_amounts_convert_to_the_exact_paise_the_simulator_sizes_with() -> None:
    """HAND-COMPUTED: 1000 rupees = 100,000 paise; 100 rupees = 10,000 paise (CONTEXT 7-E11).

    These two integers are the ONLY money inputs chunk 8's sizer takes, and both are ``int``
    -- a float here would put a float in the sizing divisor and in every PnL sum.
    """
    config = load_config(include_env=False)
    risk = config.require_risk_per_trade_paise()
    cost = config.cost_per_trade_paise()
    assert (risk, cost) == (100_000, 10_000)
    assert isinstance(risk, int) and not isinstance(risk, bool)
    assert isinstance(cost, int) and not isinstance(cost, bool)


def test_a_null_risk_per_trade_blocks_the_paise_accessor_too(tmp_path: Path) -> None:
    """The paise door goes through the same guard: a lost amount cannot size a trade."""
    path = _write_config(
        tmp_path, "risk_per_trade: null\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n" + _TAIL
    )
    with pytest.raises(ConfigError, match="OPEN-1"):
        load_config(path, include_env=False).require_risk_per_trade_paise()


def test_a_fractional_paisa_amount_is_refused(tmp_path: Path) -> None:
    """1000.005 rupees is 100,000.5 paise -- half a paisa of risk cannot exist (CONTEXT
    7-E11: prices and money are integer paise). Refused rather than rounded."""
    path = _write_config(
        tmp_path,
        "risk_per_trade: 1000.005\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n" + _TAIL,
    )
    config = load_config(path, include_env=False)
    with pytest.raises(ConfigError, match="whole number of paise"):
        config.require_risk_per_trade_paise()


def test_a_fractional_rupee_amount_that_is_whole_paise_is_accepted(tmp_path: Path) -> None:
    """12.34 rupees is exactly 1,234 paise. The conversion goes through Decimal, so the
    classic 12.34 * 100 == 1233.9999999999998 float trap cannot reach the sizer."""
    path = _write_config(
        tmp_path,
        "risk_per_trade: 1000\ncost_per_trade: 12.34\ninitial_capital: 100000\nrow_size: 24\n" + _TAIL,
    )
    assert load_config(path, include_env=False).cost_per_trade_paise() == 1234


def test_a_null_cost_per_trade_is_rejected_outright(tmp_path: Path) -> None:
    """Unlike risk_per_trade, no open item ever stood behind the cost: CONTEXT 3.5 states it,
    so a null is a config that LOST a spec value and must fail at load."""
    path = _write_config(
        tmp_path, "risk_per_trade: 1000\ncost_per_trade: null\ninitial_capital: 100000\nrow_size: 24\n" + _TAIL
    )
    with pytest.raises(ConfigError, match="cost_per_trade"):
        load_config(path, include_env=False)


@pytest.mark.parametrize("value", ["0", "-1", "'100'", "true", "[100]"])
def test_a_bad_cost_per_trade_is_rejected(tmp_path: Path, value: str) -> None:
    path = _write_config(
        tmp_path,
        f"risk_per_trade: 1000\ncost_per_trade: {value}\ninitial_capital: 100000\nrow_size: 24\n" + _TAIL,
    )
    with pytest.raises(ConfigError, match="cost_per_trade"):
        load_config(path, include_env=False)


# --- CONTEXT 3.5's starting capital (REVIEW_9A finding C1) -----------------------------


def test_repo_config_carries_the_context_starting_capital() -> None:
    """CONTEXT 3.5 (R1-Q21a): 1,00,000 rupees, and it crosses into paise exactly once."""
    config = load_config(include_env=False)
    assert config.initial_capital == 100000
    assert config.initial_capital_paise() == 10_000_000


def test_a_null_initial_capital_is_rejected_outright(tmp_path: Path) -> None:
    """Like the cost and unlike capital_reference, no open item stands behind this number:
    CONTEXT 3.5 states it, so a null is a config that LOST a spec value."""
    path = _write_config(
        tmp_path,
        "risk_per_trade: 1000\ncost_per_trade: 100\ninitial_capital: null\nrow_size: 24\n" + _TAIL,
    )
    with pytest.raises(ConfigError, match="initial_capital"):
        load_config(path, include_env=False)


@pytest.mark.parametrize("value", ["0", "-1", "'100000'", "true", "[100000]"])
def test_a_bad_initial_capital_is_rejected(tmp_path: Path, value: str) -> None:
    path = _write_config(
        tmp_path,
        f"risk_per_trade: 1000\ncost_per_trade: 100\ninitial_capital: {value}\nrow_size: 24\n" + _TAIL,
    )
    with pytest.raises(ConfigError, match="initial_capital"):
        load_config(path, include_env=False)


def test_a_config_missing_the_capital_key_is_rejected(tmp_path: Path) -> None:
    """A missing money key must not resolve to a default -- not even to CONTEXT 3.5's own
    figure, which is precisely what REVIEW_9A finding C1 found typed into portfolio.py."""
    path = _write_config(
        tmp_path, "risk_per_trade: 1000\ncost_per_trade: 100\nrow_size: 24\n" + _TAIL
    )
    with pytest.raises(ConfigError, match="Missing key"):
        load_config(path, include_env=False)


def test_a_fractional_paisa_initial_capital_is_refused(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        "risk_per_trade: 1000\ncost_per_trade: 100\ninitial_capital: 100000.005\nrow_size: 24\n" + _TAIL,
    )
    with pytest.raises(ConfigError, match="whole number of paise"):
        load_config(path, include_env=False).initial_capital_paise()


def test_no_module_in_src_hardcodes_a_context_35_money_amount() -> None:
    """**The WIDENED money tripwire (REVIEW_9A finding C1).**

    Chunk 8 asserted this over `simulate.py` alone, and that is exactly why CONTEXT 3.5's
    1,00,000 capital could sit in `portfolio.py` for a whole chunk without anything noticing.
    This walks EVERY module in `src/acumen` and asserts that none of them carries a CONTEXT 3.5
    money amount as an integer literal.

    The forbidden magnitudes are DERIVED from the committed config rather than typed here, so
    the tripwire cannot drift away from the spec values it protects: the risk in rupees and in
    paise, the cost in paise, and the capital in rupees and in paise. The cost in RUPEES (100)
    is deliberately excluded -- it collides with the paise-per-rupee scale, which fourteen
    modules legitimately use, and an engine hardcoding a cost would hardcode it in the paise
    the engines actually work in. Asserted structurally over each module's numeric literals, so
    a constant carrying an amount cannot hide where a comment mentioning one cannot trip it.

    **ITS LIMIT, written down here so a green run is not read as a proof** (REVIEW_9A_2 finding
    C4). This is a scan of integer LITERALS. It sees `CAPITAL = 10_000_000` and it does NOT see
    `10 ** 7`, `5_000_000 * 2` or `int(1e7)` -- a magnitude that is COMPUTED passes straight
    through, and the assertion at the end of this test demonstrates that rather than describing
    it. The repo already contains the worked precedent: decision B200 rewrote
    `backtest.ResidualEntry.as_dict`'s `ratio * 10000` as `ratio * 100 * 100` for exactly this
    reason (legitimately -- the two are the same Fraction, proved exhaustively in
    `tests/test_review9a2_probes.py`), so the evasion is a pattern in this tree and a future
    session must not assume a green tripwire means no module knows a money amount. What this
    test DOES prove is the thing that actually went wrong in chunk 9A: a spec amount typed as a
    constant, in any module of the package rather than in one sampled file.
    """
    import ast

    config = load_config(include_env=False)
    risk_paise = config.require_risk_per_trade_paise()
    cost_paise = config.cost_per_trade_paise()
    capital_paise = config.initial_capital_paise()
    forbidden = {
        risk_paise,
        int(config.risk_per_trade),
        cost_paise,
        capital_paise,
        int(config.initial_capital),
    }
    assert forbidden == {1_000, 10_000, 100_000, 10_000_000}

    modules = sorted((REPO_ROOT / "src" / "acumen").glob("*.py"))
    assert len(modules) > 30  # the whole package, not a sample

    offenders: dict[str, list[int]] = {}
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        }
        hits = sorted(literals & forbidden)
        if hits:
            offenders[module.name] = hits
    assert offenders == {}, f"CONTEXT 3.5 money amounts hardcoded in src/acumen: {offenders}"

    # The limit, demonstrated beside the tripwire it belongs to (REVIEW_9A_2 finding C4): the
    # same scan applied to four spellings of ONE magnitude catches only the typed one.
    def literals_of(source: str) -> set[int]:
        return {
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        }

    assert capital_paise in literals_of("CAPITAL = 10_000_000")  # <-- caught
    for evasion in ("CAPITAL = 10 ** 7", "CAPITAL = 5_000_000 * 2", "CAPITAL = int(1e7)"):
        assert capital_paise not in literals_of(evasion), evasion  # <-- invisible to the scan


def test_the_portfolio_layer_has_no_capital_default_left() -> None:
    """REVIEW_9A finding C1, the other half: the constant is GONE, and the five public
    functions that need the figure now REQUIRE it rather than defaulting to one."""
    import inspect

    from acumen import portfolio as pf

    assert not hasattr(pf, "DEFAULT_INITIAL_CAPITAL_PAISE")
    for name in ("equity_curve", "metrics", "side_split", "per_symbol", "buy_and_hold"):
        parameter = inspect.signature(getattr(pf, name)).parameters["initial_capital_paise"]
        assert parameter.default is inspect.Parameter.empty, name


def test_a_config_missing_the_cost_key_is_rejected(tmp_path: Path) -> None:
    """A missing money key must not resolve to a default (CLAUDE.md rule 1)."""
    path = _write_config(
        tmp_path, "risk_per_trade: 1000\nrow_size: 24\n" + _TAIL
    )
    with pytest.raises(ConfigError, match="Missing key"):
        load_config(path, include_env=False)


# --- Q-20: the PINNED instrument master ------------------------------------------------


def test_the_repo_config_pins_the_instrument_master_the_ruling_names() -> None:
    """QUESTIONS.md Q-20 (architect, 02-Aug-2026) pins ONE snapshot for the whole backtest.

    The name is asserted because the ruling names it: the run's ticks -- and therefore CONTEXT
    3.3's profile row grid and every POC on the 11 symbols whose tick the vendor moved -- are
    the 2026-07-31 dump's, the one the Q-18 rebuild was built and gated under.
    """
    config = load_config(include_env=False)
    assert config.instrument_master == "OpenAPIScripMaster_2026-07-31.json"


def test_the_pin_resolves_under_cache_root_and_nowhere_else() -> None:
    """The pin is a FILENAME; the loader is what turns it into a path, always under the cache."""
    config = load_config(include_env=False)
    resolved = config.instrument_master_path()
    assert resolved.name == config.instrument_master
    assert resolved.parent == config.path("cache_root") / "instrument_master"


def test_the_config_and_the_instrument_master_module_spell_the_subdir_the_same() -> None:
    """`config.MASTER_CACHE_SUBDIR` is duplicated rather than imported (no package-internal
    dependency in the module everything imports). This pins the two spellings equal, so the
    duplication can never drift into a pin that resolves to a directory nobody writes."""
    from acumen import instrument_master as im
    from acumen.config import MASTER_CACHE_SUBDIR

    assert MASTER_CACHE_SUBDIR == im.CACHE_SUBDIR


def test_a_config_that_loses_the_pin_refuses_to_load(tmp_path: Path) -> None:
    """No default and no "newest wins" fallback -- that fallback IS what Q-20 retired."""
    path = _write_config(
        tmp_path,
        "risk_per_trade: 1000\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n"
        + _PATHS,
    )
    with pytest.raises(ConfigError, match="Missing key.*instrument_master"):
        load_config(path, include_env=False)


def test_a_null_pin_is_refused_and_names_the_ruling(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        "risk_per_trade: 1000\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n"
        "instrument_master: null\n" + _PATHS,
    )
    with pytest.raises(ConfigError) as excinfo:
        load_config(path, include_env=False)
    message = str(excinfo.value)
    assert "Q-20" in message
    assert "no default" in message


@pytest.mark.parametrize(
    "value",
    [
        "sub/OpenAPIScripMaster_2026-07-31.json",
        "../OpenAPIScripMaster_2026-07-31.json",
        "/tmp/OpenAPIScripMaster_2026-07-31.json",
        "''",
        "24",
        "[a]",
    ],
)
def test_a_pin_that_is_not_a_bare_filename_is_refused(tmp_path: Path, value: str) -> None:
    """The pin may never reach outside the cache the operator snapshots -- so a separator, a
    parent-directory hop, an absolute path, an empty value and a non-string are all refused."""
    path = _write_config(
        tmp_path,
        "risk_per_trade: 1000\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n"
        f"instrument_master: {value}\n" + _PATHS,
    )
    with pytest.raises(ConfigError, match="instrument_master"):
        load_config(path, include_env=False)


# --- structural validation -------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "-3", "'24'", "24.5", "true"])
def test_bad_row_size_is_rejected(tmp_path: Path, value: str) -> None:
    path = _write_config(
        tmp_path, f"risk_per_trade: null\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: {value}\n" + _TAIL
    )
    with pytest.raises(ConfigError, match="row_size"):
        load_config(path, include_env=False)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    """A typo must fail loudly instead of silently falling back to a default."""
    path = _write_config(tmp_path, _VALID + "rowsize: 30\n")
    with pytest.raises(ConfigError, match="Unknown key"):
        load_config(path, include_env=False)


def test_missing_key_is_rejected(tmp_path: Path) -> None:
    path = _write_config(tmp_path, "risk_per_trade: null\ncost_per_trade: 100\n" + _TAIL)
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


@pytest.mark.parametrize(
    "body",
    [
        "paths: {}\n",
        "paths:\n  data_root: ''\n",
        "paths: data\n",
        # Q-18 layer 1 (CLAUDE.md, "Data-store safety"): a paths block that declares
        # NEITHER store root, only ONE of them, a RELATIVE root, or a root INSIDE the
        # repository tree is refused -- there is no default and no warning-only path.
        "paths:\n  logs_dir: logs\n",
        f"paths:\n  data_root: {_OUTSIDE_ROOT.as_posix()}\n",
        f"paths:\n  data_root: store\n  cache_root: {(_OUTSIDE_ROOT / 'cache').as_posix()}\n",
    ],
)
def test_bad_paths_block_is_rejected(tmp_path: Path, body: str) -> None:
    path = _write_config(tmp_path, "risk_per_trade: null\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n" + _PIN + body)
    with pytest.raises(ConfigError, match="paths"):
        load_config(path, include_env=False)


def test_absolute_path_values_are_kept_as_given(tmp_path: Path) -> None:
    absolute = (tmp_path / "store").as_posix()
    path = _write_config(
        tmp_path,
        "risk_per_trade: null\ncost_per_trade: 100\ninitial_capital: 100000\nrow_size: 24\n"
        + _PIN
        + f"paths:\n  data_root: {absolute}\n  cache_root: {absolute}/cache\n",
    )
    assert load_config(path, include_env=False).path("data_root") == Path(absolute)


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


# --- the Q40-d capital-infeasibility inputs (chunk 9A; BLOCKED on the trader's Q43) -----


def test_the_repo_config_leaves_both_capital_flag_keys_null() -> None:
    """CONTEXT 3.5's flags need a capital figure that is the TRADER's (Q43) and has not
    arrived. Null means the flags are NOT COMPUTED -- there is no default, not even
    CONTEXT 3.5's own 1,00,000 capital line."""
    config = load_config(include_env=False)
    assert config.capital_reference is None
    assert config.margin_basis is None
    assert config.capital_reference_paise() is None
    assert config.margin_basis_text() is None


def test_both_capital_flag_keys_are_optional_not_required(tmp_path: Path) -> None:
    """A config that predates chunk 9A still loads -- the keys are OPTIONAL, unlike the money."""
    config = load_config(_write_config(tmp_path, _VALID), include_env=False)
    assert config.capital_reference is None and config.margin_basis is None


def test_a_supplied_capital_reference_crosses_into_paise_exactly(tmp_path: Path) -> None:
    body = _VALID + "capital_reference: 100000\nmargin_basis: 5\n"
    config = load_config(_write_config(tmp_path, body), include_env=False)
    assert config.capital_reference_paise() == 10_000_000
    assert config.margin_basis_text() == "5"


def test_a_fractional_margin_basis_stays_exact(tmp_path: Path) -> None:
    """A Decimal, never a float: the tier boundary is compared against integer paise."""
    body = _VALID + "capital_reference: 100000\nmargin_basis: 4.5\n"
    config = load_config(_write_config(tmp_path, body), include_env=False)
    assert config.margin_basis_text() == "4.5"
    assert config.margin_basis == Decimal("4.5")


@pytest.mark.parametrize(
    "body,message",
    [
        ("capital_reference: 0\n", "capital_reference"),
        ("capital_reference: -1\n", "capital_reference"),
        ("capital_reference: 'lots'\n", "capital_reference"),
        ("margin_basis: 0\n", "margin_basis"),
        ("margin_basis: -2\n", "margin_basis"),
        ("margin_basis: [5]\n", "margin_basis"),
    ],
)
def test_a_nonsense_capital_flag_value_is_refused(tmp_path: Path, body: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(_write_config(tmp_path, _VALID + body), include_env=False)


def test_a_fractional_paisa_capital_reference_is_refused(tmp_path: Path) -> None:
    body = _VALID + "capital_reference: 100.005\n"
    config = load_config(_write_config(tmp_path, body), include_env=False)
    with pytest.raises(ConfigError, match="whole number of paise"):
        config.capital_reference_paise()


def test_an_unknown_key_is_still_refused_after_the_optional_ones_were_added(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigError, match="Unknown key"):
        load_config(_write_config(tmp_path, _VALID + "leverage: 5\n"), include_env=False)
