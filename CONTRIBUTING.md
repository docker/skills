# Contributing to Docker Skills

Thank you for your interest in contributing! This repository contains Docker-authored knowledge skills for AI coding agents. Issues, bug fixes, new skills, and improvements to existing skills are all welcome.

## Reporting issues

A great way to contribute is to send a detailed issue when you encounter a
problem. Before opening a new issue, check
[the issue database](https://github.com/docker/skills/issues) to see if your
problem or suggestion has already been reported.

## Submitting changes

1. Fork the repository.
2. Create a feature branch from `main`.
3. Make your changes.
   - When adding a new skill, place it under `skills/<skill-id>/` with a
     `SKILL.md` and any supporting files. Follow the structure of existing
     skills and update `catalog.yaml` accordingly.
   - When updating an existing skill, keep the `SKILL.md` frontmatter and
     section structure consistent with the rest of the repo.
4. Run the complete validation suite locally (requires
   [Task](https://taskfile.dev/) and Docker):
   ```bash
   task
   ```
5. Commit your changes with a `Signed-off-by` line (see *Sign your work* below).
6. Open a pull request and fill out the template.

## Sign your work

The sign-off is a simple line at the end of the explanation for the patch. Your
signature certifies that you wrote the patch or otherwise have the right to pass
it on as an open-source patch. The rules are pretty simple: if you can certify
the below (from [developercertificate.org](https://developercertificate.org)):

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
660 York Street, Suite 102,
San Francisco, CA 94110 USA

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

Then you just add a line to every git commit message:

    Signed-off-by: Joe Smith <joe.smith@email.com>

Use your real name (sorry, no pseudonyms or anonymous contributions.)

If you set your `user.name` and `user.email` git configs, you can sign your
commit automatically with `git commit -s`.
