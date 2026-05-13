# GitHub Actions Workflows

This directory contains all GitHub Actions workflows for the Tax Buddy project. These workflows automate testing, security scanning, code quality checks, and releases.

## 📋 Available Workflows

### 1. CI Pipeline (`ci.yml`)

**Purpose:** Continuous Integration pipeline that runs on every push and pull request.

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Jobs:**
- **Backend Tests:** Runs pytest with coverage reporting
- **Backend Linting:** Checks code style with Ruff, Black, and isort
- **Frontend Build:** Builds Next.js app and runs ESLint
- **Docker Build:** Verifies Docker image builds successfully

**Duration:** ~10-15 minutes

**How to Run Locally:**

```bash
# Backend tests
cd backend
pytest tests/ -v --cov=app --cov=ml

# Backend linting
ruff check .
black --check .
isort --check-only .

# Frontend build
cd frontend
npm run build
npm run lint

# Docker build
docker build -t tax-buddy:test .
```

### 2. Security Scan (`security.yml`)

**Purpose:** Automated security scanning for dependencies and secrets.

**Triggers:**
- Weekly schedule (Mondays at 9:00 AM UTC)
- Pull requests to `main` or `develop` branches
- Manual trigger via workflow_dispatch

**Jobs:**
- **Python Security:** Runs pip-audit, Safety, and Bandit
- **npm Security:** Runs npm audit and checks for outdated packages
- **Dependency Review:** Reviews dependency changes in PRs
- **Secret Scanning:** Scans for exposed secrets using TruffleHog

**Duration:** ~5-10 minutes

**How to Run Locally:**

```bash
# Python security
cd backend
pip install pip-audit safety bandit
pip-audit --requirement requirements.txt
safety check --file requirements.txt
bandit -r app/ ml/

# npm security
cd frontend
npm audit
npm outdated
```

### 3. Code Quality (`quality.yml`)

**Purpose:** Enforces code quality standards and documentation.

**Triggers:**
- Pull requests to `main` or `develop` branches
- Manual trigger via workflow_dispatch

**Jobs:**
- **Python Type Checking:** Runs mypy for type validation
- **Code Complexity:** Analyzes cyclomatic complexity with radon and xenon
- **Documentation Check:** Verifies essential documentation files exist
- **Docstring Coverage:** Checks Python docstring coverage with interrogate
- **Frontend Quality:** Checks for console.log statements and bundle size

**Duration:** ~5-10 minutes

**How to Run Locally:**

```bash
# Python type checking
cd backend
pip install mypy types-requests
mypy app/ ml/ --ignore-missing-imports

# Code complexity
pip install radon xenon
radon cc app/ ml/ -a
xenon --max-absolute B --max-modules A --max-average A app/ ml/

# Docstring coverage
pip install interrogate
interrogate -vv app/ ml/
```

### 4. Release (`release.yml`)

**Purpose:** Automates the release process including Docker image publishing and GitHub releases.

**Triggers:**
- Push of version tags (e.g., `v1.0.0`)
- Manual trigger via workflow_dispatch

**Jobs:**
- **Validate Release:** Validates version tag format
- **Build and Test:** Runs full test suite before release
- **Build Docker:** Builds and pushes Docker images to registry
- **Generate Changelog:** Creates changelog from git commits
- **Create Release:** Creates GitHub release with notes

**Duration:** ~20-30 minutes

**Required Secrets:**
- `DOCKER_USERNAME`: Docker Hub username
- `DOCKER_PASSWORD`: Docker Hub password/token
- `GITHUB_TOKEN`: Automatically provided by GitHub

**How to Create a Release:**

```bash
# Create and push a version tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# Or use GitHub UI to create a release
```

## 🔧 Configuration

### Caching

All workflows use caching to speed up builds:
- **pip cache:** Python dependencies
- **npm cache:** Node.js dependencies
- **Docker cache:** Docker layer caching with GitHub Actions cache

### Timeouts

Each job has reasonable timeouts to prevent hanging:
- CI jobs: 10-20 minutes
- Security scans: 10 minutes
- Quality checks: 5-10 minutes
- Release: 30 minutes

### Secrets Required

For full functionality, configure these secrets in GitHub repository settings:

| Secret | Required For | Description |
|--------|-------------|-------------|
| `GROQ_API_KEY` | CI Tests | API key for Groq AI service (optional for tests) |
| `DOCKER_USERNAME` | Release | Docker Hub username |
| `DOCKER_PASSWORD` | Release | Docker Hub password or access token |
| `GITHUB_TOKEN` | All | Automatically provided by GitHub |

## 📊 Status Badges

Add these badges to your README.md:

```markdown
![CI Pipeline](https://github.com/USERNAME/tax-buddy/actions/workflows/ci.yml/badge.svg)
![Security Scan](https://github.com/USERNAME/tax-buddy/actions/workflows/security.yml/badge.svg)
![Code Quality](https://github.com/USERNAME/tax-buddy/actions/workflows/quality.yml/badge.svg)
```

Replace `USERNAME` with your GitHub username.

## 🚀 Best Practices

### For Contributors

1. **Before Pushing:**
   - Run tests locally: `pytest` and `npm test`
   - Check linting: `ruff check .` and `npm run lint`
   - Verify build: `npm run build`

2. **Pull Requests:**
   - All CI checks must pass
   - Address any security vulnerabilities
   - Maintain code quality standards
   - Update documentation if needed

3. **Commits:**
   - Use conventional commit messages
   - Keep commits focused and atomic
   - Reference issues in commit messages

### For Maintainers

1. **Merging PRs:**
   - Ensure all workflows pass
   - Review security scan results
   - Check code quality metrics
   - Verify documentation updates

2. **Releases:**
   - Follow semantic versioning (MAJOR.MINOR.PATCH)
   - Update CHANGELOG.md before tagging
   - Test release process in a branch first
   - Verify Docker images are published

3. **Workflow Maintenance:**
   - Keep actions up to date (Dependabot helps)
   - Review and adjust timeouts as needed
   - Monitor workflow execution times
   - Optimize caching strategies

## 🔍 Troubleshooting

### Common Issues

**1. CI Fails on Dependencies**
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

**2. Docker Build Fails**
```bash
# Test locally
docker build -t tax-buddy:test .
docker run -p 8000:8000 tax-buddy:test
```

**3. Security Scan Finds Vulnerabilities**
```bash
# Update dependencies
cd backend && pip install --upgrade -r requirements.txt
cd frontend && npm audit fix
```

**4. Type Checking Fails**
```bash
# Run mypy locally with same config
cd backend
mypy app/ ml/ --ignore-missing-imports --no-strict-optional
```

### Workflow Debugging

Enable debug logging:
1. Go to repository Settings → Secrets
2. Add secret: `ACTIONS_STEP_DEBUG` = `true`
3. Re-run the workflow

View detailed logs:
1. Click on failed workflow run
2. Click on failed job
3. Expand failed step
4. Review error messages and stack traces

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [Security Best Practices](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [Caching Dependencies](https://docs.github.com/en/actions/guides/caching-dependencies-to-speed-up-workflows)

## 🔄 Future Enhancements

Potential workflow improvements:

- [ ] Add E2E testing workflow with Playwright
- [ ] Implement automatic dependency updates with auto-merge
- [ ] Add performance benchmarking workflow
- [ ] Create deployment workflow for staging/production
- [ ] Add visual regression testing
- [ ] Implement automatic changelog generation
- [ ] Add code coverage reporting to PRs
- [ ] Create workflow for generating API documentation

## 📝 Workflow Modification Guide

To add a new workflow:

1. Create a new `.yml` file in `.github/workflows/`
2. Define triggers, jobs, and steps
3. Test locally using [act](https://github.com/nektos/act)
4. Document the workflow in this README
5. Add status badge to main README

Example workflow structure:
```yaml
name: My Workflow
on: [push, pull_request]
jobs:
  my-job:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run my task
        run: echo "Hello World"
```

---

**Last Updated:** 2026-05-13  
**Maintained By:** Tax Buddy Team