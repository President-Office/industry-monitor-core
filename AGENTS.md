# Agent Instructions

This is a public, domain-neutral Python package shared by business-unit
industry monitors.

- Never add source registries, company lists, customer data, credentials,
  notification targets, raw pages, databases, or business-specific report
  wording.
- Keep the package focused on reusable adapters, validation, and bounded data
  normalization.
- Add or update unit tests for behavior changes.
- Run `python -m unittest discover -s tests -v` and `git diff --check`.
- Business repositories own their domain configuration, publication policy,
  and deployment secrets.
