import requests
import json
import time
from coordFormatting import CoordFormatting
from secret import orsSecretKey, jcdSecretKey


# Getting the updated list of velÔtoulouse stations with the current number of free bike stands
def getJCDDynamicData():
    API_URL = "https://api.jcdecaux.com"
    CONTRACT_NAME = "toulouse"
    requestUrl = API_URL + "/vls/v1/stations?contract=" + \
        CONTRACT_NAME + '&apiKey=' + jcdSecretKey

    resp = requests.get(requestUrl)
    if resp.status_code == 200:
        try:
            JCDDyanmicData = json.loads(resp.text)
            if len(JCDDyanmicData) == 0:
                raise KeyError("réponse vide du serveur")
            print("...", end='')
            return JCDDyanmicData
        except (json.JSONDecodeError, KeyError) as err:
            print(
                f"\n[X] Les données de station ne sont pas correctement formattées (get-{err})")
            exit(1)
    else:
        print(
            f"\n[X] Les données de station n'ont pas été correctement récupérées (get-{err})")
        exit(1)


# Completing JCD data for better processing
def completeJCDStaticData(JCDData):
    try:
        for station in JCDData:
            # Adding a field coordinate
            station["coordinates"] = str(
                station["position"]["lat"])+","+str(station["position"]["lng"])
        print("...", end='')
    except Exception as err:
        print(
            f"\n[X] Les données de station ne sont pas correctement formattées (complete-{err})")


def reduceNumberOfStations(addrFrom, JCDData):
    # Measured in Toulouse downtown
    # Latitude: 0.01° = 1.12km
    # Longitude: 0.01° = 805m
    # Mean ~ 1km
    KM_TO_DEGREES_CONVERTION = 0.01
    SQUARE_FIRST_HALF_LENGTH_DEGREES = 0.0025
    SQUARE_INCREMENTED_LENGTH_DEGREES = 0.0025
    MINIMAL_NB_REDUCED_STATIONS = 5
    # Limit of OpenRouteService API requests per minute
    MAXIMAL_NB_REDUCED_STATIONS = 40
    # If we are more than 2km away from any station: we give up
    MAX_NB_OF_KMS = 2.0
    MAX_NB_OF_ATTEMPTS = 1 + int(
        MAX_NB_OF_KMS * KM_TO_DEGREES_CONVERTION / SQUARE_INCREMENTED_LENGTH_DEGREES)
    JCDDataReduced = []

    addrFromSplitted = addrFrom.split(',')
    try:
        lat = float(addrFromSplitted[0].strip(" "))
        lon = float(addrFromSplitted[1].strip(" "))
    # FIXME Replace by a more specific Exception
    except Exception as err:
        print(
            f"[X] Les données statiques de station ne sont pas correctement formattées (reduce-{err})")

    nbStationFound = 0
    squareHalfLengthDegrees = SQUARE_FIRST_HALF_LENGTH_DEGREES
    nbAttempts = 0

    # Find closed stations in a square arround the coordinates. If not enough are found, extend the size of the square
    while nbStationFound == 0:
        nbAttempts += 1
        for station in JCDData:
            if abs(station["position"]["lat"]-lat) <= squareHalfLengthDegrees and abs(station["position"]["lng"]-lon) <= squareHalfLengthDegrees:
                JCDDataReduced.append(station)
                nbStationFound += 1

        if nbStationFound > MAXIMAL_NB_REDUCED_STATIONS:
            # Too much requests for the API
            SQUARE_FIRST_HALF_LENGTH_DEGREES /= 2
            SQUARE_INCREMENTED_LENGTH_DEGREES /= 2
            squareHalfLengthDegrees = SQUARE_FIRST_HALF_LENGTH_DEGREES
            nbAttempts -= 1

        if nbStationFound < MINIMAL_NB_REDUCED_STATIONS:
            # Not enough results
            squareHalfLengthDegrees += SQUARE_INCREMENTED_LENGTH_DEGREES
            # Make sure the next count is exact
            nbStationFound = 0

        if nbAttempts > MAX_NB_OF_ATTEMPTS:
            raise ValueError(
                f"[X] L'adresse indiquée est trop éloignée (plus de {MAX_NB_OF_KMS} kms) de n'importe-quelle station.")

    #print(f"DEBUG: {nbAttempts} attempts, found {nbStationFound} stations")
    return JCDDataReduced


# API: https://nominatim.org/release-docs/latest/api/Search/
def getCoordsFromAddr(addr):
    addrSplitted = addr.strip(' ').split(',')
    try:
        if len(addrSplitted) != 2:
            # Caught just below
            raise IndexError(f"Length is {addrSplitted}")
        else:
            lat = float(addrSplitted[0].strip(" "))
            lon = float(addrSplitted[1].strip(" "))
            if lat >= -90.0 and lat <= 90.0 and lon >= -180.0 and lon <= 180.0:
                return str(lat)+','+str(lon)
            else:
                raise CoordFormatting("")
    except (IndexError, ValueError):
        # Reached when lat/long are not floats
        # I guess this is an address. Calling Nominatim (OSM) API to get the coordinates
        apiUrl = "https://nominatim.openstreetmap.org"
        requestUrl = apiUrl+"/search?q="+addr+'&format=json'
        resp = requests.get(requestUrl)
        if resp.status_code != 200:
            raise CoordFormatting(
                f"erreur serveur ({resp.status_code})")
        elif resp.text == '[]':
            raise CoordFormatting("l'adresse n'existe pas")
        else:
            try:
                nominatimJsonPayload = json.loads(resp.text)
                latStr = str(nominatimJsonPayload[0]['lat'])
                lonStr = str(nominatimJsonPayload[0]['lon'])
                if latStr == "" or lonStr == "":
                    raise CoordFormatting(
                        f"la réponse du serveur est tronquée, mal formattée, ou il manque les infos de latitude ({latStr}) et longitude ({lonStr}) - ({err})")
                else:
                    rebuiltAddr = latStr + ',' + lonStr
                    return rebuiltAddr
            except json.JSONDecodeError as err:
                raise CoordFormatting(
                    f"la réponse du serveur est tronquée ou mal formattée ({err})")
            except (IndexError, KeyError, TypeError) as err:
                raise CoordFormatting(
                    f"la réponse du serveur est tronquée, mal formattée, ou il manque les infos de latitude et longitude ({err})")


# If we are in beginning mode, the station must have available bikes
# If we are in end mode, the station must have available stands
def getDistWithStation(addr, station, flagEndMode):
    VERY_LONG_DISTANCE = 9999999999999999999999.0
    MIN_AVAILABLE_BIKE = 1
    MIN_AVAILABLE_BIKE_STANDS = 3

    try:
        if station["status"] != "OPEN":
            return VERY_LONG_DISTANCE
        if flagEndMode:
            if station["available_bike_stands"] < MIN_AVAILABLE_BIKE_STANDS:
                return VERY_LONG_DISTANCE
            # Nearest distance between a station and the address
            return getDistORS(station["coordinates"], addr)
        else:
            if station["available_bikes"] < MIN_AVAILABLE_BIKE:
                return VERY_LONG_DISTANCE
            # Nearest distance the address and a station
            return getDistORS(addr, station["coordinates"])
    except (ValueError, IndexError, TypeError) as err:
        print(f"[X] Il y a eu un problème lors du calcul de distance: {err}")


# API: https://openrouteservice.org/dev/#/api-docs/v2/directions/{profile}/get
def getDistORS(addrFrom, addrTo):
    apiUrl = "https://api.openrouteservice.org"
    profile = "foot-walking"

    # For this API, lat and lon are inverted
    addrFromSplitted = addrFrom.split(',')
    addrFromFormatted = addrFromSplitted[1].strip(
        " ")+','+addrFromSplitted[0].strip(" ")

    addrToSplitted = addrTo.split(',')
    addrToFormatted = addrToSplitted[1].strip(
        " ")+','+addrToSplitted[0].strip(" ")

    requestUrl = apiUrl+"/v2/directions/"+profile+'?api_key=' + \
        orsSecretKey+'&start='+addrFromFormatted + '&end=' + addrToFormatted
    resp = requests.get(requestUrl)
    if resp.status_code == 200:
        try:
            orsJsonPayload = json.loads(resp.text)
            distance = float(
                orsJsonPayload["features"][0]["properties"]["summary"]["distance"])
            #duration = orsJsonPayload["features"][0]["properties"]["summary"]["duration"]
            return distance
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as err:
            print(
                f"\n[X] Impossible de calculer la distance à pied entre les deux points: {err}")
            exit(3)
    elif resp.status_code == 429:
        print(f"\n[X] Trop de requête, réessayez dans 1 minute")
        exit(4)
    else:
        print(
            f"\n[X] Impossible de calculer la distance à pied entre les deux points: {err}")
        exit(3)


def findNearestStation(addrFromCoord, JCDDataReduced, flagEndMode):
    if flagEndMode:
        print("Recherche de la station la plus proche de l'adresse...", end='')
    else:
        print("Recherche de la station la plus proche...", end='')
    nearestStation = min(JCDDataReduced, key=lambda station: getDistWithStation(
        addrFromCoord, station, flagEndMode))

    print("trouvée !")

    return nearestStation


def main():
    JCDData = []
    JCDDataReduced = []

    print("Initialisation...", end='')

    # Ask the velÔToulouse API to get the list of stations with its coordinates
    JCDData = getJCDDynamicData()

    completeJCDStaticData(JCDData)

    print("terminée.\n")
    time.sleep(0.5)

    # Ask if we want to go to the nearest station or if we are looking for the nearest station to drive to to go to a final address
    endMode = input("Mode actuel : Début de trajet - plus proche station à pied où prendre son vélo à partir de l'adresse indiquée.\nTape F pour passer en mode Fin de trajet - station où poser son vélo pour rejoindre l'adresse indiquée : ")
    endMode = endMode.strip(" .\n\r\t").lower()
    if endMode == "f":
        flagEndMode = True
        TEXT_INPUT_POSITION = "Adresse d'arrivée : "
        print("> Mode Fin de trajet\n")
    else:
        flagEndMode = False
        TEXT_INPUT_POSITION = "Adresse actuelle/de départ : "
        print("> Mode Début de trajet\n")

    # Ask for current position
    addrFrom = input(TEXT_INPUT_POSITION)
    addrFrom = addrFrom.strip(" .\n\r\t")

    print("")

    try:
        addrFromCoord = getCoordsFromAddr(addrFrom)
    except CoordFormatting as err:
        print(
            f"[X] Erreur lors de la récupération des coordonnées de l'adresse: {err}")
        exit(2)

    try:
        JCDDataReduced = reduceNumberOfStations(
            addrFromCoord, JCDData)

    except ValueError as err:
        print(err)
        exit(3)

    nearestStation = findNearestStation(
        addrFromCoord, JCDDataReduced, flagEndMode)
    time.sleep(1.0)

    stationName = nearestStation["name"]
    stationAddress = nearestStation["address"]
    stationAvBikeStands = nearestStation["available_bike_stands"]
    stationAvBikes = nearestStation["available_bikes"]
    print(
        f"\n> Station {stationName} ({stationAvBikes} vélo(s) disponible(s) / {stationAvBikeStands} place(s) libre(s))\n  Adresse : {stationAddress}")


if __name__ == '__main__':
    print('- toutRoule - \n')

    main()
    exit(0)
