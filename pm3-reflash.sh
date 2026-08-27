#!/bin/sh
# Regrava o Proxmark3 com o firmware da MESMA versao do cliente embarcado
# nesta imagem, resolvendo o erro:
#   "Capabilities structure version sent by Proxmark3 is not the same
#    as the one used by the client!"
#
# Uso (dentro do container):
#   pm3-reflash
#
# O aparelho reinicia sozinho ao final. Nao desconecte durante o processo.
set -e

FW_DIR=/usr/local/share/proxmark3/firmware
PM3_TTY="${PM3_TTY:-/dev/ttyACM0}"

if [ ! -c "$PM3_TTY" ]; then
    echo "[erro] device $PM3_TTY nao encontrado no container." >&2
    exit 1
fi

if [ ! -f "$FW_DIR/fullimage.elf" ]; then
    echo "[erro] firmware nao encontrado em $FW_DIR." >&2
    exit 1
fi

echo "[*] Regravando bootrom + fullimage em $PM3_TTY"
echo "[*] NAO desconecte o aparelho ate terminar."

pm3-flash-all --port "$PM3_TTY" 2>/dev/null && exit 0

# Fallback: chama o cliente diretamente caso o wrapper nao aceite --port
proxmark3 "$PM3_TTY" --flash \
    --unlock-bootloader \
    --image "$FW_DIR/bootrom.elf" \
    --image "$FW_DIR/fullimage.elf"
