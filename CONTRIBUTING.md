# Contributing to sbom-vm

Thanks for helping improve sbom-vm.

- Open an issue before larger behavior changes so the approach can be discussed.
- Keep pull requests focused on one concern.
- Include tests when the change can be tested without root, Docker, loop devices, or real disk images.
- Run `python -m py_compile sbom-vm.py generate-test-images.py` and `python -m unittest discover -s tests` before submitting code.
- Mention related issues in the PR body, for example `Closes #10`.
