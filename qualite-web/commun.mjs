// Navigateur partagé par les contrôles. En CI (conteneur sans espace de noms
// utilisateur), Chrome ne démarre qu'avec --no-sandbox.
import puppeteer from "puppeteer";

export const PUBLIC = process.env.CV_PUBLIC ?? "http://127.0.0.1:18020";
export const ADMIN = process.env.CV_ADMIN ?? "http://localhost:18021";

export function lancer() {
  return puppeteer.launch({ args: process.env.CI ? ["--no-sandbox"] : [] });
}
