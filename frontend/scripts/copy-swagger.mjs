// Copies Swagger UI (swagger-ui-dist, Apache-2.0) into the backend, which serves
// /api/docs with it: the docs page then loads nothing from a CDN (ADR 0001).
// Runs after `npm install`; the copies are not in Git (.gitignore).
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = join(here, "..", "node_modules", "swagger-ui-dist");
const target = join(here, "..", "..", "backend", "app", "static", "swagger");
const files = ["swagger-ui-bundle.js", "swagger-ui.css", "favicon-32x32.png", "LICENSE"];

if (!existsSync(source)) {
  console.warn("swagger-ui-dist is not installed: /api/docs will say how to get it.");
  process.exit(0);
}
mkdirSync(target, { recursive: true });
for (const file of files) {
  copyFileSync(join(source, file), join(target, file));
}
console.log(`Swagger UI copied to ${target}`);
