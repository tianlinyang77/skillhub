# Security

Do not report vulnerabilities or sensitive reproductions in public issues.
Before production publication, maintainers must enable Private Vulnerability
Reporting as required by the
[repository settings baseline](docs/governance/repository-settings.md). Once it
is enabled, use **Security → Report a vulnerability**. Until then, this preview
does not advertise a verified public intake address; contact a repository
maintainer through an approved private HYGON-AI channel before sharing details.

Include the affected Skill, source and catalog commits, impact, and a minimal
reproduction with secrets and customer data removed.

Skills can contain executable scripts and operational instructions. Review source ownership, requested permissions, dependencies, and scripts before installation. Revoke exposed credentials immediately; removing them from Git history is not sufficient.

Security fixes are supported on the current `main` branch. A published Skill
with an unresolved exploitable instruction, dependency, or script is removed
from generated indexes until its owning team supplies a reviewed correction.
