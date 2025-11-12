# Terraform Variable Drift (pre-commit hook)

## Install
Add to your `.pre-commit-config.yaml`:
```yaml
- repo: https://github.com/devopsonthetrail/terraform-variable-drift-pre-commit
  rev: v0.1.0
  hooks:
    - id: terraform_variable_drift
      pass_filenames: false
      always_run: true
