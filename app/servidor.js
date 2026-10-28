const express = require("express");

const PORTA = process.env.PORTA || 3000;

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

const app = express();
app.use(express.urlencoded({ extended: false }));

app.get("/", (req, res) => {
  res.send(pagina("Ambientes", "<h2>Ambientes</h2><p>Nenhum ambiente ainda.</p>"));
});

app.get("/scripts", (req, res) => {
  res.send(pagina("Scripts", "<h2>Scripts</h2><p>Nenhum script ainda.</p>"));
});

app.listen(PORTA, "0.0.0.0", () => {
  console.log(`aplicacao ouvindo na porta ${PORTA}`);
});

module.exports = { app, esc, pagina };
