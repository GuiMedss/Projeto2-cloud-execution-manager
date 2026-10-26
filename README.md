# Projeto 2 - Cloud Execution Manager

Projeto de Computacao em Nuvem para gerenciar ambientes de execucao pela web, usando namespaces e cgroups.

O projeto conta com o provisionamento da VM e a criacao de ambientes com namespaces e limites de CPU, memoria e I/O. A interface web, o banco da aplicacao e a execucao de programas enviados pelo usuario estao em desenvolvimento.

## Arquivos

- `Vagrantfile`: define a VM, os recursos e a porta de acesso.
- `provision.sh`: instala os pacotes, clona o repositorio e inicia os servicos.
- `ambientes.py`: cria ambientes isolados e aplica os limites de recursos.
- `.gitattributes`: mantem os scripts com finais de linha compativeis com Linux, mesmo no Windows.
- `.gitignore`: impede que os arquivos locais do Vagrant sejam enviados ao GitHub.

## Ambiente

- Ubuntu 22.04, com VirtualBox.
- 1 CPU e 4096 MB de memoria.
- Apache como servidor web.
- MySQL para o armazenamento permanente da aplicacao nas proximas etapas.
- Git para baixar o codigo durante o provisionamento.
- Python 3 para executar scripts Python.
- Ferramentas `unshare` e `nsenter`, do pacote `util-linux`, para trabalhar com namespaces.
- cgroups v2, disponivel no sistema da VM, para implementar os limites de recursos.

## Como executar

1. Instale o VirtualBox e o Vagrant no computador. A configuracao usa uma box para computadores Intel ou AMD de 64 bits.
2. Baixe o repositorio do projeto. O provisionamento usa a branch `main` no GitHub, que precisa estar acessivel sem solicitar login dentro da VM.
3. Na pasta que contem o `Vagrantfile`, execute:

```powershell
vagrant validate
vagrant up --provider=virtualbox
```

O primeiro provisionamento precisa de internet para baixar a box, instalar os pacotes e clonar o repositorio. A VM usa 4 GB de RAM; o computador tambem precisa de memoria livre para continuar funcionando.

Depois, abra no navegador:

```text
http://localhost:8080
```

A pagina deve mostrar que a VM e o Apache estao funcionando. Essa pagina e temporaria e ainda nao executa programas.

O codigo e clonado do GitHub em `/opt/cloud-execution-manager`. A pasta do computador nao e compartilhada com a VM.

## Como verificar

Confira o estado da VM:

```powershell
vagrant status
```

Entre na VM:

```powershell
vagrant ssh
```

Dentro da VM, execute:

```bash
nproc
free -m
systemctl is-active apache2 mysql
curl -f http://localhost
sudo git -C /opt/cloud-execution-manager log -1 --oneline
cat /sys/fs/cgroup/cgroup.controllers
unshare --version
sudo mysql -e "SELECT VERSION();"
```

Resultados esperados:

- `nproc` mostra 1 CPU; a memoria total fica um pouco abaixo de 4096 MB, por causa da memoria reservada pelo sistema.
- Apache e MySQL aparecem como `active`.
- O `curl` mostra o HTML da pagina temporaria.
- O Git mostra o ultimo commit baixado do repositorio.
- A lista de controladores inclui `cpu`, `memory` e `io`.
- O comando `unshare` e o MySQL mostram suas versoes.

O MySQL ainda nao tem o banco nem o usuario da aplicacao. Nesta etapa, o acesso de verificacao usa `sudo mysql` dentro da VM.

Para sair da VM, execute `exit`.

## Atualizar e desligar

Depois de enviar novas alteracoes para o GitHub, execute no computador:

```powershell
vagrant provision
```

O provisionamento atualiza o clone usando `git pull --ff-only` e recria a pagina temporaria do Apache.

Para desligar sem apagar os dados:

```powershell
vagrant halt
```

Para ligar novamente:

```powershell
vagrant up
```

Os dados ficam no disco da VM e continuam disponiveis apos desligar e ligar. O comando `vagrant destroy` apaga a VM e seus dados.

## Criar ambientes com limites

Com a VM atualizada pelo `vagrant provision`, entre com `vagrant ssh` e execute:

```bash
cd /opt/cloud-execution-manager
sudo python3 ambientes.py exemplo --cpu 50 --memoria 128 --io 5
sudo python3 ambientes.py outro --cpu 25 --memoria 64 --io 2
```

Os dois ambientes ficam ativos simultaneamente. O comando retorna um JSON com o nome, a unidade do systemd, a pasta de trabalho, o caminho do cgroup e os limites escolhidos.

Unidades e valores aceitos:

| Campo | Significado | Valores |
| --- | --- | --- |
| `nome` | Identificador e hostname do ambiente | Ate 30 letras minusculas, numeros ou hifens; comeca com letra |
| `cpu` | Tempo maximo de CPU, relativo a um nucleo | 1 a 100 por cento |
| `memoria` | Limite de memoria RAM | 32 a 2048 MiB |
| `io` | Limite de leitura e, separadamente, de escrita no disco da pasta de trabalho | 1 a 100 MiB/s |

Essas faixas sao escolhas da implementacao para a VM de 4 GB. Um MiB equivale a 1048576 bytes. Os limites sao tetos de consumo, nao reservas de recursos; a soma dos limites dos ambientes pode ultrapassar os recursos disponiveis na VM.

O `unshare` cria namespaces de processos (PID), hostname (UTS), comunicacao entre processos (IPC) e montagem de sistemas de arquivos (mount). Cada ambiente tem seu proprio `/proc`. O disco e a rede da VM continuam compartilhados: esta etapa nao cria um sistema de arquivos raiz separado nem um namespace de rede.

O systemd, ja instalado no Ubuntu, cria o cgroup de cada ambiente. `CPUQuota` define o limite de CPU, `MemoryMax` define a memoria e `MemorySwapMax=0` impede que swap seja usado para ultrapassar esse limite. `IOReadBandwidthMax` e `IOWriteBandwidthMax` limitam o dispositivo de disco que armazena a pasta de trabalho. O cache de arquivos pode afetar medicoes de I/O; esse limite nao controla a rede nem outros dispositivos.

As opcoes usadas estao descritas nos manuais de [unshare](https://man7.org/linux/man-pages/man1/unshare.1.html) e [controle de recursos do systemd](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html).

Um processo Python em espera mantem cada ambiente vivo, trata o sinal de encerramento e recolhe processos filhos que terminarem. O processo interno avisa ao systemd quando os namespaces e o hostname estao prontos. A execucao dos programas sera acrescentada na proxima etapa. Estes ambientes sao temporarios e nao sao recriados automaticamente ao reiniciar a VM; as pastas no disco permanecem.

### Conferir namespaces e cgroups

Dentro da VM, consulte os ambientes:

```bash
systemctl list-units 'cloud-ambiente-*.service'
sudo systemctl show cloud-ambiente-exemplo.service -p ControlGroup -p MainPID
```

Leia os limites efetivos no cgroup:

```bash
GRUPO=$(systemctl show cloud-ambiente-exemplo.service -p ControlGroup --value)
sudo cat "/sys/fs/cgroup$GRUPO/cpu.max"
sudo cat "/sys/fs/cgroup$GRUPO/memory.max"
sudo cat "/sys/fs/cgroup$GRUPO/memory.swap.max"
sudo cat "/sys/fs/cgroup$GRUPO/io.max"
```

Para o ambiente `exemplo`, `cpu.max` deve indicar uma quota equivalente a 50% do periodo, `memory.max` deve ser `134217728`, `memory.swap.max` deve ser `0`, e `io.max` deve conter `rbps=5242880` e `wbps=5242880`.

O processo principal do servico e o `unshare`. O filho dele e o processo que fica com PID 1 no novo namespace. Para conferir o hostname e a lista de processos internos:

```bash
SUPERVISOR=$(systemctl show cloud-ambiente-exemplo.service -p MainPID --value)
INICIO=$(sudo cat "/proc/$SUPERVISOR/task/$SUPERVISOR/children" | awk '{print $1}')
sudo nsenter --target "$INICIO" --mount --uts --ipc --pid hostname
sudo nsenter --target "$INICIO" --mount --uts --ipc --pid ps -ef
hostname
```

O primeiro hostname deve ser `exemplo`, e o ultimo deve continuar sendo `cloud-execution-manager`. A lista interna mostra o `python3` como PID 1 e nao lista os servicos da VM.

Para verificar as validacoes, repita a criacao de `exemplo`, use `--cpu 0` ou um nome como `../teste`. Esses casos devem ser recusados.

Para encerrar os ambientes de teste:

```bash
sudo systemctl stop cloud-ambiente-exemplo.service cloud-ambiente-outro.service
```

As pastas de trabalho ficam preservadas. A consulta de status e os comandos de encerramento e remocao pela aplicacao serao feitos nas proximas etapas.

### Integracao com a aplicacao web

A funcao `criar_ambiente(nome, cpu, memoria, io)` concentra a criacao e retorna um dicionario. A aplicacao tambem podera chamar a linha de comando com uma lista de argumentos e interpretar o JSON retornado. Os numeros devem ser inteiros, nas unidades da tabela; os campos de retorno sao `nome`, `unidade`, `pasta`, `cgroup`, `cpu`, `memoria` e `io`.

A criacao de ambientes requer `sudo` dentro da VM. A permissao para chamadas pela aplicacao web ainda depende da integracao. O Apache nao possui acesso geral de sudo.
