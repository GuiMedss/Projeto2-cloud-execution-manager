#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

REPOSITORIO="https://github.com/GuiMedss/Projeto2-cloud-execution-manager.git"
PASTA_PROJETO="/opt/cloud-execution-manager"

# instala os servicos e as ferramentas usadas no projeto
apt-get update
apt-get install -y apache2 mysql-server git curl python3 util-linux openssl

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

# a aplicacao so pode chamar o ambientes.py com sudo, sem senha
echo "cloudapp ALL=(root) NOPASSWD: /usr/bin/python3 $PASTA_PROJETO/ambientes.py *" > /etc/sudoers.d/cloudapp
chmod 440 /etc/sudoers.d/cloudapp
visudo -cf /etc/sudoers.d/cloudapp

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

# o apache recebe os acessos e encaminha para a aplicacao node
a2enmod proxy proxy_http
cat > /etc/apache2/sites-available/000-default.conf <<'APACHE'
<VirtualHost *:80>
    ServerName localhost
    ProxyRequests Off
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:3000/ retry=0
    ProxyPassReverse / http://127.0.0.1:3000/
</VirtualHost>
APACHE
apache2ctl configtest
systemctl enable --now apache2 mysql
systemctl restart apache2

echo "provisionamento concluido. acesse http://localhost:8080"
