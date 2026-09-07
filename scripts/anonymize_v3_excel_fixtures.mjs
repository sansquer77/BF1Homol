import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const fixturePasswordHash = "$2b$04$r.mdeGukB1b4FFqUP9IquOMh/Eda1S/4EDrvx19EYUgJnRp4zQ08q";
const sourceDir = process.argv[2];
const outputDir = process.argv[3];
if (!sourceDir || !outputDir) throw new Error("uso: node anonymize_v3_excel_fixtures.mjs SOURCE_DIR OUTPUT_DIR");

const sourceNames = [
  "access_logs_20260907_140041.xlsx", "apostas_20260907_140055.xlsx",
  "auth_sessions_20260907_140102.xlsx", "championship_bets_20260907_140108.xlsx",
  "championship_bets_log_20260907_140114.xlsx", "championship_results_20260907_140119.xlsx",
  "circuitos_f1_20260907_140125.xlsx", "financeiro_config_temporada_20260907_140131.xlsx",
  "financeiro_participantes_20260907_140138.xlsx", "hall_da_fama_20260907_140144.xlsx",
  "log_apostas_20260907_140151.xlsx", "login_attempts_20260907_140157.xlsx",
  "pilotos_20260907_140205.xlsx", "posicoes_participantes_20260907_140214.xlsx",
  "provas_20260907_140221.xlsx", "regras_20260907_140227.xlsx",
  "resultados_20260907_140234.xlsx", "temporadas_20260907_140241.xlsx",
  "temporadas_regras_20260907_140248.xlsx", "usuarios_20260907_140254.xlsx",
  "usuarios_status_historico_20260907_140300.xlsx",
];

function stable(kind, value, size = 10) {
  return crypto.createHash("sha256").update(`bf1-v4-fixture:${kind}:${String(value)}`).digest("hex").slice(0, size);
}

function uuidFromValue(value) {
  const hex = crypto.createHash("sha256").update(`bf1-v4-fixture:jti:${String(value)}`).digest("hex").slice(0, 32).split("");
  hex[12] = "5";
  hex[16] = ((parseInt(hex[16], 16) & 3) | 8).toString(16);
  const raw = hex.join("");
  return `${raw.slice(0, 8)}-${raw.slice(8, 12)}-${raw.slice(12, 16)}-${raw.slice(16, 20)}-${raw.slice(20)}`;
}

function anonymize(table, column, value) {
  if (value === null || value === undefined || value === "") return value;
  const col = String(column).toLowerCase();
  if (col === "senha_hash" || col === "password_hash") return fixturePasswordHash;
  if (col === "jti") return uuidFromValue(value);
  if (col === "ip_address") return `192.0.2.${parseInt(stable("ip", value, 2), 16) % 254 + 1}`;
  if (col === "email") return `fixture-${stable("email", value)}@example.invalid`;
  if (["nome", "user_nome", "apostador"].includes(col) &&
      ["usuarios", "access_logs", "championship_bets", "championship_bets_log", "log_apostas"].includes(table)) {
    return `Participante ${stable("name", value, 8)}`;
  }
  if (table === "access_logs" && col === "detalhes") return "fixture-redacted";
  if (table === "usuarios_status_historico" && col === "motivo") return "fixture-redacted";
  return value;
}

function jsonValue(value) {
  return value instanceof Date ? value.toISOString() : value;
}

await fs.mkdir(outputDir, { recursive: true });
const manifest = { format_version: 1, source_version: "3.x", generated_from: "V3 Excel per-table exports", tables: {} };

for (const filename of sourceNames) {
  const inputPath = path.join(sourceDir, filename);
  const table = filename.replace(/_\d{8}_\d{6}\.xlsx$/i, "");
  const inputBytes = await fs.readFile(inputPath);
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
  const sheetNames = workbook.worksheets.items.map((sheet) => sheet.name);
  if (sheetNames.length !== 1 || sheetNames[0] !== "data") throw new Error(`${filename}: aba data única esperada`);
  const sheet = workbook.worksheets.getItem("data");
  const used = sheet.getUsedRange();
  const values = used ? used.values : [];
  const headers = (values[0] || []).map((value) => String(value));
  const outputValues = values.map((row, rowIndex) => row.map((value, colIndex) =>
    rowIndex === 0 ? value : anonymize(table, headers[colIndex], value)
  ));
  if (used && outputValues.length) used.values = outputValues;
  workbook.recalculate();
  const inspect = await workbook.inspect({ kind: "sheet,table", sheetId: "data", range: used ? used.address : "A1:A1", maxChars: 1200, tableMaxRows: 3, tableMaxCols: 8 });
  if (!inspect.ndjson) throw new Error(`${filename}: inspeção vazia`);
  const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 20 }, maxChars: 1000 });
  if (errors.ndjson && errors.ndjson.includes('"match"')) throw new Error(`${filename}: erro de fórmula detectado`);
  const output = await SpreadsheetFile.exportXlsx(workbook);
  const outputPath = path.join(outputDir, `${table}.xlsx`);
  await output.save(outputPath);
  const logical = JSON.stringify(outputValues.map((row) => row.map(jsonValue)));
  manifest.tables[table] = {
    file: `${table}.xlsx`, sheet: "data", rows: Math.max(0, outputValues.length - 1), columns: headers,
    source_sha256: crypto.createHash("sha256").update(inputBytes).digest("hex"),
    logical_sha256: crypto.createHash("sha256").update(logical).digest("hex"),
  };
}

await fs.writeFile(path.join(outputDir, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
