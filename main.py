import googlemaps
import requests
import json
from secret import mySecretKey


# API: https://nominatim.org/release-docs/latest/api/Search/
def getCoordsFromAddr(addr):
    addrSplitted = addr.strip(' ').split(',')
    try:
        if len(addrSplitted) != 2:
            raise Exception(f"Length is {addrSplitted}")
        else:
            lat = float(addrSplitted[0])
            lon = float(addrSplitted[1])
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


def getDistGmaps(addrFrom, addrTo):
    gmaps = googlemaps.Client(key=mySecretKey)
    dist = gmaps.distance_matrix(addrFrom, addrTo)['rows'][0]['elements'][0]
    return dist


# API: https://github.com/Project-OSRM/osrm-backend/blob/master/docs/http.md
def getDistOSRM(addrFrom, addrTo):
    apiUrl = "http://router.project-osrm.org"
    profile = "foot"

    # annotations: we only request distance
    # sources/destination: else, every combination is tried and a 2x2 matrix is returned
    requestUrl = apiUrl+"/route/v1/"+profile+'/' + \
        addrFrom+';'+addrTo+"?annotations=true"
    resp = requests.get(requestUrl)
    if resp.status_code == 200 and resp.text != '{}':
        try:
            osrmJsonPayload = json.loads(resp.text)
            dist = osrmJsonPayload["routes"][0][0]
            return dist
        except Exception as err:
            print(err)
            return None

    return None


def main():
    addrFrom = '1 rue Valade, Toulouse'
    addrFromCoord = getCoordsFromAddr(addrFrom)

    addrTo = '6 Rue Antoine Deville, Toulouse'
    addrToCoord = getCoordsFromAddr(addrTo)

    # dist = getDistGmaps(addrFrom, addrTo)
    # print(dist)

    dist = getDistOSRM(addrFromCoord, addrToCoord)
    print(dist)


if __name__ == '__main__':
    print('- toutRoule - \n')

    main()
