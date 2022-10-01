# toutRoule

Ce programme permet de trouver la station de velÔToulouse la plus proche de l'adresse indiquée, en prenant en compte les infos en temps réel de la station (nombre de vélos disponibles, infos à jour...)

Il y a 2 modes : le mode Début de trajet (l'utilisateur veut rejoindre à pied la station la plus proche) et le mode Fin de trajet (l'utilisateur cherche la station où poser son vélo la plus proche de son adresse de destination finale).

Il n'a été testé qu'à Toulouse, mais au vu de l'API JCDecaux il peut être utilisé dans n'importe quelle ville ayant des stations exploitées par JCDecaux. La modification de code est minime (la variable `CITY` dans le `main()`)

## Dépendances

Il utilise trois APIs, [Nominatif OpenStreetMap](https://nominatim.org/release-docs/latest/api/Search/), [openrouteservice V2](https://openrouteservice.org/dev/#/api-docs/v2/directions) et [JCDecaux API](https://developer.jcdecaux.com/#/opendata/vls?page=getstarted). Deux d'entre elles nécessitent de créer un compte (gratuit) et demander une clé API (gratuite et libre) à entrer dans [secret.py](secret.py)

## Evolution

Une meilleure UI est à l'étude, ainsi que l'ajout de la localisation actuelle et d'un lien pour ouvrir Maps à la fin.
