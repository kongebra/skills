---
name: k-common
description: Support files for the k- team skills. Holds shared scripts, roles, templates, and version pins. Other k- skills call it.
disable-model-invocation: true
---

# k-common

This skill is a support skill, not a workflow.
Other `k-` skills call the files in this folder.
Do not run it on its own.

## Required

`k-common` is required.
Onboarding installs it with every other `k-` skill.
`uv` is required.
When `uv` is missing, a skill stops and tells the user.

## Path rule

A skill finds the scripts at `../k-common/scripts`, relative to its own folder.
This works for copy installs and for symlink installs.
The calling skill passes its own parent folder to each script as `--skills-root`.

## Entry form

Run each script like this:

```text
uv run --no-project python <skills-root>/k-common/scripts/k.py <module> ...
```

## Contents

- `scripts/k.py` is the launcher.
- `scripts/kcommon/` holds the Python modules.
- `writing-standard.md` states the writing rules for skills and docs.
- `pyproject.toml` defines the `kcommon` project. It has no dependencies.
