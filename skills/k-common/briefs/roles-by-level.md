# Roles by risk level

The two review skills use these roles for each risk level.

| Level | k-spec-review roles | k-code-review roles |
|---|---|---|
| Low | Critic, Reality check | Test quality |
| Medium | Zoom-out, Critic, Reality check | Test quality, Standards |
| High | Zoom-out, Naive reader, Critic, Reality check, Readiness | Test quality, Standards, Critic, Invariant (one for each invariant, at most 3) |

A role name maps to its file in `roles/` by lower case and hyphens. Example: `Test quality` gives `test-quality.md`.
The Zoom-out, Naive reader, and Reality check roles are not used on code in iteration 1.
