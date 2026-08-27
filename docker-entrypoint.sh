#!/bin/sh
set -e

# O wrapper "pm3" usa /dev/tty0 apenas como sentinela para checar se o processo
# tem privilegio de ler /dev/ttyXXX. Em container (e em LXC) esse node nao
# existe, o que faz o script abortar com "insufficient privileges".
# Criamos o node localmente quando possivel; se falhar, seguimos assim mesmo.
if [ ! -c /dev/tty0 ]; then
    mknod /dev/tty0 c 4 0 2>/dev/null || true
    chmod 600 /dev/tty0 2>/dev/null || true
fi

exec "$@"
