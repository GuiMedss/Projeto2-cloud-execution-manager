const express = require("express");
const { consultar } = require("./banco");
const execucao = require("./execucao");

const PORTA = process.env.PORTA || 3000;
const ESTADOS = { em_execucao: "em execucao", terminado: "terminado", erro: "erro" };

// escapa texto antes de colocar no html
function esc(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// layout comum das paginas
function pagina(titulo, corpo) {
  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>${esc(titulo)} - Cloud Execution Manager</title>
  <style>
    body { font-family: sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; }
    nav a { margin-right: 1em; }
    table { border-collapse: collapse; width: 100%; margin: 1em 0; }
    th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
    label { display: block; margin: 0.5em 0; }
    .erro { color: #b00020; }
    .ok { color: #1b5e20; }
    pre { background: #f4f4f4; padding: 1em; overflow: auto; }
  </style>
</head>
<body>
  <h1>Cloud Execution Manager</h1>
  <nav><a href="/">Ambientes</a><a href="/scripts">Scripts</a></nav>
  ${corpo}
</body>
</html>`;
}

// valida os campos do formulario de ambiente; retorna os dados limpos e a lista de erros
function validar(corpo) {
  const erros = [];
  const nome = String(corpo.nome ?? "").trim();
  const comando = String(corpo.comando ?? "").trim();
  const scriptId = corpo.script_id ? Number(corpo.script_id) : null;
  const numero = (valor) => (/^\d+$/.test(String(valor ?? "").trim()) ? Number(valor) : NaN);
  const cpu = numero(corpo.cpu);
  const memoria = numero(corpo.memoria);
  const io = numero(corpo.io);

  if (!/^[a-z][a-z0-9-]{0,29}$/.test(nome)) {
    erros.push("nome: ate 30 letras minusculas, numeros ou hifens, comecando com letra");
  }
  if (!(cpu >= 1 && cpu <= 100)) erros.push("cpu: inteiro de 1 a 100 (% de um nucleo)");
  if (!(memoria >= 32 && memoria <= 2048)) erros.push("memoria: inteiro de 32 a 2048 (MiB)");
  if (!(io >= 1 && io <= 100)) erros.push("io: inteiro de 1 a 100 (MiB/s)");
  if (scriptId !== null && !Number.isInteger(scriptId)) erros.push("script invalido");
  if (scriptId === null && !comando) erros.push("escolha um script ou informe um comando");
  if (scriptId !== null && comando) erros.push("use apenas um: script ou comando");
  if (comando.length > 255 || /[\r\n]/.test(comando)) erros.push("comando: uma linha com ate 255 caracteres");

  return { dados: { nome, cpu, memoria, io, scriptId, comando }, erros };
}

function formularioAmbiente(valores, scripts) {
  const opcoes = scripts.map((s) =>
    `<option value="${s.id}"${String(valores.script_id) === String(s.id) ? " selected" : ""}>${esc(s.nome)}</option>`);
  return `<form method="post" action="/ambientes">
    <label>Nome <input name="nome" value="${esc(valores.nome)}" maxlength="30" required></label>
    <label>CPU (% de um nucleo, 1 a 100) <input name="cpu" type="number" min="1" max="100" value="${esc(valores.cpu)}" required></label>
    <label>Memoria (MiB, 32 a 2048) <input name="memoria" type="number" min="32" max="2048" value="${esc(valores.memoria)}" required></label>
    <label>I/O (MiB/s, 1 a 100) <input name="io" type="number" min="1" max="100" value="${esc(valores.io)}" required></label>
    <label>Script enviado
      <select name="script_id"><option value="">(nenhum)</option>${opcoes.join("")}</select>
    </label>
    <label>ou comando <input name="comando" value="${esc(valores.comando)}" size="40" maxlength="255"></label>
    <button>Criar ambiente</button>
  </form>`;
}

function tabelaAmbientes(ambientes) {
  if (!ambientes.length) return "<p>Nenhum ambiente ainda.</p>";
  const linhas = ambientes.map((a) => `<tr>
      <td>${esc(a.nome)}</td>
      <td>${a.cpu}%</td>
      <td>${a.memoria} MiB</td>
      <td>${a.io} MiB/s</td>
      <td>${esc(a.script_nome || a.comando)}</td>
      <td>${ESTADOS[a.estado]}</td>
    </tr>`);
  return `<table>
    <tr><th>Nome</th><th>CPU</th><th>Memoria</th><th>I/O</th><th>Programa</th><th>Estado</th></tr>
    ${linhas.join("")}
  </table>`;
}

async function paginaAmbientes({ valores = {}, erros = [], msg = "" } = {}) {
  const scripts = await consultar("SELECT id, nome FROM scripts ORDER BY nome");
  const ambientes = await consultar(
    `SELECT a.*, s.nome AS script_nome FROM ambientes a
     LEFT JOIN scripts s ON s.id = a.script_id ORDER BY a.id DESC`);
  const avisos = erros.map((e) => `<p class="erro">${esc(e)}</p>`).join("")
    + (msg ? `<p class="ok">${esc(msg)}</p>` : "");
  return pagina("Ambientes", `<h2>Novo ambiente</h2>${avisos}${formularioAmbiente(valores, scripts)}
    <h2>Ambientes</h2>${tabelaAmbientes(ambientes)}`);
}

const app = express();
app.use(express.urlencoded({ extended: false }));

app.get("/", async (req, res, next) => {
  try {
    res.send(await paginaAmbientes({ msg: req.query.msg }));
  } catch (erro) { next(erro); }
});

app.post("/ambientes", async (req, res, next) => {
  try {
    const { dados, erros } = validar(req.body);
    let script = null;
    if (!erros.length && dados.scriptId !== null) {
      [script] = await consultar("SELECT id, caminho FROM scripts WHERE id = ?", [dados.scriptId]);
      if (!script) erros.push("script nao encontrado");
    }
    if (!erros.length) {
      const [existente] = await consultar("SELECT id FROM ambientes WHERE nome = ?", [dados.nome]);
      if (existente) erros.push("ja existe um ambiente com esse nome");
    }
    if (!erros.length) {
      try {
        const r = await execucao.criar({
          nome: dados.nome, cpu: dados.cpu, memoria: dados.memoria, io: dados.io,
          script: script && script.caminho, comando: dados.comando,
        });
        await consultar(
          `INSERT INTO ambientes (nome, cpu, memoria, io, script_id, comando, estado, unidade, pasta, cgroup, saida)
           VALUES (?, ?, ?, ?, ?, ?, 'em_execucao', ?, ?, ?, ?)`,
          [dados.nome, dados.cpu, dados.memoria, dados.io, dados.scriptId, dados.comando || null,
            r.unidade, r.pasta, r.cgroup, r.saida]);
        return res.redirect(`/?msg=${encodeURIComponent(`ambiente ${dados.nome} criado`)}`);
      } catch (erro) {
        erros.push(erro.message);
      }
    }
    res.status(400).send(await paginaAmbientes({ valores: req.body, erros }));
  } catch (erro) { next(erro); }
});

app.get("/scripts", (req, res) => {
  res.send(pagina("Scripts", "<h2>Scripts</h2><p>Nenhum script ainda.</p>"));
});

app.use((erro, req, res, next) => {
  console.error(erro);
  res.status(500).send(pagina("Erro", `<p class="erro">erro interno: ${esc(erro.message)}</p>`));
});

app.listen(PORTA, "0.0.0.0", () => {
  console.log(`aplicacao ouvindo na porta ${PORTA}`);
});
