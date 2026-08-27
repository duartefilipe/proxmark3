#!/bin/sh
set -e

# Device serial do Proxmark3 dentro do container.
# Tambem e usado como sentinela pelo wrapper pm3 (ver patch no Dockerfile).
PM3_TTY="${PM3_TTY:-/dev/ttyACM0}"
export PM3_TTY

if [ ! -c "$PM3_TTY" ]; then
    echo "[aviso] device $PM3_TTY nao encontrado no container." >&2
    echo "[aviso] confira o passthrough USB do host ate o Docker." >&2
elif [ ! -r "$PM3_TTY" ] || [ ! -w "$PM3_TTY" ]; then
    echo "[aviso] sem permissao de leitura/escrita em $PM3_TTY." >&2
fi

exec "$@"
