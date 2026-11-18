"""Sessões do Claude Code abertas ou continuadas pela sessão do Telegram, sobre o `claude --bg` nativo (v2.1.325).
Testado em 13/11/2026: `--bg --resume` numa sessão com processo vivo abre uma cópia com outro id; só continua a mesma depois do `stop` terminar.
Em 16/11/2026 o Telegram retomou sessões abertas no app Desktop (processo `interactive`) e gerou uma cópia a cada retomada; por isso `enviar` recusa esse caso.
`claude logs` devolve o terminal cru com ANSI; a resposta legível sai do transcript em ~/.claude/projects/*/<sessionId>.jsonl."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

PROJETOS = Path.home() / ".claude" / "projects"
# Stop hook só das sessões abertas aqui. Na v2.1.327 o `--bg --resume` reaproveita o --settings salvo, e qualquer flag
# repassada abre cópia (testado em 17/11/2026: sem flag continuou 1b834cb2; com --settings virou 32a8bf92).
AVISO = json.dumps({"hooks": {"Stop": [{"hooks": [
    {"type": "command", "command": f"python -I {Path(__file__).as_posix()} avisar"}]}]}})
USO = """uso:
  nova <nome> <pasta>   (prompt pelo stdin)  abre sessão nova em segundo plano
  enviar <id>           (mensagem pelo stdin) continua a mesma sessão, sem cópia; recusa se ela estiver trabalhando ou aberta no app
  ler <id>              estado e a última resposta da sessão
  listar                sessões em segundo plano
  parar <id>            encerra a sessão (a conversa fica salva)"""


def claude(*args: str, cwd: str | None = None) -> str:
    r = subprocess.run(["claude", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    return r.stdout


def agentes() -> list[dict]:
    return json.loads(claude("agents", "--json", "--all"))


def sessoes() -> list[dict]:
    return [a for a in agentes() if a.get("kind") == "background"]


def filtrar(lista: list[dict], ident: str) -> list[dict]:
    """Pelo id primeiro; o nome só desempata quando nenhum id casa (cópias levam o texto da mensagem, com ids, no nome)."""
    por_id = [a for a in lista if a.get("id") == ident or a["sessionId"].startswith(ident)]
    return por_id or [a for a in lista if ident.lower() in a.get("name", "").lower()]


def sessao(ident: str) -> dict:
    achadas = filtrar(sessoes(), ident)
    if len(achadas) != 1:
        sys.exit(f"{len(achadas)} sessões casam com {ident!r}; use o id de `listar`")
    return achadas[0]


def alvo(ident: str) -> dict:
    """Qualquer sessão: viva (background ou interactive) pelo `claude agents`, ou parada pelo transcript."""
    achadas = filtrar(agentes(), ident)
    vivas = [a for a in achadas if a.get("pid")] or achadas  # o `--all` também lista as paradas
    if len(vivas) == 1:
        return vivas[0]
    if vivas:
        sys.exit(f"{len(vivas)} sessões casam com {ident!r}; use o sessionId")
    transcripts = list(PROJETOS.glob(f"*/{ident}*.jsonl"))
    if len(transcripts) != 1:
        sys.exit(f"{len(transcripts)} transcripts casam com {ident!r}; use o sessionId")
    cwd = next((d["cwd"] for d in map(json.loads, transcripts[0].open(encoding="utf-8")) if d.get("cwd")), None)
    return {"sessionId": transcripts[0].stem, "cwd": cwd, "id": transcripts[0].stem[:8]}


def id_aberto(saida: str) -> str | None:
    m = re.search(r"backgrounded\s*·\s*([0-9a-f]{8})", saida)
    return m and m.group(1)


def ultima_resposta(linhas) -> str:
    textos = []
    for linha in linhas:
        d = json.loads(linha)
        if d.get("type") == "user" and isinstance(d["message"].get("content"), str) and not d.get("isMeta"):
            textos = []  # prompt novo: só interessa o que veio depois dele
        elif d.get("type") == "assistant":
            textos += [c["text"] for c in d["message"]["content"] if c.get("type") == "text"]
    return "\n\n".join(textos)


def nova(nome: str, pasta: str, prompt: str) -> None:
    print(claude("--bg", "--name", nome, "--permission-mode", "auto", "--settings", AVISO, "--", prompt, cwd=pasta))


def enviar(ident: str, mensagem: str) -> None:
    s = alvo(ident)
    if s.get("kind") == "interactive" and s.get("pid"):
        sys.exit(f"{s['sessionId'][:8]} ({s.get('name', '')}) está aberta no app Desktop ou num terminal (pid {s['pid']}); "
                 "retomar daqui abriria uma cópia. Mande pelo app (ou Remote Control), ou feche a sessão lá e repita.")
    if s.get("state") == "working":
        sys.exit(f"{s['id']} ainda está trabalhando; espere terminar ou `parar` antes")
    if s.get("pid"):
        claude("stop", s["id"])
        for _ in range(60):
            if not any(a.get("pid") for a in agentes() if a["sessionId"] == s["sessionId"]):
                break
            time.sleep(0.5)
        else:
            sys.exit(f"{s['id']} não encerrou em 30 s; mensagem não enviada")
    saida = claude("--bg", "--resume", s["sessionId"], "--", mensagem, cwd=s["cwd"])
    aberto = id_aberto(saida)
    if aberto and aberto != s["sessionId"][:8]:
        claude("stop", aberto)
        sys.exit(f"o Claude abriu a cópia {aberto} em vez de continuar {s['sessionId'][:8]}; parei a cópia. "
                 "Algum processo ainda segura a sessão: confira `listar` e o app Desktop.")
    print(saida)


def texto_puro(md: str, teto: int = 800) -> str:
    """O aviso sai em texto puro: o markdown da sessão aparecia cru no Telegram (17/11/2026: **, ##, crases).
    Corta no último parágrafo antes do teto, para não partir frase no meio."""
    t = re.sub(r"^```\w*\n?|^```$", "", md, flags=re.M)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", t)
    t = re.sub(r"^#{1,6}\s+", "", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), t)
    t = t.replace("`", "").strip()
    if len(t) <= teto:
        return t
    corte = t.rfind("\n\n", 0, teto)
    return t[:corte if corte > teto // 2 else teto].rstrip() + " […]"


def avisar(evento: dict) -> None:
    sys.path.insert(0, str(Path(__file__).parent))  # -I tira a pasta do script do sys.path
    import telegram_voz

    chat = telegram_voz.chat_do_hook({})
    transcript = Path(evento.get("transcript_path", ""))
    if not chat or not transcript.is_file():
        return
    sid = evento.get("session_id", "")
    nome = next((a.get("name", "") for a in sessoes() if a["sessionId"] == sid), "")
    bruta = ultima_resposta(transcript.open(encoding="utf-8")) or "(sem texto)"
    resposta = texto_puro(bruta)
    if len(resposta) < len(bruta) * 0.9:  # cortou de fato, não só tirou marcação
        resposta += f"\n\n(resposta inteira: peça \"ler {sid[:8]}\")"
    telegram_voz.mandar(chat, f"Sessão {nome} ({sid[:8]}) terminou:\n\n{resposta}")


def ler(ident: str) -> None:
    s = alvo(ident)  # sessao() só vê background: `ler` de sessão do app dava "0 sessões casam"
    transcript = next(PROJETOS.glob(f"*/{s['sessionId']}.jsonl"), None)
    print(f"{s['id']} · {s.get('name', '')} · {s.get('state')} · {s['cwd']}")
    print(ultima_resposta(transcript.open(encoding="utf-8")) if transcript else "(sem transcript ainda)")


def demo() -> None:
    linhas = [json.dumps(x) for x in (
        {"type": "user", "message": {"content": "primeira"}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "velha"}]}},
        {"type": "user", "message": {"content": "segunda"}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use"}, {"type": "text", "text": "a"}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "b"}]}},
    )]
    assert ultima_resposta(linhas) == "a\n\nb", ultima_resposta(linhas)
    assert id_aberto("backgrounded · 7c95fcba\n\n  claude agents   list sessions") == "7c95fcba"
    assert id_aberto("erro qualquer") is None
    lista = [{"id": "9875295e", "sessionId": "9875295e-99", "name": "anuncios"},
             {"id": "04d53cab", "sessionId": "04d53cab-41", "name": "cópias 7c95fcba e 9875295e"}]
    assert [a["id"] for a in filtrar(lista, "9875295e")] == ["9875295e"]
    assert [a["id"] for a in filtrar(lista, "anuncios")] == ["9875295e"]
    assert texto_puro("## Feito\n**ok** em `a.py`, ver [doc](http://x)\n```bash\nls\n```") == "Feito\nok em a.py, ver doc (http://x)\nls"
    longo = texto_puro("a" * 500 + "\n\n" + "b" * 500)
    assert longo == "a" * 500 + " […]", longo[-20:]
    print("demo ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")  # o sys.exit(msg) sai por aqui; sem isso, "sess�es" no Telegram
    entrada = lambda: sys.stdin.buffer.read().decode("utf-8").strip()  # sys.stdin.read() decodifica em cp1252: "SÃ³"
    a = sys.argv[1:]
    match a:
        case ["nova", nome, pasta]: nova(nome, pasta, entrada())
        case ["enviar", ident]: enviar(ident, entrada())
        case ["ler", ident]: ler(ident)
        case ["listar"]: [print(f"{s['id']}  {s.get('state', '?'):8} {s.get('name', '')}  ({s['cwd']})") for s in sessoes()]
        case ["parar", ident]: print(claude("stop", sessao(ident)["id"]))
        case ["avisar"]: avisar(json.loads(sys.stdin.buffer.read() or b"{}"))
        case ["--demo"]: demo()
        case _: sys.exit(USO)
