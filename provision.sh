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

systemctl enable --now apache2 mysql

echo "provisionamento concluido. acesse http://localhost:8080"
