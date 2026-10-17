# Publishing the feature branch and opening a pull request

The repository has an initial `main` commit and a pushed
`feature/football-volatility-analyzer` branch containing the source code.
Use the existing checkout; no Git bundle or reinitialization is needed.

Before publishing further changes:

```bash
source .venv/bin/activate
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 pytest -q
ruff check src tests
python -m pip check
git diff --check
git status --short
```

Keep credentials, downloaded data, trained models and generated reports out of commits.
After committing reviewed changes on the feature branch:

```bash
git push -u origin feature/football-volatility-analyzer
gh pr list --repo noahwos/kalshi-football-volatility \
  --head feature/football-volatility-analyzer --base main
# If no PR exists:
gh pr create --repo noahwos/kalshi-football-volatility \
  --base main --head feature/football-volatility-analyzer \
  --title 'Add NFL and CFB historical volatility analyzer' \
  --body-file docs/PR_DESCRIPTION.md
```

PR creation requires authenticated access to `api.github.com` in addition to Git
push access. If the environment proxy returns HTTP 403 before connecting to the
API, apply the saved allowed-domain setting to the running environment. Saving
a configuration draft alone does not apply runtime networking changes.

The feature branch also includes a GitHub Actions helper to open/update the PR
using GitHub's own token. Its first run reached GitHub successfully but was
rejected with:

> GitHub Actions is not permitted to create or approve pull requests

The repository owner must enable **Settings → Actions → General → Workflow
permissions → Allow GitHub Actions to create and approve pull requests**:
https://github.com/noahwos/kalshi-football-volatility/settings/actions

The helper requests `contents: read` and `pull-requests: write`; it never merges
or approves the PR. Once enabled, request a run with an explicit commit marker:

```bash
git commit --allow-empty -m 'Request analyzer PR [open-pr]'
git push origin feature/football-volatility-analyzer
```

Ordinary commits skip this helper, so they do not repeatedly retry a known
permission denial. It creates the PR if absent or updates its description from
`docs/PR_DESCRIPTION.md` if one already exists.

Alternatively, open the comparison in GitHub and use `docs/PR_DESCRIPTION.md`:
https://github.com/noahwos/kalshi-football-volatility/compare/main...feature/football-volatility-analyzer?expand=1

Leave the PR open for review; do not merge it as part of setup.
