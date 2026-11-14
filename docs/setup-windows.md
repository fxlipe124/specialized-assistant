# Instalação no Windows, passo a passo

Roteiro conferido numa máquina Windows 11 em novembro de 2026, com Claude Code, plugin
`telegram@claude-plugins-official` 0.0.7, bun 1.4.4, ffmpeg 9.0 e VoiceStudio 0.5.7.
Os comandos são para o **CMD** (Prompt de Comando).

Toda citação `server.ts:N` é do plugin instalado, em
`%USERPROFILE%\.claude\plugins\marketplaces\claude-plugins-official\external_plugins\telegram\`.

---

## 1. Dependências

| Peça | Para quê | Como instalar |
|---|---|---|
| bun | roda o servidor MCP do plugin (o `.mcp.json` chama `bun run ... start`) | `npm install -g bun` |
| ffmpeg | converte o mp3 do VoiceStudio para OGG/Opus, o único formato que o Telegram mostra como mensagem de voz | `winget install -e --id Gyan.FFmpeg` |
| Python 3.10+ | roda `telegram_voz.py` (só biblioteca padrão) | python.org ou `winget install Python.Python.3.12` |
| VoiceStudio | transcrição e voz locais, API compatível com a da OpenAI em `127.0.0.1:3900` | instalador do próprio app |

Processo já aberto não relê o PATH: depois de instalar o ffmpeg, abra um terminal novo.

---

## 2. Bot e token

1. No Telegram, fale com o **@BotFather**, mande `/newbot` e escolha um username terminado
   em `bot`.
2. Grave o token **sem CRLF** no fim da linha:

   ```cmd
   <nul set /p "=TELEGRAM_BOT_TOKEN=<seu token>" > "%USERPROFILE%\.claude\channels\telegram\.env"
   ```

Por que assim e não pelo Bloco de Notas: o plugin lê o `.env` com `split('\n')` e a regex
`^(\w+)=(.*)$` (`server.ts:38-39`). Com CRLF, o `\r` que sobra no fim da linha faz a regex
falhar, e o servidor sai com `TELEGRAM_BOT_TOKEN required`.

Uma variável de ambiente `TELEGRAM_BOT_TOKEN` vence o `.env` (`server.ts:33`, "Real env
wins"). Se houver uma no Windows apontando para outro bot, a sessão faz polling no bot
errado. O `iniciar.cmd` zera a variável antes de abrir o Claude justamente por isso.

O `chmod 600` que o plugin aplica no `.env` não tem efeito no Windows (`server.ts:36`).

---

## 3. Plugin ligado só numa sessão

O Telegram aceita **um** consumidor de `getUpdates` por token. Ao subir, o servidor mata o
poller anterior que encontrar em `bot.pid` (`server.ts:56-78`). Com o plugin ligado no
`settings.json` global, cada sessão do Claude aberta sobe um servidor, e eles passam a
disputar o bot.

Por isso:

- no `%USERPROFILE%\.claude\settings.json` global, `"telegram@claude-plugins-official": false`;
- o `iniciar.cmd` liga o plugin só na sessão dele, com
  `--settings ...\settings-sessao.json`.

Desligar o plugin no global não derruba servidor de sessão que já estava aberta: feche
essas sessões.

O mesmo `settings-sessao.json` traz os hooks do "digitando" e a permissão do
`claude_sessoes.py`, com caminhos em `~/.claude/scripts/`. Testado em 14/11/2026, no Claude
Code 2.1.325: os hooks ligaram o "digitando", que se renovou a cada 4 s, e o `Stop` o
desligou. A regra de permissão liberou o comando numa sessão em `--permission-mode default`;
sem a regra, o mesmo comando foi negado.

---

## 4. Parear e trancar

1. Copie o modelo, que já vem em pareamento e com a reação 👀 ao receber:
   ```cmd
   copy channel\access.example.json "%USERPROFILE%\.claude\channels\telegram\access.json"
   ```
   Sem o arquivo, o plugin também começa em pareamento, só que sem a reação.
2. Rode `iniciar.cmd`.
3. Mande uma DM ao bot. Ele responde com um código de 6 caracteres.
4. No terminal da sessão: `/telegram:access pair <codigo>`.
5. Trancar: `/telegram:access policy allowlist`. Daí em diante, quem não está na lista é
   ignorado em silêncio.

A skill `access` só aceita comando digitado no terminal, nunca um pedido que chegou pelo
próprio Telegram: mensagem de canal pode carregar injeção de prompt.

Ajustes opcionais em `access.json` (`server.ts:118-125`): `ackReaction` (reação automática ao
receber, `server.ts:958`), `replyToMode` (`off`, `first`, `all`), `textChunkLimit` e
`chunkMode` (`newline` quebra mensagens longas em parágrafo).

---

## 5. VoiceStudio

1. Abra o app e espere o motor local subir. Na primeira vez ele prepara o ambiente Python,
   e isso leva minutos. Nas seguintes, cerca de 3 minutos até a API responder `200`.
2. Confira:

   ```cmd
   curl -s -o NUL -w "%{http_code}" http://127.0.0.1:3900/v1/models
   ```

   `503` com `[starting]` no corpo quer dizer que ainda está subindo.
3. Transcrição: o motor padrão pode apontar para o Whisper large-v3 completo, que não vem
   baixado. O Turbo resolveu:

   ```cmd
   curl -s -X POST http://127.0.0.1:3900/engines/select -H "Content-Type: application/json" -d "{\"family\":\"asr\",\"backend_id\":\"faster-whisper\",\"model_id\":\"deepdml/faster-whisper-large-v3-turbo-ct2\"}"
   ```

4. Voz: `python -I %USERPROFILE%\.claude\scripts\telegram_voz.py vozes` lista as vozes, e
   `... telegram_voz.py voz <voice_id> [modelo]` escolhe uma.

Licença: a voz OmniVoice é CC-BY-NC (uso não comercial). Confira a licença do modelo que
você escolher antes de usar a voz fora do uso pessoal.

---

## 6. Problemas conhecidos

### "Não foi possível iniciar o motor local. spawn UNKNOWN"

O Windows (Smart App Control / Application Control) passou a barrar o lançador `python.exe`
que o `uv` gravou no `.venv` do VoiceStudio. O sintoma de linha de comando é `Permission
denied` ao executar esse arquivo, enquanto o Python base do runtime roda normal.

Conserto: trocar os dois lançadores do `.venv` pelos lançadores padrão do próprio Python do
runtime, guardando os originais. Com o VoiceStudio aberto na tela de erro:

```cmd
set "RT=%APPDATA%\VoiceStudio\runtime"
mkdir "%USERPROFILE%\quarentena-voicestudio"
copy "%RT%\project\.venv\Scripts\python.exe" "%USERPROFILE%\quarentena-voicestudio\"
copy "%RT%\project\.venv\Scripts\pythonw.exe" "%USERPROFILE%\quarentena-voicestudio\"
for /d %D in ("%RT%\.python\cpython-3.11.*-windows-x86_64-none") do copy /y "%D\Lib\venv\scripts\nt\python*.exe" "%RT%\project\.venv\Scripts\"
"%RT%\project\.venv\Scripts\python.exe" -c "import sys, uvicorn; print(sys.prefix)"
```

A última linha deve imprimir o caminho do `.venv`. Depois, clique em **Tente novamente** no
app. Uma atualização ou um reparo do runtime pode recriar o lançador do `uv`; se o erro
voltar, repita.

### O bot não responde

- A sessão foi aberta pelo `iniciar.cmd`? Sem `--channels`, o servidor não sobe.
- `bun --version` funciona nesse terminal?
- O `.env` tem CRLF? Regrave com o comando da seção 2.
- Há outra sessão com o plugin ligado disputando o polling?

### O áudio chega, mas a resposta sai só em texto

O script de voz falhou: quase sempre o VoiceStudio está fechado ou ainda subindo. Teste com
o `curl` da seção 5.

---

## 7. Limites do canal

- Sem histórico: a Bot API não busca mensagens antigas, a sessão só vê o que chega enquanto
  está aberta.
- O bot só responde com a sessão viva; fechou o terminal, parou.
- Anexo: 20 MB para baixar e 50 MB para enviar (`MAX_ATTACHMENT_BYTES`, `server.ts:138`).
- O `reply` recusa anexar arquivo da pasta do canal, exceto o que está em `inbox\`
  (`assertSendable`, `server.ts:144-156`): o `.env` nunca sai pelo bot.
