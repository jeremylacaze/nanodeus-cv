// Pipeline cliquable. Sans JS, tous les détails restent visibles sous le graphe.
// Grand écran : un seul panneau de détail qui suit la sélection.
// Téléphone (≤ 720 px) : accordéon, le détail s'ouvre sous le job tapé.
(function () {
  "use strict";
  var pipeline = document.querySelector(".pipeline");
  if (!pipeline) { return; }
  var conteneur = pipeline.querySelector(".details");
  var boutons = Array.prototype.slice.call(pipeline.querySelectorAll("button.job"));
  var details = Array.prototype.slice.call(conteneur.querySelectorAll("section.detail"));
  var mobile = window.matchMedia("(max-width: 720px)");
  var initial = pipeline.getAttribute("data-initial");
  var choisi = initial;

  function appliquer() {
    // Chaque détail revient d'abord dans le conteneur, dans l'ordre d'origine.
    details.forEach(function (d) { conteneur.appendChild(d); });
    boutons.forEach(function (bouton) {
      var ouvert = bouton.getAttribute("data-cle") === choisi;
      var detail = document.getElementById(bouton.getAttribute("aria-controls"));
      bouton.setAttribute("aria-expanded", ouvert ? "true" : "false");
      if (!detail) { return; }
      detail.hidden = !ouvert;
      if (ouvert && mobile.matches) { bouton.parentNode.appendChild(detail); }
    });
    conteneur.hidden = mobile.matches || !choisi;
  }

  boutons.forEach(function (bouton) {
    bouton.addEventListener("click", function () {
      var cle = bouton.getAttribute("data-cle");
      // Sur téléphone, retaper un job ouvert le referme.
      choisi = (mobile.matches && choisi === cle) ? null : cle;
      appliquer();
    });
  });

  function auChangement() {
    if (!mobile.matches && !choisi) { choisi = initial; }
    appliquer();
  }
  if (mobile.addEventListener) { mobile.addEventListener("change", auChangement); }
  else if (mobile.addListener) { mobile.addListener(auChangement); }

  appliquer();

  // Tablette : le graphe déborde à droite ; on l'amène sur le job choisi (le plus récent)
  // et la prochaine mission, sinon le visiteur arrive sur les formations les plus anciennes.
  // Un fondu signale le côté où il reste du contenu.
  var graphe = pipeline.querySelector(".graphe");
  function bords() {
    var deborde = !mobile.matches && graphe.scrollWidth > graphe.clientWidth + 1;
    graphe.classList.toggle("deborde-g", deborde && graphe.scrollLeft > 1);
    graphe.classList.toggle("deborde-d", deborde &&
      graphe.scrollLeft + graphe.clientWidth < graphe.scrollWidth - 1);
  }
  if (graphe) {
    if (!mobile.matches) { graphe.scrollLeft = graphe.scrollWidth; }
    graphe.addEventListener("scroll", bords, { passive: true });
    window.addEventListener("resize", bords);
    bords();
  }
}());
