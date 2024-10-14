import requests
import json
import time
import argparse
import subprocess
from coordFormatting import CoordFormatting
from secret import ors_secret_key, jcd_secret_key


# Getting the updated list of velÔtoulouse stations with the current number of free bike stands
def get_JCD_dynamic_data(city):
    API_URL = "https://api.jcdecaux.com"
    CONTRACT_NAME = city
    request_url = API_URL + "/vls/v1/stations?contract=" + \
        CONTRACT_NAME + '&apiKey=' + jcd_secret_key

    resp = requests.get(request_url)
    if resp.status_code == 200:
        try:
            JCD_dynamic_data = json.loads(resp.text)
            if len(JCD_dynamic_data) == 0:
                raise KeyError("réponse vide du serveur")
            print("...", end='')
            return JCD_dynamic_data
        except (json.JSONDecodeError, KeyError) as err:
            print(
                f"\n[X] Les données de station ne sont pas correctement formattées (get-{err})")
            exit(1)
    else:
        print(
            f"\n[X] Les données de station n'ont pas été correctement récupérées (get-{err})")
        exit(1)


# Completing JCD data for better processing
def extend_JCD_static_data_for_processing(JCD_data):
    try:
        for station in JCD_data:
            # Adding a field coordinate
            station["coordinates"] = str(
                station["position"]["lat"])+","+str(station["position"]["lng"])
        print("...", end='')
    except Exception as err:
        print(
            f"\n[X] Les données de station ne sont pas correctement formattées (complete-{err})")


def reduce_number_of_stations(coords_waypoint, JCD_data):
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
    JCD_data_reduced = []

    coords_waypoint_splitted = coords_waypoint.split(',')
    try:
        lat = float(coords_waypoint_splitted[0].strip(" "))
        lng = float(coords_waypoint_splitted[1].strip(" "))
    # FIXME Replace by a more specific Exception
    except Exception as err:
        print(
            f"\n[X] Les données statiques de station ne sont pas correctement formattées (reduce-{err})")

    nb_station_found = 0
    square_half_length_degrees = SQUARE_FIRST_HALF_LENGTH_DEGREES
    nb_attempts = 0

    # Find closed stations in a square arround the coordinates. If not enough are found, extend the size of the square
    while nb_station_found == 0:
        nb_attempts += 1
        for station in JCD_data:
            if abs(station["position"]["lat"]-lat) <= square_half_length_degrees and abs(station["position"]["lng"]-lng) <= square_half_length_degrees:
                JCD_data_reduced.append(station)
                nb_station_found += 1

        if nb_station_found > MAXIMAL_NB_REDUCED_STATIONS:
            # Too much requests for the API
            SQUARE_FIRST_HALF_LENGTH_DEGREES /= 2
            SQUARE_INCREMENTED_LENGTH_DEGREES /= 2
            square_half_length_degrees = SQUARE_FIRST_HALF_LENGTH_DEGREES
            nb_attempts -= 1

        if nb_station_found < MINIMAL_NB_REDUCED_STATIONS:
            # Not enough results
            square_half_length_degrees += SQUARE_INCREMENTED_LENGTH_DEGREES
            # Make sure the next count is exact
            nb_station_found = 0

        if nb_attempts > MAX_NB_OF_ATTEMPTS:
            raise ValueError(
                f"\n[X] L'adresse indiquée est trop éloignée (plus de {MAX_NB_OF_KMS} kms) de n'importe-quelle station.")

    # print(f"DEBUG: {nbAttempts} attempts, found {nbStationFound} stations")
    return JCD_data_reduced


# API: https://nominatim.org/release-docs/latest/api/Search/
def get_coords_from_addr(addr: str) -> str:
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


def ask_coords_to_termux_api() -> any:
    coords = None
    TERMUX_CMD_GPS = "termux-location -p gps -r last".split(' ')
    termux_response_gps = subprocess.run(
        TERMUX_CMD_GPS, capture_output=True)
    if termux_response_gps.returncode == 0:
        try:
            termux_response_dict = json.loads(termux_response_gps.stdout)
            if "latitude" in termux_response_dict and "longitude" in termux_response_dict:
                termux_lat = termux_response_dict['latitude']
                termux_lon = termux_response_dict['longitude']
                coords = f"{termux_lat},{termux_lon}"
        except json.JSONDecodeError:
            pass
    return coords


def ask_address_to_user_and_convert_them_in_coords(input_label_string: str, CITY: str) -> str:
    # Ask for current position
    address_input = input(input_label_string)
    address_input = address_input.strip(" .\n\r\t")

    # By default, add the city to the address
    if CITY not in address_input.lower():
        address_input = address_input+", " + CITY

    try:
        coords_waypoint = get_coords_from_addr(address_input)
    except CoordFormatting as err:
        print(
            f"\n[X] Erreur lors de la récupération des coordonnées de l'adresse: {err}")
        exit(2)
    return coords_waypoint


# If we are in beginning mode, the station must have available bikes
# If we are in end mode, the station must have available stands
def compute_distance_with_station(coords_waypoint: str, station: dict, bikers_number: int, end_mode_flag: bool):
    VERY_LONG_DISTANCE = 9999999999999999999999.0
    MAX_SECONDS_SINCE_LAST_UPDATE = 1800
    NOW_IN_EPOCH_WITH_MS = int(time.time() * 1000)

    max_available_bikes = bikers_number
    max_available_bike_stands = 2 + bikers_number
    try:
        if station["status"] != "OPEN":
            return VERY_LONG_DISTANCE
        # last_update is in epoch ms
        if NOW_IN_EPOCH_WITH_MS - station["last_update"] > 1000*MAX_SECONDS_SINCE_LAST_UPDATE:
            return VERY_LONG_DISTANCE
        if end_mode_flag:
            if station["available_bike_stands"] < max_available_bike_stands:
                return VERY_LONG_DISTANCE
            # Nearest distance between a station and the address
            return ask_ORS_to_compute_distance(station["coordinates"], coords_waypoint)
        else:
            if station["available_bikes"] < max_available_bikes:
                return VERY_LONG_DISTANCE
            # Nearest distance the address and a station
            return ask_ORS_to_compute_distance(coords_waypoint, station["coordinates"])
    except (ValueError, IndexError, TypeError) as err:
        print(f"[X] Il y a eu un problème lors du calcul de distance: {err}")


# API: https://openrouteservice.org/dev/#/api-docs/v2/directions/{profile}/get
def ask_ORS_to_compute_distance(coords_from: str, coords_to: str) -> float:
    API_URL = "https://api.openrouteservice.org"
    profile = "foot-walking"

    # For this API, lat and lon are inverted
    coords_from_splitted = coords_from.split(',')
    coords_from_formatted = coords_from_splitted[1].strip(
        " ")+','+coords_from_splitted[0].strip(" ")

    corrds_to_splitted = coords_to.split(',')
    coords_to_formatted = corrds_to_splitted[1].strip(
        " ")+','+corrds_to_splitted[0].strip(" ")

    request_url = API_URL+"/v2/directions/"+profile+'?api_key=' + \
        ors_secret_key+'&start='+coords_from_formatted + '&end=' + coords_to_formatted
    resp = requests.get(request_url)
    if resp.status_code == 200:
        try:
            ors_json_payload = json.loads(resp.text)
            distance = float(
                ors_json_payload["features"][0]["properties"]["summary"]["distance"])
            return distance
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as err:
            print(
                f"\n[X] Impossible de calculer la distance à pied entre les deux points: {err}")
            exit(3)
    elif resp.status_code == 429:
        print("\n[X] Trop de requête, réessayez dans 1 minute")
        exit(4)
    else:
        print(
            f"\n[X] Impossible de calculer la distance à pied entre les deux points: {err}")
        exit(3)


def find_closest_station(coords_waypoint: str, JCD_data_reduced: list, bikers_number: int, end_mode_flag: bool):
    closest_station = min(JCD_data_reduced, key=lambda station: compute_distance_with_station(
        coords_waypoint, station, bikers_number, end_mode_flag))
    print("trouvée !")

    return closest_station


def main(termux_api: bool, bikers_number: int):
    CITY = "toulouse"

    JCD_data = []
    JCD_data_reduced = []

    print("Initialisation...", end='')

    # Ask the velÔToulouse API to get the list of stations with its coordinates
    JCD_data = get_JCD_dynamic_data(CITY)

    extend_JCD_static_data_for_processing(JCD_data)

    print("terminée.\n")
    time.sleep(0.5)

    # Ask if we want to go to the nearest station or if we are looking for the nearest station to drive to to go to a final address
    print("Mode Début de trajet activé\n🚶-🚩--🚴--🏁\n")
    end_mode_string = input(
        "Entrez F pour passer en mode Fin de trajet\n   🚩--🚴--🏁-🚶\n> ")
    end_mode_string = end_mode_string.strip(" .\n\r\t").lower()
    if end_mode_string == "f":
        end_mode_flag = True
        input_label_string = "Adresse d'arrivée : "
        print("> Mode Fin de trajet\n")
    else:
        end_mode_flag = False
        input_label_string = "Adresse actuelle/de départ : "
        print("> Mode Début de trajet\n")

    if termux_api:
        print("Localisation en cours...", end='')
        coords_waypoint = ask_coords_to_termux_api()
        if coords_waypoint == None:
            print(" échouée. Veuillez rentrer l'adresse.")
            time.sleep(0.5)
            coords_waypoint = ask_address_to_user_and_convert_them_in_coords(
                input_label_string, CITY)
        else:
            print(" réussie.")
    else:
        coords_waypoint = ask_address_to_user_and_convert_them_in_coords(
            input_label_string, CITY)

    print("")
    if end_mode_flag:
        print("Recherche de la station la plus proche de l'adresse...", end='')
    else:
        print("Recherche de la station la plus proche...", end='')

    try:
        JCD_data_reduced = reduce_number_of_stations(
            coords_waypoint, JCD_data)
        print("...", end='')

    except ValueError as err:
        print(err)
        exit(3)

    nearest_station = find_closest_station(
        coords_waypoint, JCD_data_reduced, bikers_number, end_mode_flag)
    time.sleep(1.0)

    stationName = nearest_station["name"]
    stationAddress = nearest_station["address"]
    stationAvBikeStands = nearest_station["available_bike_stands"]
    stationAvBikes = nearest_station["available_bikes"]
    print(
        f"\n> Station {stationName} ({stationAvBikes} vélo(s) disponible(s) / {stationAvBikeStands} place(s) libre(s))\n  Adresse : {stationAddress}")


if __name__ == '__main__':
    print('- toutRoule - \n')
    parser = argparse.ArgumentParser(prog="toutRoule")
    parser.add_argument('--termux', '-t', action='store_true', required=False,
                        help='ask first Termux API to get device location')
    parser.add_argument('--bikers', '-b', type=int, action='store', default=1, required=False,
                        help='ask first Termux API to get device location')
    args = parser.parse_args()

    main(args.termux, args.bikers)
    exit(0)
