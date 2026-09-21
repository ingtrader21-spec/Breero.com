import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { afterEach, beforeEach, test } from "node:test";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const qualityPath = ".github/workflows/quality.yml";
const quality = readFileSync(join(root, qualityPath), "utf8");
const assertion = '          [[ "$DESIGN_SYSTEM_RESULT" == success ]]';
const mapping = "          DESIGN_SYSTEM_RESULT: ${{ needs.design-system-quality.result }}";
let fixture;

beforeEach(() => {
  fixture = mkdtempSync(join(tmpdir(), "breero-design-guard-"));
  for (const path of [
    "apps/web/app/enterprise-design-system.css",
    "apps/web/app/layout.tsx",
    "apps/web/components/app-shell.tsx",
    "apps/web/components/site-header.tsx",
    "apps/web/components/site-footer.tsx",
    "packages/ui/package.json",
    "packages/ui/src/index.ts",
    "packages/ui/src/marketplace.tsx",
    "packages/ui/src/marketplace.css",
    "packages/ui/src/marketplace.test.tsx",
    "docs/design-system.md",
    "docs/design-system-migration.md",
    "docs/marketplace-experience-system.md",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/workflows/design-system.yml",
    qualityPath,
  ]) {
    const destination = join(fixture, path);
    mkdirSync(dirname(destination), { recursive: true });
    copyFileSync(join(root, path), destination);
  }
});

afterEach(() => rmSync(fixture, { recursive: true, force: true }));

function checkWorkflow(source) {
  writeFileSync(join(fixture, qualityPath), source);
  return spawnSync(process.execPath, [join(root, "scripts/check-design-system.mjs")], {
    cwd: fixture,
    encoding: "utf8",
  });
}

test("accepts the checked-in aggregate gate", () => {
  const result = checkWorkflow(quality);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /DESIGN_SYSTEM_GUARD=PASS/);
});

for (const [name, replacement] of [
  ["echoed assertion", '          echo \'[[ "$DESIGN_SYSTEM_RESULT" == success ]]\''],
  ["commented assertion", `          # ${assertion.trim()}`],
  ["ignored assertion failure", `${assertion} || true`],
  ["unreachable assertion", `          if false; then\n${assertion}\n          fi`],
  ["assertion printed by a heredoc", `          cat <<'GATE'\n${assertion}\n          GATE`],
]) {
  test(`rejects an ${name}`, () => {
    assert.ok(quality.includes(assertion));
    const result = checkWorkflow(quality.replace(assertion, replacement));
    assert.equal(result.status, 1, result.stdout);
    assert.match(result.stderr, /fail the aggregate gate unless design-system-quality succeeds/);
  });
}

test("rejects an assertion in another job even when its text matches", () => {
  const result = checkWorkflow(quality.replace(assertion, "").replace(
    "  quality:\n",
    `  unrelated:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n${assertion}\n\n  quality:\n`,
  ));
  assert.equal(result.status, 1, result.stdout);
  assert.match(result.stderr, /fail the aggregate gate unless design-system-quality succeeds/);
});

test("rejects a result mapping in a different step", () => {
  const result = checkWorkflow(quality.replace(mapping, "").replace(
    "      - name: Enforce every applicable quality gate",
    `      - name: Unrelated step\n        env:\n${mapping}\n        run: echo result\n      - name: Enforce every applicable quality gate`,
  ));
  assert.equal(result.status, 1, result.stdout);
  assert.match(result.stderr, /map the design-system result into the aggregate environment/);
});

test("rejects an aggregate step that ignores failure", () => {
  const result = checkWorkflow(quality.replace(
    "      - name: Enforce every applicable quality gate",
    "      - name: Enforce every applicable quality gate\n        continue-on-error: true",
  ));
  assert.equal(result.status, 1, result.stdout);
  assert.match(result.stderr, /fail the aggregate gate unless design-system-quality succeeds/);
});
