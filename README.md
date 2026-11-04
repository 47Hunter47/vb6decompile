# vb6decompile

Recovering what a native-compiled VB6 program actually does, with evidence.

Commercial VB6 decompilers stop at one of two walls: they give you forms without
code, or code without the semantics that make it portable. This toolkit was built
while recovering a large native-compiled VB6 application (111 MB, ~34,000
procedures) whose source was lost. Every claim below is a measurement, and every
measurement has a command that reproduces it.

The point is not another disassembler. VB6 is not plain x86 at the level that
matters: strings are length-prefixed `BSTR`s stored inside `.text`, procedures are
entered through a fixed runtime prologue, most calls go through `MSVBVM60` vtable
dispatch, forms are serialised into the executable as binary property blobs, and
reports live in separate VB6 DLLs as `DataReport` blobs. Off-the-shelf tools read
none of that. These modules do.

Nothing here points at the program it was developed against: no target name, no
host, no database name, no account, no credential, no absolute install path.
**You supply every path.**

## What it does

| Stage | Command | Evidence it produces |
|---|---|---|
| PE surface of an install | `vb6d pe <dir>` | imports, exports, VB6 runtime dependency, ActiveX/COM classification |
| Procedure inventory | `vb6d procs <exe>` | object table: objects and method counts, entry points verified by prologue |
| String / SQL harvest | `vb6d literals <exe or listing dir>` | `BSTR` (UTF-16LE) literals the ASCII scanners miss, with code addresses |
| SQL reconstruction | `vb6d stitch <dir or listing>` | fragments joined into whole statements, with explicit "not provable statically" buckets |
| Form design | `vb6d frm <dir>` | controls, geometry, `Visible`, control arrays, `SSTab` pages from `.frm` text |
| Form geometry from binary | `vb6d blob <exe> --validate` | geometry for forms that have no `.frm`, calibrated against `.frm` ground truth |
| DataReport layout | `vb6d datareport <dll or dir>` | report sections, controls, captions recovered from the runtime blobs |
| Form icons from `.frx` | `scripts/frx_icon.py <frx dir> <out> [--validate <frm dir>]` | standalone `.ico` per form, extracted from the leading ICON record without the executable; coverage cross-checked against `.frm` Icon references |
| Credential gate | `vb6d mask <dir>` | connection strings redacted, then an audit counting what is still live |

## You fill these in

Every entry point takes a path; nothing is baked in. Real-target tests read five
variables and skip when they are unset.

| Variable | What you put in it |
|---|---|
| `VB6D_TARGET` | your VB6 executable, e.g. `D:/App/App.exe` or `/opt/app/App.exe` |
| `VB6D_LISTINGS` | a directory of decompiler output (listing text, `.frm`, `.frx`) |
| `VB6D_FRM_DIR` | a directory holding `.frm` design text — ground truth for `--validate` |
| `VB6D_REPORT_DIR` | the install directory holding the report DLLs |
| `VB6D_SCRUB_DENYLIST` | optional: a private file, one name per line — names you refuse to publish. The hygiene test fails if any of them appears in this repository. |

Set them for one command, or export them for a session:

```bash
# bash / zsh
export VB6D_TARGET="/opt/app/App.exe"
export VB6D_LISTINGS="$HOME/work/decompile"
export VB6D_FRM_DIR="$HOME/work/decompile"
export VB6D_REPORT_DIR="/opt/app"
```

```powershell
# PowerShell
$env:VB6D_TARGET     = "D:/App/App.exe"
$env:VB6D_LISTINGS   = "D:/work/decompile"
$env:VB6D_FRM_DIR    = "D:/work/decompile"
$env:VB6D_REPORT_DIR = "D:/App"
```

## Why not an existing tool

Measured on the same target (`docs/tool-matrix.md` has the full table, including
how each number was obtained):

* **Semi-VB-Decompiler** — the only free tool that recovers procedure *bodies*. It
  is single-threaded, overflows its `Integer` procedure counter above 32,767
  procedures (`Error 6`), needs a PE `LAA` bit patch to use more than 2 GB, and
  writes one event name for every body in a form. Bodies are pseudo-source
  (`var_64`, `arg_C`), not compilable code.
* **VBReFormer** — forms and structure, expression bodies withheld without a
  licence; cannot even accept the 111 MB executable (transport limit).
* **Ghidra / Rizin / IDA** — no VB6 knowledge: no `BSTR` literals, no procedure
  table, no form blobs, no `DataReport` blobs.
* **Generic RE engines** — correct for C/C++/Rust/Go, blind to VB6 layout. One such
  engine found 6,875 functions of 34,159 (20 %, stopped at its own instruction cap)
  and 59 strings with zero SQL, because its string scanner does not read UTF-16LE
  literals.

None of these is wrong; they are aimed at C/C++/Rust/Go binaries. The gap this
repository fills is VB6-specific structure, and it fills it with reproducible
counts rather than vendor percentages.

## Install

```
git clone <this repo> && cd vb6decompile
python -m pip install -e .
```

Python 3.11+. **Nothing outside the standard library is required** — every parser
here is hand-written, which is the point (a library wrapper would hide the layout).
`pefile` and `capstone` are optional and used only as a second opinion while
developing:

```
python -m pip install -e ".[pe,asm]"
```

## Quick start

```
vb6d pe            <install dir>                 # what is this install made of
vb6d procs         <app.exe>                     # object table: objects, method counts
vb6d procs         <app.exe> --validate          # are the entry points real prologues
vb6d literals      <app.exe>                     # BSTR/UTF-16 literals with addresses
vb6d literals      <listing dir> --sql-only      # literals a decompiler listing produced
vb6d stitch        <listing dir>                 # join fragments, classify what stayed open
vb6d frm           <listing dir>                 # .frm controls, geometry, arrays, SSTab
vb6d blob          <app.exe> --validate --frm-dir <frm dir>
vb6d datareport    <install dir>                 # report layouts from the report DLLs
vb6d mask          .                             # mask credentials in your artefacts
vb6d mask          . --dry-run                   # report only; exit 1 if anything is live
```

What one native VB6 build used while developing produced (111 MB, 802 forms), so
you can tell at a glance whether your own numbers look sane:

| Stage | Result |
|---|---|
| object table | 834 objects, 34,415 methods, 0.4 s |
| literals from the image | 167,564 in 4.6 s (6,171 with a SQL verb) |
| literals from a listing | 441,607 in 12,480 procedures |
| statements | 10,691 starts → 8,745 closed in 4,109 procedures, 494 tables |
| `.frm` design | 369 forms, 30,000 controls, 126 forms with control arrays |
| form blobs | 801 blobs, 24,967/24,967 controls (100 %), 367/369 forms |
| DataReports | 437 layouts (413 in report DLLs + 24 embedded in the executable) |

A different program legitimately gives different numbers. The tests assert
invariants and lower bounds, not these totals.

## Honest limits

* Procedure **names** are not recoverable from a native build; only addresses and
  the names a decompiler guessed. Treat every name as a hint.
* Bodies recovered by a third-party decompiler are pseudo-source. Expression-level
  fidelity does not exist in any free tool measured here.
* SQL that is built at run time (concatenated from variables) cannot be closed
  statically. `vb6d stitch` reports those gaps as gaps instead of guessing.
* Geometry recovered from the binary is calibrated, not exact for forms that
  changed after the `.frm` in hand was written; `--validate` says so per form.

## Layout

```
vb6decompile/     the library (one module per stage, stdlib only except pefile/capstone)
scripts/          standalone helpers (semi_laa.py: set the LAA bit on a copy;
                  frx_icon.py: extract the leading ICON record of a .frx)
tests/            unit tests + target tests that skip unless VB6D_TARGET is set
docs/             formats.md (structures), pitfalls.md (traps), tool-matrix.md,
                  pipeline.md (stages and what each may claim), RULES.md
```

Run the tests:

```
pip install -e ".[dev]"
pytest -q                                            # unit tests, no target needed
VB6D_TARGET="C:/path/App.exe" pytest -q              # + real-target invariants
VB6D_LISTINGS="C:/path/decompile" pytest -q          # + listing/stitching tests
VB6D_FRM_DIR="C:/path/decompile" pytest -q           # + blob calibration
VB6D_REPORT_DIR="C:/path/install" pytest -q          # + DataReport parsing
```

`docs/formats.md` is the structure reference: every offset, every grammar, and the
fields that look documented but are not what they claim (`lpMethods` in a native
build, `lpGuiTable`). `docs/pitfalls.md` is the second most useful file: it lists
the traps that cost days (double-`Integer` overflow, `OriginalFirstThunk` vs
`FirstThunk`, CP1254 vs UTF-16, `Visible` defaults, blob property sorting) with the
measurement that
proved each one.

## Licence

MIT. See `LICENSE`.
