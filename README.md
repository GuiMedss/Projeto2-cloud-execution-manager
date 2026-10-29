# Projeto 2 - Cloud Execution Manager

Projeto de Computacao em Nuvem para gerenciar ambientes de execucao pela web, usando namespaces e cgroups.

O projeto permite criar ambientes com namespaces e limites de CPU, memoria e I/O, executar programas e scripts, consultar a saida e controlar as execucoes. A aplicacao web usa MySQL para os registros e permite enviar scripts para reutilizacao.

## Arquivos

- `Vagrantfile`: define a VM, os recursos e a porta de acesso.
- `provision.sh`: instala os pacotes, clona o repositorio e inicia os servicos.
- `ambientes.py`: cria ambientes, executa programas e controla status, saida e encerramento.
- `app/`: aplicacao web em Node.js (`servidor.js`, `banco.js`, `execucao.js`, `schema.sql`).
- `.gitattributes`: mantem os scripts com finais de linha compativeis com Linux, mesmo no Windows.
- `.gitignore`: impede que os arquivos locais do Vagrant sejam enviados ao GitHub.

## Ambiente

- Ubuntu 22.04, com VirtualBox.
- 1 CPU e 4096 MB de memoria.
- Apache como servidor web.
- MySQL para o armazenamento permanente dos registros da aplicacao.
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

A pagina deve mostrar que a VM e o Apache estao funcionando. Essa pagina e temporaria. A aplicacao web fica em `http://localhost:3000`.

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

O provisionamento cria o banco e o usuario da aplicacao. O acesso de verificacao usa `sudo mysql` dentro da VM.

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
sudo python3 ambientes.py criar exemplo --cpu 50 --memoria 128 --io 5
sudo python3 ambientes.py criar outro --cpu 25 --memoria 64 --io 2
```

Os dois ambientes ficam ativos simultaneamente, aguardando um programa. O comando retorna um JSON com os dados do ambiente e seu status. O formato anterior, sem a palavra `criar`, continua funcionando.

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

Um processo Python com PID 1 mantem cada ambiente vivo e aguarda um pedido de execucao. Ele inicia o programa dentro dos namespaces e do cgroup que ja foram criados, espera o programa terminar e salva o resultado. Quando a execucao termina, os namespaces sao liberados e os arquivos de controle e saida continuam no disco. Os ambientes nao sao reiniciados automaticamente com a VM.

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
sudo python3 ambientes.py encerrar exemplo
sudo python3 ambientes.py remover outro
```

O encerramento preserva os arquivos para consulta. A remocao encerra os processos e apaga a pasta do ambiente, incluindo sua saida.

## Executar programas e consultar resultados

Dentro da VM, na pasta `/opt/cloud-execution-manager`:

```bash
sudo python3 ambientes.py criar tarefa --cpu 50 --memoria 128 --io 5
sudo python3 ambientes.py executar tarefa -- python3 -c "print('ola, mundo')"
sudo python3 ambientes.py status tarefa
sudo python3 ambientes.py saida tarefa
sudo python3 ambientes.py listar
```

A execucao ocorre em segundo plano. O envio do comando retorna sem esperar o programa terminar. Repita a consulta de status se a primeira resposta ainda indicar `em execucao`. O programa nao recebe entrada interativa pelo terminal.

Estados retornados no campo `status`:

| Status | Significado |
| --- | --- |
| `em execucao` | Ambiente ativo, aguardando um comando ou executando o programa |
| `terminado` | Programa concluido com codigo zero ou ambiente encerrado manualmente |
| `erro` | Programa falhou, nao pode ser iniciado ou o ambiente foi interrompido |

O campo `comando` fica nulo enquanto o ambiente aguarda um programa. `codigo_retorno` registra o codigo do processo quando disponivel. Em encerramentos manuais sem resultado do programa, `encerrado` fica verdadeiro e `codigo_retorno` permanece nulo.

Cada ambiente aceita uma execucao. Para executar novamente, crie outro ambiente ou remova o anterior antes de reutilizar o nome. Um comando pode iniciar varios programas, que herdam os mesmos limites. Exemplo com dois comandos em sequencia:

```bash
sudo python3 ambientes.py criar sequencia --cpu 50 --memoria 128 --io 5
sudo python3 ambientes.py executar sequencia -- bash -c 'hostname && echo concluido'
```

### Scripts e servicos

Um script salvo na VM pode ser executado pelo interpretador correspondente. A criacao e o envio pelo formulario pertencem a aplicacao web; o gerenciador recebe o caminho do arquivo:

```bash
sudo python3 ambientes.py criar script --cpu 50 --memoria 128 --io 5
sudo python3 ambientes.py executar script -- python3 /caminho/do/script.py
```

Para verificar uma execucao continua:

```bash
sudo python3 ambientes.py criar servico --cpu 25 --memoria 64 --io 2
sudo python3 ambientes.py executar servico -- bash -c 'while true; do echo "servico ativo"; sleep 2; done'
sudo python3 ambientes.py status servico
sudo python3 ambientes.py saida servico
sudo python3 ambientes.py encerrar servico
sudo python3 ambientes.py saida servico
sudo python3 ambientes.py remover servico
```

Servicos devem permanecer em primeiro plano dentro do ambiente. Quando o programa principal termina, os processos restantes sao encerrados junto com o ambiente. O encerramento manual tambem atinge os processos filhos; se necessario, o systemd forca a parada depois de dois segundos.

### Arquivos e erros

A pasta `/var/lib/cloud-execution-manager/NOME` guarda:

- `ambiente.json`: nome e configuracao do ambiente.
- `comando.json`: programa e argumentos solicitados.
- `resultado.json`: resultado da execucao, quando registrado.
- `saida.log`: saida padrao e erros, no mesmo arquivo.
- `encerrado`: marca de encerramento manual, quando nao ha resultado do programa.

Esses registros sao usados pelo controle de execucao e nao substituem as tabelas MySQL da aplicacao web. Os arquivos permanecem apos desligar a VM. Uma execucao interrompida sem resultado registrado aparece como `erro` ao consultar novamente.

O comando `saida` retorna o conteudo atual de `saida.log` em JSON, inclusive com o programa em execucao. Programas Python recebem `PYTHONUNBUFFERED=1` para disponibilizar as mensagens sem esperar o buffer encher. Outros programas podem precisar de sua propria opcao de saida sem buffer.

Exemplo de erro com codigo de retorno conhecido:

```bash
sudo python3 ambientes.py criar falha --cpu 50 --memoria 128 --io 5
sudo python3 ambientes.py executar falha -- bash -c 'echo erro-de-teste >&2; exit 3'
sudo python3 ambientes.py status falha
sudo python3 ambientes.py saida falha
```

Ao concluir, o status deve ser `erro`, o codigo deve ser `3` e a mensagem deve aparecer na saida. Os arquivos podem ser consultados ate a remocao do ambiente. Scripts reutilizaveis devem ficar fora das pastas dos ambientes para serem preservados ao remover uma execucao.

### Integracao com a aplicacao web

As funcoes disponiveis em `ambientes.py` sao:

| Funcao | Uso |
| --- | --- |
| `criar_ambiente(nome, cpu, memoria, io)` | Cria um ambiente e retorna seus dados |
| `executar_programa(nome, comando)` | Recebe uma lista com o programa e seus argumentos |
| `consultar_ambiente(nome)` | Retorna os dados e o status atual |
| `listar_ambientes()` | Retorna uma lista com os ambientes registrados |
| `ler_saida(nome)` | Retorna nome e conteudo da saida |
| `encerrar_ambiente(nome)` | Encerra a execucao e preserva os arquivos |
| `remover_ambiente(nome)` | Encerra e apaga os dados do ambiente |

A aplicacao pode importar as funcoes em Python ou chamar a linha de comando com uma lista de argumentos e interpretar o JSON de resposta. O comando `executar` recebe os argumentos depois de `--`, sem montar uma string para o shell. Para usar operadores como `&&`, e necessario chamar `bash -c` explicitamente.

Os dados do ambiente incluem `nome`, `unidade`, `pasta`, `cgroup`, `cpu`, `memoria`, `io`, `comando`, `status`, `codigo_retorno`, `erro` e `encerrado`. Um erro na chamada do gerenciador e informado em `stderr`, com codigo de saida 1. O codigo de retorno do programa executado aparece no JSON de status, pois a execucao e assincrona.

Para a interface web, a resposta tambem inclui `estado` (com `em_execucao` no lugar de `em execucao`), `mensagem` e `saida` (caminho do arquivo de log). O subcomando `saida` continua retornando o conteudo do arquivo. A criacao aceita `--comando=TEXTO` ou `--script=CAMINHO` para criar e executar em uma chamada.

A criacao de ambientes requer `sudo` dentro da VM. A aplicacao web chama o script pelo usuario `cloudapp`, que tem permissao de sudo apenas para o `ambientes.py` (veja a secao Aplicacao web). O Apache nao possui acesso geral de sudo.

## Aplicacao web

A aplicacao usa Node.js 20, Express, `mysql2` e `multer`. O provisionamento instala tudo, cria o banco, as tabelas e o usuario do MySQL, e inicia o servico `cloud-app`, executado pelo usuario `cloudapp`. Depois do `vagrant up`, basta abrir:

```text
http://localhost:3000
```

A senha do usuario do MySQL e gerada no primeiro provisionamento e fica em `/etc/cloud-execution-manager.env`, fora do repositorio.

### Paginas

- `Ambientes` (`/`): formulario de criacao (nome, CPU, memoria, I/O e um script ja enviado ou um comando), botao de atualizar o status e tabela com os ambientes. Cada linha tem os botoes de ver a saida, encerrar e remover.
- `Scripts` (`/scripts`): envio de arquivos `.py` ou `.sh` de ate 1 MB e lista dos scripts enviados. O link "usar em novo ambiente" abre o formulario de criacao com o script selecionado.
- Saida (`/ambientes/<id>/saida`): mostra os ultimos 64 KB do arquivo de saida e pode ser atualizada enquanto o servico continua rodando.

### Banco e arquivos

O banco `cloud_execution_manager` tem duas tabelas, criadas por `app/schema.sql`:

- `scripts`: `nome` original, `caminho` do arquivo no disco e `tamanho`. Os arquivos ficam em `/var/lib/cloud-scripts` e podem ser usados em varios ambientes.
- `ambientes`: `nome`, `cpu`, `memoria`, `io`, `script_id` ou `comando`, `estado` (`em_execucao`, `terminado` ou `erro`), `unidade`, `pasta`, `cgroup`, `saida` e `mensagem`. Esses campos guardam o que a execucao retorna ao criar e consultar.

O estado salvo so muda quando alguem clica em atualizar, abre a saida, encerra ou remove o ambiente. Ao remover com sucesso, o registro do ambiente e apagado.

### Contrato com a execucao

O ambiente e identificado pelo `nome`, que e unico. Unidades: `cpu` em porcentagem de um nucleo (1 a 100), `memoria` em MiB (32 a 2048) e `io` em MiB/s (1 a 100), as mesmas do `ambientes.py`. A aplicacao valida esses campos antes de chamar a execucao.

O arquivo `app/execucao.js` chama `sudo -n /usr/bin/python3 /opt/cloud-execution-manager/ambientes.py` com os argumentos abaixo, sem shell. O stdout deve ser um JSON. Em caso de erro, o programa sai com codigo 1 e escreve `erro: mensagem` no stderr; a aplicacao mostra essa mensagem.

| Acao | Chamada | Retorno |
| --- | --- | --- |
| criar | `criar NOME --cpu=N --memoria=N --io=N --script=CAMINHO` ou `--comando=TEXTO` | `nome`, `unidade`, `pasta`, `cgroup`, `saida`, `cpu`, `memoria`, `io` |
| consultar | `status NOME` | `nome`, `estado` (`em_execucao`, `terminado` ou `erro`), `saida`, `mensagem` (opcional) |
| encerrar | `encerrar NOME` | `nome`, `estado` |
| remover | `remover NOME` | `nome`, `removido` |

Combinados que a aplicacao assume:

- `saida` e o caminho do arquivo onde o ambiente grava a saida, legivel pelo usuario `cloudapp`.
- `script` e o caminho de um `.py` ou `.sh` em `/var/lib/cloud-scripts`; a execucao escolhe o interpretador pela extensao.
- `remover` tambem encerra o ambiente se ele ainda estiver rodando, limpa os recursos e nao falha se o ambiente ja nao existir.
- O `sudoers` criado no provisionamento so permite que `cloudapp` execute esse `ambientes.py`, com qualquer argumento.

### Como verificar

Dentro da VM:

```bash
systemctl is-active cloud-app
sudo journalctl -u cloud-app -n 20
sudo mysql -e "SELECT id, nome, estado FROM cloud_execution_manager.ambientes;"
ls -l /var/lib/cloud-scripts
```

Fluxo de teste pela interface: enviar um script, criar dois ambientes (um usando o script e outro com um comando), clicar em atualizar, abrir a saida de um servico que continua rodando, encerrar um ambiente e remover os dois.
