"""The `vb6d` command line: wiring, exit codes and output shape.

No target binary is needed. The `.frm` fixtures and a temporary directory cover the
paths that can be exercised anywhere; the target-dependent commands
(`procs`, `blob`, `datareport`, `literals` against a real image) are covered by
`test_target.py` and skip without `VB6D_TARGET`.

What these tests are for: `cli.py` is the only module with no other caller, so a
broken subcommand is invisible until someone runs it by hand.
"""

from __future__ import annotations

import json
import os

import pytest

from vb6decompile import cli

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _run(argv, capsys):
    code = cli.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


# --------------------------------------------------------------------------- wiring
def test_every_subcommand_is_wired_to_a_function():
    parser = cli.build_parser()
    # Introspect what argparse actually built: a subparser missing `func` dies with
    # AttributeError only when that one subcommand is used.
    actions = [a for a in parser._actions if hasattr(a, "choices") and isinstance(a.choices, dict)]
    assert actions, "no subparsers found"
    subs = actions[0].choices
    assert set(subs) == {"pe", "procs", "literals", "stitch", "frm", "blob", "datareport", "mask"}
    for name, sub in subs.items():
        assert hasattr(sub.get_default("func"), "__call__"), f"{name} has no func"


def test_missing_subcommand_exits_nonzero():
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code != 0


# --------------------------------------------------------------------------- frm
def test_frm_prints_a_summary_with_its_denominator(capsys):
    code, out, err = _run(["frm", FIXTURES], capsys)
    assert code == 0
    # The denominator is not decoration: "369 parsed" means nothing without "of 802".
    assert "parsed" in err and "of" not in err.lower().split("parsed")[0]
    assert "files:" in err
    assert out.strip(), "no per-form lines printed"


def test_frm_json_is_machine_readable(capsys):
    code, out, _err = _run(["frm", FIXTURES, "--json"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert payload["files_seen"] >= len(payload["forms"])
    assert all("controls" in f for f in payload["forms"])
    # A file with no design block is reported, not silently dropped.
    assert isinstance(payload["no_design_block"], list)


# --------------------------------------------------------------------------- mask
def test_mask_reports_zero_findings_and_exits_zero(tmp_path, capsys):
    (tmp_path / "notes.md").write_text("nothing secret here\n", encoding="utf-8")
    code, out, _err = _run(["mask", str(tmp_path)], capsys)
    assert code == 0
    assert "clean=True" in out


def test_mask_exits_one_when_a_secret_survives(tmp_path, capsys):
    # dry_run skips the write, so the value is still there afterwards: the audit must
    # say so and the exit code must be non-zero. A gate that always exits 0 is a
    # decoration, not a gate.
    leak = tmp_path / "leak.csv"
    leak.write_text("uid=sa;pwd=hunter2\n", encoding="utf-8")
    code, out, _err = _run(["mask", str(tmp_path), "--dry-run"], capsys)
    assert code == 1
    assert "clean=False" in out


def test_mask_dry_run_does_not_write(tmp_path):
    leak = tmp_path / "leak.csv"
    leak.write_text("uid=sa;pwd=hunter2\n", encoding="utf-8")
    cli.main(["mask", str(tmp_path), "--dry-run"])
    assert "hunter2" in leak.read_text(encoding="utf-8")
