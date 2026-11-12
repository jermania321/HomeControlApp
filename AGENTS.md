
# Agent Instructions

## Project

This repository is an experimental software development
workspace for learning AI-assisted development with
T3 Code and OpenCode.

## General Rules

- Inspect the existing code before proposing changes.
- Explain architectural decisions and trade-offs.
- Prefer maintainable, testable solutions.
- Never expose credentials, API keys, or tokens.
- Do not commit or push without user approval.
- Do not modify files when the user requests planning only.
- provide proper description for each commit done on the COMMIT while raising the PR

## Available Skills

### feature-planning

Use the `feature-planning` skill when the user asks to:
- Plan a new feature
- Design application architecture
- Break down implementation tasks
- Compare technical approaches

Before implementing a substantial new feature,
propose a plan and obtain approval.

## Development Workflow

1. Understand the request.
2. Identify the relevant skill.
3. Inspect the repository.
4. Plan the changes.
5. Implement only approved changes.
6. Run relevant tests.
7. Summarize modifications and remaining risks.

## Pull Request CI Follow-up

- After every authorized push to a pull request, check its GitHub Actions status.
- Do not report a queued or running check as passed or failed; report it as pending.
- Once checks finish, update the pull request's Markdown validation section with
  the relevant workflow result and link. Record failures accurately and do not
  describe the PR as green until the latest head's checks pass.
