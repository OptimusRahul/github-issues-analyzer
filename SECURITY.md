# Security policy

## Reporting a vulnerability

Do not open a public issue for a security problem. Report it privately through [GitHub's private vulnerability reporting](https://github.com/OptimusRahul/github-issues-analyzer/security/advisories/new).

Include what an attacker can do, the steps to reproduce it, and the affected version or commit. You will get a reply within a week.

## Supported versions

Only the latest commit on `master` gets security fixes.

## Scope

Issue triage reads untrusted text: issue titles, bodies and comments written by anyone. Of particular interest:

- prompt injection that makes the tool post, label or answer something it should not
- ways to make the GitHub Action do more than comment on the checked issue, add its label, and open the digest issue
- leaking tokens or API keys into comments, logs or the job summary
