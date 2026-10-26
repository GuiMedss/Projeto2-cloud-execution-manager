import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys


PASTA_DADOS = Path("/var/lib/cloud-execution-manager")


def criar_ambiente(nome, cpu, memoria, io):
    # restringe o nome para usar em pastas, hostname e servicos
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,29}", nome):
        raise ValueError("o nome deve ter ate 30 letras minusculas, numeros ou hifens e iniciar com letra")
    if any(type(valor) is not int for valor in (cpu, memoria, io)):
        raise ValueError("cpu, memoria e io devem ser numeros inteiros")
    if not 1 <= cpu <= 100:
        raise ValueError("a cpu deve estar entre 1 e 100 por cento de um nucleo")
    if not 32 <= memoria <= 2048:
        raise ValueError("a memoria deve estar entre 32 e 2048 MiB")
    if not 1 <= io <= 100:
        raise ValueError("o io deve estar entre 1 e 100 MiB por segundo")
    if os.geteuid() != 0:
        raise ValueError("execute com sudo dentro da vm")

    controladores = Path("/sys/fs/cgroup/cgroup.controllers").read_text().split()
    if not {"cpu", "memory", "io"}.issubset(controladores):
        raise ValueError("os controladores cpu, memory e io precisam estar disponiveis em cgroups v2")

    unidade = f"cloud-ambiente-{nome}.service"
    estado = subprocess.run(
        ["systemctl", "show", unidade, "--property=LoadState", "--value"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if estado != "not-found":
        raise ValueError("ja existe um ambiente com esse nome; encerre o anterior antes de reutilizar")

    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    pasta = PASTA_DADOS / nome
    pasta.mkdir(exist_ok=True)
    memoria_bytes = memoria * 1024 * 1024
    io_bytes = io * 1024 * 1024

    # o systemd cria um cgroup e aplica os limites antes de iniciar o processo
    comando = [
        "systemd-run", f"--unit={unidade}", "--service-type=notify",
        "--property=NotifyAccess=all", "--property=TimeoutStartSec=10",
        "--property=TimeoutStopSec=2", "--property=KillMode=control-group",
        f"--property=WorkingDirectory={pasta}",
        f"--property=CPUQuota={cpu}%",
        f"--property=MemoryMax={memoria_bytes}", "--property=MemorySwapMax=0",
        f"--property=IOReadBandwidthMax={pasta} {io_bytes}",
        f"--property=IOWriteBandwidthMax={pasta} {io_bytes}",
        "/usr/bin/unshare", "--mount", "--uts", "--ipc", "--pid",
        "--fork", "--mount-proc", "--kill-child",
        "/usr/bin/python3", str(Path(__file__).resolve()), "--iniciar", nome,
    ]
    try:
        subprocess.run(comando, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as erro:
        raise ValueError(f"nao foi possivel criar o ambiente: {erro.stderr.strip()}") from erro

    cgroup = subprocess.run(
        ["systemctl", "show", unidade, "--property=ControlGroup", "--value"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return {
        "nome": nome, "unidade": unidade, "pasta": str(pasta),
        "cgroup": f"/sys/fs/cgroup{cgroup}",
        "cpu": cpu, "memoria": memoria, "io": io,
    }


def manter_ambiente(nome):
    # este processo ja esta dentro dos novos namespaces
    if os.getpid() != 1:
        raise ValueError("a inicializacao interna deve ocorrer no novo namespace de processos")
    subprocess.run(["hostname", nome], check=True)

    def sair(sinal, quadro):
        sys.exit(0)

    # o pid 1 precisa tratar o sinal de encerramento e recolher processos filhos
    signal.signal(signal.SIGTERM, sair)
    subprocess.run(["systemd-notify", "--ready"], check=True)
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    # mantem os namespaces vivos ate adicionarmos a execucao de programas
    while True:
        signal.pause()


if __name__ == "__main__":
    # chamada interna feita pelo systemd depois do unshare
    if len(sys.argv) == 3 and sys.argv[1] == "--iniciar":
        manter_ambiente(sys.argv[2])
    else:
        parser = argparse.ArgumentParser(description="cria um ambiente com namespaces e limites de recursos")
        parser.add_argument("nome")
        parser.add_argument("--cpu", type=int, required=True, help="porcentagem de um nucleo: 1 a 100")
        parser.add_argument("--memoria", type=int, required=True, help="memoria em MiB: 32 a 2048")
        parser.add_argument("--io", type=int, required=True, help="leitura e escrita em MiB/s: 1 a 100")
        args = parser.parse_args()
        try:
            resultado = criar_ambiente(args.nome, args.cpu, args.memoria, args.io)
            print(json.dumps(resultado))
        except (ValueError, OSError, subprocess.CalledProcessError) as erro:
            print(f"erro: {erro}", file=sys.stderr)
            sys.exit(1)
