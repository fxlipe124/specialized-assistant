@echo off
rem Zera a sessão do Telegram. Aberto pelo explorer, roda fora da árvore de processos dela:
rem espera o turno atual acabar, encerra a sessão e o bot, reabre pelo iniciar.cmd e avisa no Telegram.
python -I "%USERPROFILE%\.claude\scripts\telegram_voz.py" reiniciar-agora
