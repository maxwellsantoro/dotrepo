# A control image, not a task environment. Preserve the pinned dependency
# filesystem while starting with a minimal, allowlisted image configuration.
FROM python:3.14.4-slim@sha256:2ca02f32b4d9d893863367ce07ec1972819f476dd38d8612f2a9cb6a41cbb727 AS dependency
FROM scratch
COPY --from=dependency / /
ENV PATH=/usr/local/bin:/usr/bin:/bin
