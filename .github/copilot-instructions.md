# Copilot instructions

Follow the repository rules in [AGENTS.md](../AGENTS.md). In short:

- Keep PRs small, under 100 changed lines (not counting tests) when possible.
- One concern per PR: never mix a fix and a feature unless it is essential, and say why when you do.
- Follow the existing architecture described in AGENTS.md. Do not introduce new patterns without an issue first.
- Keep comments and docstrings short, and only where they help future changes. Don't restate the code.
- String changes must update `strings.json` and every file in `translations/`.
- PR titles use Conventional Commits.
