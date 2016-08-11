import math
from geopy import distance, Point
from intervaltree import Interval, IntervalTree


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




def map_circle(circle, points):
    circle['inside'] = list(filter(lambda point: inside_radius(circle, point), points))
    circle['insideCount'] = len(circle['inside'])
    return circle

def map_point(point, circles):
        point['circles'] = list(filter(lambda circle, point=point: (point in circle['inside']), circles))
        return point

def asdf(circles, points):
    newCircles = []
    meh = 0
    circles = list(map(lambda circle, points=points: map_circle(circle, points), circles))
    circles = list(filter(lambda circle: circle['insideCount']>0, circles))

    points = list(map(lambda point, circles=circles: map_point(point,circles),points))

    print('circles generated')
    
    
    return (circles, points)

    #for circle in circles:
    #  circle['inside'] = []
    #  circle['insideCount'] = 0
    #  for point in points:
    #      if inside_radius(circle, point):
    #          circle['inside'].append(point)
    #          circle['insideCount'] += 1
    #          point['circles'].append(circle)
    #  if len(circle['inside']) > 0:
    #      newCircles.append(circle)
    #  meh = meh + 1
    #  if meh % 100== 0:
    #      print(meh)
    #return(newCircles, points)

def insert_point_into_tree(point, interval):
    origin = Point(point[0], point[1])
    lat_begin = distance.distance(meters=70).destination(origin, 0).latitude
    lat_end = distance.distance(meters=-70).destination(origin, 0).latitude
    interval_of_points[lat_begin:lat_end] = {'x':point[0],'y':point[1], 'covered': False,'circles':[]}
    return interval



def calculate_minimal_pointset(spawn_points):
    points = []
    interval_of_points = IntervalTree()
    for point in spawn_points:
        p = {'x':point[0],'y':point[1], 'covered': False,'circles':[]}
        points.append(p)
        interval_of_points = insert_point_into_tree(p)

        
    import math
    import random

    circles = []
    radius = config.SCAN_RADIUS-20
    for point in spawn_points:
        for i in range(0, config.SAMPLES_PER_POINT):
            r = random.uniform(0,radius)
            bearing = random.uniform(0, 359)
            
            origin = Point(point[0], point[1])
            destination = distance.distance(meters=r).destination(origin, bearing)
            
            lat2, lon2 = destination.latitude, destination.longitude


            #x = point[0] + r * math.cos(fi))
            #y = point[1] + r * math.sin(fi)
            x = lat2
            y = lon2
            circles.append({'x':x,'y':y, 'insideCount':0})
    # done
    print('circles generated')
    foo = asdf(circles, points)
    print('distances calculated')
    circles = foo[0]
    points = foo[1]
    
    
    print('points: ' +str(len(points)))
    print('sample circles: ' +str(len(circles)))
    new_circles = []
    countt = 0
    meh = 0
    while True:
      meh += 1
      # get circle with max insideCount
      #circle = circles[0]
      circle = max(circles, key=lambda circle: circle['insideCount'])
      #for i in range(0, len(circles)):
      #    if circle['insideCount'] < circles[i]['insideCount']:
      #        circle = circles[i]
      anything = False
      for point in circle['inside']:
          if not point['covered']:
              anything = True
              point['covered'] = True
              countt += 1
              
              for circle in point['circles']:
                  circle['insideCount'] -= 1
      #for j in range(0, len(circle['inside'])):
      #   if not circle['inside'][j]['covered']:
      #       anything = True
      #       circle['inside'][j]['covered'] = True
      #       countt += 1
      #       
      #       for k in range(0, len(circle['inside'][j])):
      #           circle['inside'][j]['circles'][k]['insideCount'] -=1
      if anything:
          new_circles.append(circle)
      if(countt == len(points)):
          break
      print(abs(countt-len(points)))
      if(meh % 1000 == 0):
          print('meh: ' + str(meh))
    circles = new_circles
    print('one last check')
    for point in points:
        inside = False
        for circle in point['circles']:
            if distance.distance((point['x'],point['y']), (circle['x'], circle['y'])).meters <= 70:
                inside = True
        if not inside:
            print('##################################')
            print('LONELY POINT FOUND:')
            print(point)
            print('##################################')
            
    print('done, amount circles: ' + str(len(circles)))
    return [list(map(lambda circle: (circle['x'], circle['y']),circles))]




def inside_radius(p1, p2):
    #return distance.great_circle((p1['x'], p1['y']), (p2['x'],p2['y'])).meters <= config.SCAN_RADIUS
    return haversine(p1['x'], p1['y'], p2['x'],p2['y']) <= (config.SCAN_RADIUS-5)

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
    return math.sqrt(pow(p1['x'] - p2['x'], 2) + pow(p1['y'] - p2['y'], 2))
