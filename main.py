from ast import Index
from glob import glob
import imp
import googlemaps
import requests
import json
import time
from coordFormatting import CoordFormatting
from secret import orsSecretKey, jcdSecretKey


def getJCDStaticData():
    # API_URL = "https://api.jcdecaux.com"
    API_URL = "https://developer.jcdecaux.com"
    CONTRACT_NAME = "toulouse"

    #requestUrl = API_URL + "/vls/v1/stations?contract=" + CONTRACT_NAME + '&apiKey=' + jcdSecretKey
    requestUrl = API_URL + "/rest/vls/stations/" + CONTRACT_NAME + ".json"
    resp = requests.get(requestUrl)
    if resp.status_code == 200:
        try:
            JCDStaticData = json.loads(resp.text)
            if len(JCDStaticData) == 0:
                raise KeyError("réponse vide du serveur")
            print("...", end='')
            return JCDStaticData
        except (json.JSONDecodeError, KeyError) as err:
            print(
                f"\n[X] Les données statiques de station ne sont pas correctement formattées (get-{err})")
            exit(1)
    else:
        print(
            f"\n[X] Les données statiques de station n'ont pas été correctement récupérées (get-{err})")
        exit(1)


# WIP
def getJCDDynamicData():
    API_URL = "https://api.jcdecaux.com"
    CONTRACT_NAME = "toulouse"
    requestUrl = API_URL + "/vls/v1/stations?contract=" + \
        CONTRACT_NAME + '&apiKey=' + jcdSecretKey


# Adding in JCDStaticData for each station a stringed tuple of the coordinates
def completeJCDStaticData(JCDStaticData):
    try:
        for station in JCDStaticData:
            station["coordinates"] = str(
                station["latitude"])+","+str(station["longitude"])
        print("...", end='')
    except Exception as err:
        print(
            f"[X] Les données statiques de station ne sont pas correctement formattées (complete-{err})")


def reduceNumberOfStations(addrFrom, JCDStaticData):
    # Measured in Toulouse downtown
    # Latitude: 0.01° = 1.12km
    # Longitude: 0.01° = 805m
    # Mean ~ 1km
    KM_TO_DEGREES_CONVERTION = 0.01
    SQUARE_FIRST_HALF_LENGTH_DEGREES = 0.0025
    SQUARE_INCREMENTED_LENGTH_DEGREES = 0.0025
    MINIMAL_NB_REDUCED_STATIONS = 2
    # If we are more than 2km away from any station: we give up
    MAX_NB_OF_KMS = 2.0
    MAX_NB_OF_ATTEMPTS = 1 + int(
        MAX_NB_OF_KMS * KM_TO_DEGREES_CONVERTION / SQUARE_INCREMENTED_LENGTH_DEGREES)
    JCDStaticDataReduced = []

    addrFromSplitted = addrFrom.split(',')
    try:
        lat = float(addrFromSplitted[0].strip(" "))
        lon = float(addrFromSplitted[1].strip(" "))
    # FIXME Replace by more specific Exception
    except Exception as err:
        print(
            f"[X] Les données statiques de station ne sont pas correctement formattées (reduce-{err})")

    nbStationFound = 0
    squareHalfLengthDegrees = SQUARE_FIRST_HALF_LENGTH_DEGREES
    nbAttempts = 0

    # Find closed stations in a square arround the coordinates. If not enough are found, extend the size of the square
    while nbStationFound == 0:
        nbAttempts += 1
        for station in JCDStaticData:
            if abs(station["latitude"]-lat) <= squareHalfLengthDegrees and abs(station["longitude"]-lon) <= squareHalfLengthDegrees:
                JCDStaticDataReduced.append(station)
                nbStationFound += 1

        if nbStationFound < MINIMAL_NB_REDUCED_STATIONS:
            # Not enough results
            squareHalfLengthDegrees += SQUARE_INCREMENTED_LENGTH_DEGREES
            # Make sure the next count is exact
            nbStationFound = 0

        if nbAttempts > MAX_NB_OF_ATTEMPTS:
            raise ValueError(
                f"[X] L'adresse indiquée est trop éloignée (plus de {MAX_NB_OF_KMS} kms) de n'importe-quelle station.")

    #print(f"DEBUG: {nbAttempts} attempts, found {nbStationFound} stations")
    return JCDStaticDataReduced


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
            distance = orsJsonPayload["features"][0]["properties"]["summary"]["distance"]
            duration = orsJsonPayload["features"][0]["properties"]["summary"]["duration"]
            return distance, duration
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as err:
            print(
                f"[X] Impossible de calculer la distance à pied entre les deux points: {err}")
            exit(3)
    else:
        print(
            f"[X] Impossible de calculer la distance à pied entre les deux points: {err}")
        exit(3)


def main():
    JCDStaticData = []
    JCDStaticDataReduced = []

    print("Initialisation", end='')

    # Ask the velÔToulouse API to get the list of stations with its coordinates
    JCDStaticData = getJCDStaticData()

    completeJCDStaticData(JCDStaticData)

    print("... terminée.")
    time.sleep(0.5)

    # Ask for current position
    addrFrom = input("Adresse actuelle : ")
    addrFrom = addrFrom.strip(" .\n\r\t")

    #addrFrom = '1 rue Valade, Toulouse'
    #addrFrom = '43.60798370654071, 1.4415337673273596'
    try:
        addrFromCoord = getCoordsFromAddr(addrFrom)
    except CoordFormatting as err:
        print(
            f"[X] Erreur lors de la récupération des coordonnées de l'adresse: {err}")
        exit(2)

    try:
        JCDStaticDataReduced = reduceNumberOfStations(
            addrFromCoord, JCDStaticData)

        # TEST, to remove
        # addrFrom = '43.65723761277264, 1.2737243831651757'
        # addrFromCoord = getCoordsFromAddr(addrFrom)
        # #tmp1 = reduceNumberOfStations(addrFromCoord, JCDStaticData)

        # addrFrom = '43.610949082290205, 1.4684277881390817'
        # addrFromCoord = getCoordsFromAddr(addrFrom)
        # tmp2 = reduceNumberOfStations(addrFromCoord, JCDStaticData)
        # END OF TEST

    except ValueError as err:
        print(err)
        exit(3)

    # STUB. Later, it will be the station
    addrTo = '6 Rue Antoine Deville, Toulouse'
    addrToCoord = getCoordsFromAddr(addrTo)
    # END OF STUB

    distance, duration = getDistORS(addrFromCoord, addrToCoord)
    print(f"[-] Distance={distance}m, Duration={duration}s")


if __name__ == '__main__':
    print('- toutRoule - \n')

    main()
    exit(0)
