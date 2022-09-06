import googlemaps
import requests
import json
from secret import mapsSecretKey, orsSecretKey


# API: https://nominatim.org/release-docs/latest/api/Search/
def getCoordsFromAddr(addr):
    addrSplitted = addr.strip(' ').split(',')
    try:
        if len(addrSplitted) != 2:
            raise Exception(f"Length is {addrSplitted}")
        else:
            lat = float(addrSplitted[0].strip(" "))
            lon = float(addrSplitted[1].strip(" "))
            if lat >= -90.0 and lat <= 90.0 and lon >= -180.0 and lon <= 180.0:
                return str(lat)+','+str(lon)
            else:
                return None
    except Exception:
        # Reached when lat/long are not floats
        # I guess this is an address. Calling Nominatim (OSM) API to get the coordinates
        apiUrl = "https://nominatim.openstreetmap.org"
        requestUrl = apiUrl+"/search?q="+addr+'&format=json'
        resp = requests.get(requestUrl)
        if resp.status_code != 200 or resp.text == '[]':
            return None
        else:
            try:
                nominatimJsonPayload = json.loads(resp.text)
                rebuiltAddr = str(
                    nominatimJsonPayload[0]['lat'])+','+str(nominatimJsonPayload[0]['lon'])
                return rebuiltAddr
            except Exception as err:
                print(f"[X] {err}")
                return None


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
        except Exception as err:
            print(err)
            return None

    return None


def main():
    addrFrom = '1 rue Valade, Toulouse'
    addrFromCoord = getCoordsFromAddr(addrFrom)

    addrTo = '6 Rue Antoine Deville, Toulouse'
    addrToCoord = getCoordsFromAddr(addrTo)

    distance, duration = getDistORS(addrFromCoord, addrToCoord)
    print(f"[-] Distance={distance}m, Duration={duration}s")


if __name__ == '__main__':
    print('- toutRoule - \n')

    main()
