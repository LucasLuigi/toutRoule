# toutRoule

Ce programme permet de trouver la station de velÔToulouse la plus proche de l'adresse indiquée (ou de la localisation actuelle). Des coordonnées GPS peuvent aussi être entrés.

Il ne marche qu'à Toulouse, mais au vu de l'API JCDecaux il peut être utilisé dans n'importe quelle ville ayant des stations exploitées par JC Decaux

Il utilise trois APIs, [Nominatif OpenStreetMap](https://nominatim.org/release-docs/latest/api/Search/), [openrouteservice V2](https://openrouteservice.org/dev/#/api-docs/v2/directions) et [JCDecaux API](https://developer.jcdecaux.com/#/opendata/vls?page=getstarted).

## Avancement

Pour le moment, seuls la conversion d'adresse en coordonnées et le calcul d'itinéraire sont implémentés.
