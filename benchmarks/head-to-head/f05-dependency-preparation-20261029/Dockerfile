FROM dotrepo-f05-rust-deps@sha256:6d94650b0063dbbe7921114ee693dcf24c4c279d0e15781ae1713c88e69e167d AS rust
FROM dotrepo-f05-node-go-uv@sha256:9f07b849c4603e3ad6b52c00c2dccaaf2054f8b3ec0f4add866ffdd537073c76 AS tools
FROM scratch
COPY --from=rust / /
COPY --from=tools /usr/local/go /usr/local/go
COPY --from=tools /usr/local/bin/node /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/
COPY --from=tools /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=tools /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/
ENV PATH=/usr/local/cargo/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo GOTOOLCHAIN=local GOENV=off
USER 1000:1000
WORKDIR /
ENTRYPOINT ["/bin/sh"]
CMD ["-c", "while :; do sleep 3600; done"]
