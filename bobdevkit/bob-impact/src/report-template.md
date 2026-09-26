# Change Impact Report Template

The exact layout for the `bob-impact` terminal report. Copy this structure.
Do not pad the report.

```
╭──────────────────────────────────────────────────╮
│ BOB THE BUILDER                                  │
│ CHANGE IMPACT ANALYZER                           │
╰──────────────────────────────────────────────────╯

Changed files:
  <file1>
  <file2>

Direct callers (heuristic — facades and IoC may miss some):
  <caller_file1>          → <ClassName>
  <caller_file2>          → <ClassName>

Database tables:
  <table1>
  <table2>

Tests referencing changed code:
  <test_file1>            → <ClassName>
  <test_file2>            → <ClassName>

Risk: HIGH

Findings: <count>
Rubric:   src/risk-rules.md
```

## Empty lanes

When a lane finds nothing, print one clean line. Do not pad.

| Lane empty | Print |
|---|---|
| No direct callers | `Direct callers: none` |
| No database tables | `Database tables: none` |
| No tests referencing | `Tests referencing changed code: none` |

## No findings at all

When all three lanes find nothing:

```
No findings. The change is isolated.
Risk: LOW
```
