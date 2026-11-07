// Accessibilité (WCAG 2 AA) par pa11y, avec axe et HTML_CodeSniffer. Le contraste
// dépend du thème : chaque page publique passe dans les trois, et en largeur de
// téléphone ; l'admin, en clair et en sombre (il suit le système), et en beige.
import pa11y from "pa11y";

import { ADMIN, PUBLIC, lancer } from "./commun.mjs";

const PUBLIQUES = ["/", "/en/", "/lead-tech", "/devops/contact", "/en/devops/contact", "/inconnue"];
const ADMINS = ["/admin/", "/admin/versions", "/admin/versions/1", "/admin/stock/parcours",
  "/admin/candidatures", "/admin/candidatures/nouvelle", "/admin/visites", "/admin/demandes",
  "/admin/profil"];
const BUREAU = { width: 1280, height: 900 };
const TELEPHONE = { width: 390, height: 844, isMobile: true, hasTouch: true };

const essais = [
  ...["clair", "sombre", "beige"].flatMap((theme) =>
    PUBLIQUES.map((chemin) => ({ url: PUBLIC + chemin, theme, viewport: BUREAU }))),
  ...PUBLIQUES.map((chemin) => ({ url: PUBLIC + chemin, theme: "clair", viewport: TELEPHONE })),
  ...[{ schema: "light" }, { schema: "dark" }, { theme: "beige" }].flatMap((variante) =>
    ADMINS.map((chemin) => ({ url: ADMIN + chemin, ...variante, viewport: BUREAU }))),
];

const navigateur = await lancer();
let fautes = 0;
const aRevoir = new Set();
try {
  for (const essai of essais) {
    const page = await navigateur.newPage();
    try {
      if (essai.theme) {
        await page.evaluateOnNewDocument((theme) => {
          try { localStorage.setItem("theme", theme); } catch { /* stockage bloqué */ }
        }, essai.theme);
      }
      await page.emulateMediaFeatures([
        { name: "prefers-color-scheme", value: essai.schema ?? "light" }]);
      const resultat = await pa11y(essai.url, {
        browser: navigateur, page, viewport: essai.viewport, runners: ["axe", "htmlcs"],
        standard: "WCAG2AA", timeout: 30000,
      });
      const nom = `${essai.url} [${essai.theme ?? essai.schema}, ${essai.viewport.width}px]`;
      // axe range en « à revoir » ce qu'il ne sait pas trancher (le glyphe ✓,
      // l'opacité animée du ●) ; pa11y le classe en erreur. Seules les violations
      // établies font échouer, les autres sont listées une fois à la fin.
      const erreurs = resultat.issues.filter((i) =>
        i.type === "error" && !i.runnerExtras?.needsFurtherReview);
      for (const i of resultat.issues) {
        if (i.runnerExtras?.needsFurtherReview) { aRevoir.add(`${i.code} : ${i.context}`); }
      }
      if (erreurs.length === 0) {
        console.log(`ok   ${nom}`);
        continue;
      }
      fautes += erreurs.length;
      console.log(`FAUX ${nom}`);
      for (const e of erreurs) {
        console.log(`     - [${e.runner}] ${e.code}\n       ${e.message}\n       ${e.selector}\n       ${e.context}`);
      }
    } finally {
      await page.close();
    }
  }
} finally {
  await navigateur.close();
}
if (aRevoir.size) {
  console.log(`\nÀ revoir à l'œil (axe n'a pas pu trancher) :\n  ${[...aRevoir].join("\n  ")}`);
}
console.log(fautes ? `\n${fautes} erreur(s) d'accessibilité.` : "\nAccessibilité : aucune erreur.");
process.exitCode = fautes ? 1 : 0;
