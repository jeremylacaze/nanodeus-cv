// Thème choisi par le visiteur : sombre, clair ou beige. Chargé dans <head> sans
// defer, il pose data-theme sur <html> avant le premier affichage. Sans choix,
// la feuille de style suit le système. Le choix reste dans le navigateur
// (localStorage), jamais envoyé au serveur ; « Système » l'efface.
(function () {
  "use strict";
  var THEMES = ["sombre", "clair", "beige"];
  var CLE = "theme";
  var racine = document.documentElement;

  function lire() {
    try {
      var theme = localStorage.getItem(CLE);
      return THEMES.indexOf(theme) >= 0 ? theme : null;
    } catch (e) { return null; }   // stockage bloqué : on suit le système
  }

  function appliquer(theme) {
    if (theme) { racine.setAttribute("data-theme", theme); }
    else { racine.removeAttribute("data-theme"); }
  }

  function enregistrer(theme) {
    try {
      if (theme) { localStorage.setItem(CLE, theme); } else { localStorage.removeItem(CLE); }
    } catch (e) { /* choix gardé pour cette page seulement */ }
  }

  appliquer(lire());

  document.addEventListener("DOMContentLoaded", function () {
    var choix = document.querySelector('[data-action="theme"]');
    if (!choix) { return; }
    choix.value = lire() || "systeme";
    choix.addEventListener("change", function () {
      var theme = THEMES.indexOf(choix.value) >= 0 ? choix.value : null;
      appliquer(theme);
      enregistrer(theme);
    });
    choix.parentNode.hidden = false;
  });

  // Retour arrière depuis le cache de page : le choix a pu changer sur une autre page.
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) { return; }
    var theme = lire();
    appliquer(theme);
    var choix = document.querySelector('[data-action="theme"]');
    if (choix) { choix.value = theme || "systeme"; }
  });
})();
