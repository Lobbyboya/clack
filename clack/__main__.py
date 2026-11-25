"""clack: sons de teclado mecânico para Linux (Wayland e X11)."""

import json
import socket
import sys

USAGE = """uso: clack <comando>
  daemon            roda o serviço (normalmente pelo systemd)
  on | off | toggle liga, desliga ou alterna o som
  pack [nome]       troca o pacote de som (sem nome: lista os pacotes)
  volume <0-100>    ajusta o volume
  status            mostra o estado atual"""


def send(cmd: dict) -> dict:
    from .daemon import SOCKET_PATH
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(str(SOCKET_PATH))
        s.sendall(json.dumps(cmd).encode())
        return json.loads(s.recv(65536))


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    action, value = args[0], (args[1] if len(args) > 1 else None)

    if action == "daemon":
        from .daemon import Daemon
        Daemon().run()
        return 0

    if action == "pack" and value is None:
        from .packs import list_packs
        print("\n".join(p for p in list_packs() if not p.startswith("_")))
        return 0
    if action == "volume" and value is None:
        print("informe o volume: clack volume 0-100")
        return 2

    try:
        reply = send({"action": action, "value": value})
    except (FileNotFoundError, ConnectionRefusedError):
        print("o clack não está rodando. Inicie com: systemctl --user start clack")
        return 1
    if not reply.get("ok"):
        print(f"erro: {reply.get('error')}")
        return 1
    estado = "ligado" if reply["enabled"] else "desligado"
    print(f"{estado} · pacote {reply['pack']} · volume {reply['volume']}")
    if action == "status":
        print("teclados: " + (", ".join(reply["teclados"]) or "nenhum"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
