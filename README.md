# nanodeus-cv

Le CV de Jeremy Lacaze-Rusques, en ligne sur **[cv.nanodeus.com](https://cv.nanodeus.com)**.

C'est un CV vivant. Il se présente comme le graphe d'une pipeline CI/CD, dont chaque
expérience est un job. Il existe en plusieurs versions, une par type de poste
(`/devops`…), en français et en anglais.
Chaque version se télécharge en PDF d'une page, et un QR code renvoie au site depuis le
CV papier. Tout le contenu se modifie depuis une interface d'administration, sans
commit ni déploiement.

## Pile

- **Python 3.14** et **Flask**, avec SQLAlchemy et Alembic.
- **SQLite** en WAL : un seul petit volume, et une sauvegarde à chaud.
- Flask-Babel pour le français et l'anglais.
- **WeasyPrint** pour le PDF, segno pour les QR codes, Pillow pour la photo.
- **gunicorn**, une image **Docker** en lecture seule, et **Traefik** devant.
- **GitHub Actions** : tests, audits (pip-audit, zizmor, gitleaks, hadolint), image,
  sauvegarde, puis déploiement.
- **restic** pour les sauvegardes.

## Choix d'architecture

- **Une image, deux rôles.** Le même code tourne en `public`, qui n'a aucune route
  d'administration, et en `admin`. L'admin n'est publiée que sur l'adresse Tailscale du
  serveur. Elle filtre en plus l'adresse source et le nom d'hôte, contre le DNS
  rebinding.
- **Aucun cookie public.** Le site public ne pose aucun cookie et ne charge aucun
  traceur. Une politique CSP à nonce encadre chaque page.
- **Un journal des visites sans IP.** Une visite est enregistrée sous une empreinte
  HMAC, dont le sel change chaque jour puis est détruit. Le journal sait combien de
  personnes ont consulté une version, mais jamais qui elles sont. Il est purgé après
  six mois.
- **Les coordonnées ne sortent jamais.** Le téléphone et l'email ne figurent dans
  aucune page publique. Un recruteur laisse une demande de contact. Elle est
  enregistrée avant l'envoi, puis relayée par SMTP.
- **Le PDF vient des mêmes données que la page.** Il est rendu par WeasyPrint et mis en
  cache selon son contenu : tant que rien ne change, il n'est pas recalculé.
- **Le tag est le contrat.** La production tourne sur
  `ghcr.io/jeremylacaze/nanodeus-cv:<sha>`, jamais sur `latest`. Le script de
  déploiement refuse tout tag mouvant. Chaque mise en ligne commence par une sauvegarde
  de la base.

## Développement local

```sh
python3.14 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
python scripts/i18n.py compile
./dev.sh                                   # site public : http://localhost:5010
CV_ROLE=admin CV_PORT=5011 ./dev.sh        # admin : http://localhost:5011/admin/
.venv/bin/pytest -q
```

WeasyPrint a besoin de Pango sur la machine (`brew install pango` sous macOS).

Le test de fumée de l'image démarre le Compose de production sur un volume jetable :

```sh
docker build -t nanodeus-cv:local .
PYTHON=.venv/bin/python scripts/fumee-image.sh nanodeus-cv:local
```

## Mise en ligne

Le serveur, les secrets, la sauvegarde et le retour arrière sont décrits dans
[docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md).
