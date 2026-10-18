"""Contenu initial du CV, repris du CV papier (annexe A de la spec).

Le français est la source ; l'anglais est un premier jet à relire dans l'admin.
Règle n° 1 : aucune coordonnée ici (le dépôt est public). Téléphone, email et
date de naissance se saisissent dans l'admin.
"""
from datetime import date

PROFIL = dict(
    nom_complet="Jeremy LACAZE-RUSQUES",
    localisation="Toulouse, France",
    permis="B / A2",
    interets_fr="Musique\nJeux vidéo\nDessin",
    interets_en="Music\nVideo games\nDrawing",
    date_naissance=None,
    afficher_age=False,
    ouvert_opportunites=True,
    telephone=None,
    email=None,
)

ENTREES = [
    dict(
        type="formation", voie="principale",
        intitule_fr="Licence professionnelle Développement et Qualité des logiciels",
        intitule_en="Professional bachelor's degree in Software Development and Quality",
        organisation="Université Toulouse III – Paul Sabatier", lieu="Toulouse",
        debut=date(2020, 6, 1), fin=date(2020, 6, 1),
    ),
    dict(
        type="formation", voie="principale",
        intitule_fr="Mastère Expert en Développement logiciel mobile & IoT",
        intitule_en="Master's degree, Mobile & IoT Software Development Expert",
        organisation="Ynov Campus", lieu="Toulouse",
        debut=date(2023, 6, 1), fin=date(2023, 6, 1),
    ),
    dict(
        type="poste", voie="principale",
        intitule_fr="Ingénieur DevOps", intitule_en="DevOps engineer",
        organisation="Navocap", via="Astek", lieu="Toulouse",
        debut=date(2023, 10, 1), fin=date(2024, 2, 1),
        technos="Docker · Windows · Automatisation",
        missions_fr=(
            "Mise en place d'un environnement Docker sur les machines des utilisateurs\n"
            "Image Docker fournissant un environnement Windows Data Center sur les postes"
            " des développeurs\n"
            "Automatisation du déploiement de cet environnement"),
        missions_en=(
            "Set up a Docker environment on users' machines\n"
            "Docker image providing a Windows Data Center environment on developers'"
            " workstations\n"
            "Automated the deployment of this environment"),
    ),
    dict(
        type="poste", voie="principale",
        intitule_fr="Administrateur Atlassian", intitule_en="Atlassian administrator",
        organisation="SQLI · ADS", via="Astek", lieu="Toulouse",
        debut=date(2024, 2, 1), fin=date(2025, 5, 1),
        technos="Jira · Confluence · Crowd · GitLab · Artifactory",
        missions_fr=(
            "Maintenance et développement d'outils tels que Jira, Confluence, Crowd, GitLab"
            " et Artifactory\n"
            "Support des applications en contact direct avec les utilisateurs\n"
            "Support et configuration des serveurs hébergeant les applications"),
        missions_en=(
            "Maintenance and development of tools such as Jira, Confluence, Crowd, GitLab"
            " and Artifactory\n"
            "Application support in direct contact with users\n"
            "Support and configuration of the servers hosting the applications"),
    ),
    dict(
        type="poste", voie="principale",
        intitule_fr="Administrateur applicatif", intitule_en="Application administrator",
        organisation="SQLI · ADS", lieu="Toulouse",
        debut=date(2025, 5, 1), fin=None,
        technos="Jira · Confluence · GitLab · Artifactory · Mattermost · Kubernetes",
        missions_fr=(
            "Administrateur applicatif et serveur pour : Jira Data Center, Confluence Data"
            " Center, GitLab Self-Hosted, Artifactory Self-Hosted, Mattermost Self-Hosted\n"
            "Le tout déployé sous un environnement Kubernetes"),
        missions_en=(
            "Application and server administrator for: Jira Data Center, Confluence Data"
            " Center, GitLab Self-Hosted, Artifactory Self-Hosted, Mattermost Self-Hosted\n"
            "All of it deployed on a Kubernetes environment"),
    ),
    dict(
        type="projet", voie="parallele",
        intitule_fr="ReadLN, projet personnel", intitule_en="ReadLN, personal project",
        organisation="ReadLN",
        debut=date(2025, 1, 1), fin=None,
        technos="Flask · PostgreSQL · Redis / RQ · SocketIO · Docker Compose · Traefik",
        missions_fr=(
            "Application web multi-utilisateurs de traduction de light novels (PDF / EPUB →"
            " EPUB / PDF traduit) par un LLM local, avec lecteur, discussions et"
            " notifications\n"
            "Flask, PostgreSQL, Redis / RQ, SocketIO, Docker Compose, Traefik\n"
            "CI/CD GitHub Actions, images taguées par commit sur GHCR, déploiement"
            " automatisé sur VPS, sauvegardes restic chiffrées"),
        missions_en=(
            "Multi-user web application that translates light novels (PDF / EPUB →"
            " translated EPUB / PDF) with a local LLM, with a reader, discussions and"
            " notifications\n"
            "Flask, PostgreSQL, Redis / RQ, SocketIO, Docker Compose, Traefik\n"
            "CI/CD with GitHub Actions, images tagged per commit on GHCR, automated"
            " deployment to a VPS, encrypted restic backups"),
    ),
]

SOFT_SKILLS = [
    dict(nom_fr="Porteur d'idées", nom_en="Idea driver",
         preuve_fr="A imaginé, construit et mis en production ReadLN seul.",
         preuve_en="Designed, built and shipped ReadLN to production on his own."),
    dict(nom_fr="Pédagogie", nom_en="Teaching mindset",
         preuve_fr="Support direct et accompagnement des utilisateurs Jira / Confluence.",
         preuve_en="Direct support and coaching of Jira / Confluence users."),
    # Preuve à écrire dans l'admin : sans elle, le test n'est pas affiché.
    dict(nom_fr="Autonomie", nom_en="Autonomy", preuve_fr=None, preuve_en=None),
]

_CATEGORIES = {"Ops": "Ops", "Développement": "Development", "Langues": "Languages"}
COMPETENCES = [
    dict(nom_fr=nom_fr, nom_en=nom_en, categorie_fr=cat, categorie_en=_CATEGORIES[cat])
    for cat, nom_fr, nom_en in [
        ("Ops", "Docker", "Docker"),
        ("Ops", "Kubernetes", "Kubernetes"),
        ("Ops", "Shell / PowerShell", "Shell / PowerShell"),
        ("Développement", "Java / C", "Java / C"),
        ("Développement", "Python / PostgreSQL", "Python / PostgreSQL"),
        ("Développement", "HTML / CSS / PHP / JavaScript", "HTML / CSS / PHP / JavaScript"),
        ("Langues", "Anglais technique", "Technical English"),
    ]
]

CHIFFRES = [
    dict(valeur_fr="3 ans", valeur_en="3 yrs",
         libelle_fr="d'expérience", libelle_en="of experience"),
    dict(valeur_fr="5", valeur_en="5",
         libelle_fr="outils administrés sur Kubernetes", libelle_en="tools run on Kubernetes"),
    dict(valeur_fr="1", valeur_en="1",
         libelle_fr="projet perso en production", libelle_en="side project in production"),
    dict(valeur_fr="Bac+5", valeur_en="Master's",
         libelle_fr="Mastère Ynov", libelle_en="Ynov degree"),
]

_ACCROCHE = dict(
    accroche_fr="Porteur d'idées, autonome, je fais grandir les équipes avec pédagogie.",
    accroche_en="An idea driver who works autonomously and helps teams grow through"
                " clear teaching.",
)
VERSIONS = [
    dict(slug="devops", statut="publiee", par_defaut=True,
         titre_fr="Administrateur applicatif / DevOps",
         titre_en="Application administrator / DevOps",
         prochaine_mission_fr="Administrateur applicatif senior",
         prochaine_mission_en="Senior application administrator", **_ACCROCHE),
    dict(slug="lead-tech", statut="non_listee", par_defaut=False,
         titre_fr="Administrateur applicatif / DevOps → Lead tech",
         titre_en="Application administrator / DevOps → Tech lead",
         prochaine_mission_fr="Lead tech", prochaine_mission_en="Tech lead", **_ACCROCHE),
]
