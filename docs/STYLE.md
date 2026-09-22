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
  path under `https://docs.docker.com/ai/skills/`.
- Use portable, relative links between Markdown files, including the `.md`
  suffix. Hugo's render hook resolves them for the edge site.
- Use absolute URLs only for destinations outside this documentation tree.
- Keep the catalog between `catalog-start` and `catalog-end` generated from
  `catalog.yaml`; run `task catalog` after catalog or skill-description changes.

## Validation and preview

Run `task docs:check` to lint Markdown, verify canonical URLs, build the site,
and check the generated `llms.txt`. Run `task docs:serve` to preview the site at
`http://localhost:1313/skills/`.
