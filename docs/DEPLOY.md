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

Alternatively, open the comparison in GitHub and use `docs/PR_DESCRIPTION.md`:
https://github.com/noahwos/kalshi-football-volatility/compare/main...feature/football-volatility-analyzer?expand=1

Leave the PR open for review; do not merge it as part of setup.
