# syntax=docker/dockerfile:1
# Custom sbx sandbox template that extends the default Claude template with
# extra developer tooling not bundled in the base image (fd-find, hyperfine).
#
# Build, push to a registry the host can pull from, then provision a sandbox
# that uses this template:
#
#   docker build -t my-registry.example.com/sbx/claude-plus:1.0 \
#       -f custom-template.Dockerfile .
#   docker push my-registry.example.com/sbx/claude-plus:1.0
#   sbx create claude . --template my-registry.example.com/sbx/claude-plus:1.0
#
# Pin to a specific version tag (or digest) so sandbox provisioning is
# reproducible. The bare `claude-code-docker` tag is a floating "stable" tag
# and must not be used as the base of a custom template. Substitute the real
# version available in your registry. See references/templates.md.
ARG BASE=docker/sandbox-templates:claude-code-docker-0.1.0
FROM ${BASE}

# BEFORE adding tools here, check what the base image already ships. As of
# v0.1.0, `claude-code-docker` already includes: git, gh, jq, ripgrep, less,
# lsof, make, rsync, unzip, openssh-client, dnsutils, socat, tini, sudo,
# docker-ce-cli, docker-buildx-plugin, docker-compose-plugin, bubblewrap,
# procps, psmisc. Installing them again wastes build time, bloats the layer,
# and risks downgrading what the base curated. Verify with:
#   docker run --rm docker/sandbox-templates:claude-code-docker-<version> \
#     bash -c 'command -v <tool> || dpkg -l <pkg>'
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fd-find \
        hyperfine && \
    rm -rf /var/lib/apt/lists/*

# Do not override ENTRYPOINT, CMD, or USER here: the agent kit installs the
# right defaults for Claude. Custom templates layer tooling on top, not policy.
