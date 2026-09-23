---
title: Extensions
canonical: https://docs.docker.com/ai/skills/install/extensions/
weight: 12
---

# Extensions

Use an extension when the client natively installs a repository as an extension
rather than as a marketplace plugin.

## Basic install

### Gemini CLI extension

The Gemini CLI documentation supports installing an extension from a Git URL:

```console
gemini extensions install https://github.com/docker/skills
```

Restart Gemini CLI after installation so the extension and its skills are
rediscovered.

## Advanced install

Use Gemini CLI's documented extension-management options when you need a local
checkout or an organization-managed source. Keep the complete repository
structure intact; the root `gemini-extension.json` describes the extension and
the skill directories contain referenced supporting files.

## Update, pin, and scope

Gemini CLI owns extension updates and the scope exposed by the installed client
version. The repository URL follows its selected upstream revision and is not an
immutable release pin. For a reviewed snapshot, use a tagged Git checkout as
described in [Sources and fallback](sources.md#git-clone-or-manual-copy), then
follow Gemini CLI's current local-extension instructions.

## Verification

Use Gemini CLI's extension listing interface to confirm `docker-skills` is
installed, then start a new session and ask for a matching Docker task. Confirm
that the expected skill appears before relying on it in automation.

## Troubleshooting

- If installation fails, verify GitHub access and retry with the exact HTTPS URL.
- If no skill appears, restart the client and confirm the extension is enabled.
- If an organization policy blocks remote extensions, use an approved local
  checkout or the [skills CLI](skills-cli.md).
- Update through Gemini CLI; `npx skills update` does not manage extensions.

## Related links

- [Install Docker Skills](./_index.md)
- [Gemini CLI extensions](https://geminicli.com/docs/extensions/)
- [skills CLI](skills-cli.md)
- [Sources and fallback](sources.md)
