# CV « pipeline » — cv.nanodeus.com

*Document de conception · 18/10/2026 · Jeremy LACAZE-RUSQUES*

Légende : ce qui n'est pas marqué a été **décidé par Jeremy**. *(choix de conception)*
marque un choix fait pendant la conception, contestable, que Jeremy a vu passer sans
l'imposer. *(au constructeur)* marque ce qui est laissé à l'appréciation de celui qui
construit.

---

## 1. Intention

Jeremy veut un **CV vivant** à présenter aux recruteurs, qu'il peut modifier à tout
moment sans toucher au code, et dont il peut tenir **plusieurs versions** selon le poste
visé.

- Les recruteurs arrivent **surtout depuis LinkedIn** (donc souvent sur téléphone), et
  aussi par un **QR code** imprimé sur le CV papier.
- Ce qu'ils doivent retenir : **ses expériences** et **ses soft skills**. Ses collègues
  le décrivent comme porteur d'idées, très autonome, capable de faire monter son équipe
  en compétence avec pédagogie, et le voient comme un **futur Lead tech**.
- Le site doit donner **le plus d'informations possible** tout en **cachant le
  téléphone et l'email**. Le recruteur dispose d'un bouton pour demander à être
  contacté.
- Le visuel doit être **original et interactif** et reprendre le **graphe de pipeline
  CI/CD** de GitHub Actions (celui de la release de ReadLN, voir § 4).

### Critères de réussite

1. Un recruteur qui arrive depuis LinkedIn sur son téléphone comprend **en 10 secondes**
   qui est Jeremy, son poste actuel, ce qu'il vise et ses points forts, puis peut
   explorer en détail.
2. Jeremy modifie ses expériences, sa photo, son accroche ou une version entière depuis
   l'admin, **sans commit ni déploiement**.
3. Une demande de contact arrive dans la **boîte mail perso** de Jeremy, et il y répond
   directement au recruteur avec « Répondre ».
4. Jeremy voit dans l'admin qui a consulté le site (version, date, source) et les emails
   envoyés.

### Non-objectifs (v1)

- Pas de comptes publics, de commentaires, de blog ni de CMS générique : un seul
  éditeur, Jeremy.
- Pas d'outil d'analytics tiers (Google Analytics, Plausible…) ni de géolocalisation des
  visiteurs.
- **Pas de réponse automatique au recruteur** *(choix de conception)* : sinon le
  formulaire permettrait à un robot d'envoyer des emails à n'importe quelle adresse via
  le domaine de Jeremy.
- Pas de traduction automatique : Jeremy écrit lui-même le contenu anglais.

### Anti-objectifs (le projet est raté si…)

- **Le téléphone ou l'email de Jeremy apparaît quelque part en public** : HTML, JSON,
  PDF public, balises Open Graph, sitemap, message d'erreur ou dépôt Git. C'est la règle
  n° 1.
- **L'admin est accessible depuis Internet**, même derrière un mot de passe.
- Le côté « pipeline » devient un gadget qui gêne la lecture : un recruteur non
  technique doit lire le CV aussi vite qu'un CV classique.
- Le site affiche un **bandeau cookies** (il ne doit poser aucun cookie, voir § 7).
- La boîte de Jeremy se remplit de spam à cause du formulaire.

---

## 2. Vue d'ensemble

```
                 Internet                                  Tailnet (Headscale)
                    │                                              │
           cv.nanodeus.com (TLS)                         <ip-tailnet>:<port admin>
                    │                                              │
             ┌──────▼──────┐                                ┌──────▼──────┐
             │   Traefik   │  (déjà en place, réseau proxy) │             │
             └──────┬──────┘                                │             │
             ┌──────▼──────┐                                │    admin    │
             │   public    │  même image Docker             │  (édition,  │
             │ (lecture +  │  rôle choisi par variable      │   journaux) │
             │  contact)   │  d'environnement               │             │
             └──────┬──────┘                                └──────┬──────┘
                    └───────────────┬──────────────────────────────┘
                              volume Docker
                       SQLite (WAL) + photos + PDF
                                    │
                         Brevo (SMTP / API) ──► boîte perso de Jeremy
```

- **Projet séparé de ReadLN**, dans `~/Documents/Git/nanodeus-cv`, avec son propre dépôt
  GitHub.
- **Hébergé sur le même netcup que ReadLN.** Le domaine `nanodeus.com` y est déjà géré
  (DNS netcup) et Traefik publie déjà `readln.nanodeus.com`.
- **Adresse publique : `cv.nanodeus.com`.**

---

## 3. Choix techniques

Jeremy accepte l'usage de frameworks existants. Tous les choix ci-dessous sont des
*(choix de conception)* et reprennent l'outillage de ReadLN, que Jeremy maîtrise :

| Sujet | Choix | Pourquoi |
|---|---|---|
| Serveur | **Python / Flask**, templates Jinja rendus côté serveur | Même stack que ReadLN. Le contenu est lisible sans JavaScript (bon pour les aperçus LinkedIn et l'impression). |
| Front | **JavaScript simple** (sans framework, sans étape de build) + CSS maison | Un seul écran interactif, le pipeline. React ou Vue seraient surdimensionnés. |
| Base | **SQLite** en mode WAL, dans un volume Docker ; **SQLAlchemy + Alembic** | Quelques centaines de lignes. Un second Postgres serait du poids mort. Les migrations restent obligatoires, comme dans ReadLN. |
| PDF | **WeasyPrint** | Génère le PDF à partir des mêmes templates HTML, donc toujours à jour. |
| Images | **Pillow** | Redimensionne la photo et **retire les métadonnées EXIF** (GPS d'une photo prise au téléphone). |
| QR code | **segno** | Petite dépendance, sortie SVG. |
| Emails | **Brevo** (SMTP relais ou API HTTP, *au constructeur*) | Service français, gratuit jusqu'à 300 emails par jour, conforme au RGPD. Voir § 8. |
| Interface FR/EN | **Flask-Babel** pour les textes d'interface, champs `_fr` / `_en` en base pour le contenu | Même logique que ReadLN : le français est le msgid. |
| Déploiement | Docker, image `ghcr.io/<compte>/nanodeus-cv:<sha>`, Compose, Traefik | Même contrat que ReadLN : **le tag est le contrat, jamais `latest`**. |

Conventions *(choix de conception, alignées sur ReadLN)* : code et commentaires en
**français** ; commits `FEAT(scope):`, `FIX(scope):`, `CHORE:`… ; une branche par
fonctionnalité depuis `develop` ; `pytest` ; `ruff`.

---

## 4. Le site public

### 4.1 Mise en page (validée sur maquette)

La maquette validée est **`docs/maquettes/pipeline-valide.html`** (à ouvrir dans un
navigateur, les jobs y sont cliquables). C'est un mélange de deux pistes : le **graphe
de pipeline** de GitHub Actions et la page **« résumé d'un run »**. De haut en bas :

1. **Bandeau** : photo, nom, titre de la version, localisation, badge « ouvert aux
   opportunités » (activable), accroche en une phrase, puis **3 à 4 chiffres clés**
   (ex. « 3 ans d'expérience », « 5 outils administrés sur Kubernetes », « Bac+5 »).
2. **Pipeline « Parcours »**, de gauche à droite :
   - un **groupe** de départ pour les formations (Licence pro, Mastère) ;
   - les **postes** en séquence ;
   - une **voie parallèle** en pointillés pour les **projets perso** (ReadLN en
     premier), comme le job `ci-existante` de la capture d'origine ;
   - les deux voies aboutissent à un **dernier job « Prochaine mission »**, jaune et
     pulsant (« en cours… »), dont le libellé dépend de la version (ex. « Lead tech »).
   - Chaque job affiche son statut (✓ vert), son intitulé et sa **durée** à la place du
     chrono. Les durées sont **calculées** à partir des dates.
   - **Clic sur un job** → un panneau de détail façon log s'ouvre dessous : intitulé,
     entreprise / client, dates, puis les missions comme des étapes cochées. Au
     chargement, le poste le plus récent est sélectionné.
3. **« Tests · soft skills (n/n passés) »** : chaque soft skill est un test réussi
   **accompagné de sa preuve**, une phrase factuelle (ex. « Porteur d'idées : a imaginé,
   construit et mis en production ReadLN seul »). À côté, un panneau **Stack** pour les
   compétences techniques.
4. **Bas de page** (validé tel quel) :
   - **« Secrets »** : `🔒 PHONE ***` et `🔒 EMAIL ***`, masqués comme les secrets d'un
     pipeline, avec un bouton **« Demander l'accès »** (§ 5).
   - **« Artefacts »** : le CV en PDF de la version affichée, puis les liens LinkedIn /
     GitHub, s'ils sont renseignés.
5. **Sélecteur FR / EN** (dans l'en-tête, *emplacement au constructeur*).

### 4.2 Téléphone

En dessous d'une largeur à fixer *(au constructeur)*, le pipeline passe **à la
verticale**, **le plus récent en haut**, comme une frise. Chaque job s'ouvre d'un tap
(accordéon). Bandeau, tests et bas de page gardent le même ordre. Aucun défilement
horizontal de la page.

### 4.3 Style

- **Référence : le thème sombre de GitHub** (fond `#0d1117`, cartes `#161b22`, bordures
  `#30363d`, vert `#3fb950`, jaune `#d29922`, bleu de sélection `#58a6ff`) et une police
  monospace pour les « logs ».
- Un thème clair qui suit `prefers-color-scheme` est un plus *(au constructeur)*, mais
  le sombre est la référence.
- **Accessibilité** : jobs atteignables au clavier (boutons), structure sémantique
  (liste ordonnée), contraste AA, et animation pulsante coupée sous
  `prefers-reduced-motion`.
- **Impression** : une feuille `@media print` claire et lisible (le PDF du § 6 reste la
  version de référence à télécharger).

### 4.4 Adresses

| Adresse | Contenu |
|---|---|
| `/` | La version marquée **par défaut** dans l'admin |
| `/<slug>` | Une version (ex. `/devops`, `/lead-tech`) |
| `/en/…` | Les mêmes pages en anglais |
| `/<slug>.pdf`, `/en/<slug>.pdf` | Le PDF public de la version |
| `?src=qr` | Paramètre de source (le QR code pointe dessus) |

- **Langue** *(choix de conception)* : portée par l'URL (préfixe `/en`), et non par un
  cookie, pour ne poser aucun cookie. Sur `/` sans préfixe, si l'en-tête
  `Accept-Language` préfère l'anglais, on propose (sans forcer) la version anglaise.
- **Version non listée** *(choix de conception)* : une version peut être marquée
  « non listée ». Elle reste accessible par son URL mais porte `noindex` et n'apparaît
  dans aucun lien du site. Utile pour une version faite pour une entreprise précise.
- Une version **brouillon** renvoie 404 en public.
- Si le contenu anglais d'un champ est vide, on affiche le français *(choix de
  conception)*, pour ne jamais montrer un trou.

### 4.5 Aperçu LinkedIn

Comme le lien sera partagé sur LinkedIn, chaque page porte des balises **Open Graph**
(titre, description = accroche, image) *(choix de conception)*. L'image peut être la
photo ou une carte générée, *au constructeur*. Ces balises ne contiennent jamais
d'email ni de téléphone.

---

## 5. Demande de contact

### Côté recruteur

- **« Demander l'accès »** ouvre une **fenêtre modale** avec :
  - **email** (obligatoire, validé) ;
  - **message** (obligatoire, longueur max à fixer, ~2000 caractères) ;
  - **nom** et **entreprise** (facultatifs) *(choix de conception)*.
- La version et la langue consultées sont enregistrées automatiquement.
- Après l'envoi : un message de confirmation dans la fenêtre (« Jeremy vous répondra à
  l'adresse indiquée »). En cas d'échec, un message d'erreur sobre, sans détail
  technique.
- Sans JavaScript, le formulaire doit rester utilisable (POST classique puis page de
  confirmation) *(au constructeur, mais souhaitable)*.

### Côté Jeremy

- Un email arrive sur sa **boîte perso**. L'adresse est stockée en configuration
  serveur ou dans l'admin, jamais dans le dépôt.
- **Expéditeur** : une adresse technique sur le domaine, `cv@nanodeus.com` *(nom au
  constructeur)*. **`Reply-To` = l'email du recruteur** : « Répondre » écrit directement
  au recruteur.
- Objet explicite *(choix de conception)*, ex. `[CV · lead-tech] Demande de contact — Nom (Entreprise)`.
  Corps : message, nom, entreprise, version, langue, date.

### Anti-abus *(choix de conception)*

- **Champ piège** invisible : rempli → on répond « succès » sans rien envoyer.
- **Limite par visiteur** (empreinte d'IP, § 7), ex. 3 demandes par heure et 10 par
  jour, plus une **limite globale** de sécurité, ex. 50 par jour.
- **Contrôle d'origine** sur le POST (`Origin` = hôte), comme `_csrf_origin_check`
  dans ReadLN. Il n'y a pas de jeton CSRF en cookie puisqu'il n'y a pas de cookie.
- Un captcha **sans tiers et sans cookie** (ex. ALTCHA, preuve de travail) est
  optionnel, *au constructeur* : à ajouter si le spam passe malgré le reste.
- **Chaque demande est enregistrée en base avant l'envoi**. Si Brevo est en panne, la
  demande n'est pas perdue : elle apparaît dans l'admin comme « échec », avec un bouton
  « Renvoyer ».

---

## 6. PDF

- **Un PDF par version et par langue**, généré à partir du même contenu, en A4. On
  vise 2 pages maximum, avec une mise en page **claire et imprimable** (inspirée du
  pipeline, mais lisible en noir et blanc) *(au constructeur)*.
- **PDF public** (lien « Artefacts ») : **sans téléphone ni email**, avec un lien vers
  la page `cv.nanodeus.com/<slug>` pour demander le contact.
- **PDF complet**, téléchargeable **uniquement depuis l'admin**, avec téléphone et
  email, pour les candidatures que Jeremy envoie lui-même *(choix de conception)*.
- Régénération quand le contenu change, avec un cache *(stratégie au constructeur)*.

---

## 7. Journal des visites et vie privée

Jeremy veut **suivre les visites** et **les emails envoyés** dans l'admin.

**Ce qu'on enregistre** pour chaque page vue (et pour les événements « PDF téléchargé »
et « fenêtre de contact ouverte ») *(choix de conception)* :

- date et heure ;
- version et langue ;
- **source** : `?src=qr`, sinon le domaine du `Referer` (LinkedIn, Google, direct…) ;
- type d'appareil (mobile / ordinateur), déduit du User-Agent ;
- **empreinte du visiteur** : `HMAC(IP + User-Agent, sel du jour)`. Le **sel change
  chaque jour** et l'ancien est jeté. On peut ainsi compter les visiteurs uniques d'une
  journée sans stocker d'IP et sans pouvoir suivre quelqu'un d'un jour à l'autre ;
- **robots** : ignorés, à l'exception de **`LinkedInBot`**, enregistré à part comme
  « aperçu LinkedIn ». Il indique que le lien vient d'être collé quelque part.

**Règles :**

- **Aucun cookie** sur le site public, pas même de session : pas de bandeau cookies.
- **Aucune IP en clair** en base ni dans les logs applicatifs.
- **Purge automatique** des visites de plus de **6 mois** *(choix de conception)*.
  Les demandes de contact sont conservées tant que Jeremy ne les supprime pas (il peut
  supprimer une demande depuis l'admin).
- Une courte **mention de confidentialité** en bas de page (FR/EN) explique ce qui est
  enregistré.

---

## 8. Envoi d'emails (Brevo)

- Jeremy **n'a pas encore d'adresse sur `nanodeus.com`**. Il n'en faut pas de *boîte* :
  l'adresse sert uniquement à **envoyer**, et Jeremy reçoit sur sa boîte perso.
- Étapes à documenter pour Jeremy dans le README de déploiement :
  1. créer un compte Brevo gratuit ;
  2. y **authentifier le domaine `nanodeus.com`**, ce qui ajoute dans le **DNS netcup**
     les enregistrements demandés par Brevo (code de vérification, DKIM) et un
     enregistrement **DMARC** ;
  3. déclarer l'expéditeur `cv@nanodeus.com` ;
  4. générer une clé SMTP ou API et la poser dans le `.env` du serveur.
- *Alternative* si l'offre netcup de Jeremy inclut une boîte mail : envoyer via le SMTP
  netcup. Le code doit donc parler **SMTP générique** (hôte, port, utilisateur, mot de
  passe en configuration) pour que le changement de fournisseur ne soit qu'une affaire
  de configuration *(choix de conception)*.
- Un bouton **« Envoyer un email de test »** dans l'admin.

---

## 9. L'admin (Tailscale uniquement)

### Accès

- L'admin n'est **jamais publiée sur Internet** : ni route Traefik, ni port public.
- Le netcup fait tourner **Headscale** (serveur Tailscale auto-hébergé). Son IP de
  tailnet est **`<ip-tailnet>`**, et d'autres outils d'admin y publient déjà leur port de
  cette façon. `net.ipv4.ip_nonlocal_bind=1` est déjà posé
  pour que le bind fonctionne au redémarrage, avant que l'IP n'existe.
- Mise en œuvre *(choix de conception)* : **même image, deux services Compose**.
  - `public` : rôle public, raccordé au réseau `proxy` de Traefik, **sans aucune route
    d'admin enregistrée**. Les routes d'admin n'existent pas dans ce processus, elles ne
    sont pas seulement protégées.
  - `admin` : rôle admin, port publié sur `<ip-tailnet>:<port>` uniquement.
- **Pas de mot de passe** : le tailnet est la barrière. Le service admin vérifie
  quand même que l'adresse source est dans `100.64.0.0/10` (défense en profondeur), et
  applique un contrôle `Origin` sur les écritures.
- Une erreur dans l'admin ne doit jamais casser le site public : services séparés.

### Fonctions

1. **Profil** : nom, photo (téléversement → redimensionnée, EXIF retiré), localisation,
   date de naissance (l'âge est calculé ; afficher l'âge est **optionnel**, case à
   cocher *(choix de conception)*), permis, centres d'intérêt, liens LinkedIn / GitHub,
   **téléphone et email privés** (servent seulement au PDF complet et à rien de public),
   et badge « ouvert aux opportunités ».
2. **Stock de contenu** (FR + EN pour chaque champ texte) :
   - **parcours** : chaque entrée a un **type** (poste, formation, projet perso) et une
     **voie** (principale ou parallèle). Champs : intitulé, entreprise, client / via
     (ex. « Astek → SQLI · ADS »), dates de début et de fin (fin vide = en cours), lieu,
     **missions** (liste ordonnée), technos ;
   - **soft skills** : nom + **preuve** ;
   - **compétences techniques** : nom, catégorie ;
   - **chiffres clés** : valeur + libellé, saisis à la main. « Années d'expérience »
     peut être calculé, *au constructeur*.
3. **Versions** :
   - slug, statut (brouillon / publiée / non listée), **par défaut** (une seule) ;
   - titre, accroche et libellé de « Prochaine mission », FR + EN ;
   - **cases à cocher et ordre** des éléments du stock à afficher (parcours, soft
     skills, compétences, chiffres clés) ;
   - **surcharge optionnelle** de la description d'un poste pour cette version (ex.
     mettre en avant l'encadrement dans `/lead-tech`). Champ vide = description du
     stock ;
   - boutons **Aperçu** (rendu public en direct, brouillon compris), **QR code**
     (SVG/PNG de l'URL publique avec `?src=qr`), **PDF public** et **PDF complet**.
4. **Visites** : liste filtrable (version, source, période) et quelques totaux
   (visiteurs uniques par jour, répartition par source, aperçus LinkedIn). Pas de
   graphique sophistiqué en v1 *(au constructeur)*.
5. **Emails / demandes de contact** : liste (date, nom, entreprise, email, version,
   message, statut envoyé / échec), **Renvoyer**, **Supprimer**, **email de test**.

L'admin peut rester **en français uniquement** *(choix de conception)*.

---

## 10. Contenu de départ

Jeremy demande que le site arrive **pré-rempli** à partir de son CV actuel :

- **Français** : repris du CV (annexe A).
- **Anglais** : Jeremy fournira la version définitive, mais il faut **préparer un
  premier jet** traduit à partir du CV, qu'il corrigera dans l'admin.
- **Deux versions** créées au départ : `devops` (par défaut, titre « Administrateur
  applicatif / DevOps ») et `lead-tech` (titre à proposer, ex. « Administrateur
  applicatif / DevOps → Lead tech »).
- **ReadLN** ajouté comme projet perso, sur la voie parallèle (texte en annexe A).
- **Soft skills** de départ : porteur d'idées, autonomie, pédagogie / faire monter
  l'équipe en compétence. Les **preuves** ne sont pas toutes connues : en mettre une
  quand l'annexe en fournit une, sinon un champ marqué « à compléter », visible
  **seulement dans l'admin**. Une soft skill sans preuve n'est pas affichée en public
  *(choix de conception)*.
- **Téléphone, email et photo ne sont pas dans le dépôt.** Jeremy les saisit dans
  l'admin. Jusque-là, les initiales « JL » remplacent la photo.
- Mécanisme d'amorçage (commande `flask seed`, migration de données…) *au
  constructeur*. Il ne doit **jamais écraser** un contenu déjà modifié en production.

---

## 11. Déploiement, sauvegarde, CI

- **Serveur** : dossier `/opt/nanodeus-cv/` sur le netcup, **déjà créé par Jeremy,
  propriétaire `deploy`** (l'utilisateur SSH de déploiement de ReadLN). Il contiendra
  `compose.yml` et `.env` en `chmod 600`, comme `/opt/readln/`. Les secrets (clé Brevo, sel HMAC, email de
  destination) **naissent et restent sur le serveur**.
- **Traefik** : labels `Host(cv.nanodeus.com)`, entrypoint `websecure`, resolver TLS
  `le`, réseau externe `proxy`, et confiance à exactement un saut de proxy (`ProxyFix`
  comme `TRUST_PROXY=1` dans ReadLN). Sans ça, toutes les IP seraient celle de Traefik
  et la limite anti-abus serait globale.
- **DNS** : enregistrement `cv` → IP du netcup, chez netcup.
- **Image** : `ghcr.io/<compte>/nanodeus-cv:<sha>`, jamais `latest`. Un `deploy.sh`
  côté serveur refuse les tags mouvants.
- **Sauvegarde** : le netcup a un dépôt **restic** (`/opt/readln/restic`) et un timer
  nocturne. Le volume du CV (base SQLite copiée proprement via `.backup` + photos) doit
  y être inclus, en étendant la sauvegarde existante ou avec un timer dédié *(au
  constructeur)*. **Ne jamais toucher à `/opt/readln/restic-password`.** Les fichiers de
  `/opt/…` ne sont pas déployés par une pipeline : toute modification exige un `scp`
  manuel, à documenter.
- **CI** : dépôt **public**, donc minutes Actions illimitées (voir Q1). On reprend la
  structure de ReadLN (vérifications réutilisables, build, sauvegarde pre-deploy,
  deploy), mais les contraintes de quota de ReadLN (CI seulement au merge, jobs
  regroupés) ne s'appliquent pas ici.

---

## 12. Tests attendus

En plus des tests ordinaires *(au constructeur)*, ces garanties sont **obligatoires** :

- **Aucune fuite de coordonnées** : un test renseigne un téléphone et un email
  reconnaissables dans le profil, puis parcourt **toutes** les réponses publiques
  (pages, PDF publics, Open Graph, erreurs 404/500) et vérifie que ni l'un ni l'autre
  n'y figure.
- **Aucune route d'admin dans le service public** (retourne 404).
- **Aucun en-tête `Set-Cookie`** sur le site public.
- **Aucune IP en clair** dans la table des visites.
- Formulaire de contact : champ piège, limites, `Origin`, demande enregistrée même si
  l'envoi échoue, `Reply-To` correct.
- Repli FR quand un champ EN est vide ; brouillon → 404 ; non listée → `noindex`.

---

## 13. Questions ouvertes

**Q1 — Dépôt public ou privé ?** → **Public**, décidé par Jeremy. Conséquences :

- **Minutes GitHub Actions illimitées** : la CI/CD reprend le modèle complet de ReadLN
  (tests, contrôles dont `gitleaks`, image GHCR taguée `<sha>`, déploiement par SSH
  sur tag `v*`) **sans consommer le quota** du compte. Les secrets `NETCUP_*` sont à
  recréer sur ce dépôt. Une clé SSH dédiée *(choix de conception)* est préférable à
  la réutilisation de `readln_deploy`.
- L'image GHCR est publique : elle ne contient **aucun** secret ni contenu personnel
  (le contenu vit en base sur le serveur).
- La règle n° 1 s'étend au dépôt : **ni téléphone, ni email, ni photo, ni IP du
  serveur** dans le code, les données d'amorçage ou l'historique. `gitleaks` et le test
  anti-fuite (§ 12) sont la barrière.
- Le dépôt sert aussi de **vitrine** : le lien « GitHub » des Artefacts peut pointer
  dessus. Un README soigné est donc attendu.

**Réglé pendant la conception :**

- **Gestes serveur** *(choix de conception)* : Jeremy autorise l'usage ponctuel du
  compte `deploy` (`ssh -i ~/.ssh/readln_deploy deploy@<netcup>`), à condition de tout
  nettoyer ensuite. Le constructeur prépare et vérifie lui-même ce que `deploy` peut
  faire : fichiers de `/opt/nanodeus-cv`, `.env`, `docker compose`. Ce qui demande
  `sudo` (unité systemd de sauvegarde) ou l'interface netcup (DNS `cv`) passe par un
  **runbook** que Jeremy exécute, avec un point de contrôle après chaque étape.
- **Contrôle d'IP de l'admin** *(choix de conception)* : avec un port publié par
  Docker, le conteneur peut voir l'IP de la passerelle Docker au lieu de l'IP tailnet.
  Le constructeur **le vérifie sur la vraie machine**. Si l'IP source n'est pas
  fiable, on retire le contrôle `100.64.0.0/10` plutôt que de bloquer Jeremy, et
  **le bind sur `<ip-tailnet>` reste la barrière**. Le choix retenu est documenté.
- **Sauvegarde avant déploiement** *(choix de conception)* : comme pour ReadLN, une
  copie de la base SQLite (`.backup`) est faite avant chaque déploiement.

---

## Annexe A — contenu du CV actuel (source du pré-remplissage)

**Identité** : Jeremy LACAZE-RUSQUES · Toulouse, France · 29 ans · Permis B / A2.
Téléphone et email : **non reproduits ici**, à saisir dans l'admin.

**Poste recherché** : Administrateur applicatif / DevOps.

**Profil (accroche actuelle)** : « Après différentes formations et expériences
professionnelles, j'ai acquis la capacité de m'adapter en entreprise. Je suis capable de
travailler en équipe ainsi qu'en autonomie tout en appliquant des méthodes agiles. »
→ À réécrire en une phrase autour des soft skills (porteur d'idées, autonomie,
pédagogie). Proposition validée sur la maquette : « Porteur d'idées, autonome, je fais
grandir les équipes avec pédagogie. »

**Expériences**

1. **Administrateur applicatif** · SQLI · ADS · mai 2025 → aujourd'hui
   - Administrateur applicatif et serveur pour : Jira Data Center, Confluence Data
     Center, GitLab Self-Hosted, Artifactory Self-Hosted, Mattermost Self-Hosted
   - Le tout déployé sous un environnement Kubernetes
2. **Administrateur Atlassian** · Astek → SQLI · ADS · février 2024 → mai 2025
   - Maintenance et développement d'outils tels que Jira, Confluence, Crowd, GitLab et
     Artifactory
   - Support des applications en contact direct avec les utilisateurs
   - Support et configuration des serveurs hébergeant les applications
3. **Ingénieur DevOps** · Astek → Navocap · octobre 2023 → février 2024
   - Mise en place d'un environnement Docker sur les machines des utilisateurs
   - Image Docker fournissant un environnement Windows Data Center sur les postes des
     développeurs
   - Automatisation du déploiement de cet environnement

**Formations**

- 2023 · **Mastère Expert en Développement logiciel mobile & IoT** · Ynov Campus,
  Toulouse
- 2020 · **Licence professionnelle Développement et Qualité des logiciels** ·
  Université Toulouse III – Paul Sabatier, Toulouse

**Compétences** : Docker · Kubernetes · Shell / PowerShell · Java / C · Python /
PostgreSQL · HTML / CSS / PHP / JavaScript · Anglais technique.

**Centres d'intérêt** : musique, jeux vidéo, dessin.

**Projet perso : ReadLN** (voie parallèle, en production)
- Application web multi-utilisateurs de traduction de light novels (PDF / EPUB →
  EPUB / PDF traduit) par un LLM local, avec lecteur, discussions et notifications
- Flask, PostgreSQL, Redis / RQ, SocketIO, Docker Compose, Traefik
- CI/CD GitHub Actions, images taguées par commit sur GHCR, déploiement automatisé
  sur VPS, sauvegardes restic chiffrées
- Preuve possible pour « porteur d'idées » et « autonomie » : imaginé, construit et
  mis en production seul.
