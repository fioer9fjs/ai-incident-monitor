# Security Policy — AI Incident Monitor

## Supported Versions

Only the latest commit on the `main` branch is supported with security updates.

## Reporting a Vulnerability

Please open a **private security advisory** on GitHub or email the repository owner directly. Do **not** open public issues for undisclosed security problems.

## Security Design Decisions

| Layer | Control |
|-------|---------|
| **Cloud credentials** | OIDC / Workload Identity Federation only. No long-lived service-account JSON keys are stored in the repository or in GitHub secrets. |
| **BigQuery access** | Dedicated service account with `roles/bigquery.user` only. Query cost limited by a 100 GB dry-run safety gate per execution. |
| **CI/CD** | `contents: write` and `id-token: write` are required only for the ingest job. All other jobs use the minimum required permissions. |
| **Secrets in code** | Prohibited. `docs/INFRA.local.md` is gitignored. `trufflehog` scans every PR. |
| **Dependencies** | Pinned in `requirements.txt`. Dependabot opens PRs for updates. `pip-audit` runs in CI. |
| **Input validation** | All pipeline stages validate inputs before processing. BigQuery queries are built from allow-listed static keywords only; user-facing parameters are type-checked and clamped. |
| **Output sanitisation** | File names are derived from hashes or strictly formatted timestamps, never raw user input. Path-traversal sequences are rejected at render time. |

## Automated Checks

- **SAST**: `bandit` scans Python source on every PR.
- **Dependency audit**: `pip-audit` scans for known vulnerabilities in pinned requirements.
- **Secret scanning**: `trufflehog` detects leaked credentials in commits.
- **Config validation**: `scripts/validate_config.py` runs in CI to prevent broken taxonomy or watchlist changes.

## Incident Response

1. Revert the offending commit or workflow run.
2. Rotate the Workload Identity Provider if OIDC tokens may have been leaked.
3. Review BigQuery audit logs for anomalous queries.
4. Publish an advisory once the fix is deployed.
