import { existsSync, readFileSync, readdirSync } from "node:fs";
import { extname, join, relative, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const read = (path) => readFileSync(path, "utf8");
const fail = (message, details) => {
  console.error(message, details ?? "");
  process.exit(1);
};
const walk = (directory) => readdirSync(directory, { withFileTypes: true })
  .flatMap((entry) => entry.isDirectory()
    ? walk(join(directory, entry.name))
    : [join(directory, entry.name)]);
const duplicates = (values) => values.filter((value, index) => values.indexOf(value) !== index);

const manifest = JSON.parse(read(resolve(root, "content/image-manifest.json")));
const publicRoutes = JSON.parse(read(resolve(root, "content/public-routes.json")));
const imageSource = read(resolve(root, "content/images.ts"));
const imageDefinitions = [...imageSource.matchAll(/\s(\w+): image\("([^"]+)", "([^"]+)"\)/g)]
  .map(([, id, path, alt]) => ({ id, path, alt }));
const manifestDrift = manifest.filter((item, index) => JSON.stringify({
  id: item.id,
  path: item.path,
  alt: item.alt,
}) !== JSON.stringify(imageDefinitions[index]));
if (imageDefinitions.length !== manifest.length || manifestDrift.length) {
  fail("Image manifest and TypeScript definitions have drifted", {
    definitionCount: imageDefinitions.length,
    manifestCount: manifest.length,
    manifestDrift,
  });
}
const missingImages = manifest.filter((item) => !existsSync(
  resolve(root, "public", item.path.replace(/^\//, "")),
));
if (missingImages.length) fail("Missing marketing images:", missingImages.map((item) => item.path));

const sourceFiles = [
  ...walk(resolve(root, "app")),
  ...walk(resolve(root, "components")),
  ...walk(resolve(root, "content")),
].filter((file) => [".ts", ".tsx"].includes(extname(file)));

const forbidden = [
  "app.breero.com",
  "partners.breero.com",
  "ops.breero.com",
  "/partner/login",
  "/ops/login",
];
const forbiddenHits = sourceFiles.flatMap((file) => forbidden
  .filter((value) => read(file).includes(value))
  .map((value) => `${relative(root, file)}: ${value}`));
if (forbiddenHits.length) fail("Forbidden placeholder portal links:", forbiddenHits);

const obsoleteIdentity = ["Booked4" + "Seasons", "BREERO " + "Ltd.", "hello" + "@breero.com"];
const obsoleteIdentityHits = sourceFiles.flatMap((file) => obsoleteIdentity
  .filter((value) => read(file).toLowerCase().includes(value.toLowerCase()))
  .map((value) => `${relative(root, file)}: ${value}`));
if (obsoleteIdentityHits.length) fail("Obsolete public identity references:", obsoleteIdentityHits);

const placeholderLinks = [/href\s*=\s*["']#["']/g, /href\s*=\s*["']javascript:/gi];
const placeholderHits = sourceFiles.flatMap((file) => placeholderLinks.flatMap((pattern) => [
  ...read(file).matchAll(pattern),
].map((match) => `${relative(root, file)}: ${match[0]}`)));
if (placeholderHits.length) fail("Placeholder links:", placeholderHits);

const buttonTags = sourceFiles
  .filter((file) => !file.endsWith("brand-preview/page.tsx"))
  .flatMap((file) => [...read(file).matchAll(/<(?:button|Button)\b([^>]*)>/g)]
    .map((match) => ({ file: relative(root, file), tag: match[0], attributes: match[1] })));
const deadButtons = buttonTags.filter(({ attributes }) => !/(?:onClick\s*=|type\s*=\s*["']submit["']|disabled(?:\s|=|$)|loading\s*=)/.test(attributes));
if (deadButtons.length) fail(
  "Actionless buttons:",
  deadButtons.map((item) => `${item.file}: ${item.tag}`),
);

const pageFiles = walk(resolve(root, "app")).filter((file) => file.endsWith("page.tsx"));
const toRoute = (file) => {
  const route = relative(resolve(root, "app"), file)
    .replace(/\\/g, "/")
    .replace(/(^|\/)\([^/]+\)\//g, "$1")
    .replace(/\/page\.tsx$/, "/")
    .replace(/^page\.tsx$/, "/")
    .replace(/\/$/, "");
  return route ? `/${route}` : "/";
};
const staticRoutes = new Set(pageFiles.map(toRoute).filter((route) => !route.includes("[")));
const dynamicPrefixes = pageFiles
  .map(toRoute)
  .filter((route) => route.includes("["))
  .map((route) => route.slice(0, route.indexOf("/[")));
const hrefPattern = /(?:href\s*=\s*|href\s*:\s*)["'](\/[^"'#?]*)/g;
const links = sourceFiles.flatMap((file) => [...read(file).matchAll(hrefPattern)]
  .map((match) => ({
    file: relative(root, file),
    href: match[1].replace(/\/$/, "") || "/",
  })));
const brokenLinks = links.filter(({ href }) => !staticRoutes.has(href)
  && !dynamicPrefixes.some((prefix) => href.startsWith(`${prefix}/`)));
if (brokenLinks.length) fail("Broken internal marketing links:", brokenLinks);
const missingPublicRoutes = publicRoutes.filter((route) => !staticRoutes.has(route)
  && !dynamicPrefixes.some((prefix) => route.startsWith(`${prefix}/`)));
if (missingPublicRoutes.length) fail("Missing intended public routes:", missingPublicRoutes);

const ctaSource = read(resolve(root, "content/cta.ts"));
const ctaIds = [...ctaSource.matchAll(/\bid:\s*"([^"]+)"/g)].map(([, value]) => value);
const ctaLabels = [...ctaSource.matchAll(/\blabel:\s*"([^"]+)"/g)].map(([, value]) => value);
const ctaHrefs = [...ctaSource.matchAll(/\bhref:\s*"([^"]+)"/g)].map(([, value]) => value);
const ctaAnalytics = [...ctaSource.matchAll(/\banalytics:\s*"([^"]+)"/g)].map(([, value]) => value);
if (!ctaIds.length || new Set([ctaIds.length, ctaLabels.length, ctaHrefs.length, ctaAnalytics.length]).size !== 1) {
  fail("Every CTA must define id, label, href and analytics", {
    ids: ctaIds.length,
    labels: ctaLabels.length,
    hrefs: ctaHrefs.length,
    analytics: ctaAnalytics.length,
  });
}
const duplicateCtaIds = duplicates(ctaIds);
const duplicateAnalytics = duplicates(ctaAnalytics);
if (duplicateCtaIds.length || duplicateAnalytics.length) {
  fail("CTA identifiers and analytics events must be unique", {
    duplicateCtaIds,
    duplicateAnalytics,
  });
}
const misleadingReleaseLabels = ["Book a service", "Check availability"]
  .filter((label) => ctaLabels.includes(label));
if (misleadingReleaseLabels.length) {
  fail("Request-first release contains booking-first CTA labels", misleadingReleaseLabels);
}
if (!ctaSource.includes('label: "Request a service"') || !ctaSource.includes('href: "/request-service"')) {
  fail("The canonical request CTA is missing or routed incorrectly");
}

const ctaUsageCount = sourceFiles.reduce(
  (count, file) => count + [...read(file).matchAll(/data-cta\s*=/g)].length,
  0,
);
console.log(
  `Validated ${manifest.length} manifested images, ${links.length} internal links, `
  + `${buttonTags.length} actionable buttons, ${ctaIds.length} centralized CTAs, `
  + `${ctaUsageCount} CTA usages, and ${publicRoutes.length} intended public routes `
  + `across ${staticRoutes.size} static routes.`,
);
