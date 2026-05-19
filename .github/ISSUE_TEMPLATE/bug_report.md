---
name: Bug report
about: Something is broken in Basira
labels: bug
---

## What happened

<!-- One or two sentences. What were you doing and what went wrong? -->

## Reproducing it

1.
2.
3.

## Expected behaviour

<!-- What did you expect to happen instead? -->

## Logs / error output

<details>
<summary>backend logs (paste with redacted secrets)</summary>

```
docker compose logs backend --tail=200
```

</details>

## Environment

- Basira version: <!-- /version endpoint or git SHA -->
- Deploy: docker compose / kubernetes / other
- Browser (if frontend bug):
- OS:

## Checklist

- [ ] I redacted secrets (tokens, API keys) from any pasted logs
- [ ] I searched existing issues for duplicates
- [ ] If this is a security issue, I am using
      https://github.com/2lba/basira/security/advisories/new instead
