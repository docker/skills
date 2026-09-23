# Docker Skills documentation style

The `docs/` tree is the human-facing source shared by the edge GitHub Pages site
and, in a later integration, Docker Docs. Agent-facing instructions remain under
`skills/` and must not be copied into this site wholesale.

## Content

- Write direct, task-oriented documentation for people using or contributing
  Docker Skills.
- Use standard YAML front matter with `title`, `canonical`, and optional
  navigation fields such as `weight`.
- Every Markdown content page must declare the canonical URL derived from its
  path under `https://docs.docker.com/ai/skills/`. A branch landing page may be
  named `_index.md`; leaf pages use descriptive filenames.
- Use portable, relative links between Markdown files, including the `.md`
  suffix. Hugo's render hook resolves them for the edge site.
- Use absolute URLs only for destinations outside this documentation tree.
- Keep every top-level content branch mounted in `docs/hugo.yaml` and listed in
  the primary navigation in `layouts/_default/baseof.html`. Branch leaf pages
  appear in `llms.txt` but do not each require a top-level navigation entry.
- Write catalog skill IDs in backticks. `task docs:check` rejects stale
  backticked `docker-<id>` references while allowing catalog product IDs and
  documented non-skill names.
- Keep catalog and distribution inventories between their generated markers;
  both come from `catalog.yaml`. Run `task catalog` after catalog, distribution,
  or skill-description changes.
- Installation model pages must include `Basic install`, `Advanced install`,
  `Update, pin, and scope`, `Verification`, `Troubleshooting`, and `Related
  links` sections. Do not elevate one model over its peers or publish vendor
  commands that have not been checked against current vendor documentation.

## Validation and preview

Run `task docs:check` to lint Markdown, verify canonical URLs, navigation,
portable links, and catalog skill references, build the site, and check the
generated `llms.txt`. Run `task docs:serve` to preview the site at
`http://localhost:1313/skills/`.
