# Basira - Privacy

Plain-English version. Last updated 2026-05-19, v0.1.0.

## What this is

Basira is open source and self-hostable. If you're using a deployment
that someone else runs, ask them for *their* privacy notice - this
document only covers what Basira itself collects and stores.

## What we store

When you sign in with GitHub, we store:
- Your GitHub user ID, login, avatar URL, and email (or a noreply alias
  if your email is private)
- A Fernet-encrypted copy of the OAuth access token GitHub gave us, so
  we can call the API on your behalf

When you install the App on a repo, we store:
- The installation ID and the list of repos covered by it
- For each repo: name, default branch, whether it's private, plus the
  per-repo settings you configured (severity threshold, ignored paths,
  custom rules, scan schedule)

When you run a scan, we store:
- A scan record with the commit SHA, model used, token counts, and
  per-file findings
- Findings (file, line, severity, category, message, suggestion)

When you configure notifications, we store:
- For email: your SMTP host, port, username, "from" address, and a
  Fernet-encrypted copy of the SMTP password
- For Slack / Discord: a Fernet-encrypted copy of the webhook URL

That's it. We don't run analytics, we don't fingerprint, we don't drop
third-party tracking cookies.

## What we send to third parties

- **Anthropic (Claude)** - your repository's source code, only at scan
  time, only the files you didn't ignore, only inside the request body
  for the scan call. Anthropic's data policy applies to that call. The
  request body is **not** persisted by us.
- **GitHub** - same access GitHub already grants the App you installed:
  read repo contents, read/write pull requests, write commit statuses.
- **Slack / Discord** - only if you configured a webhook. We post a
  short summary message (repo name, score, findings count, link to the
  scan report).

We do **not** sell, lease, or share any of the above with anyone else.

## How long we keep it

For as long as your account exists. Closing your account (see below)
purges everything within 7 days.

## Your rights

You can:
- **View** what we hold about you: it's all visible in the dashboard.
- **Export** your scan history as Markdown from any scan page.
- **Delete** your account: contact the operator of the Basira instance
  you're using. For self-hosters, that means `DELETE FROM users WHERE
  github_login='you'` cascades through every other table.
- **Revoke our GitHub access** at any time from
  [github.com/settings/applications](https://github.com/settings/applications).

If you're in a jurisdiction with stronger rules (GDPR, Saudi PDPL, etc.)
those apply on top - file a request and we'll honor it.

## Security

See [`SECURITY.md`](./SECURITY.md) for how to report a vulnerability.

## Changes to this policy

Any change is recorded in the git history of this file. The "Last updated"
line at the top changes with each material edit.
