# Projeto 2 - Cloud Execution Manager

Projeto de Computacao em Nuvem para criar e gerenciar ambientes de execucao pela web. Usa uma VM com Vagrant, Apache, Node.js, MySQL, namespaces e cgroups v2.

## Como executar

Instale o Vagrant e o VirtualBox. A configuracao usa um computador Intel ou AMD de 64 bits e reserva 1 CPU e 4096 MB de RAM para a VM. O computador precisa de memoria livre tambem para seu proprio sistema.

```powershell
git clone https://github.com/GuiMedss/Projeto2-cloud-execution-manager.git
cd Projeto2-cloud-execution-manager
vagrant validate
vagrant up --provider=virtualbox
```

Abra `http://localhost:8080`. O Apache encaminha as requisicoes para a aplicacao Node.js na porta 3000 da VM.

O primeiro provisionamento precisa de internet. Ele instala os pacotes, clona o repositorio em `/opt/cloud-execution-manager`, configura o banco e inicia os servicos. A pasta do computador nao e compartilhada com a VM.

## Como usar

1. Na pagina Scripts, envie um arquivo `.py` ou `.sh` de ate 1 MiB, salvo em UTF-8.
2. Na pagina Ambientes, informe nome, CPU, memoria e I/O.
3. Selecione um script enviado ou informe um comando, como `hostname && echo concluido`.
4. Crie o ambiente e clique em Atualizar status para acompanhar a execucao.
5. Abra a saida. A tela mostra os ultimos 64 KB; Baixar saida completa permite obter o arquivo inteiro.
6. Use Encerrar para parar os processos e preservar a saida. Use Remover para encerrar e apagar os dados daquele ambiente.

Um script enviado pode ser usado em varios ambientes. Os arquivos enviados ficam separados das pastas das execucoes e nao sao apagados ao remover um ambiente. Scripts Bash com BOM ou quebras de linha do Windows sao ajustados no upload.

O comando pode iniciar um programa ou varios comandos pelo Bash. A execucao acontece em segundo plano, sem entrada interativa pelo terminal. Servicos devem permanecer em primeiro plano dentro do ambiente; eles podem continuar rodando ate serem encerrados.

Cada ambiente aceita uma execucao. Para executar novamente, use outro nome ou remova o ambiente anterior. E possivel manter varios ambientes simultaneamente.

## Limites e estados

| Campo | Valores aceitos |
| --- | --- |
| Nome | Ate 30 letras minusculas, numeros ou hifens; comeca com letra |
| CPU | 1 a 100 por cento do tempo de um nucleo |
| Memoria | 32 a 2048 MiB de RAM, sem swap |
| I/O | 1 a 100 MiB/s de leitura e, separadamente, de escrita |

Um MiB equivale a 1048576 bytes. Os valores sao limites maximos, nao reservas de recursos. O limite de I/O atua no dispositivo de disco da pasta do ambiente, nao na rede; o cache pode afetar medicoes de velocidade.

| Estado | Significado |
| --- | --- |
| Em execucao | Ambiente ativo, aguardando ou executando um programa |
| Terminado | Programa terminou com codigo zero ou foi encerrado manualmente |
| Erro | Programa falhou, nao pode ser iniciado ou a execucao foi interrompida |

O status e consultado ao clicar em Atualizar status ou abrir a saida de um ambiente ainda nao terminado. A saida padrao e os erros sao gravados juntos em `saida.log`.

## Arquivos principais

- `Vagrantfile`: configura a VM, os recursos e as portas.
- `provision.sh`: instala e configura os componentes, incluindo o clone do GitHub.
- `ambientes.py`: controla ambientes, programas, limites, status, saida e remocao.
- `app/servidor.js`: recebe requisicoes e gera as paginas HTML.
- `app/execucao.js`: chama o Python e interpreta a resposta JSON.
- `app/banco.js`: conecta ao MySQL e executa as consultas.
- `app/schema.sql`: cria o banco e as tabelas.

O Node.js roda como `cloudapp`, um usuario sem login. Esse usuario tem permissao de sudo para chamar apenas o `ambientes.py`. Os processos gerenciados precisam de privilegios para criar namespaces e configurar os recursos.

O `systemd-run` cria um servico com cgroup e aplica `CPUQuota`, `MemoryMax`, `MemorySwapMax`, `IOReadBandwidthMax` e `IOWriteBandwidthMax`. O `unshare` cria namespaces de PID, UTS, IPC e mount. A rede e os arquivos do disco da VM continuam compartilhados.

Um processo Python com PID 1 aguarda o pedido, inicia o programa e recolhe os processos filhos que terminam. Quando o programa principal termina, os processos restantes sao encerrados e os namespaces sao liberados. A configuracao e o resultado continuam no disco ate a remocao.

## Armazenamento

- MySQL: banco `cloud_execution_manager`, com as tabelas `scripts` e `ambientes`.
- `/var/lib/cloud-scripts`: arquivos enviados pelo formulario.
- `/var/lib/cloud-execution-manager/NOME`: configuracao, pedido, resultado e `saida.log` de cada ambiente.
- `/etc/cloud-execution-manager.env`: senha do banco, gerada pelo provisionamento e mantida fora do repositorio.

Os JSON das pastas dos ambientes sao registros tecnicos do controle de execucao; nao substituem o banco da aplicacao web.

Ao desligar e ligar a VM, o banco, os scripts e as saidas permanecem. Os programas nao sao reiniciados automaticamente. Uma execucao interrompida sem resultado salvo aparece como erro na proxima consulta.

## Atualizar e desligar

Depois de enviar alteracoes ao GitHub:

```powershell
vagrant provision
```

O provisionamento executa `git pull --ff-only`, instala as dependencias e reinicia os servicos, preservando os dados existentes. Alteracoes feitas apenas no computador nao chegam a VM ate serem enviadas ao repositorio e carregadas pelo provisionamento.

```powershell
vagrant halt
vagrant up
```

`vagrant halt` desliga a VM sem apagar seus dados. `vagrant up` liga novamente. `vagrant destroy` apaga a VM e seus dados.

## Verificar pela VM

Entre com `vagrant ssh` e execute:

```bash
nproc
free -m
systemctl is-active apache2 mysql cloud-app
curl -f http://localhost
sudo git -C /opt/cloud-execution-manager log -1 --oneline
```

O resultado deve indicar 1 CPU, aproximadamente 4 GB de memoria e os tres servicos ativos. A memoria utilizavel fica um pouco abaixo dos 4096 MB por causa da parte reservada pelo sistema.

Para conferir os limites de um ambiente ainda em execucao:

```bash
cd /opt/cloud-execution-manager
sudo python3 ambientes.py criar verificacao --cpu 25 --memoria 64 --io 2 --comando "hostname; sleep 300"
GRUPO=$(systemctl show cloud-ambiente-verificacao.service -p ControlGroup --value)
sudo cat "/sys/fs/cgroup$GRUPO/cpu.max"
sudo cat "/sys/fs/cgroup$GRUPO/memory.max"
sudo cat "/sys/fs/cgroup$GRUPO/io.max"
sudo python3 ambientes.py status verificacao
sudo python3 ambientes.py encerrar verificacao
sudo python3 ambientes.py remover verificacao
```

A quota de CPU deve equivaler a 25% do periodo, a memoria deve ser `67108864` bytes e o I/O deve indicar `rbps=2097152` e `wbps=2097152`.

O gerenciador tambem aceita `executar NOME -- PROGRAMA ARGUMENTOS`, `listar` e `saida NOME`. Os comandos retornam JSON; uma falha na chamada escreve a mensagem em `stderr` e retorna codigo 1. O resultado do programa aparece no status, pois sua execucao e assincrona.

A interface usa o campo `estado` (`em_execucao`, `terminado` ou `erro`), `mensagem` e `saida` (caminho do log). O subcomando `saida` retorna o conteudo do arquivo. O campo `codigo_retorno` registra o resultado do programa quando disponivel; em uma parada manual ele pode permanecer nulo.

## Validacao

Os fluxos web, os limites de CPU, memoria e I/O, dois servicos simultaneos e a persistencia apos reiniciar a VM foram verificados em 29/10/2026. Tambem foram testados scripts Bash do Windows, falhas de cadastro no banco, recuperacao de status e limpeza dos processos.

O provisionamento e os fluxos web foram conferidos em uma VM limpa, com as alteracoes locais aplicadas para validacao antes do envio ao GitHub.

O acesso ao GitHub e aos repositorios de pacotes na rede da PUC precisa ser conferido no local. Antes da entrega, envie o commit final ao GitHub e atualize a VM com `vagrant provision`.
