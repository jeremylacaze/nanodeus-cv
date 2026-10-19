# Image unique du CV : le rôle (public ou admin) vient de CV_ROLE, posé par Compose.
FROM python:3.14-slim

# Pango et HarfBuzz pour WeasyPrint (importé au chargement du site public), et les
# polices DejaVu nommées par templates/pdf.css : sans elles, le PDF changerait de
# police, donc de mise en page.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Les .mo (non versionnés) sont compilés ici : le conteneur tourne en lecture seule,
# l'application ne pourrait pas les écrire au démarrage. /data recevra le volume.
RUN python scripts/i18n.py compile \
    && useradd -u 1000 -m cv \
    && mkdir /data \
    && chown cv:cv /data
# UID numérique (hadolint DL3066).
USER 1000

# XDG_CACHE_HOME : fontconfig écrit son cache dans le tmpfs /tmp.
ENV CV_DATA_DIR=/data \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/tmp/cache

EXPOSE 8000

# Aucun journal d'accès : il contiendrait l'adresse IP de chaque visiteur.
# --timeout 60 couvre la génération d'un PDF. Système de fichiers en lecture seule :
# fichiers des workers en mémoire, et pas de socket de contrôle (gunicorn ≥ 26 le
# crée sinon dans $HOME).
CMD ["gunicorn", "-k", "gthread", "-w", "2", "--threads", "4", "--timeout", "60", \
     "--worker-tmp-dir", "/dev/shm", "--no-control-socket", "-b", "0.0.0.0:8000", \
     "cv.app:create_app()"]
