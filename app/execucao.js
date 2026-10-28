const { execFile } = require("child_process");

// chama a parte de execucao (ambientes.py) com sudo e le o json da saida
// criar:    criar NOME --cpu=N --memoria=N --io=N (--script=CAMINHO | --comando=TEXTO)
// status:   status NOME     -> { nome, estado, saida, mensagem }
// encerrar: encerrar NOME   -> { nome, estado }
// remover:  remover NOME    -> { nome, removido }
// em caso de erro sai com codigo 1 e escreve "erro: mensagem" no stderr
const BASE = (process.env.EXECUCAO_CMD
  || "sudo -n /usr/bin/python3 /opt/cloud-execution-manager/ambientes.py").split(" ");

function chamar(args) {
  return new Promise((resolve, reject) => {
    execFile(BASE[0], [...BASE.slice(1), ...args], { timeout: 30000 }, (erro, stdout, stderr) => {
      if (erro) {
        const mensagem = stderr.trim().replace(/^erro:\s*/, "") || erro.message;
        return reject(new Error(mensagem));
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        reject(new Error(`resposta invalida da execucao: ${stdout.slice(0, 200)}`));
      }
    });
  });
}

// retorna { nome, unidade, pasta, cgroup, saida, cpu, memoria, io }
function criar({ nome, cpu, memoria, io, script, comando }) {
  const programa = script ? `--script=${script}` : `--comando=${comando}`;
  return chamar(["criar", nome, `--cpu=${cpu}`, `--memoria=${memoria}`, `--io=${io}`, programa]);
}

const status = (nome) => chamar(["status", nome]);
const encerrar = (nome) => chamar(["encerrar", nome]);
const remover = (nome) => chamar(["remover", nome]);

module.exports = { criar, status, encerrar, remover };
