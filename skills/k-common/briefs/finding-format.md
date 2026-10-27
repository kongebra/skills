# Finding format

Each finding has a fixed shape. The judge and the author agent both read it.

- Location: the file and line, or the spec section.
- What fails: a checkable statement of the failure.
- Suggested fix: a fix for the failure.
- Guardrail: a lint, a test, a type, or a CI check that could catch the problem automatically.
  Include this field only if such a guardrail could exist.

The attacker brief adds an ID and a proposed severity to these fields.
