@echo off
rem Zera a sessão do Telegram. Aberto pelo explorer, roda fora da árvore de processos dela:
rem espera o turno atual acabar, encerra a sessão e o bot, reabre pelo iniciar.cmd e avisa no Telegram.
rem "python" pelo explorer cai no atalho da Microsoft Store e nada roda (17/11/2026: os dois reinícios do dia); o py acha o Python instalado.
py -3 -I "%USERPROFILE%\.claude\scripts\telegram_voz.py" reiniciar-agora
