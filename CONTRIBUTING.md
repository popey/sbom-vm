# Contributing to sbom-vm

Thanks for your interest in contributing!

- Read the README for usage and prerequisites.
- Run the script locally (as root) to reproduce problems: `sudo python3 sbom-vm.py <path-to-image>`.
- Keep changes small and focused. Open an issue first for larger design changes.
- Include tests when adding or fixing parsing or logic (no test harness currently; add simple unit tests alongside changes when possible).
- Follow the repository style: minimal dependencies, clear logging, and conservative changes.

When opening PRs:
- Start a branch `repo-assist/<short-desc>` or `feature/<short-desc>`.
- Title PRs clearly; include `Closes #<issue>` if the PR resolves an issue.
- Add a short Test Status section describing local checks (syntax, manual run) and CI results if available.
- Every automated contribution includes an AI disclosure if created by Repo Assist.

If you need help, open an issue and the maintainers will advise.