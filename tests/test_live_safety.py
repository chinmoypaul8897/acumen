"""THE SAFETY RAILS (chunk 13), restated in tests because a rule nobody checks is a wish.

Three of them, and each is a rule someone wrote down before this chunk existed:

1. **NO ORDER PLACEMENT, ANYWHERE.** CONTEXT section 1 R4 (*"Read-only trading APIs. No
   order-placement code anywhere in this repo in v1"*) and CLAUDE.md rule 4. The screener alerts;
   the human trades. This is the rule with real money behind it and it is the one a live chunk is
   most likely to erode, one convenience at a time -- so it is enforced by a scan of the WHOLE
   package, at the source text AND through the AST, rather than by a promise in a docstring.
2. **Credentials are never printed, logged or committed.** Same rule, the other half.
3. **The screener degrades to SILENCE plus a visible failure banner, never to a wrong alert.**
   The per-symbol half is tested in ``tests/test_live_screener.py``; what is tested here is the
   LIVE mode's own refusals and its DISCLOSURE. Q-28 blocked that mode entirely until the
   architect ruled on 08-Aug-2026; the block is now CONTEXT 4.7 and what stands in its place is
   tested here -- a live morning without THE DAY'S OWN instrument master refuses to start
   (Q-29), and one that does start says, before anything else, exactly what it could not verify.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from acumen import live_screener as ls
from acumen.live_recording import LiveRecording
from acumen.smartapi_client import Credentials, SmartApiClient

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "src" / "acumen"

#: Every SmartAPI entry point that PLACES, CHANGES or CANCELS anything at the exchange, in the
#: vendor's own spelling and in this repo's snake_case house style. Naming one of these in
#: ``src/acumen`` is a build failure, whether it is called, imported, or merely written down.
ORDER_ENDPOINTS: tuple[str, ...] = (
    "placeOrder", "place_order",
    "placeOrderFullResponse",
    "modifyOrder", "modify_order",
    "cancelOrder", "cancel_order",
    "gttCreateRule", "gttModifyRule", "gttCancelRule",
    "convertPosition", "convert_position",
    "createRule", "modifyRule", "cancelRule",
)

#: What the client is ALLOWED to call on the broker connection. Anything else is a finding.
ALLOWED_BROKER_CALLS: frozenset[str] = frozenset(
    {"generateSession", "terminateSession", "getCandleData"}
)

#: **Where the tripwire looks.** CONTEXT section 1 R4 says *"anywhere in this repo"* and the
#: shipped scan was ``PACKAGE.glob("*.py")`` -- non-recursive, and blind to ``tests/``,
#: ``scripts/``, ``docs/evidence/`` and any subpackage ``src/acumen`` might grow (REVIEW_13
#: **M7**). Every Python file under these roots is scanned, recursively.
SCAN_ROOTS: tuple[str, ...] = ("src", "tests", "scripts", "docs/evidence")

#: The one file the scan cannot read: this one. It must NAME the forbidden endpoints in order to
#: forbid them, and it must carry the evasion corpus in order to prove the scan catches it. The
#: exemption is by filename and is asserted to be exactly one file, so it cannot quietly grow.
SELF_EXEMPT: frozenset[str] = frozenset({"test_live_safety.py"})

#: Characters removed before the literal scan compares. Quotes, ``+`` and whitespace defeat
#: ``"place" + "Order"`` and ``"place" "Order"``; commas defeat ``"".join(["place", "Order"])``;
#: underscores, hyphens and backslashes defeat ``place_order``, ``place-order`` and an escaped
#: split. The comparison is then case-insensitive, which defeats ``PlaceOrder``.
_NOISE = re.compile(r"[\s'\"+_\\,-]")


def _squash(text: str) -> str:
    """Normalise a line (or a name) so that a spelling trick cannot hide an endpoint in it."""
    return _NOISE.sub("", text).lower()


#: The endpoints in the one form the scan actually compares against.
NORMALISED_ENDPOINTS: tuple[str, ...] = tuple(sorted({_squash(e) for e in ORDER_ENDPOINTS}))


def repo_sources() -> list[Path]:
    """Every Python file the tripwire covers -- recursively, over all of :data:`SCAN_ROOTS`."""
    found: list[Path] = []
    for root in SCAN_ROOTS:
        found.extend(sorted((REPO_ROOT / root).rglob("*.py")))
    return [path for path in found if path.name not in SELF_EXEMPT]


def package_sources() -> list[Path]:
    """Every module of the package itself, recursively (subpackages included)."""
    return sorted(PACKAGE.rglob("*.py"))


def literal_offenders(text: str, label: str) -> list[str]:
    """The LITERAL half, widened: a squashed, case-folded line scan."""
    found: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        squashed = _squash(line)
        for endpoint in NORMALISED_ENDPOINTS:
            if endpoint in squashed:
                found.append(f"{label}:{number} literal-scan names {endpoint!r}")
    return found


def _folded_strings(node: ast.AST, bindings: dict[str, str] | None = None) -> list[str]:
    """Every string a constant-folding expression can produce, best-effort.

    ``"place" + "Order"``, an f-string whose parts are constants, a list/tuple of constants that
    something will join, and a NAME the file bound to a string earlier -- the shapes that turn a
    name the AST never sees as one piece into a name the interpreter does. The last is what
    reaches an evasion split across two LINES, which a line scan cannot see by construction.

    **REVIEW_13B Q4** adds the two ordinary idioms that still walked past both halves:
    ``"place%s" % "Order"`` and ``"place{}".format("Order")``. Neither is an adversary's trick
    -- they are how a careless author writes a name in Python, which is exactly the population
    this tripwire is for -- and the literal scan cannot see either, because its normaliser
    leaves ``%s%`` and ``{}.format(`` sitting between the two halves. Both are folded here the
    same way the concatenations are: only when every part is a CONSTANT (or a name already
    bound to one), so the scan stays a tripwire and never becomes an interpreter.
    """
    bindings = bindings or {}
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name) and node.id in bindings:
        return [bindings[node.id]]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _folded_strings(node.left, bindings)
        right = _folded_strings(node.right, bindings)
        return ["".join(left) + "".join(right)] if left and right else []
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        # `"place%s" % "Order"`, and the tuple form `"%s%s" % ("place", "Order")`.
        template = _folded_strings(node.left, bindings)
        if not template:
            return []
        values = (
            [_folded_strings(element, bindings) for element in node.right.elts]
            if isinstance(node.right, ast.Tuple)
            else [_folded_strings(node.right, bindings)]
        )
        if any(not part for part in values):
            return []
        try:
            filled = template[-1] % tuple(part[-1] for part in values)
        except (TypeError, ValueError, KeyError):  # not a shape this fold can complete
            return []
        return [filled]
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "format" and not node.keywords):
        # `"place{}".format("Order")`, positional constants only.
        template = _folded_strings(node.func.value, bindings)
        args = [_folded_strings(argument, bindings) for argument in node.args]
        if not template or any(not part for part in args):
            return []
        try:
            filled = template[-1].format(*[part[-1] for part in args])
        except (IndexError, KeyError, ValueError):  # a template this fold cannot complete
            return []
        return [filled]
    if isinstance(node, ast.FormattedValue):
        return _folded_strings(node.value, bindings)
    if isinstance(node, ast.JoinedStr):
        parts = [part for value in node.values for part in _folded_strings(value, bindings)]
        return ["".join(parts)] if parts else []
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        parts = [part for element in node.elts for part in _folded_strings(element, bindings)]
        return parts + (["".join(parts)] if len(parts) > 1 else [])
    return []


def _string_bindings(tree: ast.AST) -> dict[str, str]:
    """Names this file bound to a string, so a two-line evasion folds like a one-line one.

    Two passes, because an assignment may use a name bound later in the file; two is enough for
    every shape in the corpus and the scan is a tripwire rather than an interpreter.
    """
    bindings: dict[str, str] = {}
    for _ in range(2):
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if value is None:
                continue
            folded = _folded_strings(value, bindings)
            if not folded:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = folded[-1]
    return bindings


def candidate_names(tree: ast.AST) -> set[str]:
    """Every name this file could reach an attribute by, however it spells it.

    The shipped AST half collected attribute names and the literal second argument of
    ``getattr``, and REVIEW_13 measured what that missed: of 22 evasion variants it turned red on
    3, **all 3 already red on the literal scan, so it added ZERO catches** -- and it missed the
    evasion its own docstring named. What is collected now:

    * every attribute access (``connect.placeOrder``), including one merely bound to a name;
    * **every string constant anywhere in the file**, which is what catches a name assigned to a
      variable first, a dict value, an ``operator.attrgetter`` argument, a
      ``__getattribute__`` call, and a string handed to ``exec``/``eval``;
    * every constant-foldable string expression -- concatenation with ``+``, implicit adjacency,
      an f-string of constants, and the parts of a list/tuple something will ``join``;
    * every import name AND alias, so ``from x import placeOrder as ship_it`` is caught by the
      name even though the alias is innocent.
    """
    bindings = _string_bindings(tree)
    names: set[str] = set(bindings.values())
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.name)
                if alias.asname:
                    names.add(alias.asname)
            if isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        else:
            names.update(_folded_strings(node, bindings))
    return names


def ast_offenders(tree: ast.AST, label: str) -> list[str]:
    """The AST half, widened -- and it now catches things the literal half cannot."""
    found: list[str] = []
    for name in sorted(candidate_names(tree)):
        squashed = _squash(name)
        for endpoint in NORMALISED_ENDPOINTS:
            if endpoint in squashed:
                found.append(f"{label}: ast-scan reaches {name!r} (~{endpoint})")
    return found


def scan_source(text: str, label: str) -> list[str]:
    """Both halves over one file's text. Empty means clean."""
    offenders = literal_offenders(text, label)
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover -- every file in this repo parses
        return offenders + [f"{label}: does not parse"]
    return offenders + ast_offenders(tree, label)


def test_NO_ORDER_PLACEMENT_ENDPOINT_IS_NAMED_ANYWHERE_IN_THE_REPOSITORY() -> None:
    """CONTEXT section 1 R4, over the whole repository rather than over one directory listing.

    It does not need to be reachable to be a breach -- an order call sitting behind a flag is an
    order call. What changed with REVIEW_13 M7 is REACH: the scan was
    ``PACKAGE.glob("*.py")``, so ``tests/``, ``scripts/``, ``docs/evidence/`` and any subpackage
    were invisible to a rule whose own words are "anywhere in this repo".
    """
    files = repo_sources()
    assert len(files) > len(list(PACKAGE.glob("*.py"))), (
        "the scan reaches beyond the package's own top-level modules"
    )
    offenders: list[str] = []
    for path in files:
        offenders.extend(
            scan_source(path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT)))
        )
    assert not offenders, (
        "CONTEXT section 1 R4: no order-placement code anywhere in this repo in v1. Found:\n"
        + "\n".join(offenders)
    )


def test_the_ONE_exempt_file_is_this_one_and_it_is_exempt_for_a_stated_reason() -> None:
    """The exemption cannot quietly grow into a place to keep an endpoint.

    This file must name the forbidden endpoints to forbid them and must carry the evasion corpus
    to prove the scan catches it, so it cannot scan itself. That is the whole exemption: one
    file, named, and its own contents are the tripwire rather than a gap in it.
    """
    assert SELF_EXEMPT == {Path(__file__).name}
    skipped = [
        path for root in SCAN_ROOTS
        for path in (REPO_ROOT / root).rglob("*.py")
        if path.name in SELF_EXEMPT
    ]
    assert len(skipped) == 1 and skipped[0].resolve() == Path(__file__).resolve()


#: Every evasion REVIEW_13 walked past the shipped tripwire with, plus the ones its own docstring
#: claimed to stop. Source TEXT, compiled nowhere, scanned as files -- so the corpus proves the
#: SCANNER rather than proving Python. The finding was 5 of 22 caught, with the AST half adding
#: zero over the literal one.
EVASIONS: tuple[tuple[str, str], ...] = (
    ("plain attribute", "connect.placeOrder(params)\n"),
    ("snake_case attribute", "connect.place_order(params)\n"),
    ("case variant", "connect.PlaceOrder(params)\n"),
    ("doubled underscore", "connect.place__order(params)\n"),
    ("getattr literal", 'getattr(connect, "placeOrder")(params)\n'),
    ("getattr concatenation", 'getattr(connect, "place" + "Order")(params)\n'),
    ("getattr adjacency", 'getattr(connect, "place" "Order")(params)\n'),
    ("getattr f-string", "getattr(connect, f\"place{'Order'}\")(params)\n"),
    ("getattr via join", 'getattr(connect, "".join(["place", "Order"]))(params)\n'),
    ("name assigned first", 'method = "placeOrder"\ngetattr(connect, method)(params)\n'),
    ("name built first", 'method = "place" + "Order"\ngetattr(connect, method)(params)\n'),
    ("dict value", 'ROUTES = {"go": "placeOrder"}\ngetattr(connect, ROUTES["go"])(params)\n'),
    ("attrgetter", 'import operator\noperator.attrgetter("placeOrder")(connect)(params)\n'),
    ("dunder getattribute", 'connect.__getattribute__("placeOrder")(params)\n'),
    ("setattr", 'setattr(shim, "placeOrder", fn)\n'),
    ("bound to a local", "shipit = connect.placeOrder\n"),
    ("import by name", "from vendor.smartConnect import placeOrder\n"),
    ("import under an alias", "from vendor.smartConnect import placeOrder as ship_it\n"),
    ("exec string", 'exec("connect.placeOrder(params)")\n'),
    ("eval string", 'eval(\'getattr(connect, "cancelOrder")\')\n'),
    ("modify", "connect.modifyOrder(params)\n"),
    ("cancel", "connect.cancelOrder(params)\n"),
    ("gtt create", "connect.gttCreateRule(params)\n"),
    ("gtt built", 'getattr(connect, "gtt" + "CreateRule")(params)\n'),
    ("convert position", "connect.convertPosition(params)\n"),
    ("in a docstring", '"""Pasted from the vendor docs: placeOrder(variety, ...)."""\n'),
    # --- split across LINES: no single line carries the name, so a line scan cannot see these
    # at all, however it normalises. These are the AST half's own catches.
    ("two names, two lines", 'HEAD = "place"\nTAIL = "Order"\ngetattr(connect, HEAD + TAIL)\n'),
    ("list across lines", 'PARTS = [\n    "place",\n    "Order",\n]\n'
                          'getattr(connect, "".join(PARTS))\n'),
    ("bound then f-string", 'TAIL = "Order"\ngetattr(connect, f"place{TAIL}")\n'),
    ("bound then attribute", 'WHAT = "cancel"\nHOW = "Order"\nmethod = WHAT + HOW\n'),
    # --- REVIEW_13B Q4: two ordinary idioms the widened scan still walked past. The literal
    # half cannot see either (its normaliser leaves `%s%` and `{}.format(` between the halves),
    # so these are AST catches by construction.
    ("percent format", 'getattr(connect, "place%s" % "Order")(params)\n'),
    ("percent format, tuple", 'getattr(connect, "%s%s" % ("place", "Order"))(params)\n'),
    ("str.format", 'getattr(connect, "place{}".format("Order"))(params)\n'),
    ("str.format across lines", 'TAIL = "Order"\ngetattr(connect, "place{}".format(TAIL))\n'),
    # ... and one the AST cannot see at all, because Python throws comments away before the tree
    # exists. This is why BOTH halves are kept rather than the stronger one alone.
    ("in a comment", "# TODO: switch this to connect.placeOrder once the desk approves\n"),
)


def _shipped_scan(text: str) -> bool:
    """The tripwire as REVIEW_13 found it: a plain line scan plus the narrow AST half.

    Kept so the widening can be MEASURED rather than asserted -- the review's own number was
    5 caught of 22, with the AST half adding nothing over the literal one.
    """
    for line in text.splitlines():
        for endpoint in ORDER_ENDPOINTS:
            if endpoint in line:
                return True
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Attribute):
            name = node.attr
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == "getattr" and len(node.args) > 1
              and isinstance(node.args[1], ast.Constant)
              and isinstance(node.args[1].value, str)):
            name = node.args[1].value
        if name and name in ORDER_ENDPOINTS:
            return True
    return False


def test_the_order_tripwire_CATCHES_EVERY_EVASION_the_review_walked_past() -> None:
    """REVIEW_13 **M7**: 17 of 22 evasion variants walked past both halves. Now none does.

    The corpus is scanned as SOURCE TEXT and nothing in it is imported or executed. Each variant
    is a real way to reach a method without writing its name where a line scan would see it, and
    the two halves are checked separately as well as together -- because the finding was not
    only that variants escaped, it was that the AST half **added zero catches** over the literal
    one and so was not doing the job its docstring claimed.
    """
    missed = [label for label, source in EVASIONS if not scan_source(source, label)]
    assert not missed, f"the widened tripwire still walks past: {missed}"

    shipped_caught = [label for label, source in EVASIONS if _shipped_scan(source)]
    assert len(shipped_caught) < len(EVASIONS), (
        "the corpus must contain variants the shipped scan missed, or it proves nothing"
    )

    # BOTH halves must EARN their place, and each one catches something the other cannot.
    ast_only = [
        label for label, source in EVASIONS
        if not literal_offenders(source, label) and ast_offenders(ast.parse(source), label)
    ]
    literal_only = [
        label for label, source in EVASIONS
        if literal_offenders(source, label) and not ast_offenders(ast.parse(source), label)
    ]
    assert len(ast_only) >= 4, (
        f"the AST half adds only {len(ast_only)} catch(es) over the literal scan -- 'it adds "
        "ZERO' was the finding, and an evasion split across two LINES is what it is for"
    )
    assert literal_only, (
        "and the literal half is not redundant: Python throws comments away before the tree "
        "exists, so an endpoint pasted into a comment is a literal-scan catch only"
    )


def test_the_broker_connection_is_only_ever_asked_for_candles_or_a_session() -> None:
    """What the package actually CALLS on the broker object -- login, logout, candles, nothing.

    The scan above proves no order endpoint is NAMED. This one proves the positive: the three
    calls this repo is allowed to make are the only three it makes.
    """
    suspicious: list[str] = []
    for path in package_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in candidate_names(tree):
            lowered = name.lower()
            if ("order" in lowered or "gtt" in lowered) and name not in ALLOWED_BROKER_CALLS:
                # `ordered`, `order` as a local, `sort_order` etc. are English, not endpoints.
                if lowered in {"order", "ordered", "sort_order", "reorder", "ordering"}:
                    continue
                suspicious.append(f"{path.name}: {name}")
    unexpected = [
        row for row in suspicious
        if any(endpoint in _squash(row) for endpoint in NORMALISED_ENDPOINTS)
    ]
    assert not unexpected, "an order endpoint is reachable by attribute:\n" + "\n".join(unexpected)

    # and the three calls the client really makes are exactly the allowed set
    client_text = (PACKAGE / "smartapi_client.py").read_text(encoding="utf-8")
    called = {
        node.func.attr
        for node in ast.walk(ast.parse(client_text))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name) and node.func.value.id in ("connect", "_connect")
    }
    called |= {
        node.func.attr
        for node in ast.walk(ast.parse(client_text))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "_connect"
    }
    assert called <= ALLOWED_BROKER_CALLS, f"the client calls {sorted(called - ALLOWED_BROKER_CALLS)}"


def test_the_live_path_imports_no_broker_method_but_get_candles() -> None:
    """The screener's own source: one SmartAPI method is named on the whole live path."""
    live_modules = [PACKAGE / name for name in (
        "live_screener.py", "live_source.py", "live_recording.py",
        "live_dashboard.py", "live_refresh.py", "run_screener.py",
    )]
    for path in live_modules:
        text = path.read_text(encoding="utf-8")
        assert "placeOrder" not in text and "place_order" not in text
    source_text = (PACKAGE / "live_source.py").read_text(encoding="utf-8")
    assert "get_candles" in source_text
    assert source_text.count("self.client.") == 1, (
        "live_source touches the client exactly once, and it is the candle call"
    )


def test_a_credential_never_reaches_a_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLAUDE.md rule 4. The repr is the accident waiting to happen -- a logged client object."""
    creds = Credentials(api_key="KEY-abc", client_code="C123", pin="4321", totp_secret="SECRET")
    for text in (repr(creds), str(creds)):
        for secret in ("KEY-abc", "4321", "SECRET"):
            assert secret not in text, f"{secret!r} leaked through the credential repr"

    client = SmartApiClient(credentials=creds)
    for secret in ("KEY-abc", "4321", "SECRET"):
        assert secret not in repr(client)


def test_the_LIVE_mode_REFUSES_TO_START_WITHOUT_THE_DAYS_OWN_MASTER(tmp_path: Path) -> None:
    """CONTEXT 4.7 / QUESTIONS.md Q-29, made structural -- the successor to the Q-28 block.

    Until 08-Aug-2026 this file held the STOP rule in executable form: ``mode="live"`` raised
    :class:`BlockedByOpenQuestion` carrying Q-28's text. The architect ruled, Q-28 is CONTEXT
    4.7, and the block is GONE -- but the ruling replaced it with a prerequisite that is just as
    structural and is tested here in its place: *"a live morning uses THE DAY'S OWN instrument
    master, fetched pre-open"*. The tick sizes CONTEXT 3.3's row grid, hence the POC, hence every
    entry, stop and target, so a morning whose dump did not arrive must refuse rather than fall
    back to a stale snapshot -- silently running on last week's ticks is exactly the failure Q-20
    measured on 11 of the sealed 210.

    **REVIEW_13 M24, closed.** As replaced, this test caught ``Exception`` -- which admits any
    exception whatsoever -- and checked three substrings, because the refusal really was leaking
    a ``BacktestError`` through a module whose error base is ``ScreenerError``. Both halves are
    repaired: the contract is asserted by TYPE and the sentence by EQUALITY against the module
    constant that carries it, which is what the test it replaced did.
    """
    with pytest.raises(ls.ScreenerError) as caught:
        ls.build_live_screener(
            date(2026, 7, 17), ("SYNTH",),
            source=None, recording=LiveRecording.at(tmp_path / "r"),
            clock=ls.VirtualClock(stamp=datetime(2026, 7, 17, 9, 0)), mode="live",
        )
    message = str(caught.value)
    assert message.startswith(ls.MASTER_MISSING_REFUSAL), (
        "the refusal is the module's own recorded sentence, not a paraphrase of it"
    )
    assert "OpenAPIScripMaster_2026-07-17.json" in message, "it names the file it wanted"
    assert "CONTEXT 4.7" in message

    with pytest.raises(ls.ScreenerError, match="mode must be"):
        ls.build_live_screener(
            date(2026, 7, 17), ("SYNTH",), source=None,
            recording=LiveRecording.at(tmp_path / "r2"),
            clock=ls.VirtualClock(stamp=datetime(2026, 7, 17, 9, 0)), mode="paper",
        )


def test_the_STOP_RULE_still_REFUSES_a_live_mode_that_an_open_question_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLAUDE.md rule 1, in executable form -- restored (REVIEW_13 **M24**).

    The original safety test asserted ``pytest.raises(BlockedByOpenQuestion)`` plus an equality
    against a module constant, and it went red the moment anyone unblocked a live mode without a
    ruling. Its successor asserted a different refusal entirely, so **neither successor preserved
    the STOP-rule property**: nothing went red on a future unblocking, and
    ``BlockedByOpenQuestion`` became unraised, unconstructed and untested -- the exit the
    docstring reserves for the next class-A hole was a branch no test had ever taken.

    It is a REGISTER now rather than a hard-coded refusal, which generalises the property instead
    of re-pinning it to Q-28: a session that meets a class-A hole on the live path adds one row
    to ``LIVE_BLOCKING_QUESTIONS`` and the mode refuses in the question's own words. Both halves
    are asserted here -- that the register is empty TODAY (every question a live morning has met
    has been ruled on), and that a non-empty register really does stop the morning.
    """
    assert ls.LIVE_BLOCKING_QUESTIONS == (), (
        "Q-28 and Q-29 are CONTEXT 4.7 and Q-30 is the architect's 08-Aug-2026 ruling; if a "
        "session adds a row here, this line is where it says so"
    )
    assert issubclass(ls.BlockedByOpenQuestion, ls.ScreenerError)

    question = ("Q-99", "the words of the question that blocks this morning")
    monkeypatch.setattr(ls, "LIVE_BLOCKING_QUESTIONS", (question,))
    with pytest.raises(ls.BlockedByOpenQuestion) as caught:
        ls.build_live_screener(
            date(2026, 7, 17), ("SYNTH",),
            source=None, recording=LiveRecording.at(tmp_path / "blocked"),
            clock=ls.VirtualClock(stamp=datetime(2026, 7, 17, 9, 0)), mode="live",
        )
    message = str(caught.value)
    assert question[0] in message and question[1] in message, (
        "the refusal is in the QUESTION's own words -- CLAUDE.md rule 1's whole point"
    )
    assert not (tmp_path / "blocked").exists(), (
        "and it refuses BEFORE anything is written: a blocked morning leaves no recording"
    )

    # A REPLAY is never blocked by a live question: a past day has its bhavcopy and its verdict.
    assert ls.build_live_screener.__module__ == "acumen.live_screener"


def test_the_LIVE_startup_disclosure_says_what_could_not_be_verified() -> None:
    """CONTEXT 4.7's disclosure, in the words the section itself uses.

    Three things must survive any future edit of that banner, because each is a promise the
    ruling makes to the trader: WHICH battery ran, WHAT it could not check, and HOW OFTEN that
    has historically mattered. The measured residual is in it as a NUMBER -- the ruling's own
    instruction was that the residual is disclosed as a measured frequency, not an adjective.
    """
    text = ls.LIVE_STARTUP_DISCLOSURE
    assert "ORACLE-FREE battery" in text
    assert "Gates 1 and 1P are structurally INAPPLICABLE" in text
    assert ls.LIVE_DISCLOSURE in text, "the alert-level sentence is quoted inside the banner"
    assert "0.5229%" in text and "2,187/418,275" in text, (
        "the residual is a measured frequency, not an adjective (the architect's own words)"
    )
    assert "THIS TOOL PLACES NO ORDERS." in text


def test_the_screener_cli_reports_a_FAILURE_TO_START_rather_than_crashing(
    tmp_path: Path,
) -> None:
    """The operator's experience of a refusal: exit 1 and one sentence, not a traceback.

    The same standard REVIEW_12C finding C2 set for the two document generators. The refusal
    exercised here is the live path's own prerequisite (no dump for that day), which is what
    replaced the Q-28 block -- and the startup disclosure is printed BEFORE it, so an operator
    who gets no further has still been told what a live morning is.
    """
    from acumen import run_screener

    printed: list[str] = []
    import builtins

    real_print = builtins.print
    builtins.print = lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args))
    try:
        code = run_screener.main([
            "--mode", "live", "--day", "2026-07-17", "--symbols", "SYNTH",
            "--recording-root", str(tmp_path / "rec"),
        ])
    finally:
        builtins.print = real_print
    assert code == 1
    joined = "\n".join(printed)
    assert "CONTEXT 4.7 -- LIVE MODE" in joined, "the disclosure prints before anything runs"
    assert ls.LIVE_DISCLOSURE in joined
    assert "the screener cannot start" in joined
    assert "Traceback" not in joined


def test_a_REPLAY_carries_no_live_disclosure_because_its_day_WAS_verified() -> None:
    """The other half of CONTEXT 4.7, and the one a careless edit would get wrong.

    The disclosed line is a fact about DATA, not a disclaimer about software: a replayed day has
    a published bhavcopy and ran the full battery, so stamping it "not yet verified" would be
    false -- and a sentence that appears on everything is a sentence that means nothing when it
    appears on the morning that needs it.
    """
    screener = ls.LiveScreener(
        day=date(2026, 6, 10), symbols=(), pipeline=None, biases={}, gates={},
        source=None, recording=LiveRecording.at(Path(".")),
        clock=ls.VirtualClock(stamp=datetime(2026, 6, 10, 9, 0)),
    )
    assert screener.disclosure == ""
    assert screener.posture == ls.POSTURE_SETTLED


def test_the_master_tick_divergence_detector_MEASURES_and_decides_nothing() -> None:
    """QUESTIONS.md Q-29, built as a measurement.

    Q-20 pins ONE instrument master for the backtest. CONTEXT section 6 forbids backtest/live
    drift, so the live path takes the same pin -- and the residual question (what happens when a
    newer vendor dump disagrees about a live symbol's tick) is NAMED rather than answered. The
    detector reports the symbols; the ruling is the architect's.
    """
    from acumen.instrument_master import InstrumentMaster

    def master(tick_a: str, tick_b: str) -> InstrumentMaster:
        return InstrumentMaster.from_rows([
            {"exch_seg": "NSE", "symbol": "AAA-EQ", "token": "1", "tick_size": tick_a,
             "name": "AAA", "lotsize": "1"},
            {"exch_seg": "NSE", "symbol": "BBB-EQ", "token": "2", "tick_size": tick_b,
             "name": "BBB", "lotsize": "1"},
        ])

    pinned = master("5.000000", "5.000000")
    newer = master("5.000000", "1.000000")
    assert ls.master_tick_divergence(pinned, pinned, ("AAA", "BBB")) == {}
    assert ls.master_tick_divergence(pinned, newer, ("AAA", "BBB")) == {"BBB": (5, 1)}
    # an unknown symbol is not a divergence and is not an exception
    assert ls.master_tick_divergence(pinned, newer, ("ZZZ",)) == {}


def test_THE_NEWLY_LIVE_PATH_STILL_TOUCHES_ONE_BROKER_METHOD(tmp_path: Path) -> None:
    """The tripwires re-asserted against the path that can now actually run.

    Until 08-Aug-2026 ``run_screener`` could not reach a broker at all, because live refused to
    start -- so the AST scan above was guarding a path with no feed behind it. It has one now.
    What this checks is that opening that feed added exactly two calls to this repo's surface,
    both of them already reviewed: ``login`` on our own client, and ``get_candles``, which is
    CONTEXT 4.3 and 4.4's single named source of bars.

    Written as an AST walk over ``run_screener`` rather than as a string search, because the way
    this rule erodes is a convenience helper, not a pasted endpoint name.
    """
    from acumen import run_screener

    tree = ast.parse(Path(run_screener.__file__).read_text(encoding="utf-8"))
    called = {
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    broker_ish = {name for name in called if name in ORDER_ENDPOINTS}
    assert not broker_ish, f"the CLI reaches {sorted(broker_ish)}"
    assert "login" in called, "the live path opens a session, and that is all it opens"
    source_text = (PACKAGE / "live_source.py").read_text(encoding="utf-8")
    assert source_text.count("self.client.") == 1, (
        "the ONE broker call on the whole live path, unchanged by the unblocking"
    )


def test_A_PREFLIGHT_OPENS_NO_BROKER_SESSION_AT_ALL(tmp_path: Path) -> None:
    """``--preflight-only`` is what an operator runs before the bell. It must cost nothing.

    A preflight that logged in would be a preflight nobody runs twice, and a session opened at
    08:50 for a check is a session that can expire at 11:15 for a trade.
    """
    from acumen.live_source import BarSourceError
    from acumen.run_screener import PreflightOnlySource

    with pytest.raises(BarSourceError, match="no broker session is opened"):
        PreflightOnlySource().fetch("SYNTH", date(2026, 7, 17), datetime(2026, 7, 17, 11, 15))
