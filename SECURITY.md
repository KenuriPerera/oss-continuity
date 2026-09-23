# Security Policy

Please report vulnerabilities **privately** using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
("Report a vulnerability" on the repository's *Security* tab). Do not open a public issue.

You can expect an acknowledgement within 7 days. Only the latest release receives fixes.

Relevant areas: the tool reads untrusted repository content and, when `GITHUB_TOKEN` is set,
sends that token only to `api.github.com` and `raw.githubusercontent.com`.
