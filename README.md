# Projeto 2 - Cloud Execution Manager

Projeto de Computacao em Nuvem para gerenciar ambientes de execucao pela web, usando namespaces e cgroups.

## Arquivos

- `Vagrantfile`: define a VM, os recursos e a porta de acesso.
- `provision.sh`: instala os pacotes, clona o repositorio e inicia os servicos.
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
2. Faca o commit inicial e envie os arquivos para a branch `main` do repositorio no GitHub. O repositorio precisa estar acessivel para o clone sem solicitar login dentro da VM.
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

O codigo e clonado em `/opt/cloud-execution-manager`. A pasta do computador nao e compartilhada com a VM: o codigo dentro dela vem do GitHub, conforme o enunciado.

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

O provisionamento atualiza o clone usando `git pull --ff-only`. Nesta etapa ele tambem recria a pagina temporaria do Apache. Quando a aplicacao web for implementada, esse trecho sera substituido pela configuracao dela.

Para desligar sem apagar os dados:

```powershell
vagrant halt
```

Para ligar novamente:

```powershell
vagrant up
```

Os dados ficam no disco da VM e continuam disponiveis apos desligar e ligar. O comando `vagrant destroy` apaga a VM e seus dados.
