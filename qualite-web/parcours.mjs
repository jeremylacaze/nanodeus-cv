// Comportement de la page dans Chromium : parcours cliquable (static/pipeline.js),
// liens directs, clavier, accordéon sur téléphone, sélecteur de thème et modale de
// contact. Aucune erreur JavaScript ni violation de la CSP n'est tolérée.
import { PUBLIC, lancer } from "./commun.mjs";

const navigateur = await lancer();
const fautes = [];
let page;

function verifier(condition, message) {
  console.log(`${condition ? "ok  " : "FAUX"} ${message}`);
  if (!condition) { fautes.push(message); }
}

async function ouvrir(chemin, viewport = { width: 1280, height: 900 }) {
  if (page) { await page.close(); }
  page = await navigateur.newPage();
  await page.setViewport(viewport);
  page.on("pageerror", (e) => fautes.push(`erreur JS sur ${chemin} : ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error") { fautes.push(`console sur ${chemin} : ${m.text()}`); }
  });
  await page.evaluateOnNewDocument(() => {
    window.__violations = [];
    document.addEventListener("securitypolicyviolation",
      (e) => window.__violations.push(`${e.violatedDirective} ${e.blockedURI}`));
  });
  const reponse = await page.goto(PUBLIC + chemin, { waitUntil: "networkidle0" });
  verifier(reponse.ok(), `${chemin} : HTTP ${reponse.status()}`);
}

// Clé du job ouvert ; null si aucun, "plusieurs" si plus d'un.
const ouverts = () => page.$$eval("button.job[aria-expanded=true]",
  (b) => (b.length > 1 ? "plusieurs" : b[0]?.dataset.cle ?? null));
const visibles = () => page.$$eval("section.detail",
  (d) => d.filter((x) => !x.hidden && x.offsetParent !== null).map((x) => x.id));
const cles = () => page.$$eval("button.job", (b) => b.map((x) => x.dataset.cle));
const violations = () => page.evaluate(() => window.__violations);

try {
  // --- Grand écran : un seul détail, celui du poste le plus récent. -------------
  await ouvrir("/devops");
  const toutes = await cles();
  const initial = await page.$eval(".pipeline", (p) => p.dataset.initial);
  verifier(toutes.length > 3, `${toutes.length} jobs dans le parcours`);
  verifier(await ouverts() === initial, `au chargement, le job initial (${initial}) est ouvert`);
  verifier(JSON.stringify(await visibles()) === JSON.stringify([`detail-${initial}`]),
    "un seul détail visible, le sien");

  const historique = await page.evaluate(() => history.length);
  await page.click(`button.job[data-cle="${toutes[0]}"]`);
  verifier(await ouverts() === toutes[0], "un clic ouvre le job cliqué");
  verifier(await page.evaluate(() => location.hash) === `#detail-${toutes[0]}`,
    "l'adresse porte l'ancre du job choisi");
  verifier(await page.evaluate(() => history.length) === historique, "sans entrée d'historique");

  // --- Clavier ----------------------------------------------------------------
  await page.focus(`button.job[data-cle="${toutes[0]}"]`);
  await page.keyboard.press("ArrowRight");
  verifier(await ouverts() === toutes[1], "→ passe au job suivant");
  verifier(await page.evaluate(() => document.activeElement.dataset.cle) === toutes[1],
    "… et y met le focus");
  await page.keyboard.press("End");
  verifier(await ouverts() === toutes.at(-1), "Fin : dernier job");
  await page.keyboard.press("Home");
  verifier(await ouverts() === toutes[0], "Début : premier job");
  await page.keyboard.press("ArrowLeft");
  verifier(await ouverts() === toutes[0], "← au premier job : reste en place");

  // --- Lien direct ------------------------------------------------------------
  await ouvrir(`/devops#detail-${toutes[1]}`);
  verifier(await ouverts() === toutes[1], "un lien direct ouvre son job");
  await page.click(`#detail-${toutes[1]} a.ancre`);
  verifier(await ouverts() === toutes[1], "le # du détail garde le job ouvert");
  await ouvrir("/devops#detail-inexistant");
  verifier(await ouverts() === initial, "une ancre inconnue retombe sur le job initial");

  // --- Téléphone : accordéon ----------------------------------------------------
  await ouvrir("/devops", { width: 390, height: 844, isMobile: true, hasTouch: true });
  const cible = toutes[0];
  await page.click(`button.job[data-cle="${cible}"]`);
  verifier(await ouverts() === cible, "téléphone : un tap ouvre le job");
  verifier(await page.$eval(`#detail-${cible}`,
    (d) => d.previousElementSibling?.matches("button.job") ?? false),
  "téléphone : le détail s'ouvre sous le job tapé");
  await page.click(`button.job[data-cle="${cible}"]`);
  verifier(await ouverts() === null, "téléphone : retaper le job le referme");
  verifier((await visibles()).length === 0, "téléphone : plus aucun détail visible");

  // --- Thème ------------------------------------------------------------------
  await ouvrir("/devops");
  verifier(await page.$eval(".theme", (t) => !t.hidden), "le sélecteur de thème est visible avec JS");
  await page.select('[data-action="theme"]', "beige");
  verifier(await page.$eval("html", (h) => h.dataset.theme) === "beige", "le thème choisi s'applique");
  await page.reload({ waitUntil: "networkidle0" });
  verifier(await page.$eval("html", (h) => h.dataset.theme) === "beige", "… et survit au rechargement");
  await page.select('[data-action="theme"]', "systeme");
  verifier(await page.$eval("html", (h) => !h.hasAttribute("data-theme")), "« Système » l'efface");

  // --- Modale de contact --------------------------------------------------------
  await page.click('[data-action="demander-acces"]');
  verifier(await page.$eval(".modale-contact", (m) => m.open), "« Demander l'accès » ouvre la modale");
  verifier(await page.evaluate(() => document.activeElement?.name) === "email",
    "… le focus va au champ email");
  await page.keyboard.press("Escape");
  verifier(await page.$eval(".modale-contact", (m) => !m.open), "Échap la referme");

  verifier((await violations()).length === 0, `aucune violation de CSP ${await violations()}`);
} finally {
  if (page) { await page.close(); }
  await navigateur.close();
}

for (const f of fautes.filter((f) => f.includes(" : ") && !f.startsWith("/"))) {
  console.log(`FAUX ${f}`);
}
console.log(fautes.length ? `\n${fautes.length} contrôle(s) en échec.` : "\nParcours : tout fonctionne.");
process.exitCode = fautes.length ? 1 : 0;
