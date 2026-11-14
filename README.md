<div align="center">

# specialized-assistant

**Converse com o Claude Code pelo Telegram, por texto ou por voz, com transcrição e fala rodando na sua máquina.**

![Windows](https://img.shields.io/badge/Windows-11-0078D4?logo=windows&logoColor=white)
![Claude Code](https://img.shields.io/badge/Claude_Code-channels-D97757)
![Telegram](https://img.shields.io/badge/Telegram-bot-26A5E4?logo=telegram&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10%2B_stdlib-3776AB?logo=python&logoColor=white)

</div>

---

Você manda um áudio no Telegram. O Claude Code transcreve, trabalha no seu computador e
responde duas vezes: um texto completo, com código, links e caminhos, e um áudio curto com o
essencial. A voz e a transcrição rodam localmente no [VoiceStudio](#voicestudio): nenhum
áudio sai da máquina, e não há chave de API de voz para pagar.

## Como funciona

```mermaid
flowchart LR
    U["📱 Você no Telegram"] -- "texto, foto ou áudio" --> B["Bot API"]
    B -- "long polling" --> S["Plugin telegram<br/>(servidor MCP em bun)"]
    S -- "&lt;channel&gt;" --> C["Sessão do Claude Code<br/>aberta pelo iniciar.cmd"]
    C -- "transcrever" --> V["VoiceStudio<br/>127.0.0.1:3900"]
    C -- "falar" --> V
    V -- "mp3" --> F["ffmpeg → OGG/Opus"]
    C -- "reply (texto)" --> S
    F -- "sendVoice" --> B
    B --> U
```

1. O plugin oficial `telegram@claude-plugins-official` recebe a mensagem e a entrega à sessão.
2. Se for áudio, a sessão baixa o arquivo e chama `telegram_voz.py transcrever`, que manda o
   áudio ao Whisper do VoiceStudio.
3. A resposta sai em texto pela ferramenta `reply` e, logo depois, em áudio por
   `telegram_voz.py falar`: o VoiceStudio sintetiza em mp3, o ffmpeg converte para
   OGG/Opus, e o script envia como mensagem de voz nativa.

As regras de comportamento (sempre texto e áudio, áudio curto e sem markdown, avisar antes
de trabalho longo) ficam em [`channel/instrucoes-voz.md`](channel/instrucoes-voz.md) e
entram na sessão por `--append-system-prompt-file`.

## O que tem aqui

| Arquivo | Vai para | Papel |
|---|---|---|
| [`channel/iniciar.cmd`](channel/iniciar.cmd) | `%USERPROFILE%\.claude\channels\telegram\` | Abre a sessão com o canal, o plugin e as instruções de voz |
| [`channel/settings-sessao.json`](channel/settings-sessao.json) | idem | Liga o plugin só nesta sessão |
| [`channel/instrucoes-voz.md`](channel/instrucoes-voz.md) | idem | Regras da sessão: como receber e responder em voz |
| [`channel/.env.example`](channel/.env.example) | idem, como `.env` | Modelo do arquivo do token do bot |
| [`scripts/telegram_voz.py`](scripts/telegram_voz.py) | `%USERPROFILE%\.claude\scripts\` | Transcreve, sintetiza e envia voz; só biblioteca padrão |
| [`docs/setup-windows.md`](docs/setup-windows.md) | | Instalação passo a passo e problemas conhecidos |
| [`docs/originais/`](docs/originais/) | | Guia genérico em inglês que serviu de ponto de partida |

## Instalação rápida

Pré-requisitos: [Claude Code](https://docs.claude.com/en/docs/claude-code), bun, ffmpeg,
Python 3.10+ e o VoiceStudio. Os detalhes de cada passo estão em
[`docs/setup-windows.md`](docs/setup-windows.md). No CMD, de dentro do clone:

```cmd
mkdir "%USERPROFILE%\.claude\channels\telegram" "%USERPROFILE%\.claude\scripts"
copy channel\iniciar.cmd channel\settings-sessao.json channel\instrucoes-voz.md "%USERPROFILE%\.claude\channels\telegram\"
copy scripts\telegram_voz.py "%USERPROFILE%\.claude\scripts\"
python -I "%USERPROFILE%\.claude\scripts\telegram_voz.py" --demo
```

Depois:

1. **Plugin**: numa sessão do Claude Code, `/plugin install telegram@claude-plugins-official`.
   No `settings.json` global, deixe-o `false`; quem liga é o `iniciar.cmd`.
2. **Token**: crie o bot no @BotFather e grave o `.env` **sem CRLF**:
   ```cmd
   <nul set /p "=TELEGRAM_BOT_TOKEN=<seu token>" > "%USERPROFILE%\.claude\channels\telegram\.env"
   ```
3. **Pasta de trabalho**: edite `PASTA_DE_TRABALHO` no `iniciar.cmd`.
4. **VoiceStudio**: abra o app e espere a API responder em `http://127.0.0.1:3900`.
5. **Rode** `iniciar.cmd`, mande uma DM ao bot e pareie com `/telegram:access pair <codigo>`.
   Tranque com `/telegram:access policy allowlist`.

## O script de voz

```text
telegram_voz.py transcrever <arquivo>        imprime o texto do áudio
telegram_voz.py falar <chat_id> [reply_to]   lê o texto do stdin e manda como mensagem de voz
telegram_voz.py amostra <arquivo.ogg>        lê o texto do stdin e grava o áudio, sem Telegram
telegram_voz.py vozes                        lista as vozes do VoiceStudio
telegram_voz.py voz <voice_id> [modelo]      escolhe a voz
telegram_voz.py modo <chat_id> [texto|audio] lê ou troca o modo de resposta do chat
telegram_voz.py --demo                       auto-check, sem rede
```

| Variável | Padrão | Para quê |
|---|---|---|
| `VOICESTUDIO_URL` | `http://127.0.0.1:3900` | Onde está a API do VoiceStudio |
| `TELEGRAM_VOZ_IDIOMA` | `pt` | Idioma da transcrição e da fala |
| `TELEGRAM_STATE_DIR` | `%USERPROFILE%\.claude\channels\telegram` | Pasta do canal, a mesma variável que o plugin usa |
| `TELEGRAM_BOT_TOKEN` | lido do `.env` | Token do bot; o script nunca o imprime |

## VoiceStudio

App desktop que expõe, em `127.0.0.1:3900`, uma API compatível com a da OpenAI
(`/v1/audio/transcriptions` e `/v1/audio/speech`). Só responde com o app aberto. Testado na
versão 0.5.7, com o Whisper large-v3 Turbo na transcrição.

> [!WARNING]
> A voz OmniVoice é licenciada CC-BY-NC, só para uso não comercial. Confira a licença do
> modelo de voz que você escolher.

> [!TIP]
> Se o app mostrar **"Não foi possível iniciar o motor local. spawn UNKNOWN"**, o Windows
> está barrando o `python.exe` do `.venv` dele. O conserto está em
> [`docs/setup-windows.md`](docs/setup-windows.md#não-foi-possível-iniciar-o-motor-local-spawn-unknown).

## Segurança

- O token do bot vive só no `.env`, que está no `.gitignore` junto com `access.json`,
  `inbox\`, `state\` e `bot.pid`.
- O plugin recusa anexar qualquer arquivo da pasta do canal, exceto o que está em `inbox\`:
  o `.env` não sai pelo bot.
- Com a política `allowlist`, quem não foi pareado é ignorado em silêncio, e o pareamento só
  se aprova pelo terminal, nunca por mensagem do próprio Telegram.
- O `iniciar.cmd` abre a sessão em `--permission-mode auto`. Ajuste ao nível de autonomia que
  você quer dar a quem fala com o bot.

## Limites

- O bot só responde enquanto a sessão está aberta, e só vê o que chega com ela aberta.
- Um token, uma sessão: o Telegram aceita um único consumidor de `getUpdates` por bot.
- Só o Windows foi testado. O lançador é CMD.
