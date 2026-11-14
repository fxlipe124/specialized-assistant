@echo off
rem Sessão do Claude Code ouvindo o bot do Telegram, com voz pelo VoiceStudio local.
rem O plugin fica desligado nas outras sessões (settings.json) para só esta fazer polling do bot.
rem O plugin dá prioridade a uma variável de ambiente sobre o .env; zerada aqui, só o .env vale.
rem Troque PASTA_DE_TRABALHO pela pasta onde a sessão deve abrir.
set "TELEGRAM_BOT_TOKEN="
set "PASTA_DE_TRABALHO=%USERPROFILE%"
cd /d "%PASTA_DE_TRABALHO%"
claude --channels plugin:telegram@claude-plugins-official ^
  --settings "%USERPROFILE%\.claude\channels\telegram\settings-sessao.json" ^
  --append-system-prompt-file "%USERPROFILE%\.claude\channels\telegram\instrucoes-voz.md" ^
  --permission-mode auto ^
  --name telegram
