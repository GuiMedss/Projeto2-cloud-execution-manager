import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time


PASTA_DADOS = Path("/var/lib/cloud-execution-manager")


def pasta_ambiente(nome):
    # o nome tambem sera usado em pastas, hostname e servicos
    if not isinstance(nome, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,29}", nome):
        raise ValueError("o nome deve ter ate 30 letras minusculas, numeros ou hifens e iniciar com letra")
    pasta = PASTA_DADOS / nome
    if pasta.is_symlink():
        raise ValueError("a pasta do ambiente nao pode ser um link simbolico")
    return pasta


def bloquear():
    if os.geteuid() != 0:
        raise ValueError("execute com sudo dentro da vm")
    # evita duas alteracoes simultaneas nos arquivos de controle
    arquivo = open("/run/cloud-execution-manager.lock", "a")
    fcntl.flock(arquivo, fcntl.LOCK_EX)
    return arquivo


def salvar_json(caminho, dados):
    # troca o arquivo inteiro para que uma leitura nao encontre json incompleto
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados), encoding="utf-8")
    temporario.replace(caminho)


def estado_servico(unidade):
    resultado = subprocess.run(
        ["systemctl", "show", unidade, "-p", "LoadState", "-p", "ActiveState", "-p", "Result"],
        check=True, capture_output=True, text=True,
    )
    return dict(linha.split("=", 1) for linha in resultado.stdout.splitlines() if "=" in linha)


def consultar_registro(nome):
    pasta = pasta_ambiente(nome)
    if not (pasta / "ambiente.json").is_file():
        raise ValueError("ambiente nao encontrado")
    dados = json.loads((pasta / "ambiente.json").read_text(encoding="utf-8"))
    pedido = pasta / "comando.json"
    dados.update({"comando": None, "codigo_retorno": None, "erro": None, "encerrado": False})
    if pedido.exists():
        dados["comando"] = json.loads(pedido.read_text(encoding="utf-8"))["comando"]

    if (pasta / "resultado.json").exists():
        dados.update(json.loads((pasta / "resultado.json").read_text(encoding="utf-8")))
    elif (pasta / "encerrado").exists():
        dados.update({"status": "terminado", "encerrado": True})
    else:
        servico = estado_servico(dados["unidade"])
        if servico.get("ActiveState") in ("active", "activating"):
            dados["status"] = "em execucao"
        else:
            erro = "o ambiente foi interrompido antes de registrar o resultado"
            if servico.get("Result") not in (None, "success"):
                erro += f" ({servico['Result']})"
            dados.update({"status": "erro", "erro": erro})
    # os campos extras mantem o formato usado pela aplicacao web
    dados.update({
        "estado": dados["status"].replace(" ", "_"),
        "saida": str(pasta / "saida.log"), "mensagem": dados["erro"],
    })
    return dados


def criar_ambiente(nome, cpu, memoria, io):
    pasta = pasta_ambiente(nome)
    if any(type(valor) is not int for valor in (cpu, memoria, io)):
        raise ValueError("cpu, memoria e io devem ser numeros inteiros")
    if not 1 <= cpu <= 100:
        raise ValueError("a cpu deve estar entre 1 e 100 por cento de um nucleo")
    if not 32 <= memoria <= 2048:
        raise ValueError("a memoria deve estar entre 32 e 2048 MiB")
    if not 1 <= io <= 100:
        raise ValueError("o io deve estar entre 1 e 100 MiB por segundo")

    with bloquear():
        controladores = Path("/sys/fs/cgroup/cgroup.controllers").read_text().split()
        if not {"cpu", "memory", "io"}.issubset(controladores):
            raise ValueError("os controladores cpu, memory e io precisam estar disponiveis em cgroups v2")
        unidade = f"cloud-ambiente-{nome}.service"
        if pasta.exists() or estado_servico(unidade)["LoadState"] != "not-found":
            raise ValueError("ja existe um ambiente com esse nome; remova o anterior antes de reutilizar")

        pasta.mkdir(parents=True)
        dados = {
            "nome": nome, "unidade": unidade, "pasta": str(pasta),
            "cgroup": f"/sys/fs/cgroup/system.slice/{unidade}",
            "cpu": cpu, "memoria": memoria, "io": io,
        }
        salvar_json(pasta / "ambiente.json", dados)
        (pasta / "saida.log").touch()
        memoria_bytes = memoria * 1024 * 1024
        io_bytes = io * 1024 * 1024

        # o systemd aplica os limites antes de iniciar os novos namespaces
        comando = [
            "systemd-run", f"--unit={unidade}", "--service-type=notify",
            "--property=NotifyAccess=all", "--property=TimeoutStartSec=10",
            "--property=TimeoutStopSec=2", "--property=KillMode=control-group",
            f"--property=WorkingDirectory={pasta}",
            f"--property=StandardOutput=append:{pasta / 'saida.log'}",
            "--property=StandardError=inherit",
            f"--property=CPUQuota={cpu}%",
            f"--property=MemoryMax={memoria_bytes}", "--property=MemorySwapMax=0",
            f"--property=IOReadBandwidthMax={pasta} {io_bytes}",
            f"--property=IOWriteBandwidthMax={pasta} {io_bytes}",
            "/usr/bin/unshare", "--mount", "--uts", "--ipc", "--pid",
            "--fork", "--mount-proc", "--kill-child",
            "/usr/bin/python3", str(Path(__file__).resolve()), "--iniciar", nome,
        ]
        resultado = subprocess.run(comando, capture_output=True, text=True)
        if resultado.returncode != 0:
            erro = "nao foi possivel criar o ambiente: " + resultado.stderr.strip()
            # desfaz uma criacao que falhou para permitir outra tentativa
            parar_servico(unidade)
            shutil.rmtree(pasta)
            raise ValueError(erro)
        return consultar_registro(nome)


def executar_programa(nome, comando):
    if not isinstance(comando, list) or not comando or not comando[0]:
        raise ValueError("informe o programa e seus argumentos em uma lista")
    if any(not isinstance(parte, str) or "\0" in parte for parte in comando):
        raise ValueError("os argumentos devem ser textos sem caractere nulo")

    with bloquear():
        dados = consultar_registro(nome)
        pasta = pasta_ambiente(nome)
        if dados["status"] != "em execucao" or (pasta / "comando.json").exists():
            raise ValueError("cada ambiente aceita uma execucao; crie outro ambiente para executar novamente")
        # o processo interno le o pedido e inicia o programa no mesmo cgroup
        salvar_json(pasta / "comando.json", {"comando": comando})
        return consultar_registro(nome)


def consultar_ambiente(nome):
    with bloquear():
        return consultar_registro(nome)


def listar_ambientes():
    with bloquear():
        ambientes = []
        for registro in sorted(PASTA_DADOS.glob("*/ambiente.json")):
            ambientes.append(consultar_registro(registro.parent.name))
        return ambientes


def ler_saida(nome):
    with bloquear():
        consultar_registro(nome)
        saida = pasta_ambiente(nome) / "saida.log"
        return {"nome": nome, "saida": saida.read_text(encoding="utf-8", errors="replace")}


def parar_servico(unidade):
    servico = estado_servico(unidade)
    if servico["LoadState"] != "not-found":
        subprocess.run(["systemctl", "stop", unidade], check=True, capture_output=True, text=True)
        subprocess.run(["systemctl", "reset-failed", unidade], capture_output=True)


def encerrar_ambiente(nome):
    with bloquear():
        dados = consultar_registro(nome)
        pasta = pasta_ambiente(nome)
        parar_servico(dados["unidade"])
        if not (pasta / "resultado.json").exists():
            if dados["status"] == "erro":
                salvar_json(pasta / "resultado.json", {"status": "erro", "erro": dados["erro"]})
            else:
                # o encerramento manual preserva a saida para consulta
                (pasta / "encerrado").touch()
        return consultar_registro(nome)


def remover_ambiente(nome):
    with bloquear():
        pasta = pasta_ambiente(nome)
        if not pasta.exists():
            return {"nome": nome, "removido": True}
        dados = consultar_registro(nome)
        parar_servico(dados["unidade"])
        # o nome validado limita a remocao a uma pasta dentro do diretorio de dados
        if pasta.resolve().parent != PASTA_DADOS.resolve():
            raise ValueError("a pasta esta fora do diretorio de ambientes")
        shutil.rmtree(pasta)
        return {"nome": nome, "removido": True}


def manter_ambiente(nome):
    if os.getpid() != 1:
        raise ValueError("a inicializacao interna deve ocorrer no novo namespace de processos")
    pasta = pasta_ambiente(nome)
    subprocess.run(["hostname", nome], check=True)

    def sair(sinal, quadro):
        sys.exit(0)

    # o pid 1 trata o encerramento e aguarda o programa executado
    signal.signal(signal.SIGTERM, sair)
    subprocess.run(["systemd-notify", "--ready"], check=True)
    pedido = pasta / "comando.json"
    while not pedido.exists():
        time.sleep(0.2)

    comando = json.loads(pedido.read_text(encoding="utf-8"))["comando"]
    with (pasta / "saida.log").open("ab", buffering=0) as saida:
        try:
            programa = subprocess.Popen(
                comando, stdin=subprocess.DEVNULL, stdout=saida, stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            # o pid 1 tambem recolhe filhos adotados enquanto o programa continua
            while True:
                pid, estado = os.waitpid(-1, 0)
                if pid == programa.pid:
                    codigo = os.waitstatus_to_exitcode(estado)
                    programa.returncode = codigo
                    break
            resultado = {"status": "terminado" if codigo == 0 else "erro", "codigo_retorno": codigo}
            if codigo != 0:
                resultado["erro"] = f"o programa terminou com codigo {codigo}"
        except (OSError, ValueError) as erro:
            mensagem = f"nao foi possivel executar o programa: {erro}"
            saida.write((mensagem + "\n").encode("utf-8"))
            resultado = {"status": "erro", "codigo_retorno": 127, "erro": mensagem}
        salvar_json(pasta / "resultado.json", resultado)


def main():
    parser = argparse.ArgumentParser(description="gerencia ambientes com namespaces e limites de recursos")
    acoes = parser.add_subparsers(dest="acao", required=True)
    criar = acoes.add_parser("criar", help="cria um ambiente aguardando um programa")
    criar.add_argument("nome")
    criar.add_argument("--cpu", type=int, required=True, help="porcentagem de um nucleo: 1 a 100")
    criar.add_argument("--memoria", type=int, required=True, help="memoria em MiB: 32 a 2048")
    criar.add_argument("--io", type=int, required=True, help="leitura e escrita em MiB/s: 1 a 100")
    programa = criar.add_mutually_exclusive_group()
    programa.add_argument("--script", help="caminho de um script .py ou .sh")
    programa.add_argument("--comando", help="comando que sera executado pelo bash")
    executar = acoes.add_parser("executar", help="envia um programa para o ambiente")
    executar.add_argument("nome")
    executar.add_argument("comando", nargs=argparse.REMAINDER)
    acoes.add_parser("listar", help="lista os ambientes e seus estados")
    for acao in ("status", "saida", "encerrar", "remover"):
        subparser = acoes.add_parser(acao)
        subparser.add_argument("nome")

    argumentos = sys.argv[1:]
    # mantem o comando de criacao usado na primeira versao
    if argumentos and argumentos[0] not in acoes.choices and not argumentos[0].startswith("-"):
        argumentos = ["criar", *argumentos]
    args = parser.parse_args(argumentos)
    if args.acao == "criar":
        comando = None
        if args.script is not None:
            script = Path(args.script).resolve()
            if not script.is_file() or script.suffix.lower() not in (".py", ".sh"):
                raise ValueError("informe um arquivo .py ou .sh existente")
            interpretador = "/usr/bin/python3" if script.suffix.lower() == ".py" else "/bin/bash"
            comando = [interpretador, str(script)]
        elif args.comando is not None:
            if not args.comando.strip():
                raise ValueError("o comando nao pode estar vazio")
            comando = ["/bin/bash", "-c", args.comando]
        dados = criar_ambiente(args.nome, args.cpu, args.memoria, args.io)
        return executar_programa(args.nome, comando) if comando else dados
    if args.acao == "executar":
        comando = args.comando[1:] if args.comando[:1] == ["--"] else args.comando
        return executar_programa(args.nome, comando)
    if args.acao == "listar":
        return listar_ambientes()
    if args.acao == "status":
        return consultar_ambiente(args.nome)
    if args.acao == "saida":
        return ler_saida(args.nome)
    if args.acao == "encerrar":
        return encerrar_ambiente(args.nome)
    return remover_ambiente(args.nome)


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--iniciar":
            manter_ambiente(sys.argv[2])
        else:
            print(json.dumps(main()))
    except (ValueError, OSError, subprocess.CalledProcessError) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        sys.exit(1)
