You are in one repository.

Goal: audit and fix GitHub Actions CI/CD only when this repo has GitHub Actions configured and the latest relevant GitHub Actions state is broken.

This is an audit task, so do not treat a successful local agent run as success. Success requires an explicit GitHub Actions status check with `gh` before and after any attempted fix.

First, check for GitHub Actions workflows in `.github/workflows/*.yml` or `.github/workflows/*.yaml`.

If no GitHub Actions workflows exist, make no changes and finish with:

`AUDIT_OK no GitHub Actions workflows`

If workflows exist:

1. Verify GitHub CLI access with `gh auth status`.
2. Resolve the GitHub repo and default branch with `gh repo view --json nameWithOwner,defaultBranchRef`.
3. Determine the audit target:
   - If the current branch has an open PR, audit the current PR branch/checks.
   - Otherwise audit the default branch.
4. Enumerate relevant enabled GitHub Actions workflows from `.github/workflows` and `gh workflow list`.
5. Query the latest relevant run for each workflow on the audit target with `gh run list` and inspect details with `gh run view`.

Do not rely on only one global `gh run list --limit 1`; repos can have multiple workflows, and a passing or unrelated latest workflow does not prove CI/CD is healthy.

Classify the audit result:

- `AUDIT_OK`: all relevant latest runs are completed and successful, skipped for an expected reason, or there are no runs yet for a workflow that has not been triggered.
- `AUDIT_BROKEN`: one or more relevant latest runs failed, timed out, were cancelled because of a real workflow/build/test/deploy problem, or have failing jobs.
- `AUDIT_PENDING`: one or more relevant latest runs are queued, waiting, requested, or in progress.
- `AUDIT_UNABLE`: GitHub status cannot be confidently determined because `gh` is unavailable, auth is missing, the repo cannot be resolved, logs cannot be fetched, or workflow/run mapping is ambiguous.

Only make code or workflow changes for `AUDIT_BROKEN`.

If `AUDIT_OK`, make no changes and finish with the workflow/run IDs checked.

If `AUDIT_PENDING`, make no changes and finish with the pending workflow/run IDs. Do not call this fixed.

If `AUDIT_UNABLE`, make no changes and finish with the exact command or data that failed. Do not call this fixed.

If `AUDIT_BROKEN`:

1. Inspect the failing job logs with `gh run view <run-id> --log-failed`.
2. Inspect the workflow config and the smallest relevant repo code/test/config surface.
3. Make the smallest repo-appropriate fix.
4. Run relevant local validation commands.
5. Do not touch non-GitHub CI/CD systems.
6. Do not make unrelated refactors.
7. Re-query GitHub Actions state with `gh run list` / `gh run view`.

Post-fix reporting is required:

- If the pre-fix failure is fixed locally but GitHub has not rerun yet, finish with `AUDIT_BROKEN_FIXED_LOCALLY` and include the failed run ID plus local validation commands.
- If the latest GitHub run is now passing, finish with `AUDIT_OK_FIXED` and include the passing run ID.
- If failures remain, finish with `AUDIT_BROKEN_REMAINS` and include the remaining failing workflow/run IDs.
- If status cannot be rechecked, finish with `AUDIT_UNABLE_AFTER_FIX` and include the exact failed command.

The final response must include:

- audit target branch or PR
- workflow names and run IDs checked
- classification
- changes made, if any
- validation commands run
