// Admin : confirmation des suppressions, et un seul envoi par formulaire.
document.addEventListener("submit", (evenement) => {
  const formulaire = evenement.target;
  if (!(formulaire instanceof HTMLFormElement)) return;
  if (formulaire.dataset.confirmer && !window.confirm(formulaire.dataset.confirmer)) {
    evenement.preventDefault();
    return;
  }
  if (formulaire.dataset.envoye) {
    evenement.preventDefault();
    return;
  }
  formulaire.dataset.envoye = "1";
  // Désactivé après le départ de la requête : un bouton désactivé tout de suite
  // retirerait son name/value des données envoyées.
  setTimeout(() => {
    for (const bouton of formulaire.querySelectorAll("button, input[type=submit]")) {
      bouton.disabled = true;
    }
  }, 0);
});

// Page restaurée par le retour arrière (cache d'historique) : les formulaires
// gardaient leur état « envoyé » et leurs boutons désactivés.
window.addEventListener("pageshow", (evenement) => {
  if (!evenement.persisted) return;
  for (const formulaire of document.querySelectorAll("form[data-envoye]")) {
    delete formulaire.dataset.envoye;
    for (const bouton of formulaire.querySelectorAll("button, input[type=submit]")) {
      bouton.disabled = false;
    }
  }
});
