#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

REPOSITORIO="https://github.com/GuiMedss/Projeto2-cloud-execution-manager.git"
PASTA_PROJETO="/opt/cloud-execution-manager"

# instala os servicos e as ferramentas usadas no projeto
apt-get update
apt-get install -y apache2 mysql-server git curl python3 util-linux

# baixa o codigo e permite atualizar ao repetir o provisionamento
if [ -d "$PASTA_PROJETO/.git" ]; then
  git -C "$PASTA_PROJETO" pull --ff-only origin main
else
  git clone --branch main "$REPOSITORIO" "$PASTA_PROJETO"
fi

# confirma que a vm usa cgroups v2 para os limites de recursos
if [ ! -f /sys/fs/cgroup/cgroup.controllers ]; then
  echo "erro: a vm precisa usar cgroups v2."
  exit 1
fi

# prepara a pasta de trabalho dos ambientes no disco da vm
mkdir -p /var/lib/cloud-execution-manager

# esta pagina serve para conferir o acesso ao servidor web
cat > /var/www/html/index.html <<'HTML'
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Cloud Execution Manager</title>
</head>
<body>
  <h1>Cloud Execution Manager</h1>
  <p>A VM e o Apache estao funcionando.</p>
  <p>A interface de gerenciamento sera adicionada nas proximas etapas.</p>
</body>
</html>
HTML

# instala o node 20 para a aplicacao web
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 18 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

# usuario sem login que executa a aplicacao web
id cloudapp >/dev/null 2>&1 || useradd --system --home-dir "$PASTA_PROJETO" --shell /usr/sbin/nologin cloudapp

# instala as dependencias da aplicacao
(cd "$PASTA_PROJETO/app" && npm ci --omit=dev --no-audit --no-fund)

# pasta dos scripts enviados pela aplicacao, no disco da vm
mkdir -p /var/lib/cloud-scripts
chown cloudapp:cloudapp /var/lib/cloud-scripts

# senha do banco gerada uma vez e guardada fora do repositorio
ARQUIVO_ENV="/etc/cloud-execution-manager.env"
if [ ! -f "$ARQUIVO_ENV" ]; then
  echo "DB_SENHA=$(openssl rand -hex 16)" > "$ARQUIVO_ENV"
  chmod 600 "$ARQUIVO_ENV"
fi
SENHA_DB=$(grep '^DB_SENHA=' "$ARQUIVO_ENV" | cut -d= -f2)

# cria o banco, as tabelas e o usuario da aplicacao
systemctl enable --now mysql
mysql < "$PASTA_PROJETO/app/schema.sql"
mysql -e "CREATE USER IF NOT EXISTS 'cloudapp'@'localhost' IDENTIFIED BY '$SENHA_DB';
ALTER USER 'cloudapp'@'localhost' IDENTIFIED BY '$SENHA_DB';
GRANT ALL ON cloud_execution_manager.* TO 'cloudapp'@'localhost';"

# servico systemd da aplicacao web
cat > /etc/systemd/system/cloud-app.service <<'UNIT'
[Unit]
Description=cloud execution manager (aplicacao web)
After=network.target mysql.service

[Service]
User=cloudapp
EnvironmentFile=/etc/cloud-execution-manager.env
WorkingDirectory=/opt/cloud-execution-manager/app
ExecStart=/usr/bin/node servidor.js
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable cloud-app
systemctl restart cloud-app

systemctl enable --now apache2 mysql

echo "provisionamento concluido. acesse http://localhost:3000"
