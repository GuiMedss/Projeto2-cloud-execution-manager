const mysql = require("mysql2/promise");

// dados de conexao vem do ambiente configurado no provisionamento
const pool = mysql.createPool({
  host: process.env.DB_HOST || "localhost",
  user: process.env.DB_USUARIO || "cloudapp",
  password: process.env.DB_SENHA || "",
  database: process.env.DB_NOME || "cloud_execution_manager",
  connectionLimit: 5,
});

async function consultar(sql, params = []) {
  const [linhas] = await pool.query(sql, params);
  return linhas;
}

module.exports = { consultar };
