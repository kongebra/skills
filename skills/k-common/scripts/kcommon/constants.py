"""Shared constants for the k- skills. Glob syntax is the one in kcommon.globs.match."""

CI_GLOBS: tuple[str, ...] = (
    ".github/workflows/**",
    ".github/actions/**",
    ".circleci/**",
    "Jenkinsfile",
    "azure-pipelines*.yml",
    "azure-pipelines.yaml",
    "pipelines/**/*.yml",
    ".azuredevops/**",
    "bitbucket-pipelines.yml",
    ".gitlab-ci.yml",
    ".forgejo/workflows/**",
)

GUARDRAIL_GLOBS: tuple[str, ...] = (
    "AGENTS.md",
    "CODEOWNERS",
    ".github/CODEOWNERS",
    "docs/CODEOWNERS",
    ".github/workflows/**",
    ".github/hooks/**",
    ".claude/settings.json",
    ".claude/skills/**",
    ".agents/skills/**",
    ".codex/**",
    "skills-lock.json",
    ".pre-commit-config.yaml",
    "lefthook.yml",
    ".husky/**",
    "CLAUDE.md",
    ".mcp.json",
    ".claude/agents/**",
    ".claude/commands/**",
    ".github/copilot-instructions.md",
    *CI_GLOBS,
)

INFRA_GLOBS: tuple[str, ...] = ("infra/**", "*.bicep", "*.tf", "Dockerfile")

DEPENDENCY_GLOBS: tuple[str, ...] = (
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "*.csproj",
    "packages.lock.json",
    "Directory.Packages.props",
    "pyproject.toml",
    "uv.lock",
    "requirements*.txt",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
)

MIGRATION_GLOBS: tuple[str, ...] = ("**/migrations/**",)

TEST_GLOBS: tuple[str, ...] = (
    "**/test/**",
    "**/tests/**",
    "test_*",
    "*_test.*",
    "*.test.*",
    "*Tests.cs",
)

# Regular expressions, matched on added lines.
SKIP_MARKERS: tuple[str, ...] = (
    r"@skip\b",
    r"@unittest\.skip",
    r"pytest\.mark\.skip",
    r"\.skip\(",
    r"\bxit\(",
    r"@Disabled",
    r"\[Ignore\]",
    r"\bSkip\s*=",
    r"t\.Skip\(",
)

CODEOWNERS_PATHS: tuple[str, ...] = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")

IGNORE_PROBES: tuple[str, ...] = (
    "docs/superpowers/x",
    ".agent-work/x",
    ".superpowers/x",
)

REPO_SKILL_DIRS: tuple[str, ...] = (".agents/skills", ".claude/skills")
# Relative to the home directory.
USER_SKILL_DIRS: tuple[str, ...] = (".claude/skills", ".agents/skills", ".copilot/skills")

MATT_SKILLS: tuple[str, ...] = ("grilling", "grill-with-docs", "domain-modeling")

EVIDENCE_HEAD_CHARS = 5000
EVIDENCE_TAIL_CHARS = 15000
RUN_TIMEOUT_SECONDS = 600
