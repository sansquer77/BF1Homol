import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const source = process.env.BF1_OPENAPI_URL ?? fileURLToPath(new URL("../../api/openapi-v1.json", import.meta.url));
execFileSync("pnpm", ["exec", "openapi-typescript", source, "-o", "src/lib/api/schema.d.ts"], {
  cwd: new URL("..", import.meta.url),
  stdio: "inherit",
});
