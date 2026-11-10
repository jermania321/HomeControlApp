
---
name: implementation
description: Implement an approved software feature or bug fix in the current repository. Use when the user explicitly asks to implement, code, build, or fix functionality after approving the scope.
---

# Feature Implementation

Follow this workflow when implementing approved changes.

## 1. Understand

- Read AGENTS.md and relevant project documentation.
- Review the approved feature requirements.
- Inspect the existing code before making changes.
- Identify affected files and dependencies.

## 2. Implement

- Make small, focused changes.
- Follow existing coding conventions.
- Avoid unnecessary dependencies.
- Handle errors and edge cases.
- Do not modify unrelated functionality.

## 3. Validate

- Add or update relevant tests.
- Run available tests when permitted.
- Report test failures accurately.
- Do not claim success without verification.

## 4. Review

- Inspect the resulting changes.
- Identify security and reliability concerns.
- Suggest a separate reviewer pass.

## Safety

- Never expose credentials or secrets.
- Do not push, merge, or deploy without approval.
- Ask before destructive operations.
- If requirements are unclear, explain assumptions.
- Do not implement unapproved scope.

## Output

Summarize:
1. Changes made
2. Files modified
3. Tests and results
4. Known limitations
5. Suggested next steps
