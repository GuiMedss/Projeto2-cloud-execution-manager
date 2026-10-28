CREATE DATABASE IF NOT EXISTS cloud_execution_manager CHARACTER SET utf8mb4;
USE cloud_execution_manager;

-- scripts enviados pelo usuario; o arquivo fica no disco da vm
CREATE TABLE IF NOT EXISTS scripts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  caminho VARCHAR(255) NOT NULL UNIQUE,
  tamanho INT NOT NULL,
  criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- cpu em % de um nucleo, memoria em MiB e io em MiB/s
CREATE TABLE IF NOT EXISTS ambientes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nome VARCHAR(30) NOT NULL UNIQUE,
  cpu INT NOT NULL,
  memoria INT NOT NULL,
  io INT NOT NULL,
  script_id INT NULL,
  comando VARCHAR(255) NULL,
  estado ENUM('em_execucao', 'terminado', 'erro') NOT NULL DEFAULT 'em_execucao',
  unidade VARCHAR(80) NULL,
  pasta VARCHAR(255) NULL,
  cgroup VARCHAR(255) NULL,
  saida VARCHAR(255) NULL,
  mensagem TEXT NULL,
  criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE RESTRICT
);
