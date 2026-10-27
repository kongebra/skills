# Team agentic workflow skills - design

- **Date:** 2026-10-26
- **Revised:** 2026-10-27, after three rounds of adversarial review and a spike.
- **Status:** Approved by Svein on 2026-10-27.
- **Owner:** Svein Danielsen
- **Type:** Dated design archive.
  This document records why the repo exists and how the team builds it.
  The team does not maintain it as documentation.

Marks used in this document:

- **[Svein]** - Svein decided this.
- **[call]** - The author of this document decided this.
  Svein can override it.
- **[verify]** - A fact that the build must confirm before the design depends on it.

## 1. Intent

This repo holds a shared set of agent skills for a development team.
The skills standardise one way to move a work item from a board to a pull request (PR) with AI coding agents.
The team uses the repo across projects and across coding agents.
This is iteration 1.

The workflow combines four sources:

- Spec-driven development: a spec and a plan come before code.
- The Elephant-Goldfish Model (EGM): the agent that wrote a document does not review it.
  Reviewers start with a fresh context.
  They read only the document and the code.
- Matt Pocock's grilling and domain modeling: they provide a structured interview, a glossary, and ADRs.
- obra/superpowers: it provides brainstorming, plans, worktrees, subagent-driven development, and test-driven development.

### 1.1 End goal

The end goal is that no human reviews the code line by line. **[Svein]**
The team must earn this trust over time. **[Svein]**
The team must feel comfortable with it. **[Svein]**
At the start, humans review every PR. **[call]**

Risk decides how much review a change gets. **[Svein]**
Low-risk changes need little review.
High-risk changes need more reviewers and more tests.
High-risk changes also need a human review of the code.

### 1.2 Where the human works

1. The human (the "creator") gives a work item to the agent.
2. The creator and the agent grill and brainstorm.
   The result is a spec.
3. Fresh-context reviewers attack the spec.
   The creator then approves the reviewed spec (approval 1). **[Svein]**
4. The agent writes the plan.
   Fresh-context reviewers attack the plan.
   The creator then approves the reviewed plan (approval 2). **[Svein]**
   At approval 2, the creator also chooses in advance to keep the branch (section 5). **[call]**
   Approval 2 is the last human step before the PR. **[Svein]**
   Steps 1 to 4 run interactively, in the creator's session, with `k-work` as an in-session skill. **[Svein]**
5. After approval 2, the outside runner `k-run` drives every autonomous stage headless. **[Svein]**
   `k-run` enforces the checks between the stages (section 6.12). **[Svein]**
   The agent implements the work, reviews the code, and opens the PR without a human.
   After approval 2, the run stops only at a safety stop. **[call]**
   A safety stop is not an approval.
   Section 5.2 lists the safety stops.
6. The creator reads the PR and merges it. **[Svein]**

Each approval comes after an adversarial review. **[Svein]**
The creator therefore approves each document only after fresh-context reviewers attacked it. **[Svein]**
Section 5.5 describes what happens to a finding that is still open at the round cap.

### 1.3 Future models

Models from Anthropic, OpenAI, and other vendors improve fast. **[Svein]**
The workflow must stay useful when models get better. **[Svein]**
The workflow must not limit better models. **[Svein]**
Therefore the skills state goals, gates, and evidence. **[call]**
They do not prescribe each step. **[call]**
Limits such as round caps and reviewer counts are configuration. **[call]**
They are not fixed rules. **[call]**

## 2. Goals, non-goals, anti-goals

### Goals

- The team has one standard workflow, from work item to PR.
- The workflow works in Claude Code, GitHub Copilot, Codex, OpenCode, and Pi. **[Svein]**
  The team rarely uses Hermes. **[Svein]**
- Each PR contains evidence.
  A non-technical reader can trust this evidence.
- The team keeps the updates of the upstream skills.
  The team knows when an update breaks the workflow.
- The repo stays small.
  It holds only what the upstream skills do not provide.

### Iteration 1 scope

Iteration 1 contains every skill and the runner script that the workflow needs from intake to PR. **[Svein]**
All team skills and the runner script use the prefix `k-`. **[Svein]**
The prefix is temporary. **[Svein]**
It can change later. **[Svein]**

| Component | Purpose |
|---|---|
| `k-work` | Entry skill. It runs the stages up to approval 2 in the creator's session and resumes from the ledger. |
| `k-run` | Script, not a skill. Outside runner. Drives the autonomous stages headless after approval 2 and enforces the checks between stages. |
| `k-intake` | Reads the work item, runs the preflight, and creates the worktree, the ledger, and the provisional risk level. |
| `k-spec-review` | Attacks the spec before approval 1 and the plan before approval 2, in a fresh context. |
| `k-code-review` | Reviews what superpowers does not cover. |
| `k-pr` | Pushes the branch and creates the PR with the risk facts, the evidence, and the decisions. |
| `k-report-finding` | Files out-of-scope findings in the background. |
| `k-guardrails-check` | Checks a project and reports its guardrails. |

The repo is public on GitHub as `kongebra/skills`. **[Svein]**

The release bar is: **[call]**

- Automated evals must pass on Claude Code and on Copilot CLI.
- VS Code Copilot has a manual smoke test checklist for each release.
  It has no automated eval.
- Codex, OpenCode, and Pi have best-effort support.
  This means the evals run, but a failure does not block a release.
- No eval writes to a live board or a live code host (section 7.3).
- The first pair is Azure DevOps Boards as the board and GitHub as the code host.
  Other boards and code hosts use the facts in `AGENTS.md`.
  They are unverified until a project uses them.

### Non-goals (iteration 1)

- The workflow does not include automatic merge.
- The repo has no skill that configures guardrails in a project. **[Svein]**
  The repo only checks and reports. **[Svein]**
- The repo has no loop that processes PR review comments in iteration 1. **[call: iteration 2]**
  This loop later replaces the personal `review-burndown` skill. **[call: iteration 2]**
- `k-review-principles` is not in iteration 1. **[call: iteration 2]**
  It collects past review feedback.
  The feedback includes PR comments (also Copilot reviews) and corrections in agent session transcripts.
  It condenses the feedback into principles.
  It also finds principles that nobody has written down.
  `k-code-review` reads the result.
  Iteration 1 already records guardrail proposals (section 6.5).
  These proposals later feed this skill.
- This repo does not provide a sandbox or dev container base image for agents. **[Svein]**
  The image work belongs in a separate repo with its own owner.
  `k-guardrails-check` only reports whether a project uses one. **[Svein]**

### Anti-goals

The workflow fails when one of these conditions is true, even if it works technically:

- The PR summary hides a risky change.
- Review loops never end, or they cost more than the change is worth.
- The workflow adds so many steps that the team skips it for small changes.
- An upstream update silently changes behaviour for some teammates and not for others.
- Text from a work item makes the agent do something that the creator did not request.

## 3. Constraints

### 3.1 Upstream skills

- The team uses obra/superpowers without change. **[Svein]**
  The team does not edit it. **[Svein]**
- From mattpocock/skills, the team uses only `grilling`, `grill-with-docs`, and `domain-modeling`. **[Svein]**
  The team does not use his tickets, `to-spec`, or his GitHub-issue workflow. **[Svein]**
  `grill-with-docs` has `disable-model-invocation: true`.
  Only a human can start it.
  The workflow therefore calls `grilling` and `domain-modeling` directly. **[call]**
- The team does not install the EGM plugin. **[Svein]**
  The repo uses only ideas from EGM. **[Svein]**
  EGM is Apache-2.0.
  If any role file reuses EGM text, the repo must include attribution. **[call]**

### 3.2 Specs, plans, and the durable record

- Specs and plans are working documents for agents.
  The project does not commit them to git. **[Svein]**
  They are gitignored. **[Svein]**
- The durable record has three parts: **[call]**
  - The work item holds the acceptance criteria and the answers to open questions.
    The agent updates the work item before it opens the PR.
  - The PR holds the summary, the evidence, and the decisions.
  - The repo holds ADRs and `GLOSSARY.md`.
    `domain-modeling` writes them.
- Put design documents about this repo in `docs/design/`. **[Svein]**
  Date each document. **[Svein]**

### 3.3 Writing standard

All text that the workflow writes follows ASD-STE100 (Simplified Technical English). **[Svein]**
This includes specs, reviews, code comments, and PR text. **[Svein]**
The rule applies to written artifacts: the spec, the plan, review reports, code comments, work item updates, and the PR. **[call]**
It does not apply to the live conversation with the creator.

The team cannot change the upstream skills.
The rule therefore reaches them through an instruction in the project's `AGENTS.md` and through every team brief. **[call]**
`k-work` and `k-run` also pass the rule into the prompt of every upstream stage. **[call]**
The rule then does not depend on the coding agent loading `AGENTS.md`. **[call]**

ASD owns the copyright of the ASD-STE100 dictionary. **[call]**
The repo states the writing rules. **[call]**
The repo does not copy the dictionary. **[call]**

An STE finding never blocks a review loop and never starts a new round. **[call]**

### 3.4 Boards and code hosts

- Work items come from boards such as Azure DevOps Boards and Jira. **[Svein]**
  Most work items are not a developer's own idea. **[Svein]**
- Teams host code on GitHub, Azure DevOps Repos, GitLab, or Forgejo. **[Svein]**
- Each board and code host has a CLI or an API. **[Svein]**
  The skills use the CLI. **[Svein]**

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

- Every team skill reads `AGENTS.md` by its path. **[call]**
  It does not depend on the coding agent to load it. **[call]**
  It passes the facts that the subagent needs into each subagent brief. **[call]**
- A fresh-context review never runs in the same context as the author. **[call]**
  If a coding agent cannot start a subagent, the skill stops and tells the creator. **[call]**
  The creator can override this and continue. **[call]**
  Then the review is "not independent". **[call]**
  The risk level becomes high. **[call]**
  A human reviews the code. **[call]**
  The PR shows the review mode. **[call]**
- A Claude Code hook can block the command when the hook times out. **[call]**
  This needs `onFailure: "block"`, from v2.1.295 or later. **[call]**
  A Copilot CLI hook always lets the command run when the hook times out. **[call]**
  No setting changes this. **[call]**
  The Claude Code snippets in this repo configure the hooks to block. **[call]**
  The Copilot CLI snippets keep the hooks fast, to reduce the risk. **[call]**
  CI is the backstop. **[call]**

### 3.6 Where the skills live

The project repo controls the version of every skill that the workflow uses. **[Svein]**
This gives version control: every person on the project gets the same skills, and each change is a reviewed PR.

- superpowers runs as a plugin, as its authors intend. **[Svein]**
  The project settings enable the plugin and pin its version, where the coding agent supports this.
  The plugin keeps its session-start hook, which a skills-only install does not include.
  The team installs the plugin from the superpowers marketplace, not from the official Anthropic marketplace, because the official marketplace updates plugins automatically by default.
- In the repo, as committed files: `grilling`, `grill-with-docs`, and `domain-modeling` from mattpocock/skills, all `k-` skills, and the domain-specific skills of the project. **[Svein]**
- In the repo: `skills-lock.json`, the plugin settings, the `AGENTS.md` work tracking section, and the guardrails that the project adopts.
- At user level: only personal skills and personal instructions.
- Never in the repo: specs, plans, the ledger, local settings files, credentials, and session logs.

Each team and each repo can pin its own versions.
The skills repo publishes the last known good versions (section 7.1).
A version bump is a PR in each project repo.

A copy at user level can override the repo copy.
In Claude Code, a personal skill overrides a project skill with the same name (Claude Code docs, skills page).
Therefore nobody keeps a copy of a team workflow skill at user level. **[call]**

`k-work` runs a preflight check before it starts. **[Svein]**
It stops with a clear message when one of these checks fails:

- superpowers is present, and its version is a last known good version (section 7.1).
  A newer version can change the seams in section 5.7, so presence alone is not enough.
- `grilling`, `grill-with-docs`, and `domain-modeling` are present.
- No user-level skill has the same name as a skill in the repo.

`k-guardrails-check` reports the same items. **[call]**

## 4. Approaches

The team considered three ways to build the repo.

**A. A thin team layer over the upstream skills.**
The team chose this approach. **[Svein]**
The repo holds only the team skills, the role files, the templates, the harness snippets, and a list of tested upstream versions.
Each project repo pins superpowers as a plugin in its settings, and commits the other skills as files (section 3.6). **[Svein]**
The team installs them with `npx skills add <source>#<sha>`, for example `mattpocock/skills#<sha> -s grilling -s domain-modeling`.
The `<sha>` is the fixed commit, as a 40-character SHA.
The command works from GitHub, Azure DevOps, and GitLab.
Tradeoffs: The workflow depends on how superpowers passes control between skills.
The team inserts the spec review through instructions.
The team has not yet tested this on each coding agent.
The creator approves twice.
Approval 1 is for the reviewed spec.
Approval 2 is for the reviewed plan.

**B. One bundle with copies of all skills.**
The repo copies superpowers, Matt's three skills, and the team skills at fixed commits.
A sync script delivers upstream changes as PRs.
Gains: B needs one install.
B gives exact versions.
B lets the team patch the superpowers handoffs.
Tradeoffs: B changes superpowers.
The sync needs much effort, because superpowers went from v6.3 to v7.0.1 in about 10 weeks.
The copies become different from upstream over time.
B is the fallback when A breaks and changes in team files cannot fix the break (section 7.4). **[Svein]**

**C. A complete rewrite.**
The team rejected this approach.
The team would lose upstream improvements.
The team would maintain everything alone.

## 5. The workflow

```text
work item
  k-work runs these stages interactively, in the creator's session:
  -> k-intake             (team)        worktree, provisional risk level, ledger
  -> grilling             (Matt)        with domain-modeling
  -> brainstorming        (superpowers) spec (design doc), builder check
  -> k-spec-review        (team)        attack the spec, fix, cap
  -> creator approves the reviewed spec (approval 1)                    [human]
  -> writing-plans        (superpowers) plan, final risk level
  -> k-spec-review        (team)        attack the plan, fix, cap
  -> creator approves the reviewed plan (approval 2)                    [human]
       the creator also gives the integration choice "keep the branch"
  k-run (outside runner) drives these stages headless and enforces the checks between them:
  -> subagent-driven-development + test-driven-development (superpowers)
  -> finishing-a-development-branch (superpowers)  keep the branch
  -> k-code-review        (team)        what superpowers does not cover
  -> k-pr                 (team)        push, create the PR, evidence, risk facts, decisions
  -> creator reads and merges                                            [human]
```

The entry skill `k-work` runs the stages up to approval 2 in order and resumes from the ledger. **[call]**
After approval 2, `k-run` drives the stages (section 6.12). **[Svein]**
Each stage skill also works alone. **[call]**

`k-work` and `k-run` handle three superpowers handoffs.
Section 5.7 states the rule for each seam.

- After `brainstorming` writes the spec, `k-work` runs `k-spec-review` on the spec. **[call]**
  This follows the brainstorming rule that the creator approves the document only after the checks are back.
  The creator then approves the reviewed spec (approval 1). **[Svein]**
  The seam rule is S1 in section 5.7.
- After `writing-plans` saves the plan, `k-work` runs `k-spec-review` on the plan, with the spec as context.
  This run comes before the plan approval question. **[call]**
  The creator then approves the reviewed plan (approval 2). **[Svein]**
  `k-work` gives the execution method in advance.
  The method is subagent-driven. **[call]**
  The team workflow does not use the "Native" method (`executing-plans`), because this method has no review per task.
  The workflow allows it only through the override in section 3.5, with the same consequences.
  The seam rule is S2 in section 5.7.
- `subagent-driven-development` ends when it calls `finishing-a-development-branch`.
  This skill shows a menu.
  After approval 2, no human acts until the PR. **[Svein: no human after approval]**
  `k-run` therefore answers the menu with the creator's choice to keep the branch. **[call: how]**
  This answer is the creator's own choice from approval 2, given early.
  This respects the upstream rule that the integration decision is the creator's.
  The seam rule is S4 in section 5.7.
  `k-code-review` then runs. **[call: how]**
  `k-pr` then pushes the branch and creates the PR with its own body. **[call: how]**

`brainstorming` also runs its builder check.
The builder check is a fresh subagent with `builder-check-prompt.md`.
It runs as upstream defines it. **[call]**
Brainstorming skips its builder check for a small change.
At high risk, the Naive reader and Readiness roles still run. **[call]**
They attack, and the builder check only asks questions.

At each approval, `k-work` shows the creator these items: **[call]**

- The reviewed document.
- Each blocking finding that is still open because a review reached its round cap.
  The creator decides each finding: fix it now, or accept it as a recorded decision.
- At approval 2, the diff of the spec against the baseline copy from approval 1 (section 5.4).
- At approval 2, the verification commands as a separate list.
  A command runs unattended only when it also appears in `AGENTS.md`, the CI config, or the project's package scripts.
  Any other command needs an explicit OK from the creator.
- At approval 2, the update that the agent will write to the acceptance criteria in the work item.
- At approval 2, the integration choice "keep the branch".

The ledger records the creator's decisions.

These handoffs use instructions.
They get a contract check (section 7.2) and an eval (section 7.3).

### 5.0 Fast path for trivial changes

Intake proposes "trivial" for a change such as a typo, a docs fix, or a one-line fix with an existing test. **[call]**
The creator confirms it. **[call]**
A trivial change skips brainstorming, the plan, and the spec review.
It still runs `test-driven-development`, `k-code-review`, and `k-pr`.
Grilling runs only when the work item has open questions.

The PR shows that the change used the fast path.
The fast path writes a minimal ledger entry.
The entry has the acceptance criteria with IDs, the verification command, and the named tests.
`red-check` runs as normal (section 6.5).
The creator gives the integration choice "keep the branch" when the creator confirms the fast path. **[call]**

When the diff touches a protected path, the change leaves the fast path.
`k-code-review` runs at the new level.
The PR says so.

### 5.1 One interview

Grilling and domain modeling lead the interview. **[call]**
They take the work item as input. **[call]**
Brainstorming then starts with this material.
It follows its "they have already said what they want" path.
This path has a short echo, the approaches, and the design doc.
The creator does not answer the same questions twice.

### 5.2 Questions the creator cannot answer

The creator is often not the author of the work item. **[Svein]**
The agent marks each question as "the creator can answer" or "the work item author must answer". **[call]**
The agent posts each question of the second type as a comment on the work item.
Then it pauses.
It does not guess.
The ledger records the state "waiting for answer", with the questions and where the agent posted them.
The creator resumes by running `k-work` again.
`k-work` then checks the work item for answers.
After approval 2, no human acts in the normal flow.
The run stops only in these cases, which are safety stops: **[Svein]**

- Tests fail in finishing.
- A question appears that only a human can answer.
- A guardrail blocks an action.
- The approved spec or plan changes (section 5.4).
  The creator re-approves the change, which records a new hash, or rejects the change.
- The subagent budget of the build stage is used up (section 5.7).
  The creator raises the budget in the ledger, or stops the run.
- The run detects an early push before `k-pr` (section 5.7).
  On resume, `k-run` compares the remote ref with the SHA that `k-pr` recorded.
  A push by `k-pr` itself is not early.

After a failed test, a human-only question, or a guardrail block, the creator resolves the cause and resumes.
`k-run` then re-runs the stage from its start.

At a safety stop, the run records the state and the cause in the ledger.
Then the run waits for the creator to resume.
Before approval 2, the creator resumes with `k-work`. **[call]**
After approval 2, the creator resumes with `k-run`. **[call]**
A safety stop is not an approval.
The PR shows who answered each question.

### 5.3 Risk levels

Intake sets a provisional risk level from the work item. **[call]**
The level uses the type of work and any protected path or area that the work item names. **[call]**
The final level comes after the plan exists. **[call]**
It uses the files that the plan says it will change (section 5.6), checked against the protected paths. **[call]**
The `k-spec-review` run on the plan uses the final level.
The risk level never goes down. **[call]**
Each step uses the highest level found so far, and the ledger records it.
The plan review can raise the level.
Then the spec roles that the new level adds also run on the spec, before approval 2.
`k-pr` checks the level again against the real diff and raises it when necessary. **[call]**

| Level | Typical change | Spec review | Human code review (start) |
|---|---|---|---|
| Low | Docs, small local change with tests | The roles in section 6.4. A trivial change skips it. | Yes, until the team loosens it |
| Medium | Normal feature or fix | The roles in section 6.4 | Yes, until the team loosens it |
| High | Protected paths: login, auth, migrations, infrastructure, CI, guardrail files, dependencies | The roles in section 6.4, and more rounds | Yes, always in iteration 1 |

The role lists in section 6.4 are defaults. **[call]**
`AGENTS.md` can change them. **[call]**

When `k-pr` finds a higher level than the level that the reviews used, `k-code-review` runs again. **[call]**
It uses the roles for the new level.
The PR states "risk raised late" and gives the reason. **[call]**
The spec review does not repeat after the build, because a human reviews all code in iteration 1. **[call]**

The project's `AGENTS.md` lists the protected paths and each loosening that the team agreed. **[call]**
This follows the blast-radius rule. **[Svein]**
The rule says to judge shared code on a critical path by what fails when it fails. **[Svein]**
Do not judge it by how often it failed. **[Svein]**

`k-pr` also raises the level from numbers in the diff. **[call]**
The numbers are the lines changed, the files touched, the number of CODEOWNERS teams touched, and the ratio of test lines to production lines. **[call]**
The thresholds are in `AGENTS.md`. **[call]**
Intake, the risk script, and `k-pr` read `AGENTS.md` and CODEOWNERS from the base ref, not from the worktree. **[call]**
A diff that changes `AGENTS.md`, CODEOWNERS, CI files, hook config, or agent settings sets the level to high. **[call]**
The source is the ReviewDebt talk (eBay, AI Engineer 2026).
The talk scores PRs with deterministic checks and no model.

These rules apply when the team loosens human code review: **[call]**

- The team loosens one level at a time.
  The team records the decision and its date in `AGENTS.md`.
- Time alone is never enough.
  A level loosens only after both of these conditions are true:
  - A recorded run of agent PRs has no reverts, no hotfixes, and no blocking problem that only a human found.
  - There is a maintainability signal, such as churn in recently changed files.
- After loosening, humans still review a random share of PRs at that level in full.
- Any incident makes the level one step stricter.

The team records this counterweight on purpose.
Models are trained to make tests pass, and that training does not penalise bad design.
Agent reviewers raise the minimum quality, but they do not replace human judgement of design (Dex Horthy, "Why Software Factories Fail", 2026).
The design answers this in two ways:

- It moves design decisions earlier (section 5.6).
- It requires humans to review the code until the evidence shows that this is not necessary.

### 5.4 State and resume

Intake creates the worktree first. **[call]**
The agent then creates the spec, the plan, and all team files inside the worktree. **[call]**
`using-git-worktrees` detects an existing worktree and does not create a second one.

Superpowers keeps its default paths (`docs/superpowers/specs/`, `docs/superpowers/plans/`). **[call]**
Superpowers also uses `.superpowers/`. **[call]**
The project gitignores `docs/superpowers/`, `.agent-work/`, and `.superpowers/`. **[call]**
Team files are in `.agent-work/<work-item-id>/`. **[call]**
`k-intake` checks the ignore rules (section 6.2).
`k-pr` fails when the diff contains files under these paths (section 6.6).

The ledger (`ledger.md`) records the stage, the round, open findings, the work item ID, the branch, and the risk level.
Every team skill reads the ledger when it starts.
The ledger also records: **[call]**

- The creator's decisions and the options that the creator rejected.
  The PR can then show them.
- A structured handoff note after each stage.
  It states what is done, what is left, the commands that ran with their exit codes, and the problems found.
- The hash of the approved spec at approval 1.
- The baseline: at approval 1, `k-work` stores a copy of the approved spec in `.agent-work/<id>/`.
- The hashes of the approved spec and the approved plan at approval 2.
  The plan hash ignores the checkbox state, because some executors may tick checkboxes.
- The rulings.
  `k-run` captures the "Rulings I made" list from the final message of the build stage.
  It compares the count of rulings, not the exact text.
  A mismatch becomes a decision in the PR (section 5.7, S3).
- The subagent use of each review loop and of the build stage.
  The ledger can also record the token use as a number.

When the spec changes before approval 2, the attackers review the changed parts before approval 2. **[Svein]**
Approval 2 shows the diff against the baseline. **[Svein]**
Approval 2 then records new hashes for both the spec and the plan.
A change to the spec or the plan after approval 2 is a safety stop (section 5.2). **[call]**
The agent can write the ledger, so the hashes catch accidents and not attacks.

When a stage resumes, it starts a fresh session. **[call]**
It loads only the ledger and the artifacts. **[call]**
It does not load the old conversation. **[call]**

A worktree does not isolate databases, caches, or shared services. **[call]**
Two agents on the same machine can still interfere with each other in these resources. **[call]**
This is a known limit. **[call]**

### 5.5 Review loops

Both review skills use adversarial review. **[Svein]**
The pattern comes from an Anthropic engineering lead (podcast, 2026-10-20) and from Jesse Vincent's post on adversarial review (2026-05-01).

One round has three steps: **[call]**

1. **Attackers.**
   Several fresh-context subagents each try to prove that the work is wrong.
   They do not confirm it.
   Each finding must be concrete and checkable.
   It names a line, a section, or a test.
   It says what fails.
2. **Judge.**
   One more fresh-context subagent reads all findings.
   It merges duplicates.
   It rejects findings that are not valid or not actionable.
   It marks each remaining finding as blocking or not blocking.
   The judge removes the author's bias from the filtering step.
3. **Author.**
   The author agent handles the findings that the judge kept.
   It can still reject a finding.
   It then writes the reason.
   The next round receives the rejected findings and their reasons.

Stop rule: The loop stops when the judge keeps no blocking findings. **[call]**
When the attackers find only problems that the judge rejects as not actionable, this indicates that the work is good.
The round cap is a safeguard.
The defaults are 3 rounds for each run of spec review and 2 rounds for code review.
The 2 code review rounds come after the superpowers final review.
`AGENTS.md` can change the defaults.
Rounds after the first attack only the changed parts and the findings that the author rejected. **[call]**

At the cap of a spec review, the open blocking findings go to the creator at the next approval.
The creator decides each finding: fix it now, or accept it as a recorded decision. **[call]**
At the cap of a code review, the skill adds the open findings to the PR as decisions.

Each team review loop has a subagent budget. **[call]**
The default is at least `rounds x (attackers + 1)`. **[call]**
`AGENTS.md` holds the default, and the ledger records the use. **[call]**
When a loop goes above its budget, the loop stops as at the round cap. **[call]**
The workflow has no token budget.
The ledger can record token use as a number, without enforcement. **[call]**
The build stage follows section 5.7, S5.

Models: Finding flaws is easier than creating the work, so attackers run on the Build tier. **[call]**
The judge runs on the Think tier. **[call]**
A per-project switch in `AGENTS.md` controls the cross-vendor attacker. **[call]**
The default is off, because this attacker sends project material to another vendor. **[call]**
When the switch is on, one attacker uses a model from another vendor. **[call]**
This needs a coding agent that can choose a model for a subagent.
The model tier file (section 6.9) lists this for each coding agent. **[call]**

### 5.6 What the spec and the plan must contain

`k-work` passes these requirements to `brainstorming` and `writing-plans` as instructions. **[call]**
The contract checks (section 7.2) and the evals (section 7.3) cover them.

- **Current state.**
  The spec describes how the affected part of the system works today.
  The reality check role tests the spec's claims against this description.
- **Program design.**
  The spec lists the types, the signatures, and the call paths that the change adds or changes.
  The plan lists the files that it will change.
  Reviewers then check the diff against decisions that the team already made.
  They do not need to judge the design later, when the code exists.
- **One alternative.**
  The spec describes at least one other approach and checks it against the vendor docs.
  It also explains why the team did not choose that approach.
  The wording of the work item must not decide the design alone.
- **Acceptance criteria with IDs.**
  Each criterion has an ID, for example `AC-1` or `AC-2`.
  Each criterion maps to at least one task in the plan.
  Each test that proves a criterion has the ID in its name or description.
- **Named tests per task.**
  Each task lists the tests that must pass before the task is done.
- **Verification commands.**
  The spec lists the exact commands that prove the work.
  Approval 2 shows them as a separate list (section 5).
- **In scope and out of scope.**
  The spec states what is in scope and what is out of scope.
  `k-report-finding` uses the out-of-scope items as input.

### 5.7 Upstream seam contract

A seam is a point where a runner hands control to an upstream skill.
The runner is `k-work` before approval 2 and `k-run` after approval 2.
This section states each seam rule once.
Other sections refer to it. **[call]**
The spike ran on 2026-10-27, headless, on a throwaway fixture repo.
It used Claude Code 2.1.311 and Copilot CLI 1.0.95.
Each verdict is one sample (n=1).

| Seam | What the runner controls | What it cannot control | Spike result | Fail-closed action |
|---|---|---|---|---|
| S1 brainstorming hand-over | The instruction to stop after the spec and its builder check, before approval and before `writing-plans`. The prompt names the spec path and says "do not commit it". | The final message. It still has the spec path and a "calls I made" list. It can have a question. | Partly holds in both coding agents. The stop works. The hand-over text stays. | `k-work` (in session, before approval 2) gates on artifacts, not on the message. The spec file exists at the named path. `git ls-files` shows that the spec is not committed. No code changed. The stop marker is in the last result only. If the spec is committed, `k-work` stops before review 1. |
| S2 writing-plans | The execution method in the prompt. The stop before plan approval. | - | Holds in both. | `k-work` (in session, before approval 2) gates on the plan file and the stop marker. |
| S3 subagent-driven development rulings | The capture of the final message of the build stage. Upstream says the "Rulings I made" list in this message is exhaustive. | Deletion of the workspace at the end. The wording of each ruling. | The spike tested copy-at-end only. It did not test append-when-made. Copy-at-end holds in Claude Code, but one run paraphrased the text. It partly holds in Copilot CLI: the order was right, but the agent skipped the upstream whole-branch review by its own ruling. | `k-run` (outside, after approval 2) captures the final message. The "Rulings I made" list is the source of truth. The check compares the count of rulings, not the exact text. A mismatch becomes a decision in the PR, not a safety stop. A skipped upstream review is also a decision in the PR. |
| S4 finishing menu | The creator's advance choice "keep", phrased as "invoke finishing-a-development-branch, then select the keep option". | Menu text and numbering. | Holds in both, with a normal branch and with detached HEAD, when finishing runs alone. | `k-run` (outside, after approval 2) phrases it as "invoke, then select keep". An instruction with only the outcome made the agent skip finishing. Match the keep option by intent, never by text or number. If no keep option exists, `k-run` stops. Never select an option that merges or pushes. `k-intake` creates a named branch. |
| S5 budgets | The count of subagent runs, from the events of the coding agent. | Token totals. They are mostly cache reads and are not reliable. | Counting is possible in both. | Budgets count subagent runs only, for each team review loop (section 5.5). In the build stage, `k-run` (outside, after approval 2) records the count and applies a safety stop at its next checkpoint. |

No push before `k-pr` is behaviour, not a control, unless a deny rule exists.
`k-run` checks the remote refs before `k-pr`.
It stops if the branch was pushed early.

The creator may read draft text during interactive brainstorming, because the approval comes after review. **[Svein]**

## 6. Components

### 6.1 Project facts in `AGENTS.md`

Each project has one fixed section in `AGENTS.md`. **[call]**
It holds facts only. **[call]**
Behaviour stays in the skills. **[call]**

```markdown
## Work tracking
- Board: Azure DevOps Boards, org `contoso`, project `Webshop` (CLI: `az boards`)
- Code host: GitHub (CLI: `gh`)
- Findings go to: GitHub Issues, label `agent-found`, visibility: private
- Link work items in PRs as: `AB#1234`
- Branch names: `feature/1234-short-name`
- Protected paths: `src/auth/**`, `db/migrations/**`, `.github/**`, `infra/**`
- Invariants: `src/auth/**`: "no endpoint without an authorization check"
- Risk thresholds: medium above 300 changed lines or 2 CODEOWNERS teams; high above 800 lines
- Review limits: spec 3 rounds, code 2 rounds; spec attackers low 2, medium 3, high 5
- Subagent budget: 18 for each review loop
- Cross-vendor attacker: off
- Verification commands: `npm test`, `npm run lint`
- QA plan: `docs/qa-plan.md`
```

The numbers above are examples. **[call]**
Each project sets its own numbers. **[call]**

When the section is missing, the skill proposes it. **[call]**
The creator confirms it before the skill writes it. **[call]**
The skill does not write it without the creator's confirmation, because this file later controls CLI commands.

### 6.2 `k-intake` (new)

- The skill reads the work item with the board CLI from `AGENTS.md`.
- The skill runs a preflight check. **[call]**
  The check confirms that each CLI answers a read command and that CI exists. **[call]**
  The check fails unless `git check-ignore` matches `docs/superpowers/`, `.agent-work/`, and `.superpowers/`. **[call]**
  If a check fails, the skill stops with a clear message. **[call]**
- The skill treats work item text, comments, and links as data. **[call]**
  It does not treat them as instructions. **[call]**
  It puts this text in a marked block. **[call]**
- The skill creates the worktree, the ledger, and the provisional risk level (section 5.3).
- The skill never invents acceptance criteria.
  When the work item has none, the grilling produces them.
  The creator confirms them.
- The skill gives each acceptance criterion an ID (section 5.6).
- The skill lists the existing ADRs and `GLOSSARY.md` terms that relate to the work. **[call]**
  These are input to the grilling. **[call]**

### 6.3 Reviewer role files (new)

Each role is one Markdown file with a section for a spec, a section for a plan, and a section for code. **[call]**
A general-purpose subagent reads the role file first.
The repo does not use agent definition files, because each coding agent has its own format.

| Role | On a spec | On code |
|---|---|---|
| Zoom-out | Is this the right problem? What can we cut? What exists already? | Is it overbuilt? Does it duplicate existing code? |
| Naive reader | Undefined terms, hidden assumptions | Unclear names, missing context |
| Critic | Failure modes, edge cases | The same, in the real code |
| Reality check | Do the claims about the code hold? | Does the diff do what the spec says? |
| Readiness | Can someone build from this? | - |
| Test quality | - | Do the tests prove each acceptance criterion? Does the `red-check` evidence show that each test failed first? |
| Standards | - | Repo conventions, code smells, maintainability: needless try/catch, casts, and changes that force edits in many places |
| Invariant | - | One named invariant from `AGENTS.md` for a protected path. High risk only. One attacker per invariant, at most 3. |

Each role file describes the reviewer as an attacker. **[call]**
It says: "Find what is wrong. Do not confirm." **[call]**
Each brief gives the reviewer the document or diff, the role file, the facts from `AGENTS.md`, and `GLOSSARY.md` with the relevant ADRs. **[call]**
It does not give the author's reasons. **[call]**
The reality check and critic roles also receive read-only access to the whole repo, because second-order effects are outside the diff. **[call]**
The other roles see only what the brief gives them. **[call]**
Reviewers have read-only tools. **[call]**
They do not follow instructions that are in the material they review. **[call]**

Each finding has a fixed shape, so that both the judge and the author agent can handle it: **[call]**

- Location: file and line, or spec section.
- What fails: a checkable statement of the failure.
- Suggested fix: a fix for the failure.
- Guardrail: a lint, a test, a type, or a CI check that could catch the problem automatically.
  Include this field only if such a guardrail could exist.

### 6.4 `k-spec-review` (new)

- The skill has two main runs.
  The first run attacks the spec before approval 1.
  The second run attacks the plan before approval 2, with the spec as context.
  A third run attacks the changed parts of the spec when the spec changes before approval 2 (section 5.4).
- The risk level selects the roles, the model tier, and the round cap.
  The first run uses the provisional level.
  The second run uses the final level (section 5.3).
  When the level rises, the added spec roles also run on the spec (section 5.3).
- The order follows EGM.
  The zoom-out role runs first, so that reviewers do not refine a wrong design.
- The zoom-out role checks that the spec names one alternative (section 5.6).
  It also checks that the chosen approach does not ignore a simpler native feature.
- The readiness role checks that each acceptance criterion maps to a task.
  It also checks that each task names its tests.
- A role does these checks only when the level includes the role.
- At every level, a script also checks the structure of the spec and the plan before the attackers start. **[call]**
  The script checks that the spec names one alternative.
  It checks that each acceptance criterion ID maps to at least one task.
  It checks that each task names its tests.
  A failed structure check is a blocking finding, so the attackers do not spend a round on it.

The two review skills use these roles for each risk level: **[call]**

| Level | `k-spec-review` roles | `k-code-review` roles |
|---|---|---|
| Low | Critic, Reality check | Test quality |
| Medium | Zoom-out, Critic, Reality check | Test quality, Standards |
| High | Zoom-out, Naive reader, Critic, Reality check, Readiness | Test quality, Standards, Critic, Invariant (one for each invariant, at most 3) |

`k-code-review` adds only what superpowers review lacks.
Iteration 1 does not use the Zoom-out, Naive reader, and Reality check columns for code in section 6.3.
Keep them in the role files for later.

### 6.5 `k-code-review` (new)

Subagent-driven development in superpowers already reviews each task and the whole branch.
The team skill covers only what that review does not cover: test quality, proof that the tests failed first, project standards, and protected paths. **[call]**
Proof that a test failed first is a fact, not a claim. **[call]**
Superpowers commits tests and code together, and git hooks run the tests.
The team therefore does not require separate commits for tests and code.
The proof is recorded at the moment it happens, not rebuilt later. **[call]**
Spec review round 2 showed that a rebuild from the merge base fails for new code, because the code under test does not exist there.

Two scripts make the proof: **[call]**

- `red-record` runs at the red step of `test-driven-development`.
  The implementer runs it instead of the plain test command.
  It runs the named test, and it writes the output, the exit code, and a hash of the test file to `.agent-work/<id>/evidence/`.
- `red-check` runs in `k-code-review`, before the test quality reviewer starts.
  It reads the evidence files and the final branch.

The pass condition of `red-check`: **[call]**

- Each named test for each acceptance criterion has a red record.
- The red record shows a failure in that named test.
- A syntax error or a failure in another test does not count.
  A missing symbol counts only when the symbol is the feature that the test names.
- The hash of the test file in the red record matches the final test file, or the diff between them changes only setup code.
  A changed assertion needs a new red record.
- After each fix round, `red-check` runs again.

The test quality reviewer stays read-only.
It reads the evidence file.
It never checks out commits.
It treats a claim without evidence as not done.

Rules for the proof: **[call]**

- Medium and high risk: a missing or failed red record is a blocking finding.
- Low risk: a missing or failed red record becomes a decision in the PR.
- Exempt: docs, config without behaviour, and refactors that existing tests already cover.
  For a refactor, the proof is that the same tests pass before and after.
- The PR records the command and its output, so a squash merge does not remove the evidence.

Findings become guardrails: **[call]**
When a finding names a guardrail that could catch the problem automatically, `k-code-review` records it in the ledger as a guardrail proposal.
The PR lists the proposals.
A human decides whether to build them.
The workflow improves over time when repeated review comments become deterministic checks (Lopopolo, Jain, and Zakariasson, AI Engineer 2026).

### 6.6 `k-pr` (new)

The PR contains these items, in this order: **[call]**

1. A non-technical summary in ASD-STE100.
2. The risk level.
3. **Risk facts.**
   A script makes them from the diff, and the skill pastes them without change.
   The model cannot edit this block.
   The script reads `AGENTS.md` and CODEOWNERS from the base ref (section 5.3).
   The skill pastes the block with a hash of its content.
   The block lists:
   - changed protected paths
   - new or changed dependencies and lock files
   - migrations
   - CI and infrastructure changes
   - deleted or skipped tests
   - test counts before and after
   - lines changed
   - files touched
   - CODEOWNERS teams touched
   - the ratio of test lines to production lines
   - the people who last changed the touched paths, as suggested human reviewers
4. The acceptance criteria as a checklist, with their IDs.
   Each item has its evidence, which is a test name or a command.
   This block is the stable record of what the creator approved, because the spec itself is gitignored.
5. A table of the checks that ran.
   The checks are hooks, CI jobs, and review roles.
   The table also lists the rules that each check used.
6. Decisions.
   This item has two groups:
   - The creator's decisions and rejected options from the ledger.
   - Decisions that the agent made without asking.
     These are the brainstorming "calls I made" list and the rulings in the ledger.
     They also include the findings that the creator or the loop left open at a cap.
7. Who answered each open question.
8. The review mode: fresh-context subagents, or "not independent".
9. Guardrail proposals from `k-code-review`.
10. A link to the work item.

Before the skill does anything, it checks these conditions: **[call]**

- The current spec and plan files match the hashes that the ledger recorded at approval 2.
  The plan hash ignores the checkbox state (section 5.4).
  When they do not match, the skill refuses to run.
  A fast-path change has no approved spec or plan, so no hash applies.
- The diff contains no files under `docs/superpowers/`, `.agent-work/`, or `.superpowers/`.
  When it does, the skill fails.
- The risk level from the real diff is not higher than the level that the reviews used.
  When it is higher, the skill applies the late raise rule (section 5.3).

The skill pushes the branch and creates the PR with the code host CLI from `AGENTS.md`.
The skill writes the PR body once.
The PR follows the repo's PR template.
Before the PR opens, the skill updates the acceptance criteria in the work item.
The creator saw this update at approval 2.
A secret scan and redaction runs on every outbound write. **[call]**
Outbound writes are work item comments, acceptance criteria updates, issue bodies, and PR bodies.

A CI job runs the risk facts script on the PR. **[call]**
The job fails when the block in the PR body differs from the script output.
The compare uses the base SHA that the block records, and it ignores the volatile fields.
The same job fails when the PR has no rationale or no work item link.

Who writes the reason: Some practitioners say that only the human author should write the reason for a change.
In this workflow, the reason comes from the creator-approved spec and the recorded decisions. **[call]**
The agent only assembles it. **[call]**

When the project has a QA plan (listed in `AGENTS.md`), `k-pr` attaches the evidence that the plan requires, such as screenshots of a UI change. **[call]**
The PR needs visual evidence for UI work at medium or high risk. **[call]**

### 6.7 `k-guardrails-check` (new, report only)

The skill checks a project and writes a report. **[Svein]**
It never changes the project. **[Svein]**
It has one reference file for each area. **[call]**
It starts one read-only subagent for each area, in parallel. **[call]**

The skill gives each area one of these ratings:

- `none`
- `soft`: instruction only
- `harness`: hook or permission
- `hard`: CI or server

For each area, the report also records the answer to one question: "Can the agent edit this control?"

The areas are:

1. `AGENTS.md`: the skill checks that the file is present and correct, and that it has the work tracking section.
2. Harness hooks and permissions: the skill checks that they deny these actions:
   - `--no-verify`
   - `gh pr merge` and the same command on other hosts
   - force push
   - push to the default branch
   - writes to guardrail files

   It also checks that Claude Code hooks block on timeout.
   Copilot CLI hooks always let the command run on timeout.
   The skill rates a deny on Copilot CLI that depends on a timeout as `soft`.
3. Git hooks: the skill checks for lint, tests, and secret scan.
4. CI: the skill checks that required checks exist.
   It checks that they are the same checks as the local hooks.
   It also checks that workflow files are protected.
5. Tests: the skill checks for a coverage gate and that the project detects deleted or skipped tests.
6. Protected paths and CODEOWNERS: the skill checks both.
7. Dependencies and licences: the skill checks both.
8. Secrets and identity: the skill checks secret scanning and what the CLI tokens can do.
9. Untrusted input: the skill checks that the project marks work item text as data.
10. Upstream skills: the skill checks that the team pins them at the last known good versions.

Agent review does not count as a guardrail layer in the ratings, because reviewers read the same material as the author. **[call]**

Rating rules from the video research on 2026-10-27: **[call]**

- An allowlist of commands and capabilities rates higher than a denylist.
  The denies in area 2 are the minimum, not the goal.
- The skill treats an allowed interpreter, such as `python3`, as broad shell access.
- The skill checks isolation with five yes-or-no questions.
  Each question asks whether the agent can reach one of these:
  - secrets
  - the network
  - files outside the workspace
  - other users' data
  - unlimited resources
- Area 8 checks whether CLI tokens are present in the agent's environment, and what those tokens can do.
- The check confirms that reviewer subagents really have read-only permissions in each coding agent.
- Lint and test failures should say how to fix the problem.
  The check notes when they do not.
- Structural tests (dependency rules between layers, file length caps) are part of test strength.

Research on 2026-10-27 proposes more areas:

- control-plane integrity
- agent run isolation and egress
- tool and MCP allowlists
- static strictness and anti-weakening
- test strength
- contract and data safety
- supply chain provenance
- provenance and audit
- damage limits after merge
- the trust ladder

By default, the skill runs a core set. **[call]**
It runs an extended set on request or according to the project's stack and risk. **[call]**
The plan decides the exact split between core and extended.

### 6.8 `k-report-finding`

When an agent finds a problem that is out of scope, a background subagent investigates it. **[Svein]**
The subagent checks for duplicates. **[Svein]**
It then files an issue or a board bug, as `AGENTS.md` says. **[Svein]**
The skill has these requirements: **[call]**

- The skill takes one finding as input, with its location and reason.
- `k-work` and `k-run` invoke the skill in the background during the build and the code review.
  The user invokes it when the skill runs alone.
- The default cap is 3 findings for each work item.
- The skill scans for secrets and redacts them before filing.
- The skill files no security findings in a public tracker.
- `AGENTS.md` gives the tracker visibility as `public`, `private`, or `unknown`.
  The skill writes a draft for the human when the visibility is `public` or `unknown`.

### 6.9 Model tiers

Skills name a tier, not a model: Read, Build, or Think. **[call]**
One file in the repo maps each tier to a model for each coding agent.
When a coding agent cannot choose a model for a subagent, the subagent uses the main model.
The skill says so once.

### 6.10 Harness snippets

The repo has hook and permission snippets for each coding agent.
They cover the denies in section 6.7, area 2.
They are reference material. **[Svein]**
`k-guardrails-check` refers to them. **[Svein]**
No skill installs them. **[Svein]**

### 6.11 Rules for writing the skills

These rules apply to every `k-` skill. **[call]**
The sources are Matt Pocock, "Building Great Agent Skills: The Missing Manual" (2026), and Philipp Schmid, "Don't Ship Skills Without Evals" (2026).

- **Invocation.**
  Each skill records who starts it.
  The user invokes `k-work` and `k-guardrails-check`.
  `k-work` calls the stage skills before approval 2.
  `k-run` starts the stages after approval 2.
  `k-work` and `k-run` also invoke `k-report-finding` in the background.
  The user also invokes a stage skill or `k-report-finding` when the user runs it alone.
  A skill uses model invocation only when it must trigger without the user.
  Then the evals include trigger cases.
  Support for `disable-model-invocation` differs between coding agents (section 8).
  Each user-invoked skill ships `agents/openai.yaml` next to `SKILL.md`.
- **Steps and references.**
  `SKILL.md` holds the steps.
  It stays short, under 500 lines.
  Material that only one branch needs is in a separate file, and the skill refers to this file.
  The role files are an example.
- **Leading words.**
  Each concept has one term.
  Use it the same way everywhere.
  The terms are: attacker, judge, finding, ruling, risk fact, ledger, and grader (for evals only).
- **Focused phases.**
  One skill covers one phase at a time.
  For this reason, grilling, brainstorming, and planning stay separate.
- **Pruning.**
  Every PR that changes a skill needs a deletion test.
  If the team can remove a paragraph without a change in eval results, the team removes it.
  Each fact has one source of truth.
  The skills do not duplicate instructions.

### 6.12 `k-run` (new)

`k-work` starts `k-run` when the creator gives approval 2. **[call]**
The creator can also start `k-run` directly, for example to resume after a safety stop.

`k-run` is a script outside the coding agent. **[Svein]**
It is not a skill. **[Svein]**
`k-work` runs the stages up to approval 2 in the creator's session.
After approval 2, `k-run` drives every autonomous stage headless. **[Svein]**
These stages are the build, finishing, `k-code-review`, and `k-pr`.

`k-run` starts the coding agent for each stage.
It reads the harness events and the final message of each stage.
It uses the same per-agent adapters as the eval runner (section 7.3).

`k-run` enforces these checks between the stages: **[Svein]**

- **Artifact gates.**
  The artifacts that the next stage needs must exist.
  The spec and plan hashes must match the hashes from approval 2 (section 5.4).
- **Subagent counts.**
  `k-run` counts the subagent runs from the events and applies the budget (section 5.7, S5).
- **Rulings capture.**
  `k-run` captures the "Rulings I made" list from the final message of the build stage.
  It counts the rulings in that list (section 5.7, S3). **[call]**
  It compares that count with the `Ruling:` lines in the events of the build stage.
- **Remote-ref check.**
  Before `k-pr` runs, `k-run` checks the remote refs for an early push (section 5.7).
- **Safety stops.**
  `k-run` stops at each safety stop in section 5.2.
  It records the state and the cause in the ledger.
  On resume, it applies the exit that section 5.2 defines for that stop.

## 7. Upstream versions and sync

### 7.1 Last known good

The repo keeps one file with the last known good version of each upstream. **[Svein]**
The file lists:

- superpowers: commit and plugin version
- mattpocock/skills: commit
- the `skills` CLI: version

Each project repo pins the superpowers plugin version in its settings, and commits the other skill files and its `skills-lock.json` (section 3.6). **[Svein]**
A version bump is a PR in each project repo.

### 7.2 Contract checks (cheap, weekly)

A scheduled CI job reads the upstream files at their latest commit. **[call]**
It checks the points that the workflow depends on: **[call]**

- Brainstorming has its approval gate and passes control to `writing-plans`.
- The spec path can be overridden.
  The default path did not change.
- The plan header has the `Spec:` line.
- `writing-plans` ends with the approval question and the execution choice.
- Brainstorming still has `builder-check-prompt.md`.
- Subagent-driven development has the "Rulings" list and the final review.
- `final-review.md` still collects the rulings before it removes the workspace.
- Subagent-driven development still ends with `finishing-a-development-branch`.
  The menu in `finishing-a-development-branch` still has a "keep" option.
  Finishing does not push for that option.
- The skill names did not change.
- `grilling` and `domain-modeling` exist, with the same names.

When a check fails, the job opens an issue.
The job does not change any install.

### 7.3 Evals (on every skill change and every version bump)

The eval design follows Philipp Schmid, "Don't Ship Skills Without Evals" (Google DeepMind, 2026). **[call]**

- **Cases beside the skill.**
  Each skill has an eval file next to it, for example `evals/cases.yaml`.
  Each case has a prompt, an expectation whether the skill should trigger, a fixture workspace, and the checks.
- **Positive and negative cases.**
  Start with 5 cases for each skill.
  At least 2 cases should trigger the skill.
  At least 2 cases should not trigger it.
  Grow to 10-20 cases for each skill, with at least 5 cases of each kind.
- **Cheap checks first.**
  Most checks are scripts that test the output and the trace.
  They ask: Was `gh pr create` run?
  Does the PR body have the risk facts block?
  Does the review file exist?
  Does the trace show no PR creation before `k-code-review` ends?
  Did `k-pr` write the PR body once?
  The team uses a model grader with a rubric only for complex traces, such as the quality of attacker findings.
- **Outcomes, not paths.**
  A check tests the result, not the exact steps.
- **Isolation and repetition.**
  Each run uses a fresh clone of the fixture.
  Each case runs 5 times.
  The result is a pass rate, and the threshold is 80 percent.
  One run is too noisy.
  These numbers are defaults, and data changes them. **[call]**
- **Fixture.**
  The fixture has a stub board CLI.
  The stub returns fixed work items and records every write.
  The fixture also has a local bare git remote.
  Human gates in headless runs get scripted answers from a file for each case.
- **One runner, one adapter per coding agent.**
  The automated eval runner has an adapter for Claude Code (`claude -p`) and for Copilot CLI (`copilot -p`).
  The best-effort adapters call `codex exec`, `opencode run`, and `pi -p`.
  `k-run` uses the same adapters (section 6.12).
  VS Code Copilot has no adapter.
  It uses the manual smoke test checklist (section 2).
- **Ablation.**
  Each eval also runs without the skill.
  When the model passes without it, the skill is a candidate to retire.
  This also shows which upstream skills newer models no longer need.
  Keep the eval after the team retires a skill.
  Restore the skill if the results become worse.
- **Robustness.**
  Some cases vary the wording of the work item, to check that `k-intake` and the risk level stay stable.

A change to a team skill merges only when its evals pass at the threshold. **[call]**
A version bump is a team PR that shows the upstream diff and the eval results.
It merges only when the evals pass.

### 7.4 Switch to B

When changes in team files (skills, snippets, scripts) cannot fix a break, the team copies superpowers into this repo. **[Svein]**
The team uses the last known good commit. **[Svein]**
The team then releases a bundle. **[Svein]**
The contract checks and evals stay the same, so B changes the packaging and not the design.

## 8. Things to verify before or during the build

1. The spike on 2026-10-27 tested the seams once (n=1) in Claude Code and Copilot CLI (section 5.7).
   The evals in section 7.3 repeat these checks on every skill change and every version bump.
   Verify the seams in the other coding agents.
2. Verify that the team can pin superpowers to a version in Codex, OpenCode, Pi, Copilot CLI, and Hermes.
   Claude Code and VS Code Copilot support pinning.
   Some coding agents update plugins automatically.
3. Verify that the Copilot cloud agent supports subagents and user-level skills.
4. Verify that a `preToolUse` hook in VS Code Copilot can block a terminal command.
5. Verify how each coding agent handles the invocation flag on a user-invoked skill.
   Verify that Copilot CLI respects `disable-model-invocation`.
   OpenCode ignores `disable-model-invocation`.
   Codex uses `agents/openai.yaml` with `policy.allow_implicit_invocation: false`.
6. Verify that skills can call other skills in Codex, OpenCode, Pi, and Hermes.
7. Verify that an `npx skills` restore installs the same content.
   The lock file records a ref and a hash, not a commit.
   The restore command is experimental.
   It installs into `.agents/skills`.
   It does not link into `.claude/skills`.
   A commit pin needs a 40-character SHA in the source (`owner/repo#<sha>`).
   Onboarding uses `npx skills add -a claude-code`, or a link step, for Claude Code.
8. Verify the ASD-STE100 rule details against the official Issue 9 text.
9. Find a subagent extension for Pi that the team can approve.
   Verify how this extension selects a model.
10. Verify whether a hook in Codex can block a shell command before the command runs.
    The docs and a 2026 OpenAI talk disagree on the hook names.
11. Verify the Codex plugin for Claude Code.
    The plugin can run a Codex review inside a Claude Code session.
    This can give a cross-vendor attacker in Claude Code.
12. Verify whether the team can convert EARS-style acceptance criteria to property-based tests (Amazon Kiro).
    The conversion is optional, for medium and high risk.
13. The spike found that Copilot CLI added a co-author trailer to one commit.
    Verify the commit trailer behaviour of each coding agent against the team attribution policy.
14. Verify that the events of Copilot CLI show the `Ruling:` lines of the build stage.
    The spike checked subagent counts in the events, not the ruling lines.
    Section 6.12 depends on this for the rulings count.
15. Decide how `k-run` grants tool permissions to headless runs.
    In the spike, narrow permissions made Copilot CLI skip an upstream review step.
    Broad permissions need the sandbox, which is a separate repo.
    This is a design question, not only a plan detail.
16. Sections 6.12, 5.2, and 5.7 changed after the last review round, because the round cap was reached.
    No attacker reviewed these changes.
17. Verify how each coding agent enables and pins a plugin from project settings.
    Claude Code and VS Code Copilot support project settings for plugins.
    For Copilot CLI, pinning from the repo is not verified.
    Also verify how `k-work` reads the installed superpowers version in each coding agent.
18. Verify which copy wins in Copilot CLI, Codex, OpenCode, and Pi when a user-level skill and a project skill have the same name.
19. Verify that committed skill symlinks work on Windows, or commit copies instead.
20. Section 3.6 changed after the last review round. No attacker reviewed it.

## 9. Left to the builder

The builder decides these items:

- The repo layout, the file formats, and the script language for the risk facts script and the contract checks.
- The fixture repo, the stub board CLI, the eval scenarios, and the manual smoke test checklist for VS Code Copilot.
- The exact wording of the role files and skills, in ASD-STE100.
- The onboarding guide, with install steps for each coding agent, the trust step, and the pins.
  The install steps set `DISABLE_TELEMETRY=1`, because the `skills` CLI can send identifiers of non-public sources.
