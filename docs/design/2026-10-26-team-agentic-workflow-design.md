# Team agentic workflow skills - design

- **Date:** 2026-10-26
- **Status:** Draft for approval.
- **Owner:** Svein Danielsen
- **Type:** Dated design archive. This document records why the repo exists and how it is built. It is not maintained documentation.

Marks used in this document:

- **[Svein]** - Svein decided this.
- **[call]** - The author of this document decided this, and Svein can override it.
- **[verify]** - A fact that the build must confirm before the design depends on it.

## 1. Intent

This repo holds a shared set of agent skills for a development team.
The skills standardise one way to take a work item from a board to a pull request (PR) with AI coding agents.
The team uses the repo across projects and across coding agents.
This is iteration 1.

The workflow combines four sources:

- Spec-driven development: a spec and a plan come before code.
- The Elephant-Goldfish Model (EGM): the agent that wrote a document does not review it. Reviewers start with a fresh context and read only the document and the code.
- Matt Pocock's grilling and domain modeling: a structured interview, a glossary, and ADRs.
- obra/superpowers: brainstorming, plans, worktrees, subagent-driven development, and test-driven development.

### 1.1 End goal

The end goal is that no human reviews the code line by line. **[Svein]**
The team must earn this trust over time, and the team must feel comfortable with it. **[Svein]**
At the start, humans review every PR. **[call]**

Risk controls review. **[Svein]**
Low-risk changes need little review.
High-risk changes need more reviewers, more tests, and human eyes on the code.

### 1.2 Where the human works

1. The human (the "creator") takes a work item to the agent.
2. The creator and the agent grill and brainstorm. The result is a spec and a plan.
3. Fresh-context reviewers review the spec and the plan.
4. The creator approves the reviewed spec and plan. This is the last human step before the PR. **[Svein]**
5. The agent implements, reviews the code, and opens the PR without a human.
6. The creator reads the PR and merges it. **[Svein]**

The spec review runs before the final approval, so that the creator is not asked again when a reviewer finds a problem. **[Svein]**

### 1.3 Future models

Models from Anthropic, OpenAI, and other vendors improve fast. **[Svein]**
The workflow must stay useful when models get better, and it must not limit better models. **[Svein]**
Therefore the skills state goals, gates, and evidence. They do not prescribe each step. **[call]**
Limits such as round caps and reviewer counts are configuration, not fixed rules. **[call]**

## 2. Goals, non-goals, anti-goals

### Goals

- One standard workflow for the team, from work item to PR.
- The workflow works in Claude Code, GitHub Copilot, Codex, OpenCode, and Pi. Hermes is used rarely. **[Svein]**
- Each PR carries evidence that a non-technical reader can trust.
- The upstream skills keep their updates, and the team knows when an update breaks the workflow.
- The repo stays small. It holds only what the upstream skills do not provide.

### Iteration 1 scope

Iteration 1 contains every skill the workflow needs from intake to PR. **[Svein]**
All team skills use the prefix `k-`. The prefix is temporary and can change later. **[Svein]**

| Skill | Purpose |
|---|---|
| `k-work` | Entry skill. Runs the stages in order and resumes from the ledger. |
| `k-intake` | Reads the work item, runs the preflight, creates the worktree, the ledger, and the risk level. |
| `k-spec-review` | Fresh-context review of the spec and the plan. |
| `k-code-review` | Review of what superpowers does not cover. |
| `k-pr` | Risk facts, evidence, decisions, and the PR. |
| `k-report-finding` | Files out-of-scope findings in the background. |
| `k-guardrails-check` | Checks a project and reports its guardrails. |

The repo is public on GitHub as `kongebra/skills`. **[Svein]**

Release bar: **[call]**

- Evals must pass on Claude Code and on Copilot (VS Code and CLI).
- Codex, OpenCode, and Pi get best-effort support. Their evals run, but a failure does not block a release.
- The evals use Azure DevOps Boards with GitHub as the first board and code host pair. Other boards and code hosts work through the facts in `AGENTS.md`. They are unverified until a project uses them.

### Non-goals (iteration 1)

- Automatic merge.
- A skill that sets up guardrails in a project. The repo only checks and reports. **[Svein]**
- A loop that works through PR review comments. This replaces the personal `review-burndown` skill later. **[call: iteration 2]**
- A sandbox or dev container base image for agents. It is a separate repo with its own owner. `guardrails-check` only reports whether a project uses one. **[Svein]**

### Anti-goals

The workflow fails, even if it technically works, when:

- The PR summary hides a risky change.
- Review loops run without end or cost more than the change is worth.
- The workflow adds so many steps that the team skips it for small changes.
- An upstream update silently changes behaviour for some teammates and not for others.
- Text from a work item steers the agent to do something that the creator did not ask for.

## 3. Constraints

### 3.1 Upstream skills

- obra/superpowers is used as it is. The team does not change it. **[Svein]**
- From mattpocock/skills, the team uses only `grilling`, `grill-with-docs`, and `domain-modeling`. The team does not use his tickets, `to-spec`, or his GitHub-issue workflow. **[Svein]**
  `grill-with-docs` has `disable-model-invocation: true`. Only a human can start it. The workflow therefore calls `grilling` and `domain-modeling` directly. **[call]**
- The team does not install the EGM plugin. The repo takes ideas from EGM only. **[Svein]**
  EGM is Apache-2.0. If any role file reuses EGM text, the repo must include attribution. **[call]**

### 3.2 Specs, plans, and the durable record

- Specs and plans are working documents for agents. They stay out of git (gitignored). **[Svein]**
- The durable record is: **[call]**
  - The work item: acceptance criteria and the answers to open questions. The agent updates the work item before it opens the PR.
  - The PR: summary, evidence, and decisions.
  - ADRs and `GLOSSARY.md`: `domain-modeling` writes these into the repo.
- Design documents about this repo itself go in `docs/design/`, dated. **[Svein]**

### 3.3 Writing standard

All text that the workflow writes follows ASD-STE100 (Simplified Technical English). This includes specs, reviews, code comments, and PR text. **[Svein]**
The rule applies to written artifacts: the spec, the plan, review reports, code comments, work item updates, and the PR. **[call]**
It does not apply to the live conversation with the creator.
The upstream skills cannot be changed, so the rule reaches them through an instruction in the project's `AGENTS.md` and through every team brief. **[call]**
The ASD-STE100 dictionary is copyright of ASD. The repo states the writing rules and does not copy the dictionary. **[call]**
An STE finding never blocks a review loop and never starts a new round. **[call]**

### 3.4 Boards and code hosts

- Work items come from boards such as Azure DevOps Boards and Jira. Most work items are not a developer's own idea. **[Svein]**
- Code lives on GitHub, Azure DevOps Repos, GitLab, or Forgejo. **[Svein]**
- Each board and code host has a CLI or an API. The skills use the CLI. **[Svein]**

### 3.5 Coding agent differences (checked 2026-10-26)

| | Claude Code | Copilot | Codex | OpenCode | Pi | Hermes |
|---|---|---|---|---|---|---|
| Project skill folder | `.claude/skills` only | `.github`, `.claude`, `.agents` | `.agents` | `.opencode`, `.claude`, `.agents` | `.pi`, `.agents` | `.hermes`, `.agents` |
| Reads `AGENTS.md` | Only when no `CLAUDE.md` exists | Yes | Yes | Yes | Yes | First match only |
| Subagents | Yes | Yes (VS Code, CLI). Cloud agent: [verify] | Yes | Yes | No. Example extension only | Yes |
| Model per subagent | Yes, and effort | Yes | Yes, and effort | Yes | In the extension | Global setting only |
| Can block `git commit --no-verify` | Hook | CLI hook. VS Code: [verify] | Hook or rule, after trust | Plugin or permission rule | Extension | User config only |
| Needs a trust step on first run | Project plugins | [verify] | Hooks and rules | [verify] | Project skills | Project skills |

Consequences:

- Every team skill reads `AGENTS.md` by its path. It does not depend on the coding agent to load it. It passes the needed facts into each subagent brief. **[call]**
- A fresh-context review never runs in the same context as the author. If a coding agent cannot start a subagent, the skill stops and tells the creator. **[call]**
  The creator can override this and continue. Then the review is "not independent", the risk level becomes high, and a human reviews the code. The PR shows the review mode. **[call]**
- Hooks in Claude Code and Copilot CLI let the command run when the hook times out, unless the hook is configured to block. The snippets in this repo configure them to block. **[call]**

## 4. Approaches

Three ways to build the repo were considered.

**A. A thin team layer on top of the upstream skills.** Chosen. **[Svein]**
The repo holds only the team skills, the role files, the templates, the harness snippets, and a list of tested upstream versions.
Superpowers is installed with its own installer for each coding agent.
Matt's three skills are installed with `npx skills add mattpocock/skills -s grilling -s domain-modeling` at a fixed commit.
The team skills are installed with `npx skills`. It works from GitHub, Azure DevOps, and GitLab.
Tradeoffs: the workflow depends on how superpowers hands over between skills. The spec review fits in through instructions, and this is not yet tested on each coding agent. The creator approves twice: the design, then the reviewed plan.

**B. One bundle with copies of all skills.**
The repo copies superpowers, Matt's three skills, and the team skills at fixed commits. A sync script brings upstream changes as PRs.
Gains: one install, exact versions, and the option to patch the superpowers hand-overs.
Tradeoffs: it changes superpowers, the sync is real work (superpowers went from v6.3 to v7.0.1 in about 10 weeks), and the copies drift from upstream.
B is the fallback when A breaks (section 7.4). **[Svein]**

**C. A rewrite from scratch.** Rejected.
The team would lose upstream improvements and maintain all of it alone.

## 5. The workflow

```text
work item
  -> k-intake             (team)        worktree, risk level, ledger
  -> grilling             (Matt)        with domain-modeling
  -> brainstorming        (superpowers) design doc, creator approves  [human]
  -> writing-plans        (superpowers) plan
  -> k-spec-review        (team)        fresh reviewers, fix, cap
  -> creator approves reviewed spec + plan                              [human]
  -> subagent-driven-development + test-driven-development (superpowers)
  -> k-code-review        (team)        what superpowers does not cover
  -> k-pr                 (team)        evidence, risk facts, decisions
  -> creator reads and merges                                            [human]
```

A thin entry skill runs the stages in order and resumes from the ledger. Each stage skill also works alone. **[call]**

The entry skill takes over two superpowers hand-overs:

- After `writing-plans` saves the plan, the entry skill runs `spec-review` before the plan approval question. The creator then approves the reviewed spec and plan, and the entry skill gives the execution method in advance: subagent-driven. **[call]**
  The "Native" method (`executing-plans`) is not used in the team workflow, because it has no review per task. It is allowed only through the override in section 3.5, with the same consequences.
- `subagent-driven-development` ends by calling `finishing-a-development-branch`, which shows a menu. After the creator's approval, no human acts until the PR, so the entry skill answers the menu with "push and create a PR". `code-review` runs before the push, and `pr` writes the PR body. **[Svein: no human after approval]** **[call: how]**

Both take-overs work through instructions. Both get a contract check (section 7.2) and an eval (section 7.3).

### 5.0 Fast path for trivial changes

Intake proposes "trivial" for a change such as a typo, a docs fix, or a one-line fix with an existing test. The creator confirms it. **[call]**
A trivial change skips brainstorming, the plan, and the spec review.
It still runs `test-driven-development`, `code-review`, and `pr`.
Grilling runs only when the work item has open questions.
The PR shows that the fast path was used. When the diff touches a protected path, the risk facts raise the level, and the PR says so.

### 5.1 One interview

Grilling and domain modeling lead the interview, with the work item as input. **[call]**
Brainstorming then starts with this material. It takes its "they have already said what they want" path: a short echo, the approaches, and the design doc.
The creator does not answer the same questions twice.

### 5.2 Questions the creator cannot answer

The creator is often not the author of the work item. **[Svein]**
The agent marks each question as "the creator can answer" or "the work item author must answer". **[call]**
The agent posts the second type as a comment on the work item and pauses. It does not guess.
The PR shows who answered each question.

### 5.3 Risk levels

Intake sets a risk level. The PR skill checks the level again against the real diff and raises it when needed. **[call]**

| Level | Typical change | Spec review | Human code review (start) |
|---|---|---|---|
| Low | Docs, small local change with tests | One combined reviewer, or skipped for a trivial change | Yes, until the team loosens it |
| Medium | Normal feature or fix | All reviewer roles | Yes, until the team loosens it |
| High | Protected paths: login, auth, migrations, infrastructure, CI, guardrail files, dependencies | All roles, strongest model, more rounds | Yes, always in iteration 1 |

The project's `AGENTS.md` lists the protected paths and any loosening that the team has agreed. **[call]**
This follows the blast-radius rule: shared code on a critical path is judged by what fails when it fails, not by how often it has failed. **[Svein]**

### 5.4 State and resume

Intake creates the worktree first. The spec, the plan, and all team files then start inside the worktree. **[call]**
`using-git-worktrees` detects an existing worktree and does not create a second one.
Superpowers keeps its default paths (`docs/superpowers/specs/`, `docs/superpowers/plans/`). The project gitignores `docs/superpowers/`. **[call]**
Team files go in `.agent-work/<work-item-id>/`, which is gitignored. **[call]**
The ledger (`ledger.md`) records the stage, the round, open findings, the work item ID, the branch, and the risk level. Every team skill reads the ledger when it starts.

### 5.5 Review loops

Each loop has a round cap and a severity bar. **[call]**
Only blocking findings start a new round.
At the cap, the loop stops. Open findings go to the PR as decisions.
Defaults: spec review 3 rounds, code review 2 rounds after the superpowers final review. `AGENTS.md` can change the defaults.
The author agent sorts each finding as accepted or rejected, and gives a reason. The next reviewer sees rejected findings and their reasons.

## 6. Components

### 6.1 Project facts in `AGENTS.md`

Each project has one fixed section. It holds facts only. Behaviour stays in the skills. **[call]**

```markdown
## Work tracking
- Board: Azure DevOps Boards, org `contoso`, project `Webshop` (CLI: `az boards`)
- Code host: GitHub (CLI: `gh`)
- Findings go to: GitHub Issues, label `agent-found`, visibility: private
- Link work items in PRs as: `AB#1234`
- Branch names: `feature/1234-short-name`
- Protected paths: `src/auth/**`, `db/migrations/**`, `.github/**`, `infra/**`
- Review limits: spec 3 rounds, code 2 rounds
```

When the section is missing, the skill proposes it, and the creator confirms it before the skill writes it. **[call]**
The skill does not write it alone, because this file later steers CLI commands.

### 6.2 `k-intake` (new)

- Reads the work item with the board CLI from `AGENTS.md`.
- Runs a preflight check: each CLI answers a read command, and CI exists. If a check fails, the skill stops with a clear message. **[call]**
- Treats work item text, comments, and links as data, not as instructions. It puts this text in a marked block. **[call]**
- Creates the worktree, the ledger, and the risk level.
- Never invents acceptance criteria. When the work item has none, the grilling produces them, and the creator confirms them.

### 6.3 Reviewer role files (new)

Each role is one Markdown file with a section for a spec and a section for code. **[call]**
A general-purpose subagent reads the role file first. The repo does not use agent definition files, because each coding agent has its own format.

| Role | On a spec | On code |
|---|---|---|
| Zoom-out | Is this the right problem? What can we cut? What exists already? | Is it overbuilt? Does it duplicate existing code? |
| Naive reader | Undefined terms, hidden assumptions | Unclear names, missing context |
| Critic | Failure modes, edge cases | The same, in the real code |
| Reality check | Do the claims about the code hold? | Does the diff do what the spec says? |
| Readiness | Can someone build from this? | - |
| Test quality | - | Do the tests prove each acceptance criterion? Did each test fail before the code existed? |
| Standards | - | Repo conventions, code smells |

Each brief gives the reviewer only the document or diff, the role file, and the facts from `AGENTS.md`. It does not give the author's reasons. **[call]**
Reviewers have read-only tools, and they do not follow instructions found in the material they review. **[call]**

### 6.4 `k-spec-review` (new)

- Runs after `writing-plans` and before the creator's final approval.
- Reviews the spec and the plan together.
- The risk level selects the roles, the model tier, and the round cap.
- The order follows EGM: zoom-out first, so that a wrong design is not polished.

### 6.5 `k-code-review` (new)

The superpowers subagent-driven development already reviews each task and the whole branch.
The team skill covers only what that review does not cover: test quality, proof that the tests failed first, project standards, and protected paths. **[call]**
Proof that a test failed first is a fact, not a claim. **[call]**
The test commit comes before the code commit. The entry skill adds this rule to the plan's global constraints, because superpowers does not require a separate test commit.
The reviewer runs the tests on the commit before the code and records the output.
A claim without output counts as not done.

Rules for the proof: **[call]**

- Medium and high risk: a missing proof is a blocking finding.
- Low risk: a missing proof goes to the PR as a decision.
- Exempt: docs, config without behaviour, and refactors that existing tests already cover. For a refactor, the proof is that the same tests pass before and after.
- The PR records the command and its output, so a squash merge does not remove the evidence.

### 6.6 `k-pr` (new)

The PR contains, in this order: **[call]**

1. A non-technical summary in ASD-STE100.
2. The risk level.
3. **Risk facts**, made by a script from the diff, and pasted without change. The model cannot edit this block. It lists changed protected paths, new or changed dependencies and lock files, migrations, CI and infrastructure changes, deleted or skipped tests, and test counts before and after.
4. The acceptance criteria as a checklist. Each item has its evidence: a test name or a command.
5. Decisions that the agent made without asking. Sources: the brainstorming "calls I made" list, the superpowers "Rulings" list, and findings that were open when a loop reached its cap.
6. Who answered each open question.
7. The review mode: fresh-context subagents, or not independent.
8. A link to the work item.

The PR is created with the code host CLI from `AGENTS.md`, and it follows the repo's PR template.
Before the PR opens, the skill updates the acceptance criteria in the work item.

### 6.7 `k-guardrails-check` (new, report only)

The skill checks a project and writes a report. It never changes the project. **[Svein]**
It has one reference file per area and starts one read-only subagent per area in parallel. **[call]**

Each area gets a rating: none, soft (instruction only), harness (hook or permission), or hard (CI or server).
Each area also answers: "Can the agent edit this control?"

Areas:

1. `AGENTS.md`: present, correct, has the work tracking section.
2. Harness hooks and permissions: deny `--no-verify`, `gh pr merge` and the same command on other hosts, force push, push to the default branch, and writes to guardrail files. Hooks block on timeout.
3. Git hooks: lint, tests, secret scan.
4. CI: required checks, the same checks as the local hooks, workflow files protected.
5. Tests: coverage gate, detection of deleted or skipped tests.
6. Protected paths and CODEOWNERS.
7. Dependencies and licences.
8. Secrets and identity: secret scanning, what the CLI tokens can do.
9. Untrusted input: work item text marked as data.
10. Upstream skills: pinned at the last known good versions.

Agent review does not count as a guardrail layer in the ratings, because reviewers read the same material as the author. **[call]**

Research on 2026-10-27 proposes more areas: control-plane integrity, agent run isolation and egress, tool and MCP allowlists, static strictness and anti-weakening, test strength, contract and data safety, supply chain provenance, provenance and audit, damage limits after merge, and the trust ladder.
The skill runs a core set by default and an extended set on request or by the project's stack and risk. **[call]**
The exact split between core and extended is left to the plan.

### 6.8 `k-report-finding`

When an agent finds a problem that is out of scope, a background subagent explores it, checks for duplicates, and files an issue or a board bug, as `AGENTS.md` says. **[Svein]**
Requirements: a cap per task, a secret scan and redaction before filing, no security findings in a public tracker, and a draft for the human when the tracker visibility is public or unknown. **[call]**

### 6.9 Model tiers

Skills name a tier, not a model: Read, Build, or Think. **[call]**
One file in the repo maps each tier to a model for each coding agent.
When a coding agent cannot choose a model for a subagent, the subagent uses the main model, and the skill says so once.

### 6.10 Harness snippets

The repo has hook and permission snippets for each coding agent. They cover the denies in section 6.7, area 2.
They are reference material. `guardrails-check` points to them. No skill installs them. **[Svein]**

## 7. Upstream versions and sync

### 7.1 Last known good

The repo keeps one file with the last known good version of each upstream: superpowers (commit and plugin version), mattpocock/skills (commit), and the `skills` CLI (version). **[Svein]**
Everyone installs these versions.
Each project commits its `skills-lock.json`.

### 7.2 Contract checks (cheap, weekly)

A scheduled CI job reads the upstream files at their latest commit and checks the points the workflow depends on: **[call]**

- Brainstorming has its approval gate and hands over to `writing-plans`.
- The spec path can be overridden, and the default path has not changed.
- The plan header has the `Spec:` line.
- `writing-plans` ends with the approval question and the execution choice.
- Subagent-driven development has the "Rulings" list and the final review.
- Subagent-driven development still ends with `finishing-a-development-branch`, and its menu still has the "push and create a PR" option.
- The skill names have not changed.
- `grilling` and `domain-modeling` exist, with the same names.

When a check fails, the job opens an issue. No install changes.

### 7.3 Evals (expensive, on each version bump)

Each team skill has a scripted scenario on a small fixture repo. **[call]**
The scenario runs headless in each coding agent: `claude -p`, `copilot -p`, `codex exec`, `opencode run`, and `pi -p`.
A version bump is a team PR that shows the upstream diff and the eval results. It merges only when the evals pass.

### 7.4 Switch to B

When a break cannot be fixed with team glue, the team copies superpowers into this repo at the last known good commit and ships a bundle. **[Svein]**
The contract checks and evals stay the same, so B changes the packaging, not the design.

## 8. Things to verify before or during the build

1. Spec review fits between `writing-plans` and the approval question through instructions in each coding agent. The same check applies to the `finishing-a-development-branch` menu answer.
2. Superpowers can be pinned to a version in Codex, OpenCode, Pi, Copilot CLI, and Hermes. Claude Code and VS Code Copilot support pinning. Some coding agents update plugins automatically.
3. Copilot cloud agent: subagent support and user-level skills.
4. VS Code Copilot: a `preToolUse` hook can block a terminal command.
5. Copilot CLI honours `disable-model-invocation`.
6. Skills can call other skills in Codex, OpenCode, Pi, and Hermes.
7. `npx skills` restore installs the same content (the lock file records a ref and a hash, not a commit).
8. The ASD-STE100 rule details, against the official Issue 9 text.
9. Pi: a team-approved subagent extension and how it selects a model.

## 9. Left to the builder

- The repo layout, the file formats, and the script language for the risk facts script and the contract checks.
- The fixture repo and the eval scenarios.
- The exact wording of the role files and skills, in ASD-STE100.
- The onboarding guide: install steps per coding agent, the trust step, and the pins.
