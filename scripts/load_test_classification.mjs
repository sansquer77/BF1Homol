import { writeFile } from "node:fs/promises";

const args = Object.fromEntries(process.argv.slice(2).map((item) => {
  const [key, ...value] = item.split("=");
  return [key.replace(/^--/, ""), value.join("=")];
}));
const baseUrl = (args["base-url"] || "").replace(/\/$/, "");
const season = args.season || "2026";
const users = Number(args.users || 25);
const iterations = Number(args.iterations || 3);
const output = args.output || "load-test-classification.json";
const email = process.env.BF1_LOAD_EMAIL;
const password = process.env.BF1_LOAD_PASSWORD;

if (!baseUrl || !email || !password) {
  throw new Error("--base-url, BF1_LOAD_EMAIL e BF1_LOAD_PASSWORD são obrigatórios");
}

const login = await fetch(`${baseUrl}/api/v1/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json", Origin: baseUrl },
  body: JSON.stringify({ email, password }),
});
if (login.status !== 200) throw new Error(`Login recusado: HTTP ${login.status}`);
const cookies = login.headers.getSetCookie().map((value) => value.split(";", 1)[0]).join("; ");
const target = `${baseUrl}/api/v1/classification?season=${season}`;
const request = async () => {
  const started = performance.now();
  try {
    const response = await fetch(target, { headers: { Cookie: cookies } });
    const body = await response.arrayBuffer();
    return { status: response.status, duration_ms: performance.now() - started, bytes: body.byteLength };
  } catch (error) {
    return { status: 0, duration_ms: performance.now() - started, bytes: 0, error: error.name };
  }
};

const warmup = await request();
if (warmup.status !== 200) throw new Error(`Warm-up recusado: HTTP ${warmup.status}`);
const started = performance.now();
const samples = (await Promise.all(Array.from({ length: users }, async () => {
  const results = [];
  for (let index = 0; index < iterations; index += 1) results.push(await request());
  return results;
}))).flat();
const wallSeconds = (performance.now() - started) / 1000;
const durations = samples.map((sample) => sample.duration_ms).sort((a, b) => a - b);
const percentile = (value) => durations[Math.min(durations.length - 1, Math.max(0, Math.ceil(value * durations.length) - 1))];
const failures = samples.filter((sample) => sample.status !== 200);
const statusCounts = Object.fromEntries([...new Set(samples.map((sample) => sample.status))].sort().map((status) => [status, samples.filter((sample) => sample.status === status).length]));
const report = {
  target, virtual_users: users, iterations_per_user: iterations, requests: samples.length,
  wall_seconds: Number(wallSeconds.toFixed(3)), requests_per_second: Number((samples.length / wallSeconds).toFixed(3)),
  failures: failures.length, error_rate: Number((failures.length / samples.length).toFixed(6)),
  latency_ms: {
    min: Number(durations[0].toFixed(3)),
    mean: Number((durations.reduce((sum, value) => sum + value, 0) / durations.length).toFixed(3)),
    p50: Number(percentile(0.5).toFixed(3)), p95: Number(percentile(0.95).toFixed(3)),
    p99: Number(percentile(0.99).toFixed(3)), max: Number(durations.at(-1).toFixed(3)),
  },
  status_counts: statusCounts,
};
await writeFile(output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));
process.exitCode = failures.length ? 1 : 0;
