"""Sessões novas do Claude Code abertas pela sessão do Telegram, sobre o `claude --bg` nativo (v2.1.325).
Testado em 13/11/2026: `--bg --resume` numa sessão com processo vivo abre uma cópia com outro id; só continua a mesma depois do `stop` terminar.
O `stop` volta antes do processo morrer (a segunda tentativa imediata ainda abriu cópia), por isso `enviar` espera o pid sumir do `claude agents`.
`claude logs` devolve o terminal cru com ANSI; a resposta legível sai do transcript em ~/.claude/projects/*/<sessionId>.jsonl."""
import json
import subprocess
import sys
import time
from pathlib import Path

PROJETOS = Path.home() / ".claude" / "projects"
USO = """uso:
  nova <nome> <pasta>   (prompt pelo stdin)  abre sessão nova em segundo plano
  enviar <id>           (mensagem pelo stdin) continua a sessão; recusa se ela estiver trabalhando
  ler <id>              estado e a última resposta da sessão
  listar                sessões em segundo plano
  parar <id>            encerra a sessão (a conversa fica salva)"""


def claude(*args: str, cwd: str | None = None) -> str:
    r = subprocess.run(["claude", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    return r.stdout


def sessoes() -> list[dict]:
    return [a for a in json.loads(claude("agents", "--json", "--all")) if a.get("kind") == "background"]


def sessao(ident: str) -> dict:
    achadas = [a for a in sessoes() if a.get("id") == ident or a["sessionId"] == ident or ident.lower() in a.get("name", "").lower()]
    if len(achadas) != 1:
        sys.exit(f"{len(achadas)} sessões casam com {ident!r}; use o id de `listar`")
    return achadas[0]


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
    print(claude("--bg", "--name", nome, "--permission-mode", "auto", "--", prompt, cwd=pasta))


def enviar(ident: str, mensagem: str) -> None:
    s = sessao(ident)
    if s.get("state") == "working":
        sys.exit(f"{s['id']} ainda está trabalhando; espere terminar ou `parar` antes")
    if s.get("pid"):
        claude("stop", s["id"])
        for _ in range(60):
            if not sessao(s["id"]).get("pid"):
                break
            time.sleep(0.5)
        else:
            sys.exit(f"{s['id']} não encerrou em 30 s; mensagem não enviada")
    print(claude("--bg", "--resume", s["sessionId"], "--", mensagem, cwd=s["cwd"]))


def ler(ident: str) -> None:
    s = sessao(ident)
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
    print("demo ok")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    match a:
        case ["nova", nome, pasta]: nova(nome, pasta, sys.stdin.read().strip())
        case ["enviar", ident]: enviar(ident, sys.stdin.read().strip())
        case ["ler", ident]: ler(ident)
        case ["listar"]: [print(f"{s['id']}  {s.get('state', '?'):8} {s.get('name', '')}  ({s['cwd']})") for s in sessoes()]
        case ["parar", ident]: print(claude("stop", sessao(ident)["id"]))
        case ["--demo"]: demo()
        case _: sys.exit(USO)
