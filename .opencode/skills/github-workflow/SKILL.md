
---
name: github-workflow
description: Review Git changes, prepare feature branches, commits, and pull requests. Use when asked to prepare code for GitHub, examine Git status, organize commits, or create a pull request.
---

# GitHub Workflow

Prepare repository changes for safe collaboration.

## 1. Inspect

- Check the current branch and working tree status.
- Examine changed and untracked files.
- Review the diff before staging.
- Identify generated files, credentials, and unrelated changes.

## 2. Validate

- Confirm relevant tests have passed.
- Check that .gitignore excludes generated files.
- Identify any remaining reviewer findings.
- Never claim tests passed without evidence.

## 3. Prepare

- Recommend a descriptive feature branch.
- Group related changes into a logical commit.
- Suggest a concise commit message.
- Prepare a pull request description with test results.

## 4. Approval

- Do not create or switch branches without approval.
- Do not stage or commit without approval.
- Do not push or create a pull request without approval.
- Never merge or force-push automatically.
- Never include secrets or credentials.

## Git Naming Conventions

### Branch Names

- Use lowercase letters.
- Use underscores (_) between words.
- Prefix feature branches with `feature/`.
- Prefix bug-fix branches with `fix/`.
- Prefix maintenance branches with `chore/`.
- Make branch names descriptive but avoid excessive length.

Example:
`feature/email_priority_classification_with_unit_tests`

### Commit Messages

Follow Conventional Commits:

`type: short description`

Supported types:
- feat
- fix
- refactor
- test
- docs
- chore

Use a concise subject followed by an optional body
explaining important changes.

Never commit or push without explicit user approval.

## Output

Provide:
1. Repository status
2. Files proposed for commit
3. Test results
4. Suggested branch name
5. Suggested commit message
6. Pull request summary
7. Risks or blockers
