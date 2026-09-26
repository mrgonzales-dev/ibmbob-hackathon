# Change Impact Risk Rubric

The only source of risk truth. The scanner applies this rubric. It does not
guess.

## How the scanner computes risk

The scanner counts two signals per changed file:

| Signal | How the scanner finds it |
|---|---|
| Direct callers | Other PHP files that reference the changed class name |
| Tests referencing | Files in `tests/` that reference the changed class name |

## Risk table

| Direct callers | Tests referencing | Risk | Reason |
|---|---|---|---|
| Yes | Yes | HIGH | The change ripples to callers. Tests exist to catch breaks. |
| Yes | No | HIGH | The change ripples to callers. No test safety net. |
| No | Yes | MED | No production ripple. Tests may still break. |
| No | No | LOW | The change is isolated. Low blast radius. |

## Overall risk

The overall risk for the change set is the highest risk across all changed
files.

| Overall | Meaning |
|---|---|
| HIGH | At least one changed file has direct callers. |
| MED | No callers, but tests reference a changed file. |
| LOW | No callers and no tests. The change is isolated. |

## What the scanner does NOT do

| Claim | Why the scanner skips it |
|---|---|
| Affected business rules | A grep cannot know which business rules a service implements. That is semantic, not syntactic. |
| Tests that will fail | A grep counts references, not failures. Only running tests tells you what broke. |
| Indirect callers | Facades, IoC, and magic methods break naive tracing. Report direct callers only. Mark them as heuristic. |
