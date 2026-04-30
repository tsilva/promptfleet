You are in one GitHub repository.

Goal: review open Dependabot PRs without changing the local checkout, and enable GitHub auto-merge only for clearly safe PRs.

Do not run `gh pr checkout`.
Do not run `git checkout`, `git switch`, `git pull`, `git merge`, or any command that changes the working tree.
Do not edit files.
Do not install dependencies.
Do not run local tests.

Use GitHub data only:
- `gh pr list --state open --search "author:app/dependabot"`
- `gh pr view PR_NUMBER --json number,title,body,url,author,headRefName,baseRefName,mergeable,reviewDecision,changedFiles,files,commits,statusCheckRollup`
- `gh pr diff PR_NUMBER --patch`
- `gh pr checks PR_NUMBER`
- `gh pr merge PR_NUMBER --auto --squash --delete-branch` only when safe

For each Dependabot PR, classify it.

Only enable auto-merge if all are true:
- Author is Dependabot.
- The diff changes dependency manifests and lockfiles only.
- The update is patch-level, a minor dev-dependency update, or qualifies under the 7-day aged release rule below.
- No major version bump.
- No runtime, framework, build, deploy, auth, payment, or database package upgrade unless obviously low-risk or it qualifies under the 7-day aged release rule below.
- No source code, config, workflow, Docker, environment, or script changes.
- No new lifecycle scripts or suspicious package metadata changes.
- GitHub checks are passing, or required checks are pending and branch protection will gate auto-merge.
- The PR is mergeable or expected to become mergeable after checks complete.

7-day aged release rule:
- A minor runtime or production dependency update can be considered safe if every updated package version is at least 7 days old relative to today.
- This exception only applies when the diff is still limited to dependency manifests and lockfiles, and all other safety criteria are met.
- If the diff changes lock metadata, dependency constraints, or transitive resolutions beyond the headline package, identify every package whose version may be forced or newly resolved by that change. Each of those package versions must also be at least 7 days old.
- Use release dates from the PR body/release notes when present, or package upload timestamps visible in lockfile diffs. If you cannot determine the release/upload age for every affected package, do not use this exception.
- Do not use this exception for major updates, framework/build/deploy/auth/payment/database package updates, lifecycle script changes, source/config/workflow changes, failing checks, or ambiguous mergeability.

For safe PRs:
- Run `gh pr merge PR_NUMBER --auto --squash --delete-branch`.
- Do not directly merge with a local git command.

For anything unsafe, ambiguous, failing, conflicted, or not confidently reviewed:
- Do not merge.
- Report why it was skipped.

At the end, verify the local checkout was not changed with:
`git status --porcelain`

Return a concise summary:
- AUTO-MERGE ENABLED
- SKIPPED
- NEEDS HUMAN REVIEW
- CHECKS FAILING
