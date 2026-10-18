// Modale « Demander l'accès ». Sans JavaScript (ou sans <dialog>), le lien du bas
// de page mène à la page de contact et le formulaire part en POST classique.
// Tous les textes viennent du serveur et sont posés par textContent.
(function () {
  "use strict";
  var modale = document.querySelector(".modale-contact");
  var lien = document.querySelector('[data-action="demander-acces"]');
  if (!modale || !lien || typeof modale.showModal !== "function") { return; }
  var formulaire = modale.querySelector("form");
  var bouton = formulaire.querySelector('button[type="submit"]');
  var retour = formulaire.querySelector(".retour");
  var confirmation = modale.querySelector(".confirmation");

  lien.addEventListener("click", function (e) {
    e.preventDefault();
    modale.showModal();
    // Ouverture comptée comme une visite du contact (204, sans réponse à lire).
    if (navigator.sendBeacon) { navigator.sendBeacon(formulaire.action + "/ouverture"); }
    formulaire.elements.email.focus();
  });

  modale.querySelector('[data-action="fermer-contact"]').addEventListener("click", function () {
    modale.close();
  });

  function poserErreurs(erreurs) {
    formulaire.querySelectorAll("[data-erreur]").forEach(function (p) {
      var nom = p.getAttribute("data-erreur");
      var champ = formulaire.elements[nom];
      p.textContent = erreurs[nom] || "";
      if (erreurs[nom]) { champ.setAttribute("aria-invalid", "true"); }
      else { champ.removeAttribute("aria-invalid"); }
    });
  }

  formulaire.addEventListener("submit", function (e) {
    e.preventDefault();
    if (bouton.disabled) { return; }   // double clic : une seule demande
    bouton.disabled = true;
    retour.textContent = "";
    fetch(formulaire.action, {
      method: "POST",
      body: new URLSearchParams(new FormData(formulaire)),
      headers: { Accept: "application/json" }
    }).then(function (r) {
      // 403 et 413 rendent une page HTML : r.json() échoue, d'où le message générique.
      return r.json().then(function (donnees) { return { statut: r.status, donnees: donnees }; });
    }).then(function (res) {
      poserErreurs(res.donnees.erreurs || {});
      // 202 : l'email n'est pas parti, mais la demande est enregistrée. Pas de renvoi.
      if (res.statut === 200 || res.statut === 202) {
        formulaire.hidden = true;
        confirmation.textContent = res.donnees.message;
        confirmation.hidden = false;
        return;
      }
      retour.textContent = res.donnees.message;
      bouton.disabled = false;
    }).catch(function () {
      retour.textContent = modale.getAttribute("data-erreur-reseau");
      bouton.disabled = false;
    });
  });
})();
