## Description

<!-- Provide a brief description of the changes in this PR -->

## Type of Change

<!-- Mark the relevant option with an "x" -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Dependency update

## Testing Checklist

<!-- ALL items must be checked before merging -->

### Pre-Commit

- [ ] Pre-commit hooks installed (`make pre-commit-install`)
- [ ] Pre-commit checks pass (`make pre-commit`)
- [ ] No debug statements or print() left in code

### Unit Tests

- [ ] All existing unit tests pass (`pytest -m unit`)
- [ ] New unit tests added for new functionality
- [ ] Code coverage ≥ 80% (`pytest --cov=m8tes --cov-report=term`)
- [ ] Tests are isolated (no external dependencies)

### Code Quality

- [ ] Code formatted with Black (`make format`)
- [ ] Linting passes with Ruff (`make lint`)
- [ ] Type checking passes with mypy (`make type-check`)
- [ ] No security issues (`bandit -r m8tes/`)

### Integration (if applicable)

- [ ] Integration tests pass (if touching external APIs)
- [ ] E2E tests pass locally (if changing SDK behavior)
  - Backend started: `cd ../../../backend && flask run`
  - Worker started: `cd ../../../cloudflare/m8tes-agent && npm run dev`
  - E2E tests: `make test-e2e`

### Documentation

- [ ] Docstrings updated for public APIs
- [ ] README.md updated (if changing public interface)
- [ ] CHANGELOG.md updated (if user-facing change)
- [ ] Code comments added for complex logic

## Breaking Changes

<!-- If this is a breaking change, describe the impact and migration path -->

None / N/A

## Reviewer Notes

<!-- Any specific areas you'd like reviewers to focus on? -->

## Local Testing Evidence

<!-- Paste output from key test runs to demonstrate testing was performed -->

```bash
# Example:
$ make ci-test
# ... test output showing all tests passing

$ pytest --cov=m8tes --cov-report=term
# ... coverage report showing ≥ 80%
```

## Related Issues

<!-- Link related issues here using #issue_number -->

Fixes #
Relates to #

---

## Reviewer Checklist

<!-- For reviewers - ensure all items are verified before approving -->

- [ ] Code follows project style guidelines
- [ ] Tests are comprehensive and meaningful
- [ ] No obvious security vulnerabilities
- [ ] Changes are backwards compatible (or breaking changes are documented)
- [ ] Documentation is accurate and complete
