FROM ghcr.io/astral-sh/uv@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv
FROM python@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates iproute2 && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /uvx /usr/local/bin/
COPY controller.py /controller.py
ENV HOME=/work UV_CACHE_DIR=/work/uv-cache UV_PYTHON_DOWNLOADS=never UV_NO_CONFIG=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /work
USER 1000:1000
ENTRYPOINT []
CMD ["/bin/sleep", "infinity"]
