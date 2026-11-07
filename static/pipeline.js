// Pipeline cliquable. Sans JS, tous les détails restent visibles sous le graphe.
// Grand écran : un seul panneau de détail qui suit la sélection.
// Téléphone (≤ 720 px) : accordéon, le détail s'ouvre sous le job tapé.
// Lien direct : /devops#detail-<clé> ouvre ce job ; un clic met l'adresse à jour.
// Clavier : flèches, Début et Fin passent d'un job à l'autre.
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
  var PREFIXE = "#detail-";

  function bouton(cle) {
    for (var i = 0; i < boutons.length; i++) {
      if (boutons[i].getAttribute("data-cle") === cle) { return boutons[i]; }
    }
    return null;
  }

  function appliquer() {
    // Chaque détail revient d'abord dans le conteneur, dans l'ordre d'origine.
    details.forEach(function (d) { conteneur.appendChild(d); });
    boutons.forEach(function (b) {
      var ouvert = b.getAttribute("data-cle") === choisi;
      var detail = document.getElementById(b.getAttribute("aria-controls"));
      b.setAttribute("aria-expanded", ouvert ? "true" : "false");
      if (!detail) { return; }
      detail.hidden = !ouvert;
      if (ouvert && mobile.matches) { b.parentNode.appendChild(detail); }
    });
    conteneur.hidden = mobile.matches || !choisi;
  }

  // L'adresse suit la sélection, sans entrée d'historique ni saut de page : elle se
  // copie telle quelle pour pointer vers une expérience précise.
  function noterAdresse() {
    if (!window.history || !history.replaceState) { return; }
    var base = location.pathname + location.search;
    history.replaceState(null, "", choisi ? base + PREFIXE + choisi : base);
  }

  // Job désigné par l'ancre de l'adresse, s'il existe ; renvoie son bouton.
  function depuisAncre() {
    if (location.hash.indexOf(PREFIXE) !== 0) { return null; }
    var b = bouton(decodeURIComponent(location.hash.slice(PREFIXE.length)));
    if (!b) { return null; }
    choisi = b.getAttribute("data-cle");
    appliquer();
    b.scrollIntoView({ block: "center", inline: "center" });
    return b;
  }

  function choisir(b) {
    var cle = b.getAttribute("data-cle");
    // Sur téléphone, retaper un job ouvert le referme.
    choisi = (mobile.matches && choisi === cle) ? null : cle;
    appliquer();
    noterAdresse();
  }

  boutons.forEach(function (b) {
    b.addEventListener("click", function () { choisir(b); });
  });

  pipeline.addEventListener("keydown", function (e) {
    var i = boutons.indexOf(document.activeElement);
    if (i < 0 || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) { return; }
    var j = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1,
              Home: 0, End: boutons.length - 1 }[e.key];
    if (j === undefined) { return; }
    e.preventDefault();
    j = Math.max(0, Math.min(boutons.length - 1, j));
    if (j === i) { return; }
    boutons[j].focus();
    choisir(boutons[j]);
  });

  // Un clic sur le # d'un détail (ou une ancre suivie dans la page) change l'adresse.
  window.addEventListener("hashchange", depuisAncre);

  function auChangement() {
    if (!mobile.matches && !choisi) { choisi = initial; }
    appliquer();
  }
  if (mobile.addEventListener) { mobile.addEventListener("change", auChangement); }
  else if (mobile.addListener) { mobile.addListener(auChangement); }

  appliquer();
  var ancre = depuisAncre();

  // Tablette : le graphe déborde à droite ; sans ancre, on l'amène sur le job choisi
  // (le plus récent) et la prochaine mission, sinon le visiteur arrive sur les
  // formations les plus anciennes. Un fondu signale le côté où il reste du contenu.
  var graphe = pipeline.querySelector(".graphe");
  function bords() {
    var deborde = !mobile.matches && graphe.scrollWidth > graphe.clientWidth + 1;
    graphe.classList.toggle("deborde-g", deborde && graphe.scrollLeft > 1);
    graphe.classList.toggle("deborde-d", deborde &&
      graphe.scrollLeft + graphe.clientWidth < graphe.scrollWidth - 1);
  }
  if (graphe) {
    if (!mobile.matches && !ancre) { graphe.scrollLeft = graphe.scrollWidth; }
    graphe.addEventListener("scroll", bords, { passive: true });
    window.addEventListener("resize", bords);
    bords();
  }
}());
