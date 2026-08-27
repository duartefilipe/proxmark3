# ---------- Stage 1: compila o cliente Proxmark3 (Iceman fork) ----------
FROM debian:bookworm-slim AS builder

ARG PM3_REPO=https://github.com/RfidResearchGroup/proxmark3.git
ARG PM3_REF=master

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        ca-certificates \
        build-essential \
        pkg-config \
        libreadline-dev \
        libssl-dev \
        libbz2-dev \
        liblz4-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 --branch "${PM3_REF}" "${PM3_REPO}" .

# Cliente apenas (sem Qt, Bluetooth, Python e GD) para reduzir dependencias.
# Nao usamos "make install" pois ele tenta instalar o firmware (bootrom/armsrc),
# que exigiria o toolchain arm-none-eabi.
# client/install  -> binario proxmark3 + resources
# common/install  -> scripts de apoio, incluindo o wrapper "pm3"
RUN make client -j"$(nproc)" SKIPQT=1 SKIPBT=1 SKIPPYTHON=1 SKIPGD=1 \
    && make client/install common/install PREFIX=/usr/local DESTDIR=/out \
        SKIPQT=1 SKIPBT=1 SKIPPYTHON=1 SKIPGD=1


# ---------- Stage 2: imagem final com o painel web ----------
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-psycopg2 \
        bash \
        libreadline8 \
        libssl3 \
        libbz2-1.0 \
        liblz4-1 \
        procps \
    && rm -rf /var/lib/apt/lists/*

# Cliente pm3 compilado no stage anterior
COPY --from=builder /out/usr/local /usr/local

WORKDIR /app
COPY server.py ./
COPY public/ ./public/

ENV PM3_HOST=0.0.0.0 \
    PM3_PORT=8787

EXPOSE 8787

CMD ["python3", "server.py"]
