# Déploiement de cv.nanodeus.com

Runbook de la production sur le serveur netcup, qui héberge déjà ReadLN (Traefik,
réseau Docker `proxy`, compte `deploy`, dépôt restic). Le compte `deploy` n'a **pas**
`sudo` : les gestes marqués « compte d'administration » se font avec le compte qui l'a.
Notations :

- `<netcup>` : nom ou IP publique du serveur ;
- `<ip-tailnet>` : son adresse Tailscale (100.x.y.z) ;
- `<boîte perso>` : l'adresse qui reçoit les demandes de contact.

Aucune de ces valeurs n'entre dans le dépôt, qui est public.

Chaque étape finit par un **point de contrôle**. On ne passe à la suivante qu'une fois
ce contrôle vert.

## 1. Préparer le serveur

`/opt/nanodeus-cv` existe déjà, et il appartient à `deploy`. Depuis le poste de
travail, à la racine du dépôt :

```sh
scp deploy/compose.yml deploy/deploy.sh deploy/backup.sh deploy/ssh-commande.sh \
    deploy@<netcup>:/opt/nanodeus-cv/
ssh deploy@<netcup> 'chmod 755 /opt/nanodeus-cv/*.sh && chmod 600 /opt/nanodeus-cv/compose.yml'
```

Le `.env` se crée **sur le serveur**. Les secrets y naissent et n'en sortent jamais :
ils ne passent ni par un commit, ni par un rapport, ni par un terminal partagé.

```sh
ssh deploy@<netcup>
cd /opt/nanodeus-cv
umask 077
{
  echo "CV_PROD=1"
  echo "SECRET_KEY=$(openssl rand -hex 32)"
  echo "CV_SEL_HMAC=$(openssl rand -hex 32)"
  echo "CV_URL_PUBLIQUE=https://cv.nanodeus.com"
  echo "CV_ADMIN_ECOUTE=<ip-tailnet>:8780"
  echo "CV_ADMIN_HOTES=<ip-tailnet>"
} > .env
nano .env    # ajouter les variables CV_SMTP_* et CV_EMAIL_* (étape 4)
```

La liste complète des variables, commentée, est dans `deploy/env.exemple`. La ligne
`CV_IMAGE` n'est jamais écrite à la main : `deploy.sh` s'en charge.

Côté DNS netcup, créer un enregistrement `cv` (A, et AAAA si le serveur a une IPv6)
qui pointe vers le serveur.

Deux réglages du serveur, à faire une fois avec le compte d'administration :

- `net.ipv4.ip_nonlocal_bind=1` (dans `/etc/sysctl.d/`) : au démarrage, Docker publie
  le port de l'admin avant que `tailscale0` ait son adresse.
- `sudo tailscale set --snat-subnet-routes=false` : sans lui, Tailscale masque la source
  de tout paquet du tailnet retransmis vers un conteneur. L'admin verrait alors la
  passerelle Docker (172.x) au lieu d'une adresse 100.x, et répondrait 403. Ce
  masquage ne sert qu'à un serveur qui annonce des routes ou sert de nœud de sortie ;
  le réglage est persistant.

**Contrôle :**
- `ls -la /opt/nanodeus-cv` montre `.env` en `-rw-------`, avec `deploy` pour
  propriétaire ;
- `sudo iptables -t nat -S ts-postrouting` ne contient aucune règle `MASQUERADE` ;
- `docker network ls` liste `proxy` ;
- `dig +short cv.nanodeus.com` renvoie l'IP du serveur.

Ne jamais afficher le `.env`, ni lancer un `docker compose config` sans le rediriger
vers `/dev/null`.

## 2. Clé SSH de la pipeline, à commande forcée

La pipeline a sa propre clé. Elle n'ouvre que deux commandes :
`/opt/nanodeus-cv/backup.sh --db-only` et `/opt/nanodeus-cv/deploy.sh <image>`. C'est
`ssh-commande.sh` qui le garantit. Sur le poste de travail :

```sh
ssh-keygen -t ed25519 -N '' -C nanodeus-cv-ci -f ~/.ssh/nanodeus-cv-ci
```

Ajouter **une ligne** à `~deploy/.ssh/authorized_keys` sur le serveur, en collant la
clé publique (`~/.ssh/nanodeus-cv-ci.pub`) après les options :

```
command="/opt/nanodeus-cv/ssh-commande.sh",restrict ssh-ed25519 AAAA… nanodeus-cv-ci
```

**Contrôle :**
- `ssh -i ~/.ssh/nanodeus-cv-ci deploy@<netcup> id` répond « commande refusée » ;
- `ssh -i ~/.ssh/nanodeus-cv-ci deploy@<netcup> /opt/nanodeus-cv/backup.sh --db-only`
  répond « Première mise en ligne : rien à sauvegarder ».

## 3. Secrets et environnement GitHub `production`

Dans *Settings → Environments*, créer l'environnement `production`. Sous *Deployment
branches and tags*, choisir *Selected branches and tags* et n'y ajouter que la règle de
tag `v*`. Les jobs `backup` et `deploy`, les seuls qui lisent les secrets, ne
tourneront alors que sur un tag de version.

Dans *Settings → Rules → Rulesets*, ajouter une règle de tags sur `v*` qui réserve leur
création et leur suppression aux administrateurs du dépôt.

Poser ensuite les quatre secrets de l'environnement :

```sh
gh secret set NETCUP_HOST --env production         # <netcup>
gh secret set NETCUP_USER --env production         # deploy
gh secret set NETCUP_SSH_KEY --env production < ~/.ssh/nanodeus-cv-ci
```

La clé d'hôte se vérifie **avant** d'être posée. La pipeline lui fera une confiance
aveugle : elle tourne en `StrictHostKeyChecking=yes` et refuse tout autre hôte.

```sh
ssh-keyscan -t ed25519 <netcup> > hote-netcup
ssh-keygen -lf hote-netcup
```

Comparer l'empreinte affichée à celle que donne, **sur le serveur**,
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Une fois les deux empreintes
identiques, et seulement à ce moment-là :

```sh
gh secret set NETCUP_KNOWN_HOSTS --env production < hote-netcup
rm hote-netcup
```

Une fois les secrets posés, effacer la clé privée du poste :
`rm ~/.ssh/nanodeus-cv-ci`.

**Contrôle :** `gh secret list --env production` liste les quatre noms.

## 4. Envoi des emails (Brevo)

1. Créer un compte Brevo gratuit.
2. Dans *Senders, Domains & Dedicated IPs → Domains*, authentifier `nanodeus.com`.
   Brevo demande plusieurs enregistrements : le code de vérification, la clé DKIM et
   un enregistrement DMARC. Les créer dans le DNS netcup. Si aucune politique DMARC
   n'existe encore, `_dmarc` en TXT `v=DMARC1; p=none;` suffit pour commencer.
3. Dans *Senders*, déclarer l'expéditeur `cv@nanodeus.com`. Aucune boîte n'est
   nécessaire : l'adresse ne sert qu'à envoyer.
4. Dans *SMTP & API → SMTP*, générer une clé SMTP. La poser dans le `.env` du serveur :

   ```
   CV_SMTP_HOTE=smtp-relay.brevo.com
   CV_SMTP_PORT=587
   CV_SMTP_TLS=starttls
   CV_SMTP_UTILISATEUR=<identifiant SMTP affiché par Brevo>
   CV_SMTP_MOT_DE_PASSE=<clé SMTP>
   CV_EMAIL_EXPEDITEUR=cv@nanodeus.com
   CV_EMAIL_DESTINATAIRE=<boîte perso>
   ```

**Contrôle :**
- Brevo affiche le domaine comme authentifié ;
- après la mise en ligne (étape 6), le bouton « Envoyer un email de test » de l'admin
  fait arriver un email dans la boîte perso, sans passer par les indésirables.

## 5. Timer de nuit : sauvegarde et purge

L'unité `nanodeus-cv-nuit` tourne à 04:15, après la sauvegarde de ReadLN (03:30). Elle
purge d'abord les sels passés et les visites de plus de six mois, puis sauvegarde la
base et les photos dans le dépôt restic de ReadLN, sous `--host nanodeus-cv`. Une purge
en échec n'empêche pas la sauvegarde ; elle se lit dans le journal de l'unité.

Les unités sont déposées par `deploy` à côté des scripts. On évite `/tmp`, qui est un
tmpfs sur ce serveur :

```sh
scp deploy/nanodeus-cv-nuit.service deploy/nanodeus-cv-nuit.timer \
    deploy@<netcup>:/opt/nanodeus-cv/
```

Puis, avec le **compte d'administration** :

```sh
sudo cp /opt/nanodeus-cv/nanodeus-cv-nuit.service /opt/nanodeus-cv/nanodeus-cv-nuit.timer \
    /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nanodeus-cv-nuit.timer
```

Le mot de passe du dépôt, `/opt/readln/restic-password`, est seulement lu. On ne le
supprime **jamais**, et on ne le régénère **jamais** : sans lui, toutes les sauvegardes
du serveur sont perdues.

**Contrôle**, avec le compte d'administration :
- `systemctl list-timers nanodeus-cv-nuit.timer` affiche le prochain passage ;
- après la mise en ligne, `sudo systemctl start nanodeus-cv-nuit.service` puis
  `sudo journalctl -u nanodeus-cv-nuit -n 30` se terminent par « Sauvegarde nocturne
  terminée ».

## 6. Mise en ligne par tag

La release part d'un tag `v*` posé sur `develop`, une fois la CI verte :

```sh
git tag -a v1.0.0 -m "v1.0.0"
git push origin v1.0.0
```

`release.yml` enchaîne quatre étapes : les vérifications, l'image
`ghcr.io/jeremylacaze/nanodeus-cv:<sha>`, la sauvegarde `--db-only`, puis
`deploy.sh`. Le script tire l'image, réécrit `CV_IMAGE` dans le `.env`, rejoue la
migration et attend que `public` soit sain.

À la toute première release, le paquet GHCR est encore privé, et le serveur ne peut
pas le tirer. Le job `deploy` échoue alors sur le `docker pull`, avant d'avoir rien
changé sur le serveur. Il faut passer le paquet en public (*Package settings → Change
visibility → Public*), puis relancer le job (*Re-run failed jobs*).

**Contrôle :**
- `curl -sI https://cv.nanodeus.com/` renvoie 200, une en-tête
  `Content-Security-Policy` et aucun `Set-Cookie` ;
- `curl -s https://cv.nanodeus.com/sante` renvoie `ok` ;
- `curl -sI https://cv.nanodeus.com/admin/` renvoie 404 ;
- depuis une machine du tailnet, `http://<ip-tailnet>:8780/admin/` ouvre l'admin. Après
  une visite, son journal porte une source en 100.x, et non une adresse du réseau
  Docker ;
- depuis une machine hors du tailnet, `curl -m 5 http://<netcup>:8780/` échoue.

## 7. Retour arrière

Quand le déploiement échoue après la bascule, `deploy.sh` affiche la commande de retour
arrière, avec l'image précédente. Il ne la lance jamais lui-même. Les journaux de
l'échec restent sur le serveur, dans `/opt/nanodeus-cv/echecs/` : ils peuvent contenir
des demandes de contact, et le log de la release est public. Les SHA des images
publiées se trouvent dans l'historique des runs de `release.yml`.

**Release sans migration.** Dans une session SSH sur le serveur :

```sh
/opt/nanodeus-cv/deploy.sh ghcr.io/jeremylacaze/nanodeus-cv:<sha précédent>
```

**Release avec migration.** L'ancienne image ne connaît pas la révision Alembic de la
base, et son service `migrate` refuse de démarrer. La commande ci-dessus échoue donc,
puis propose à son tour l'image fautive. L'ordre est le suivant :

1. arrêter les services (étape 8, point 2) ;
2. restaurer le snapshot `pre-deploy` pris juste avant la release fautive (étape 8,
   points 1 et 3) ;
3. **sans** passer par l'étape 8, point 4, lancer
   `/opt/nanodeus-cv/deploy.sh ghcr.io/jeremylacaze/nanodeus-cv:<sha précédent>`.
   Le script réécrit `CV_IMAGE`, puis démarre l'ancienne image sur la base restaurée.

Un `up -d` lancé avant le point 3 démarrerait l'image fautive, qui migrerait de nouveau
la base restaurée.

**Contrôle :** les contrôles de l'étape 6 repassent au vert.

## 8. Restauration depuis restic

Toutes les commandes se lancent sur le serveur, dans `/opt/nanodeus-cv`. Pendant la
restauration, ne poser aucun tag `v*`, et ne pas la lancer à l'heure du timer (04:15).
Commencer par définir l'accès au dépôt :

```sh
RESTIC=(docker run --rm --hostname nanodeus-cv
  -v /opt/readln/restic:/repo
  -v /opt/readln/restic-password:/run/secrets/restic-password:ro
  -e RESTIC_REPOSITORY=/repo -e RESTIC_PASSWORD_FILE=/run/secrets/restic-password)
IMAGE_RESTIC=$(sed -n 's/^RESTIC_IMAGE="\(.*\)"$/\1/p' backup.sh)
```

1. Choisir le snapshot : `"${RESTIC[@]}" "$IMAGE_RESTIC" snapshots --host nanodeus-cv`.
   La famille `pre-deploy` ne contient que la base. La famille `nightly` contient la
   base et les photos.
2. Arrêter les services :
   `docker compose --project-directory /opt/nanodeus-cv -f compose.yml stop public admin`.
3. Restaurer dans le volume. Ensuite, remplacer la base vivante par sa copie, retirer
   le journal WAL et rendre les fichiers à l'UID 1000 :

   ```sh
   "${RESTIC[@]}" -v nanodeus-cv-donnees:/data --entrypoint sh "$IMAGE_RESTIC" -c '
     restic restore <id du snapshot> --target / &&
     cp /data/.sauvegarde/cv.sqlite3 /data/cv.sqlite3 &&
     rm -f /data/cv.sqlite3-wal /data/cv.sqlite3-shm &&
     chown -R 1000:1000 /data'
   ```

   `latest --host nanodeus-cv --tag cv,nightly` peut remplacer l'identifiant.
4. Redémarrer : `docker compose --project-directory /opt/nanodeus-cv -f compose.yml up -d`.

**Contrôle :** les contrôles de l'étape 6 passent, et l'admin montre le contenu
attendu.

## 9. Fichiers copiés à la main

La pipeline ne dépose **aucun** fichier sur le serveur. Elle tire une image et rejoue
`deploy.sh`, rien de plus. Toute modification de `deploy/compose.yml`, `deploy.sh`,
`backup.sh`, `ssh-commande.sh` ou des unités systemd exige un nouveau `scp`, comme aux
étapes 1 et 5 (et, pour les unités, un nouveau `sudo cp` suivi d'un `daemon-reload`). Sans cela, le serveur continue d'exécuter l'ancienne version, sans
aucun avertissement.

Après chaque copie, comparer les fichiers, unités installées comprises :

```sh
ssh deploy@<netcup> 'cd /opt/nanodeus-cv && sha256sum *.sh compose.yml &&
  cd /etc/systemd/system && sha256sum nanodeus-cv-nuit.service nanodeus-cv-nuit.timer'
(cd deploy && sha256sum *.sh compose.yml nanodeus-cv-nuit.service nanodeus-cv-nuit.timer)
```

Les deux listes doivent donner les mêmes empreintes, fichier par fichier.
