
---
description: Develop a feature using the Architect, Developer, and Reviewer agents
agent: orchestrator
---

# Develop Feature

Feature request: $ARGUMENTS

Follow the project AGENTS.md instructions.

## Phase 1 — Planning

1. Delegate planning to the architect agent.
2. Use the feature-planning skill.
3. Examine the existing codebase.
4. Create a proposed implementation plan.
5. Present the plan and wait for user approval.

## Phase 2 — Implementation

After approval:

1. Delegate implementation to the developer agent.
2. Use the implementation skill.
3. Write or update relevant tests.
4. Run tests and document results.

## Phase 3 — Review

1. Delegate the changes to the reviewer agent.
2. Fix confirmed review findings using the developer.
3. Repeat the review if necessary.
4. Stop after three unsuccessful review cycles.

## Phase 4 — GitHub

1. Use the github-workflow skill.
2. Inspect the full Git diff.
3. Check for secrets and unexpected changes.
4. Prepare a feature branch and focused commits.
5. Request approval before publishing.

Never push, merge, force-push, or deploy without
the required user approval.

## Final Report

Include:
- Feature implemented
- Files changed
- Test results
- Review findings
- Commit and PR status
- Outstanding approvals
