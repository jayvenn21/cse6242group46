/**
 * Build step for Vercel: copy frontend + data into public/ (same URL layout
 * as serving from repo root: /frontend, /data, /baselines, /outputs).
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const out = path.join(root, "public");

function rmrf(p) {
  if (fs.existsSync(p)) {
    fs.rmSync(p, { recursive: true, force: true });
  }
}

function copyDir(src, dest) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.cpSync(src, dest, { recursive: true });
}

rmrf(out);
fs.mkdirSync(path.join(out, "data", "processed"), { recursive: true });
fs.mkdirSync(path.join(out, "baselines", "outputs"), { recursive: true });
fs.mkdirSync(path.join(out, "outputs", "interpretability"), { recursive: true });

copyDir(path.join(root, "frontend"), path.join(out, "frontend"));
fs.copyFileSync(
  path.join(root, "data", "processed", "grid_cells.geojson"),
  path.join(out, "data", "processed", "grid_cells.geojson")
);
fs.copyFileSync(
  path.join(root, "baselines", "outputs", "model_results.csv"),
  path.join(out, "baselines", "outputs", "model_results.csv")
);
const intDir = path.join(root, "outputs", "interpretability");
for (const f of fs.readdirSync(intDir)) {
  fs.copyFileSync(
    path.join(intDir, f),
    path.join(out, "outputs", "interpretability", f)
  );
}

const indexHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="refresh" content="0; url=frontend/index.html" />
  <title>Fire risk explorer</title>
</head>
<body>
  <p><a href="frontend/index.html">Open the app</a></p>
</body>
</html>
`;
fs.writeFileSync(path.join(out, "index.html"), indexHtml);
console.log("Wrote", out);
