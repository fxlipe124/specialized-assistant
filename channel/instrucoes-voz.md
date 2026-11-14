# Sessão Telegram com voz

Esta sessão conversa com o usuário pelo Telegram. Tudo o que ele manda chega como `<channel source="telegram" ...>`; tudo o que você responde sai pelas ferramentas do plugin ou pelo script de voz. Texto escrito no terminal ele não vê.

## Áudio e texto, sempre

Toda resposta sai nos dois formatos, venha a mensagem em texto ou em áudio (`attachment_kind="voice"` ou `"audio"`):

1. Texto completo pela ferramenta `reply`, com tudo: código, comando, link, caminho, id, tabela, valor exato.
2. Logo depois, o áudio pelo script, com a versão falada da mesma resposta, em `reply_to` a mensagem dele.

O áudio não lê o texto palavra por palavra: diz o essencial e, se houver código, link ou tabela, fala só que está no texto.

## Receber áudio

1. `download_attachment` com o `attachment_file_id` devolve o caminho do arquivo.
2. Transcrever:
   ```bash
   python -I ~/.claude/scripts/telegram_voz.py transcrever "<caminho>"
   ```
3. Tratar o texto transcrito como a mensagem dele. Se a transcrição vier vazia ou sem sentido, pedir em texto que ele repita.

## Responder em áudio

```bash
python -I ~/.claude/scripts/telegram_voz.py falar <chat_id> <message_id> <<'FIM'
texto falado aqui
FIM
```

- Escrever para ser ouvido: frases curtas, sem markdown, sem emoji, sem lista com marcador, sem contrabarra.
- Resposta longa: o áudio leva o resumo (até uns 40 segundos de fala) e o detalhe vai em texto.
- Se o script falhar (VoiceStudio fechado ou porta 3900 sem resposta), responder em texto e avisar numa linha que a voz está fora.

## Sessões novas

Quando ele pedir uma sessão nova, zerada ou separada, abrir outra sessão do Claude em segundo plano, sem o contexto desta conversa, pelo script:

```bash
python -I ~/.claude/scripts/claude_sessoes.py nova <nome-curto> <pasta> <<'FIM'
pedido dele, completo, porque a sessão nova não sabe nada desta conversa
FIM
```

- Pasta padrão: a pasta onde esta sessão abriu, a menos que ele diga outra.
- Responder com o id e o nome que o script imprimir.
- `listar` mostra as sessões e o estado (`working`, `done`, `stopped`); `ler <id>` traz a última resposta; `parar <id>` encerra.
- Mensagem dele para uma sessão aberta: `enviar <id>` com o texto pelo stdin, no mesmo formato do `nova`. Se ela ainda estiver trabalhando, o script recusa: avisar e perguntar se espera ou se para.
- Não verificar em laço: ler a sessão quando ele perguntar por ela.
- No PC, ele abre qualquer uma com `claude attach <id>`.

## Trabalho longo

Antes de uma tarefa que leve mais que um minuto, mandar uma linha dizendo o que vai fazer. No fim, o resultado no mesmo formato da pergunta.
