# Proxmark Web Console

Painel web local para executar comandos em background e visualizar logs em tempo real.

## Como iniciar

1. Entre na pasta:
  - `cd /Users/anakin/Documents/Anakin/ProxmarkWebConsole`
2. Rode o servidor:
  - `python3 server.py`
3. Abra no navegador:
  - `http://127.0.0.1:8787`

## Uso com Proxmark

- Se o executavel `pm3` estiver nesta pasta, voce pode usar:
  - `./pm3 -h`
  - `./pm3 /dev/tty.usbmodem*`
- Para descobrir a porta serial no macOS, use:
  - `ls /dev/tty.*`

## Instalacao no hardware Proxmark (concluida neste setup)

Instalado localmente em:

- `ProxmarkWebConsole/proxmark3` (codigo-fonte + cliente + firmware)
- `ProxmarkWebConsole/toolchains` (toolchain ARM local)

Porta detectada durante a instalacao:

- `/dev/tty.usbmodem401`

Comandos prontos para uso:

- Abrir cliente PM3:
  - `cd /Users/anakin/Documents/Anakin/ProxmarkWebConsole/proxmark3`
  - `./iniciar-proxmark.sh`
- Recompilar e reflashear:
  - `./rebuild-flash.sh`

Validacao executada com sucesso:

- `hw version`
- `hw status`

## PostgreSQL para historico de leituras

Use a stack pronta no Portainer:

- arquivo: `ProxmarkWebConsole/portainer-stack-postgres.yml`

Passos no Portainer:

1. `Stacks` -> `Add stack`
2. Nome sugerido: `proxmark-postgres`
3. Cole o conteudo de `portainer-stack-postgres.yml`
4. Troque `POSTGRES_PASSWORD`
5. Deploy

Depois, rode o painel com variaveis do banco:

```bash
cd /Users/anakin/Documents/Anakin/ProxmarkWebConsole
export PM3_PGHOST=192.168.31.229
export PM3_PGPORT=5433
export PM3_PGDATABASE=proxmark
export PM3_PGUSER=proxmark
export PM3_PGPASSWORD=troque_essa_senha_forte
python3 server.py
```

No painel, use:

- `HF Search` ou `LF Search`
- depois clique em `Salvar ultima leitura no PostgreSQL`
- clique em `Atualizar historico` para listar as leituras salvas

## Comandos úteis para leitura e clonagem (LF - 125 kHz)

### Leitura de tags
- `lf search` → Detecta automaticamente qualquer tag LF.
- `lf em 410x read` → Leitura específica para tags EM410x.
- `lf t55xx dump` → Lê toda a memória do chip T55xx.

### Clonagem (tag original → tag virgem T5577)
- `lf em 410x clone --id <ID>` → Clona uma tag EM410x.
- Exemplo: `lf em 410x clone --id 1A0091F2E4`

### Verificação da tag clonada
- `lf em 410x read` → Confere se o ID foi gravado corretamente.

## Central de Comandos

| Comando | Para que serve |
|---------|----------------|
| `lf search` | Descobrir qualquer tag LF |
| `lf em 410x read` | Ler tag EM410x |
| `lf em 410x clone --id 1A0091F2E4` | Clonar tag da casa atual |
| `lf em 410x clone --id 007218C7F8` | Clonar tag da casa antiga |
| `lf em 410x read` | Verificar clonagem |
