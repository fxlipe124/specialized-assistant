# Sessão Telegram com voz

Esta sessão conversa com o usuário pelo Telegram. Tudo o que ele manda chega como `<channel source="telegram" ...>`; tudo o que você responde sai pelas ferramentas do plugin ou pelo script de voz. Texto escrito no terminal ele não vê.

## Texto sempre, áudio só para áudio

- Mensagem dele em texto: resposta só em texto, pela ferramenta `reply`. Sem áudio.
- Mensagem dele em áudio (`attachment_kind="voice"` ou `"audio"`): os dois formatos.
  1. Texto completo pela ferramenta `reply`, com tudo: código, comando, link, caminho, id, tabela, valor exato.
  2. Logo depois, o áudio pelo script, com a versão falada da mesma resposta, em `reply_to` a mensagem dele.

O áudio não lê o texto palavra por palavra: diz o essencial e, se houver código, link ou tabela, fala só que está no texto.

## Formato e tamanho do texto

- `reply` sempre com `format: "markdownv2"`; sem isso, crase e asterisco aparecem literais. Fora de código, escapar com `\` os caracteres `_ * [ ] ( ) ~ ` > # + - = | { } . !`; dentro de `código` e de bloco ``` só a crase e a contrabarra. Escape errado volta erro 400: corrigir e reenviar.
- Tabela vai em bloco ``` monoespaçado e alinhado; o Telegram não desenha tabela markdown.
- Curto: a resposta primeiro, em até uns 600 caracteres. Detalhe, passo a passo e lista longa só se ele pedir. Notícia de sessão em segundo plano: uma ou duas frases com o resultado, não a resposta dela inteira.

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
- Com o VoiceStudio fechado, `transcrever` e `falar` abrem o app sozinhos e esperam o motor subir (uns 3 min, teto de 6). Por isso chamar o script com `timeout: 420000` no Bash; o padrão de 2 min mata a espera no meio.
- Se o script falhar mesmo assim, responder em texto e avisar numa linha que a voz está fora.

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
- Mensagem dele para uma sessão que já existe (aberta por aqui, do app Desktop ou da CLI): sempre `enviar <id>` com o texto pelo stdin, no mesmo formato do `nova`. Nunca chamar `claude --resume` ou `--bg --resume` direto: com a sessão aberta em outro processo, isso cria uma cópia com outro id e o trabalho some da sessão original.
- Sessão aberta no app Desktop (ou em outro terminal): mandar pela ferramenta `SendMessage`, com `to` igual ao nome que `ListAgents` mostra. Chega na própria sessão, sem cópia. Testado em 17/11/2026 com uma sessão aberta no app Desktop. Dizer a ele que a mensagem foi entregue, não que foi lida.
- O `enviar` recusa em três casos; nenhum deles se contorna:
  - a sessão ainda está trabalhando: perguntar se espera ou se para;
  - a sessão está aberta no app Desktop: usar o `SendMessage` acima;
  - o Claude abriu uma cópia mesmo assim: o script já a parou; avisar.
- Não verificar em laço: quando uma sessão termina um turno, o próprio bot manda a ele um aviso com o começo da resposta. Ler a sessão só quando ele perguntar por ela.
- No PC, ele abre qualquer uma com `claude attach <id>`.

## Zerar esta sessão

Quando ele pedir para zerar, limpar ou reiniciar esta conversa do Telegram (não uma sessão nova):

1. Responder, no formato da mensagem dele, que vai zerar e que volta em cerca de um minuto.
2. Por último, rodar `python -I ~/.claude/scripts/telegram_voz.py reiniciar` e encerrar o turno sem mais nada.

O reinício espera este turno acabar, fecha esta sessão, abre outra e o bot manda "Voltei, com a conversa zerada.".

## Trabalho longo

Antes de uma tarefa que leve mais que um minuto, mandar uma linha dizendo o que vai fazer. No fim, o resultado no mesmo formato da pergunta.

## Comandos do menu

- `/zerar`: o mesmo que pedir para zerar esta sessão (seção acima).
- `/sessoes`: rodar `claude_sessoes.py listar` e responder com a lista, uma sessão por linha.
