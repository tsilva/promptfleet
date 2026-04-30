You are in one repository.

Goal: reduce supply-chain risk by ensuring every package manager used by this repo avoids installing packages that were freshly released.

This is a repo-specific implementation task. Inspect the repository first, then make the smallest appropriate changes for the package managers actually present.

Detect package managers from manifests, lockfiles, config files, and CI install commands. Common signals include:

- Python uv: `uv.lock`, `pyproject.toml` with uv usage, CI commands using `uv`
- Python pip: `requirements*.txt`, `constraints*.txt`, `pip.conf`, CI commands using `pip install`
- npm: `package-lock.json`, `npm-shrinkwrap.json`, `.npmrc`, CI commands using `npm ci` or `npm install`
- pnpm: `pnpm-lock.yaml`, `pnpm-workspace.yaml`, CI commands using `pnpm install`
- Bun: `bun.lock`, `bun.lockb`, `bunfig.toml`, CI commands using `bun install` or `bun ci`
- Yarn: `yarn.lock`, `.yarnrc.yml`, CI commands using `yarn install`
- Other managers: Poetry, Pipenv, Cargo, Go modules, Composer, Maven, Gradle, NuGet, or any repo-specific tooling

Preferred minimum package age:

- Use 7 days unless the repository already has a stricter policy.
- Do not weaken an existing stricter freshness delay.
- If a setting exists but is shorter than 7 days, increase it to 7 days.

Apply supported settings:

- uv: add or update `[tool.uv] exclude-newer = "7 days"` in `pyproject.toml`.
- npm: add or update `.npmrc` with `min-release-age=7`.
- pnpm: add or update `pnpm-workspace.yaml` with `minimumReleaseAge: 10080`.
- Bun: add or update `bunfig.toml` with:

```toml
[install]
minimumReleaseAge = 604800
```

- pip: add a repo-local `pip.conf` only when CI or scripts can be updated to use it, then ensure install environments set `PIP_CONFIG_FILE` to that file. The config should include:

```ini
[install]
uploaded-prior-to = P7D
```

  Alternatively, update CI install steps to export `PIP_UPLOADED_PRIOR_TO=P7D` before `pip install`.

- Yarn Berry/modern Yarn: add or update `.yarnrc.yml` with `npmMinimalAgeGate: 7d`.

For unsupported or unclear managers:

- Do not invent a config setting.
- Prefer lockfile-only installs where applicable.
- Report the package manager as `NEEDS HUMAN REVIEW` with the reason.

Also align automated dependency update tools when present:

- Dependabot: if `.github/dependabot.yml` exists, add or update `cooldown.default-days: 7` for package ecosystems touched by this task, without disrupting unrelated settings.
- Renovate: if Renovate config exists, add or update `minimumReleaseAge` to at least `7 days` in the appropriate package rule or global config.

CI/install hardening:

- If CI exists, ensure install commands use locked/frozen modes where appropriate:
  - uv: `uv sync --locked`
  - npm: `npm ci`
  - pnpm: `pnpm install --frozen-lockfile`
  - Bun: `bun ci` when supported by the repo, otherwise preserve repo conventions and freshness config
  - Yarn: `yarn install --immutable`
- Do not rewrite CI broadly. Only adjust install commands or environment variables directly related to this supply-chain policy.

Validation:

- Run the repo's formatting or config validation if obvious and cheap.
- Do not perform broad dependency upgrades.
- Do not delete or regenerate lockfiles unless required by the package manager and clearly safe.
- Check `git diff` before finishing.

Final response must include:

- `APPLIED` entries for package managers where freshness gates were added or updated
- `ALREADY_OK` entries for package managers that already had a sufficient policy
- `NEEDS HUMAN REVIEW` entries for unsupported or ambiguous managers
- files changed
- validation commands run
