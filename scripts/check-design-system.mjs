#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { extname } from "node:path";

const ROOT = process.cwd();
const REQUIRED_FILES = [
  "apps/web/app/enterprise-design-system.css",
  "packages/ui/src/marketplace.tsx",
  "packages/ui/src/marketplace.css",
  "packages/portal/src/styles.css",
  "packages/ui/src/marketplace.test.tsx",
  "docs/design-system.md",
  "docs/design-system-migration.md",
  "docs/marketplace-experience-system.md",
  "HORIZON-ADOPTION.md",
  "horizon/suite.json",
  ".github/CODEOWNERS",
  ".github/pull_request_template.md",
  ".github/workflows/design-system.yml",
  ".github/workflows/quality.yml",
];

const ALLOWED_STYLE_AUTHORITIES = new Set([
  "packages/ui/src/styles.css",
  "packages/ui/src/marketplace.css",
  "packages/portal/src/styles.css",
  "apps/web/app/globals.css",
  "apps/web/app/marketplace.css",
  "apps/web/app/brand.css",
  "apps/web/app/enterprise-design-system.css",
]);

const CODE_EXTENSIONS = new Set([".tsx", ".ts", ".jsx", ".js", ".css", ".scss"]);
const JSX_EXTENSIONS = new Set([".tsx", ".jsx"]);
const errors = [];

function git(args) {
  return execFileSync("git", args, { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
}

function read(path) {
  return readFileSync(path, "utf8");
}

function fail(message) {
  errors.push(message);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function stripJavaScriptComments(source) {
  let result = "";
  let state = "code";
  let quote = "";

  for (let index = 0; index < source.length; index += 1) {
    const current = source[index];
    const next = source[index + 1];

    if (state === "line-comment") {
      if (current === "\n") {
        result += current;
        state = "code";
      }
      continue;
    }

    if (state === "block-comment") {
      if (current === "*" && next === "/") {
        index += 1;
        state = "code";
      } else if (current === "\n") {
        result += current;
      }
      continue;
    }

    if (state === "string") {
      result += current;
      if (current === "\\") {
        if (next !== undefined) {
          result += next;
          index += 1;
        }
      } else if (current === quote) {
        state = "code";
        quote = "";
      }
      continue;
    }

    if (current === "/" && next === "/") {
      state = "line-comment";
      index += 1;
      continue;
    }

    if (current === "/" && next === "*") {
      state = "block-comment";
      index += 1;
      continue;
    }

    if (current === '"' || current === "'" || current === "`") {
      state = "string";
      quote = current;
      result += current;
      continue;
    }

    result += current;
  }

  return result;
}

function activeJavaScript(path) {
  return stripJavaScriptComments(existsSync(path) ? read(path) : "");
}

function hasSideEffectImport(source, specifier) {
  const escaped = escapeRegExp(specifier);
  return new RegExp(`^\\s*import\\s+["']${escaped}["']\\s*;?\\s*$`, "m").test(source);
}

function activeYaml(path) {
  return (existsSync(path) ? read(path) : "")
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("#"))
    .join("\n");
}

// Inspect the workflow's block-style YAML without adding an install dependency
// to this standalone CI guard. Unsupported layouts fail the checks below.
function yamlBlock(source, key, indent) {
  const lines = source.split("\n");
  const header = new RegExp(`^ {${indent}}${escapeRegExp(key)}:\\s*(.*)$`);
  const start = lines.findIndex((line) => header.test(line));
  if (start < 0) return { value: "", body: "" };
  let end = start + 1;
  while (end < lines.length && (!lines[end].trim() || lines[end].search(/\S/) > indent)) end += 1;
  return { value: lines[start].match(header)[1].trim(), body: lines.slice(start + 1, end).join("\n") };
}

function hasDesignAssertion(step) {
  if (!/^ {8}shell:\s*bash\s*$/m.test(step) || /^ {8}(?:if|continue-on-error):/m.test(step)) return false;
  const run = yamlBlock(step, "run", 8);
  if (!/^\|[+-]?$/.test(run.value)) return false;
  const commands = run.body.split("\n").map((line) => line.trim()).filter(Boolean);
  if (commands.shift() !== "set -euo pipefail") return false;

  // Only unconditional assertions may precede this check. This excludes quoted
  // text, heredocs, functions, branches and commands that disable errexit.
  for (const command of commands) {
    if (!/^\[\[\s*"\$[A-Z_]+"\s*==\s*success\s*\]\]\s*(?:#.*)?$/.test(command)) return false;
    if (/^\[\[\s*"\$DESIGN_SYSTEM_RESULT"\s*==\s*success\s*\]\]\s*(?:#.*)?$/.test(command)) return true;
  }
  return false;
}

for (const path of REQUIRED_FILES) {
  if (!existsSync(path)) fail(`missing required governance file: ${path}`);
}

const layout = activeJavaScript("apps/web/app/layout.tsx");
if (!hasSideEffectImport(layout, "@breero/ui/marketplace.css")) {
  fail("RootLayout must actively import the shared marketplace experience stylesheet");
}
if (!hasSideEffectImport(layout, "./enterprise-design-system.css")) {
  fail("RootLayout must actively import enterprise-design-system.css");
}
if (hasSideEffectImport(layout, "./horizon.css") || hasSideEffectImport(layout, "./horizon-compatibility.css")) {
  fail("RootLayout must not import a parallel Horizon stylesheet; Horizon rules belong in enterprise-design-system.css");
}
if (!layout.includes("data-horizon-root") || !layout.includes('data-horizon-theme="breero"')) {
  fail("RootLayout must register the converged Breero Horizon shell markers");
}
const enterpriseStyles = existsSync("apps/web/app/enterprise-design-system.css") ? read("apps/web/app/enterprise-design-system.css") : "";
if (!enterpriseStyles.includes("PAS-111 HORIZON SHELL CONVERGENCE") || !enterpriseStyles.includes(".hz-site-header")) {
  fail("enterprise-design-system.css must contain the folded Horizon shell authority");
}
if (!/^\s*import\s*\{[^}]*\bManrope\b[^}]*\}\s*from\s*["']next\/font\/google["']\s*;?/m.test(layout)) {
  fail("RootLayout must keep an active Manrope import from next/font/google");
}

const uiIndex = activeJavaScript("packages/ui/src/index.ts");
if (!/^\s*export\s+\*\s+from\s+["']\.\/marketplace["']\s*;?/m.test(uiIndex)) {
  fail("@breero/ui must actively export the shared marketplace primitives");
}

const uiPackage = existsSync("packages/ui/package.json") ? read("packages/ui/package.json") : "";
if (!uiPackage.includes('"./marketplace.css": "./src/marketplace.css"')) {
  fail("@breero/ui must publish the marketplace stylesheet export");
}

const shell = activeJavaScript("apps/web/components/app-shell.tsx");
if (!/<SiteHeader(?:\s|\/|>)/.test(shell) || !/<SiteFooter(?:\s|\/|>)/.test(shell)) {
  fail("AppShell must actively render the shared SiteHeader and SiteFooter");
}

const header = activeJavaScript("apps/web/components/site-header.tsx");
if (!/<Logo(?:\s|\/|>)/.test(header) || !/data-cta\s*=\s*["']header-request-service["']/.test(header)) {
  fail("SiteHeader must actively render the shared BREERO logo and truthful request-service CTA");
}
if (/href\s*=\s*["']\/booking["']/.test(header) || />\s*Book a service\s*</.test(header)) {
  fail("Global header must not promise booking while the accepted shell remains request-first");
}

const footer = activeJavaScript("apps/web/components/site-footer.tsx");
if (!/data-cta\s*=\s*["']footer-request-service["']/.test(footer)) {
  fail("SiteFooter must actively render the truthful request-service conversion action");
}

const codeowners = existsSync(".github/CODEOWNERS") ? read(".github/CODEOWNERS") : "";
if (!/^\/\.github\/workflows\/quality\.yml\s+@appolon1908-hue\s*$/m.test(codeowners)) {
  fail("CODEOWNERS must protect the aggregate required quality workflow");
}

const quality = activeYaml(".github/workflows/quality.yml");
const jobs = yamlBlock(quality, "jobs", 0).body;
const aggregate = yamlBlock(jobs, "quality", 2).body;
const needs = yamlBlock(aggregate, "needs", 4).body;
const steps = yamlBlock(aggregate, "steps", 4).body.split(/(?=^ {6}- )/m)
  .filter((step) => /^ {6}- /m.test(step))
  .map((step) => step.replace(/^ {6}- /, "        "));
const enforcingSteps = steps.filter(hasDesignAssertion);
const mapsDesignResult = (step) => /^ {10}DESIGN_SYSTEM_RESULT:\s*\$\{\{\s*needs\.design-system-quality\.result\s*\}\}\s*$/m
  .test(yamlBlock(step, "env", 8).body);
for (const [description, satisfied] of [
  ["define the design-system-quality job", Boolean(yamlBlock(jobs, "design-system-quality", 2).body)],
  ["require design-system-quality in the aggregate needs list", /^ {6}-\s+design-system-quality\s*$/m.test(needs)],
  ["map the design-system result into the aggregate environment", enforcingSteps.some(mapsDesignResult)],
  ["fail the aggregate gate unless design-system-quality succeeds", enforcingSteps.some(mapsDesignResult)
    && /^ {4}if:\s*always\(\)\s*$/m.test(aggregate) && !/^ {4}continue-on-error:/m.test(aggregate)],
]) {
  if (!satisfied) fail(`Required quality workflow must ${description}`);
}

let base = process.argv[2]?.trim();
if (!base || /^0+$/.test(base)) {
  try {
    base = git(["merge-base", "HEAD", "origin/main"]);
  } catch {
    base = "";
  }
}

let diff = "";
let changedFiles = [];
if (base) {
  try {
    diff = git(["diff", "--unified=0", `${base}...HEAD`, "--"]);
    changedFiles = git(["diff", "--name-only", `${base}...HEAD`, "--"])
      .split("\n")
      .filter(Boolean);
  } catch {
    diff = "";
    changedFiles = [];
  }
}

for (const path of changedFiles) {
  if (!JSX_EXTENSIONS.has(extname(path)) || !existsSync(path)) continue;
  const source = activeJavaScript(path);
  if (/\bstyle\s*=/.test(source)) {
    fail(`${path}: JSX style attributes are prohibited; use shared classes and tokens`);
  }
}

if (!diff) {
  console.log("DESIGN_GUARD_RANGE=STRUCTURAL_ONLY");
} else {
  console.log(`DESIGN_GUARD_BASE=${base}`);
  let currentFile = "";

  for (const line of diff.split("\n")) {
    if (line.startsWith("+++ b/")) {
      currentFile = line.slice(6);
      continue;
    }
    if (!line.startsWith("+") || line.startsWith("+++")) continue;
    if (!CODE_EXTENSIONS.has(extname(currentFile))) continue;

    const added = line.slice(1);

    if (/font-family\s*:/.test(added) && !ALLOWED_STYLE_AUTHORITIES.has(currentFile)) {
      fail(`${currentFile}: font-family must be controlled by the shared design system`);
    }

    const rawColor = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/;
    if (rawColor.test(added) && !ALLOWED_STYLE_AUTHORITIES.has(currentFile)) {
      fail(`${currentFile}: literal color added outside approved style/token authority`);
    }

    if (/\b(?:bg|text|border|ring)-(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/.test(added)) {
      fail(`${currentFile}: random palette utility added; use BREERO tokens/shared components`);
    }

    if (/\b(?:m|p|gap|w|h|top|right|bottom|left)-\[[^\]]+\]/.test(added)) {
      fail(`${currentFile}: arbitrary utility value added; use shared spacing/layout tokens`);
    }

    if (/\brounded-full\b/.test(added) && /apps\/web\/app\/.*page\.(t|j)sx?$|apps\/web\/components\//.test(currentFile)) {
      fail(`${currentFile}: new decorative pill geometry requires a design-system exception`);
    }

    if ((currentFile.startsWith("apps/web/") || currentFile.startsWith("packages/ui/")) &&
        /\.(css|scss)$/.test(currentFile) &&
        !ALLOWED_STYLE_AUTHORITIES.has(currentFile)) {
      fail(`${currentFile}: new/changed parallel stylesheet is outside approved authorities`);
    }
  }
}

if (errors.length) {
  console.error("DESIGN_SYSTEM_GUARD=FAIL");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log("DESIGN_SYSTEM_GUARD=PASS");
