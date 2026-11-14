"""Voz do canal Telegram do Claude Code: transcreve o áudio recebido e responde em áudio, ambos pelo VoiceStudio local.
Um arquivo só, em stdlib, no lugar dos sete scripts .sh que o guia genérico cita e nunca forneceu.
Telegram só mostra como mensagem de voz um OGG/Opus; o VoiceStudio devolve mp3, por isso o áudio passa pelo ffmpeg.
VoiceStudio em 127.0.0.1:3900 sem chave (loopback); o token do bot vem do .env do canal e nunca é impresso."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

PASTA = Path(os.environ.get("TELEGRAM_STATE_DIR") or Path.home() / ".claude" / "channels" / "telegram")
ESTADO = PASTA / "state"
VOICESTUDIO = os.environ.get("VOICESTUDIO_URL", "http://127.0.0.1:3900").rstrip("/")
IDIOMA = os.environ.get("TELEGRAM_VOZ_IDIOMA", "pt")
DIGITANDO_INTERVALO = 4  # o "digitando" do Telegram some sozinho em ~5 s
DIGITANDO_TETO = 15 * 60  # ponytail: teto fixo se o Stop não vier; turno mais longo que isso perde o indicador


def chave(nome: str) -> str:
    if os.environ.get(nome):
        return os.environ[nome]
    try:
        for linha in (PASTA / ".env").read_text(encoding="utf-8").splitlines():
            if linha.startswith(nome + "="):
                return linha.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    sys.exit(f"{nome} ausente em {PASTA / '.env'}")


def multipart(campos: dict, arquivos: dict) -> tuple[bytes, str]:
    fronteira = uuid.uuid4().hex
    partes = []
    for nome, valor in campos.items():
        partes.append(f'--{fronteira}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valor}\r\n'.encode())
    for nome, (arquivo, conteudo, tipo) in arquivos.items():
        cabecalho = f'--{fronteira}\r\nContent-Disposition: form-data; name="{nome}"; filename="{arquivo}"\r\nContent-Type: {tipo}\r\n\r\n'
        partes.append(cabecalho.encode() + conteudo + b"\r\n")
    partes.append(f"--{fronteira}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={fronteira}"


def requisitar(url: str, cabecalhos: dict, corpo: bytes | None = None) -> bytes:
    pedido = urllib.request.Request(url, data=corpo, headers=cabecalhos, method="POST" if corpo is not None else "GET")
    try:
        with urllib.request.urlopen(pedido, timeout=300) as resposta:
            return resposta.read()
    except urllib.error.HTTPError as erro:
        # A URL do Telegram leva o token: só o host e o corpo do erro saem.
        sys.exit(f"HTTP {erro.code} em {urllib.parse.urlsplit(url).netloc}: {erro.read().decode('utf-8', 'replace')[:800]}")


def ler_estado(nome: str, padrao: str) -> str:
    arquivo = ESTADO / nome
    return arquivo.read_text(encoding="utf-8").strip() if arquivo.exists() else padrao


def gravar_estado(nome: str, valor: str) -> None:
    ESTADO.mkdir(parents=True, exist_ok=True)
    (ESTADO / nome).write_text(valor, encoding="utf-8")


def modo(chat_id: str, novo: str | None = None) -> str:
    if novo:
        if novo not in ("texto", "audio"):
            sys.exit("modo é 'texto' ou 'audio'")
        gravar_estado(f"{chat_id}.modo", novo)
    return ler_estado(f"{chat_id}.modo", "texto")


def transcrever(caminho: str) -> str:
    conteudo = Path(caminho).read_bytes()
    corpo, tipo = multipart({"language": IDIOMA}, {"file": (Path(caminho).name, conteudo, "application/octet-stream")})
    resposta = requisitar(f"{VOICESTUDIO}/v1/audio/transcriptions", {"Content-Type": tipo}, corpo)
    return json.loads(resposta)["text"].strip()


def sintetizar(texto: str, destino: Path) -> None:
    voz = json.loads(ler_estado("voz.json", "{}"))
    pedido = {"input": texto, "language": IDIOMA, "response_format": "mp3", "voice": voz.get("voice", "default")}
    if voz.get("model"):
        pedido["model"] = voz["model"]
    mp3 = requisitar(f"{VOICESTUDIO}/v1/audio/speech", {"Content-Type": "application/json"}, json.dumps(pedido).encode())
    with tempfile.TemporaryDirectory() as pasta:
        entrada = Path(pasta) / "voz.mp3"
        entrada.write_bytes(mp3)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(entrada), "-c:a", "libopus", "-b:a", "48k", str(destino)], check=True)


def telegram(metodo: str, corpo: bytes, tipo: str = "application/json") -> None:
    url = f"https://api.telegram.org/bot{chave('TELEGRAM_BOT_TOKEN')}/{metodo}"
    resultado = json.loads(requisitar(url, {"Content-Type": tipo}, corpo))
    if not resultado.get("ok"):
        sys.exit(f"Telegram recusou: {resultado.get('description')}")


def falar(chat_id: str, texto: str, responder_a: str | None = None) -> None:
    # O laço do "digitando" lê a ação a cada envio: durante a síntese o chat mostra "gravando áudio".
    gravar_estado("digitando_acao", "record_voice")
    try:
        try:
            telegram("sendChatAction", json.dumps({"chat_id": chat_id, "action": "record_voice"}).encode())
        except (SystemExit, OSError):
            pass  # sem o indicador o áudio ainda sai
        with tempfile.TemporaryDirectory() as pasta:
            ogg = Path(pasta) / "voz.ogg"
            sintetizar(texto, ogg)
            campos = {"chat_id": chat_id}
            if responder_a:
                campos["reply_parameters"] = json.dumps({"message_id": int(responder_a)})
            corpo, tipo = multipart(campos, {"voice": ("voz.ogg", ogg.read_bytes(), "audio/ogg")})
        telegram("sendVoice", corpo, tipo)
    finally:
        gravar_estado("digitando_acao", "typing")


def chat_do_hook(evento: dict) -> str | None:
    achado = re.search(r'<channel source="telegram"[^>]*\bchat_id="(-?\d+)"', evento.get("prompt", ""))
    if achado:
        gravar_estado("ultimo_chat", achado.group(1))
        return achado.group(1)
    if ultimo := ler_estado("ultimo_chat", ""):
        return ultimo
    permitidos = json.loads((PASTA / "access.json").read_text(encoding="utf-8")).get("allowFrom", [])
    return str(permitidos[0]) if len(permitidos) == 1 else None


def digitando(evento: dict) -> None:
    marca = ESTADO / "digitando"
    if marca.exists() and marca.read_text(encoding="utf-8") and time.time() - marca.stat().st_mtime < 3 * DIGITANDO_INTERVALO:
        return  # laço vivo: ele regrava a marca a cada envio
    chat = chat_do_hook(evento)
    if not chat:
        return
    ficha = uuid.uuid4().hex
    gravar_estado("digitando", ficha)
    sem_janela = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    # Saídas em DEVNULL: herdando o stdout do hook, o Claude Code esperaria o laço terminar.
    subprocess.Popen([sys.executable, "-I", __file__, "digitando-laco", chat, ficha], creationflags=sem_janela,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)


def digitando_laco(chat: str, ficha: str) -> None:
    fim = time.time() + DIGITANDO_TETO
    while time.time() < fim and ler_estado("digitando", "") == ficha:
        try:
            acao = ler_estado("digitando_acao", "typing")
            telegram("sendChatAction", json.dumps({"chat_id": chat, "action": acao}).encode())
        except (SystemExit, OSError):
            pass  # falha de rede num envio não derruba o indicador
        if ler_estado("digitando", "") != ficha:
            return  # o Stop chegou durante o envio: não ressuscitar a marca
        gravar_estado("digitando", ficha)
        time.sleep(DIGITANDO_INTERVALO)


def vozes() -> None:
    dados = json.loads(requisitar(f"{VOICESTUDIO}/v1/audio/voices", {}))
    for voz in dados.get("voices", []) if isinstance(dados, dict) else dados:
        print(f"{voz.get('voice_id')}  {voz.get('name')}  {voz.get('type', '')}  {voz.get('language') or ''}".rstrip())


def demo() -> None:
    global ESTADO
    corpo, tipo = multipart({"chat_id": "1"}, {"voice": ("v.ogg", b"\x00\x01", "audio/ogg")})
    fronteira = tipo.split("boundary=")[1]
    assert corpo.startswith(f"--{fronteira}\r\n".encode()) and corpo.endswith(f"--{fronteira}--\r\n".encode())
    assert b'name="voice"; filename="v.ogg"' in corpo and b"\x00\x01\r\n" in corpo
    with tempfile.TemporaryDirectory() as pasta:
        ESTADO = Path(pasta)
        assert modo("42") == "texto"
        assert modo("42", "audio") == "audio" and modo("42") == "audio"
        assert chat_do_hook({"prompt": '<channel source="telegram" chat_id="123" message_id="9">oi'}) == "123"
        assert chat_do_hook({"tool_name": "Bash"}) == "123"  # PreToolUse não traz o prompt: usa o último chat
    print("ok")


USO = """uso: telegram_voz.py <comando>
  modo <chat_id> [texto|audio]       lê ou troca o modo de resposta do chat
  transcrever <arquivo>              imprime o texto do áudio
  falar <chat_id> [reply_to]         lê o texto do stdin e manda como mensagem de voz
  amostra <arquivo.ogg>              lê o texto do stdin e grava o áudio, sem Telegram
  vozes                              lista as vozes do VoiceStudio
  voz <voice_id> [modelo]            escolhe a voz (padrão: 'default' no motor ativo)
  digitando [parar]                  hook: mantém o "digitando" do Telegram ligado enquanto a sessão trabalha
  --demo                             auto-check, sem rede"""


def main(argumentos: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # rodando com -I o PYTHONUTF8 é ignorado e o "já" sairia como cp1252
    if not argumentos:
        sys.exit(USO)
    comando, resto = argumentos[0], argumentos[1:]
    if comando == "--demo":
        demo()
    elif comando == "modo" and resto:
        print(modo(*resto[:2]))
    elif comando == "transcrever" and len(resto) == 1:
        print(transcrever(resto[0]))
    elif comando == "falar" and resto:
        falar(resto[0], sys.stdin.buffer.read().decode("utf-8").strip(), resto[1] if len(resto) > 1 else None)
    elif comando == "amostra" and len(resto) == 1:
        sintetizar(sys.stdin.buffer.read().decode("utf-8").strip(), Path(resto[0]))
    elif comando == "digitando":  # hook: UserPromptSubmit e PreToolUse ligam, Stop desliga
        if resto == ["parar"]:
            gravar_estado("digitando", "")
        else:
            digitando(json.loads(sys.stdin.buffer.read() or b"{}"))
    elif comando == "digitando-laco" and len(resto) == 2:
        digitando_laco(*resto)
    elif comando == "vozes":
        vozes()
    elif comando == "voz" and resto:
        gravar_estado("voz.json", json.dumps({"voice": resto[0], "model": resto[1] if len(resto) > 1 else None}))
    else:
        sys.exit(USO)


if __name__ == "__main__":
    main(sys.argv[1:])
