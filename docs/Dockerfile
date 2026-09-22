# syntax=docker/dockerfile:1

FROM debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251

ARG HUGO_VERSION=0.163.0
ARG TARGETARCH
ARG HUGO_SHA256_AMD64=6291775b7d012f9b10fb377ba914e5b1589c0b0d2531b695fa9029be14750111
ARG HUGO_SHA256_ARM64=ed50d3ec8c5b427013137e38718a5d398a90956ce9e3a8a3cb7ebf3fdd01072b

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl \
    && case "$TARGETARCH" in \
         amd64) checksum="$HUGO_SHA256_AMD64" ;; \
         arm64) checksum="$HUGO_SHA256_ARM64" ;; \
         *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && curl -fsSLo /tmp/hugo.tar.gz "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-${TARGETARCH}.tar.gz" \
    && echo "${checksum}  /tmp/hugo.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/hugo.tar.gz -C /usr/local/bin hugo \
    && rm -rf /var/lib/apt/lists/* /tmp/hugo.tar.gz

WORKDIR /src
EXPOSE 1313
CMD ["hugo", "server", "--bind", "0.0.0.0"]
