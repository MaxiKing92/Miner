import math
from geopy import distance, Point
from intervaltree import Interval, IntervalTree
import pickle
import os


import config


def get_map_center():
    """Returns center of the map"""
    lat = (config.MAP_END[0] + config.MAP_START[0]) / 2
    lon = (config.MAP_END[1] + config.MAP_START[1]) / 2
    return lat, lon


def get_scan_area():
    """Returns the square kilometers for configured scan area"""
    lat1 = config.MAP_START[0]
    lat2 = config.MAP_END[0]
    lon1 = config.MAP_START[1]
    lon2 = config.MAP_END[1]
    p1 = Point(lat1, lon1)
    p2 = Point(lat1, lon2)
    p3 = Point(lat1, lon1)
    p4 = Point(lat2, lon1)

    width = distance.distance(p1, p2).kilometers
    height = distance.distance(p3, p4).kilometers
    area = int(width * height)
    return area


def get_start_coords(worker_no):
    """Returns center of square for given worker"""
    grid = config.GRID
    total_workers = grid[0] * grid[1]
    per_column = int(total_workers / grid[0])
    column = worker_no % per_column
    row = int(worker_no / per_column)
    part_lat = (config.MAP_END[0] - config.MAP_START[0]) / float(grid[0])
    part_lon = (config.MAP_END[1] - config.MAP_START[1]) / float(grid[1])
    start_lat = config.MAP_START[0] + part_lat * row + part_lat / 2
    start_lon = config.MAP_START[1] + part_lon * column + part_lon / 2
    return start_lat, start_lon


def float_range(start, end, step):
    """xrange for floats, also capable of iterating backwards"""
    if start > end:
        while end < start:
            yield start
            start += -step
    else:
        while start < end:
            yield start
            start += step


def get_gains():
    """Returns lat and lon gain

    Gain is space between circles.
    """
    start = Point(*get_map_center())
    base = config.SCAN_RADIUS * math.sqrt(3)
    height = base * math.sqrt(3) / 2
    dis_a = distance.VincentyDistance(meters=base)
    dis_h = distance.VincentyDistance(meters=height)
    lon_gain = dis_a.destination(point=start, bearing=90).longitude
    lat_gain = dis_h.destination(point=start, bearing=0).latitude
    return abs(start.latitude - lat_gain), abs(start.longitude - lon_gain)




def map_circle(interval_circle, points):
    interval_begin = interval_circle[0]
    interval_end = interval_circle[1]

    circle = interval_circle[2]

    lat = circle ['x']
    circle['inside'] = [point[2] for point in points[lat] if inside_radius(circle, point[2])]

    circle['insideCount'] = len(circle['inside'])

    return Interval(interval_begin, interval_end, circle)

def map_point(interval_point, circles):
    interval_begin = interval_point[0]
    interval_end = interval_point[1]
    point = interval_point[2]
    
    lat = point['x']
    point['circles'] = [circle[2] for circle in circles[lat] if inside_radius(circle[2], point)]

    return Interval(interval_begin, interval_end, point)

def map_points_to_circles(circles, points):
    newCircles = []
    meh = 0
    circles = IntervalTree(map(lambda interval_circle, points=points: map_circle(interval_circle, points), circles))

    points = IntervalTree(map(lambda point, circles=circles: map_point(point,circles),points))

    print('circles generated')
    
    return (circles, points)

def insert_point_into_tree(point, interval):

    origin = Point(point['x'], point['y'])

    # have some margin for rounding
    offset = config.SCAN_RADIUS + 30
    lat_begin = distance.distance(meters=-offset).destination(origin, 0).latitude
    lat_end = distance.distance(meters=offset).destination(origin, 0).latitude

    interval[lat_begin:lat_end] = point
    return interval



def calculate_minimal_pointset(spawn_points):
    filename = (str(config.MAP_START) +'_' +str(config.MAP_END) + '.data')
    if os.path.isfile(filename):
        points = pickle.load(open(filename, "rb" ))

        # slice list into
        n = config.GRID[0] * config.GRID[1] # total workers
        points = [ points[i::n] for i in range(0,n) ]

        # and sort the points for each worker
        points = [
            sort_points_for_worker(p, i)
            for i, p in enumerate(points)
        ] 

        # save it
        return points

    points = []
    interval_of_points = IntervalTree()

    radius = config.SCAN_RADIUS-5
    interval_of_circles = IntervalTree()
    import math
    import random

    for point in spawn_points:
        p = {'x':point[0],'y':point[1], 'covered': False,'circles':[]}
        points.append(p)
        interval_of_points = insert_point_into_tree(p, interval_of_points)

        for i in range(0, config.SAMPLES_PER_POINT):
            r = random.uniform(0,radius)
            bearing = random.uniform(0, 359)
            
            origin = Point(point[0], point[1])
            destination = distance.distance(meters=r).destination(origin, bearing)
            
            lat2, lon2 = destination.latitude, destination.longitude

            x = lat2
            y = lon2
            a_circle = {'x':x,'y':y, 'insideCount':0}
            dist = distance.distance((x,y), point).meters
            if dist > 70:
                print('wtf???')

            interval_of_circles = insert_point_into_tree(a_circle, interval_of_circles)

        

    print('circles generated')
    foo = map_points_to_circles(interval_of_circles, interval_of_points)
    print('distances calculated')
    circles = foo[0]
    points = foo[1]
    
    
    print('points: ' +str(len(points)))
    print('sample circles: ' +str(len(circles)))
    new_circles = []
    countt = 0
    while True:
      # get circle with max insideCount
      circle = max(circles, key=lambda circle: circle[2]['insideCount'])[2]
      anything = False
      for point in circle['inside']:
          if not point['covered']:
              anything = True
              point['covered'] = True
              countt += 1
              
              for circle_b in point['circles']:
                  circle_b['insideCount'] -= 1
      if anything:
          new_circles.append(circle)
      if(countt == len(points)):
          break
    circles = new_circles

    # ensure that every point is going to be scanned
    for interval_point in points:
        point = interval_point[2]
        inside = False
        for circle in circles:
            # if there's a circle which covers the point, we can stop the evaluation for this point
            if distance.distance((point['x'], point['y']), (circle['x'], circle['y'])).meters <= 70:
                inside = True
                break
        if not inside:
            print('lonely circle found')
            new_circles.append({'x':point['x'],'y': point['y']})
            
    print('done, amount circles: ' + str(len(circles)))

    points = list(map(lambda circle: (circle['x'], circle['y']),circles))

    pickle.dump(points, open(filename, "wb" ))

    # slice list into
    n = config.GRID[0] * config.GRID[1] # total workers
    points = [ points[i::n] for i in range(0,n) ]

    # and sort the points for each worker
    points = [
        sort_points_for_worker(p, i)
        for i, p in enumerate(points)
    ] 

    # save it
    return points




def inside_radius(p1, p2):
    return distance.distance((p1['x'], p1['y']), (p2['x'],p2['y'])).meters <= config.SCAN_RADIUS
    #return haversine(p1['x'], p1['y'], p2['x'],p2['y']) <= (config.SCAN_RADIUS-5)

from math import radians, cos, sin, asin, sqrt
def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    km = 6367 * c
    return km*1000


def get_points_per_worker():
    """Returns all points that should be visited for whole grid"""
    total_workers = config.GRID[0] * config.GRID[1]

    lat_gain, lon_gain = get_gains()

    points = [[] for _ in range(total_workers)]
    total_rows = math.ceil(
        abs(config.MAP_START[0] - config.MAP_END[0]) / lat_gain
    )
    total_columns = math.ceil(
        abs(config.MAP_START[1] - config.MAP_END[1]) / lon_gain
    )
    for map_row, lat in enumerate(
        float_range(config.MAP_START[0], config.MAP_END[0], lat_gain)
    ):
        row_start_lon = config.MAP_START[1]
        odd = map_row % 2 != 0
        if odd:
            row_start_lon -= 0.5 * lon_gain
        for map_col, lon in enumerate(
            float_range(row_start_lon, config.MAP_END[1], lon_gain)
        ):
            # Figure out which worker this should go to
            grid_row = int(map_row / float(total_rows) * config.GRID[0])
            grid_col = int(map_col / float(total_columns) * config.GRID[1])
            if map_col >= total_columns:  # should happen only once per 2 rows
                grid_col -= 1
            worker_no = grid_row * config.GRID[1] + grid_col
            points[worker_no].append((lat, lon))
    points = [
        sort_points_for_worker(p, i)
        for i, p in enumerate(points)
    ]
    return points


def sort_points_for_worker(points, worker_no):
    center = get_start_coords(worker_no)
    return sorted(points, key=lambda p: get_distance(p, center))


def get_distance(p1, p2):
    return math.sqrt(pow(p1[0] - p2[0], 2) + pow(p1[1] - p2[1], 2))
