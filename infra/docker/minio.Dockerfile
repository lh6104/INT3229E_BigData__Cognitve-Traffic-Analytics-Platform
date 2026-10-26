# Upstream community registry images are unavailable; build the unchanged pinned
# AGPL source. Keep source and license with the binary for local redistribution.
FROM golang:1.24.8-alpine AS build
ARG MINIO_REVISION=9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a
ARG MINIO_SOURCE_SHA256=45521908307306e925c98d629e1c17d78c8b72b6ee242b1bfb1409f7d8ee5841
RUN apk add --no-cache ca-certificates curl git
WORKDIR /src
RUN curl -fsSL "https://codeload.github.com/minio/minio/tar.gz/${MINIO_REVISION}" -o /source.tar.gz \
    && echo "${MINIO_SOURCE_SHA256}  /source.tar.gz" | sha256sum -c - \
    && tar xzf /source.tar.gz --strip-components=1
ENV CGO_ENABLED=0 GOMAXPROCS=4
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    go build -trimpath -o /minio .

FROM alpine:3.22
RUN apk add --no-cache ca-certificates curl
COPY --from=build /minio /usr/local/bin/minio
COPY --from=build /source.tar.gz /usr/share/minio/source.tar.gz
COPY --from=build /src/LICENSE /usr/share/minio/LICENSE
LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.revision="9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a" \
      org.opencontainers.image.licenses="AGPL-3.0-only"
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
