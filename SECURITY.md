# Security policy

## Reporting a vulnerability

If you think you've found a security issue, please **do not** open a public
GitHub issue. Instead:

- Use [GitHub Security Advisories](https://github.com/2lba/basira/security/advisories/new)
  to file a private report, or
- Email `security@` the maintainer (see the address on the
  [@2lba GitHub profile](https://github.com/2lba)).

Include:
- A description of the issue and its impact
- Steps to reproduce
- Any logs or proof-of-concept code

I aim to respond within **3 working days**. Critical issues get a fix in
the next minor release; high/medium are batched into the next planned
release; low/info goes into the backlog.

Basira does **not** run a paid bug bounty. Public credit in the
CHANGELOG is offered to anyone who reports a valid issue and is happy to
be named.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | yes (active dev) |
| < 0.1   | no |

## Scope

In scope:
- Basira's backend (`backend/`) and frontend (`frontend/`)
- Auth flows (OAuth + session)
- Webhook handling
- Scan engine + Anthropic prompt path
- Per-user data isolation (IDOR)

Out of scope:
- Issues that require physical access to the deploy server
- Self-XSS on a victim's own machine
- Findings produced by Claude that turn out to be wrong (those are model
  quality issues, file them as regular bugs)
- Anything in third-party services we depend on (GitHub, Anthropic) —
  please report those upstream

## What we've already audited

See `docs/security/threat-model.md` and `docs/security/owasp-audit.md` for
the current threat model and OWASP 2021 coverage. If your finding overlaps
with a known item documented there, that's fine — we'd still rather know.
