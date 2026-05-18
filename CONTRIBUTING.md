# Contributing to ShaprAI

Thank you for helping sharpen the next generation of Elyan-class agents!

## Getting Started

```bash
# Clone the repo
git clone https://github.com/Scottcjn/shaprai.git
cd shaprai

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Prerequisites

ShaprAI depends on several Elyan Labs projects:

- [beacon-skill](https://github.com/Scottcjn/beacon-skill) for agent discovery
- [grazer-skill](https://github.com/Scottcjn/grazer-skill) for content discovery
- [Atlas (via beacon-skill)](https://github.com/Scottcjn/beacon-skill) for deployment orchestration
- A RustChain wallet for RTC token integration

## Making Changes

1. **Fork** the repository
2. **Create a branch** from `main`: `git checkout -b feat/my-change`
3. **Make your changes** and run `pytest`
4. **Commit** using [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `chore:`
5. **Push** to your fork and open a **Pull Request**

## Code Style

- Python 3.10+
- Type hints on all public functions
- Docstrings for modules, classes, and public methods
- Run `ruff check` before submitting

## What to Work On

- Check [open issues](https://github.com/Scottcjn/shaprai/issues) for tasks
- Browse [rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties/issues) for RTC-paid bounties
- Training pipeline improvements, new agent templates, and documentation are high-value areas

## Security

If you find a security vulnerability, **do not open a public issue**. Use GitHub's private vulnerability reporting or contact the maintainer directly.
