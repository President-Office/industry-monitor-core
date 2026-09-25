# Industry Monitor Core

Shared, domain-neutral building blocks for business-unit industry monitors.

This package contains no source registries, company lists, credentials, report
titles, or business-unit data. A domain project owns its own configuration and
public-report policy.

Current shared capability:

- reviewed AKShare ETF history adapter
- bounded normalization of public daily market rows
- configurable ETF observation registry validation

The package deliberately does not decide whether an ETF is relevant to a
business domain, make investment recommendations, or publish a report.
