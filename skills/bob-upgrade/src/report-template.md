# Risk report template

Print the report exactly as this file shows it. Keep the box characters.
Keep one blank line between blocks. Never print a finding you cannot point to.

## Header

```
╭──────────────────────────────────────────╮
│ 🛠️ BOB THE BUILDER                      │
│ DEPENDENCY UPGRADE ANALYZER              │
╰──────────────────────────────────────────╯
```

Then print the analysis line, using the versions from the detect phase.

```
Analyzing <current> → <target>...
```

Then print the inventory lines. Take every number from `preflight.py`. Do not
estimate a count.

```
✓ composer.json
✓ composer.lock
✓ <n> PHP files
✓ <n> dependencies
✓ <n> test cases
```

If a lock file is missing, print this line in its place.

```
✓ composer.lock (missing)
```

## Severity summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ UPGRADE RISKS FOUND

HIGH   <count>
MED    <count>
LOW    <count>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## High findings

Print this header only when the count is above zero.

```
🔴 HIGH RISK
```

Then number each finding from 1. Use this shape for each one.

```
1. <short title>

   <relative/path/to/file>:<line>

   Uses:
   <the code or setting that breaks>

   Replacement:
   <the code or setting to use instead>

   Rule: <ID from the breaking-change file>
```

Use `<file>` without a line number when no line applies. Omit the `Rule` line
only when the finding came from the live upgrade guide. In that case, add this
line at the end of the finding.

```
   Source: <url from the upgrade guide>
```

## Medium and low findings

Print these two blocks when the count is above zero. Do not list each item.

```
🟡 MEDIUM

<n> potential issues
```

```
🟢 LOW

<n> informational findings
```

## A clean project

Print this instead of the severity summary when the report holds no findings.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ NO UPGRADE RISKS FOUND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Then state which files were scanned and that the upgrade guide held no matching
change. Do not print the confirmation prompt in this case.

## Confirmation prompt

Print this last. Stop and wait for the answer. Accept `Y`, `y`, `yes`, or `N`,
`n`, `no`.

```
Would you like Bob to create an upgrade plan?

[Y] Yes
[N] No
```

## Plan output

After the user answers yes, print the plan. Keep the phase order.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UPGRADE PLAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phase 1  Update dependencies
Phase 2  Resolve deprecated APIs
Phase 3  Update configuration
Phase 4  Run migration tests
Phase 5  Run the complete test suite
Phase 6  Generate the upgrade PR
```

Then run one subtask per phase. Give each subtask the findings that belong to
it. Phase 6 writes `UPGRADE-PR.md`. It runs `gh pr create` only when `gh` is on
the PATH and the repository has a remote.
