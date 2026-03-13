# ShaprAI CLI Accessibility Audit

**Date:** 2026-03-12
**Auditor:** Bounty Agent
**Standard:** WCAG 2.1 AA (adapted for CLI interfaces)
**Scope:** ShaprAI CLI (`shaprai` command-line tool)

## Context

ShaprAI is a CLI-only Python application — it has no web UI. This audit
adapts WCAG 2.1 AA success criteria to the terminal environment where
the CLI is used. The Flameholder has TBI and mobility challenges, so
accessible CLI output is essential — not optional.

---

## Issues Found

### Issue 1: Table output not parseable by screen readers

**WCAG Reference:** 1.3.1 Info and Relationships (Level A)

**Severity:** High

**Description:**
`shaprai fleet status` and `shaprai template list` render tables using
fixed-width column alignment. Screen readers (NVDA, VoiceOver, ORCA)
read these as a stream of text, making it impossible to associate cell
values with their column headers.

**Before:**
```
Name                      State           Template             Platforms
--------------------------------------------------------------------------------
my-agent                  DEPLOYED        bounty_hunter        github, bottube
```
Screen reader announces: "Name State Template Platforms dashes my-agent DEPLOYED
bounty underscore hunter github comma bottube" — no association between
"my-agent" and "Name."

**Fix applied:**
- Added `--format plain` mode: each row prints every field with its header
  label (e.g. "Name: my-agent", "State: DEPLOYED"), so screen readers
  announce the label with each value.
- Added `--format json` mode: outputs a JSON array of objects for assistive
  technology integrations and scripting.

---

### Issue 2: No machine-readable output for assistive tools

**WCAG Reference:** 1.3.2 Meaningful Sequence (Level A)

**Severity:** High

**Description:**
Several commands output key-value details using whitespace alignment
(e.g. the `shaprai create` summary). There was no way to extract
structured data from CLI output for use with screen readers, automation,
or other assistive tools.

**Fix applied:**
- Added `--format json` global option that all commands respect.
- JSON output uses consistent key names derived from display labels.
- The `shaprai.a11y` module centralises formatting logic so every
  command automatically supports all three output modes.

---

### Issue 3: Inconsistent error identification

**WCAG Reference:** 3.3.1 Error Identification (Level A)

**Severity:** Medium

**Description:**
Error messages used inconsistent prefixes and formatting:
- Some started with "Error:" — e.g. `create`, `deploy`
- Others used "FAILED" — e.g. `train --phase driftlock`
- Some wrote to stderr, others to stdout
- No machine-readable error format for screen readers

A user relying on a screen reader or text parser cannot reliably detect
when a command has failed.

**Fix applied:**
- All error messages now go through `emit_error()`, which always
  prefixes with "Error:" in text/plain mode.
- In JSON mode, errors are emitted as `{"error": "...", "hint": "..."}`.
- All errors are written to stderr in text/plain mode.

---

### Issue 4: Error messages lack corrective suggestions

**WCAG Reference:** 3.3.3 Error Suggestion (Level AA)

**Severity:** Medium

**Description:**
Many error messages stated what went wrong but did not suggest what to
do next. Examples:
- `Error: Agent 'x' not found.` — does not say how to create one.
- `Error: Template 'y' not found.` — does not say how to list templates.

**Fix applied:**
- Added `hint` parameter to `emit_error()`.
- Every error now includes a specific corrective action, e.g.:
  `Hint: Run 'shaprai template list' to see available templates.`

---

### Issue 5: Insufficient help text on CLI options

**WCAG Reference:** 3.3.2 Labels or Instructions (Level A)

**Severity:** Low

**Description:**
Several CLI options had minimal help text:
- `--phase` said only "Training phase" — did not explain valid values
  or the required ordering.
- `--template` said only "Template name or path" — did not explain
  where templates come from.
- `--data` said only "Path to training data" — did not describe format.

**Fix applied:**
- Expanded help strings for `--phase`, `--template`, `--model`, `--data`,
  `--platform`, `--lesson`, `--description`, and `--format`.
- Added docstring detail to `train`, `graduate`, `sanctuary`, and
  `evaluate` commands.

---

### Issue 6: Key-value output lacks explicit label association

**WCAG Reference:** 1.3.1 Info and Relationships (Level A)

**Severity:** Medium

**Description:**
The `shaprai create` and `shaprai evaluate` commands displayed details
using whitespace-aligned "pseudo-labels" like:
```
  Model:    qwen/Qwen3-7B
  State:    CREATED
```
The alignment relies on visual spacing. In `--format plain`, labels
use an explicit "Label: Value" pattern. In `--format json`, the
association is semantic (object key → value).

**Fix applied:**
- Replaced ad-hoc `click.echo` formatting with `emit_key_value()`.
- `plain` mode outputs "Label: Value" per line.
- `json` mode outputs `{"label": "value"}`.

---

## Summary of Fixes

| # | Issue | WCAG | Severity | Status |
|---|-------|------|----------|--------|
| 1 | Table output not screen-reader-friendly | 1.3.1 | High | Fixed |
| 2 | No machine-readable output | 1.3.2 | High | Fixed |
| 3 | Inconsistent error identification | 3.3.1 | Medium | Fixed |
| 4 | Errors lack corrective suggestions | 3.3.3 | Medium | Fixed |
| 5 | Insufficient help text | 3.3.2 | Low | Fixed |
| 6 | Key-value labels not associated | 1.3.1 | Medium | Fixed |

## Files Changed

- **`shaprai/a11y.py`** (new) — Accessible output formatting module
- **`shaprai/cli.py`** (modified) — Added `--format` option, uses `a11y` helpers
- **`tests/test_a11y.py`** (new) — 25 test cases covering all output modes
- **`ACCESSIBILITY_AUDIT.md`** (new) — This audit report

## Testing

```bash
# Run the accessibility test suite
pytest tests/test_a11y.py -v

# Manual screen-reader testing (example with --format plain)
shaprai --format plain fleet status
shaprai --format json template list
```

## Notes

ShaprAI is a CLI tool — traditional WCAG web-UI criteria (color contrast
ratios, focus indicators, ARIA labels) are not directly applicable.
This audit adapts the relevant WCAG principles to the CLI context:
structured output for screen readers, consistent error messaging, and
machine-readable alternatives for assistive technology integration.
