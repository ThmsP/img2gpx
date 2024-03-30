import gpxpy
import osmnx
import geopandas as gpd
from shapely.geometry import Point, LineString
import json
import matplotlib.pyplot as plt
import datetime, sys
import time
from parameters import cache_folder

osmnx.config(cache_folder=cache_folder)
#matplotlib.use('Agg')

class DualOutput:
    def __init__(self, fichier):
        self.terminal = sys.stdout
        self.terminal_stderr = sys.stderr
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log = open(fichier, "a")
        self.log.write(f"\n\n----\n{now}\n") 

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def write_error(self, message):
        self.terminal_stderr.write(message)
        self.log.write(message)

    def flush(self):
        # Cette méthode flush est nécessaire pour l'interface de fichier.
        self.terminal.flush()
        self.log.flush()

    def close(self):
        if self.log:
            self.log.close()
            self.log = None


def pd(message):
    if not hasattr(pd, "start_time"):
        pd.start_time = time.time()

    duration = time.time() - pd.start_time
    print(message, f" {duration:.2f} seconds")


def save_json(path, object):

    if not isinstance(object, (dict, list)):
        raise ValueError("Objet is not a dictionnary.")

    with open(path, 'w') as file:
        json.dump(object, file, indent=4)

    return True

# Lecture du fichier GPX
def gpx_reader(path):

    with open(path, 'r') as fichier:
        gpx = gpxpy.parse(fichier)
        return gpx


def gpx_name(gpx):
    name = gpx.name if gpx.name else ""
    if name:
        return name

    for track in gpx.tracks:
        name = track.name if track.name else ""
        if name:
            return name
        for segment in track.segments:
            if segment.name:
                return segment.name

    return "Trace"

def gpx_meters(gpx):
    
    gpx_meters = []    
    km = 0
    prev_point = None

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                #print(point.latitude, point.longitude,point.elevation)
                if prev_point:
                    km += point.distance_3d(prev_point)
                prev_point = point
                gpx_meters.append(km)
    return gpx_meters


def gpx_elevations(gpx, window_size=150):  # window_size en mètres
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            points.extend(segment.points)
    
    smoothed_elevations = []
    distances = [0]  # Distance initiale à 0 pour le premier point
    
    # Calculer les distances cumulatives
    for i in range(1, len(points)):
        distance = points[i].distance_3d(points[i-1])
        distances.append(distances[-1] + distance)

    total_distance = distances[-1]
    
    # Appliquer le lissage avec une pondération par la distance
    for i, point in enumerate(points):
        weighted_sum, weight_total = 0, 0
        for j, point_j in enumerate(points):
            # Calculer la distance entre le point i et j
            distance_ij = abs(distances[j] - distances[i])
            if distance_ij <= window_size:
                # Calculer le poids basé sur la distance inverse à la fenêtre
                weight = 1 - (distance_ij / window_size)
                weighted_sum += point_j.elevation * weight
                weight_total += weight
        smoothed_elevation = weighted_sum / weight_total if weight_total else point.elevation
        smoothed_elevations.append(smoothed_elevation)
    
    return smoothed_elevations


def calculate_distance(gpx, meters, latitude, longitude):
    
    photo_point = gpxpy.gpx.GPXTrackPoint(latitude, longitude, 0)
    distance = float('inf') #valeur infinie positive
    i = 0
    from_start = 0

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                
                current_distance = point.distance_2d(photo_point)

                if current_distance < distance:
                    distance = current_distance
                    from_start = meters[i]

                i += 1

    return (round(distance), round(from_start))


def plot_graph(G_projected, coordinates=None):
    if coordinates == None:
        geometries = []
    elif isinstance(coordinates[0], tuple):  # Liste de points
        geometries = [Point(lon, lat) for lat, lon in coordinates]
    else:  # Un seul point
        lat, lon = coordinates
        geometries = [Point(lon, lat)]

    # Tracer le graphe
    fig, ax = osmnx.plot_graph(G_projected, show=False, close=False)

    # Créer un GeoDataFrame pour les points ou les segments
    if len(geometries) > 0:
        gdf_points = gpd.GeoDataFrame([{'geometry': geom} for geom in geometries], crs='EPSG:4326')
        gdf_points_proj = gdf_points.to_crs(G_projected.graph['crs'])
        
        # Tracer les points
        if len(geometries) > 1:
            # Si plus d'un point, tracer également un segment (LineString) les reliant
            line = LineString(geometries)
            gdf_line = gpd.GeoDataFrame([{'geometry': line}], crs='EPSG:4326').to_crs(G_projected.graph['crs'])
            gdf_line.plot(ax=ax, linewidth=2, color='red')
        ax.scatter(gdf_points_proj.geometry.x, gdf_points_proj.geometry.y, color='red', zorder=3)
    
    plt.show()
