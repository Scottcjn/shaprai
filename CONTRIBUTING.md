# Contributing to ShaprAI

Thank you for your interest in contributing to ShaprAI! This document provides guidelines and instructions for contributing.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Git
- pip or poetry

### Setup

1. **Fork the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/shaprai.git
   cd shaprai
   ```

2. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Verify installation**
   ```bash
   pytest tests/ -v
   ```

## 📋 Development Workflow

### 1. Choose an Issue
- Browse [open issues](https://github.com/Scottcjn/shaprai/issues)
- Look for bounties you can tackle
- Comment on the issue to claim it

### 2. Create a Branch
```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/issue-123
```

### 3. Make Changes
- Follow existing code style
- Add tests for new functionality
- Update documentation as needed

### 4. Run Tests
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=shaprai

# Run specific test file
pytest tests/test_driftlock.py -v
```

### 5. Commit Changes
```bash
git add .
git commit -m "feat: add new feature - Fixes #123"
```

**Commit message format:**
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation
- `test:` for test additions
- `refactor:` for code refactoring

### 6. Push and Create PR
```bash
git push origin feat/your-feature-name
```

Then create a Pull Request on GitHub referencing the issue.

## 🎯 Code Style

### Python Style
- Follow [PEP 8](https://pep8.org/)
- Use type hints
- Maximum line length: 100 characters
- Use double quotes for strings

### Example
```python
from typing import Optional, List

class DriftLock:
    """Detects semantic drift in agent responses."""
    
    def __init__(self, threshold: float = 0.4) -> None:
        self.threshold = threshold
        self.anchor_phrases: List[str] = []
    
    def compute_drift(self, response: str) -> float:
        """Compute drift score between response and anchor phrases."""
        pass
```

## 🧪 Testing Requirements

- **Unit tests**: Required for all new features
- **Integration tests**: For complex workflows
- **Coverage**: Aim for 80%+ coverage
- **Test naming**: `test_<function>_<scenario>.py`

## 📝 Pull Request Guidelines

### PR Title
- Clear and descriptive
- Reference issue number: `Fixes #123`

### PR Description
```markdown
## Summary
Brief description of changes

## Changes
- List key changes
- Include any breaking changes

## Testing
- Describe tests added
- Include manual testing steps

## Related Issue
Fixes #123
```

### Review Process
1. CI checks must pass
2. At least one maintainer approval
3. Address review comments promptly
4. Bounty paid after merge to main

## 🏆 Bounty Program

We offer RTC rewards for contributions:

| Type | Reward |
|------|--------|
| Bug fix | 5-15 RTC |
| Feature | 10-50 RTC |
| Major feature | 50-100 RTC |
| Documentation | 2-10 RTC |

See [bounties issue](https://github.com/Scottcjn/rustchain-bounties) for details.

## 💬 Questions?

- Open a [discussion](https://github.com/Scottcjn/shaprai/discussions)
- Join our Discord
- Comment on relevant issues

## 🎨 Code of Conduct

Be respectful and inclusive. We welcome contributors of all backgrounds and experience levels.

---

**Ready to contribute?** Pick an issue and start coding! 🚀
