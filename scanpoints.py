import os
import pickle
from collections import deque
import math
import random

from geopy import distance, Point
from intervaltree import Interval, IntervalTree

import config

def map_circle(interval_circle, points):
    """
    Parameters:
        interval_circle: - a scan circle
                         - type: Interval(begin, end, circle_data)
        points: IntervalTree of spawn points, can be queries by latitude

    Return value:
        - interval_circle with all points added which are within it's
          scan radius
    """

    # extract interval data and latitude
    circle = interval_circle.data
    lat = circle ['x']

    # find all points which are within radius
    circle['inside'] = [
            point[2] 
            for point in points[lat] 
            if inside_radius(circle, point[2])
    ]

    circle['insideCount'] = len(circle['inside'])

    # return a new Interval, as you can't just modify the data of an interval
    return Interval(interval_circle.begin, interval_circle.end, circle)


def map_point(interval_point, circles):
    """
    Parameters:
        interval_point: - A spawnpoint
                        - type: Interval(begin, end, point_data)
        circles: IntervalTree of scan circles, can be queries by latitude

    Return value:
        - point with a list of the scan circles which cover this point
    """

    # extract interval data and latitude
    point = interval_point.data
    lat = point['x']

    point['circles'] = [
            circle[2] 
            for circle in circles[lat] 
            if inside_radius(circle[2], point)
    ]

    return point

def _distance_calculations(circles, points):
    """
    Parameters:
        circles: IntervalTree of scan circles, sorted by latitude
        points: IntervalTree of spawn points, sorted by latitude

    Return value:
        - IntervalTree of scan circles, now we know which and how many points
          lie within their scan ranges
        - List of spawn points, each of them has a list of scan circle which it
          resides in.


    """

    # checks for all circles which points lies within their radius
    circles = IntervalTree(map(lambda interval_circle, points=points: map_circle(interval_circle, points), circles))

    # adds the list of scan circles to the point which all cover the point
    points = list(map(lambda point, circles=circles: map_point(point,circles),points))

    return (circles, points)


def insert_point_into_tree(point, interval):
    """
    Inserts a datapoint into an IntervalTree structure with some offset added
    so that it can be queried for scanning.

    Parameters:
        - point: some data which has an x and y coordinate, 
                 either spawnpoint or scan circle
        - interval: the interval it needs to be inserted into
    
    Return value: The IntervalTree with the inserted point.
    """

    origin = Point(point['x'], point['y'])

    # have some margin for rounding
    offset = config.SCAN_RADIUS + 10

    lat_begin = distance.distance(meters=-offset).destination(origin, 0).latitude
    lat_end = distance.distance(meters=offset).destination(origin, 0).latitude

    # insert point with range [lat - offset : lat + offset]
    interval[lat_begin:lat_end] = point
    return interval





def distribute_pointset(points):
    """
    Distributes a list of scanpoints amongst workers and returns 
    a list of lists, each sublist is the set of scanpoints for one 
    of the workers

    Parameters:
        - points: list of (lat, lon) pairs

    Return value:
        - list of lists of (lat, lon) pairs
    """


    # how many points one row should have
    each_row = int(len(points) / config.GRID[0])
    # how many points one column of one row should have
    each_col = int(each_row / config.GRID[1])

    
    # do the actual distribution
    distributed_scanpoints = _actually_distribute_points(points, each_row, each_col)

    # filter out empty scanpoint sets, in case there is one
    final_list = list(filter(
        lambda worker_set: len(worker_set) > 0, 
        distributed_scanpoints
    ))

    return final_list


def _actually_distribute_points(points, each_row, each_col):
    """
    Does the actualy distribution part of distribute_pointset()
    """
    final_list = []
    # sort scanpoints by latitude(point[0])
    lat_sorted_points = deque(sorted(points, key=lambda point: point[0]))

    for row_number in range(0, config.GRID[0]):
        row_cell = []

        # add scanpoint to the list while there are point in the 
        # queue or we have enough points added
        while len(lat_sorted_points) > 0 and len(row_cell) < each_row:
            row_cell.append(lat_sorted_points.popleft())

        # distribute the points of this row
        distribution_for_this_row = _distribute_scanpoint_column(row_cell, each_col)

        final_list.extend(distribution_for_this_row)
    

    # check that that there was nothing skipped(rounding errors)
    if len(lat_sorted_points):
        total_worker = config.GRID[0] * config.GRID[1]

        # something was skipped, add it to the last worker if there are
        # enough lists already, otherwise append it as anothers workers
        # lists
        if len(final_list) < total_worker:
            final_list.append(list(lat_sorted_points))
        else:
            final_list[-1].extend(list(lat_sorted_points))

    return final_list

def _distribute_scanpoint_column(row_cell, each_col):
    """
    Returns splits the points in row_cell amongst #(each_col) workers
    and returns the distribution as list of lists
    """
    return_list = []

    # sort the input list by longitude
    lon_sorted_points = deque(sorted(row_cell, key=lambda point: point[1]))
    
    # iterate over columns in the row
    for col_number in range(0, config.GRID[1]):
        col_cell = []

        # add scanpoint to the list while there are point in the 
        # queue or we have enough points added
        while len(lon_sorted_points) > 0 and len(col_cell) < each_col:
            col_cell.append(lon_sorted_points.popleft())
    

        # append each of the lists
        return_list.append(col_cell)

    # if there are scan points left in the queue(rounding errors), 
    # add them to the last worker
    if len(lon_sorted_points):
        return_list[-1].extend(list(lon_sorted_points))

    return return_list

def _pointset_storage_filename():
    """
    Long name so that we can store all the relevant metadata in the name and
    have easy loading and dumping of the data with pickle
    """
    start_cords = '''{map_start_lat}-{map_start_lon}'''.format(
            map_start_lat=min(config.MAP_START[0], config.MAP_END[0]),
            map_start_lon=min(config.MAP_START[1], config.MAP_END[1]),
    )
    end_cords= '''{map_end_lat}-{map_end_lon}'''.format(
            map_end_lat=max(config.MAP_START[0], config.MAP_END[0]),
            map_end_lon=max(config.MAP_START[1], config.MAP_END[1]),
    )
    filename = '''{start_cords}__{end_cords}.data'''.format(
            start_cords=start_cords,
            end_cords=end_cords
    )
    return filename
    

def already_generated_pointset():
    """
    checks if we already calculated the scan points
    and returns them if that's the case
    """
    filename = _pointset_storage_filename()
    if os.path.isfile(filename):
        points = pickle.load(open(filename, "rb" ))

        return distribute_pointset(points)
    else:
        return False

def _generate_samples(spawn_points):
    """
    Generates a set of scan circles(or rather their centers) randomly around each
    point, so that the point still is included in the scan area.
    """
    # create the IntervalTrees
    interval_of_points = IntervalTree()
    interval_of_circles = IntervalTree()

    # the maximum radius used should have some tolerance so that we can be sure
    # that even if there are small errors we still are in the scan area
    radius = config.SCAN_RADIUS-5

    for point in spawn_points:
        # convert the list of tuples to actually useful objects which can store
        # the circles in which they are located and if they are already covered
        # by a circle which we've choosen for our final set of scanpoints
        new_point = {'x':point[0],'y':point[1], 'covered': False,'circles':[]}
        interval_of_points = insert_point_into_tree(new_point, interval_of_points)

        # generate #SAMPLES_PER_POINT circles per spawn point
        for i in range(0, config.SAMPLES_PER_POINT):
            
            # move randomly in any direction/distance inside the radius
            some_distance_away = random.uniform(0,radius)
            bearing = random.uniform(0, 359)
            
            origin = Point(point[0], point[1])
            destination = distance.distance(meters=some_distance_away).destination(origin, bearing)
            
            lat2, lon2 = destination.latitude, destination.longitude

            x = lat2
            y = lon2
            a_circle = {'x':x,'y':y, 'insideCount':0}
            dist = distance.distance((x,y), point).meters
            if dist > config.SCAN_RADIUS:
                print('wtf???')

            interval_of_circles = insert_point_into_tree(a_circle, interval_of_circles)
    return (interval_of_points, interval_of_circles)


def _choose_best_scanpoints_from_samples(circles, number_of_spawn_points):
    """
    Given a set of scanpoints and how many spawn point there are, choose those 
    from the set which cover the most points. When done we should have a 
    set of scan points which cover all spawn points and is as small as possible.
    """
    new_circles = []
    covered_points_counter = 0
    while True:
      # get circle with the highest number of uncovered points
      interval_circle = max(circles, key=lambda circle: circle[2]['insideCount'])
      circle = interval_circle.data

      uncovered_point_found = False
      for point in circle['inside']:

          # iterate over each point which is covered by this circle and check
          # if it's already covered by a circle from the final scan point set.
          if not point['covered']:
              # set variable to true, so that this circle will be added to the
              # final scan point set
              uncovered_point_found = True
              # declare this point as covered by a circle of the final set
              point['covered'] = True
              # obviously increase the covered points counter
              covered_points_counter += 1

              # every circle which covers this point gets it's insideCount
              # reduced as this point is no longer of concern to any of them
              for circle_b in point['circles']:
                  circle_b['insideCount'] -= 1
      
      # add this circle to the list if it covers an additional point
      if uncovered_point_found:
          new_circles.append(circle)

      # As this circle as already served it's purpose we can remove it savely from
      # the list
      circles.remove(interval_circle)

      # We are done when our covered points counter reaches the amount of points
      # that we have to cover
      if(covered_points_counter == number_of_spawn_points):
          break

    return new_circles


def _check_scan_point_set_for_safety(points, scan_points):
    """
    Given a final set of scan points and the set which should be covered
    by these scan points, check if they all are covered and if not add
    them as their own scan points
    """
    for point in points:
        covered = False
        for circle in scan_points:
            # if there's a circle which covers the point, we can stop the evaluation for this point
            if distance.distance((point['x'], point['y']), (circle['x'], circle['y'])).meters <= config.SCAN_RADIUS:
                covered = True
                break
        if not covered:
            print('A sadlonely circle has been found :(')
            scan_points.append({'x':point['x'],'y': point['y']})

    return scan_points


def calculate_minimal_pointset(spawn_points):
    """
    Given a set of spawn locations calculate and return the best possible scan
    points so that we can reduce the amount of scanning as much as possible.
    Result is already split up into worker sublists
    """

    # check if we have anything to do at all
    pointset = already_generated_pointset()
    if pointset:
        return pointset


    print('Number of spawnpoints: ' +str(len(spawn_points)))
    print('Generating samples...')
    interval_of_points, interval_of_circles = _generate_samples(spawn_points)
    print('Sample creation finished')
    print(str(len(interval_of_points))+ ' samples were created.')
    print('Starting distance calculations')
    circles, points = _distance_calculations(interval_of_circles, interval_of_points)
    print('Distance calculations finished')
    
    # select the best samples
    scan_points = _choose_best_scanpoints_from_samples(circles, len(points))

    # better check the result
    scan_points = _check_scan_point_set_for_safety(points, scan_points)
    print('Calculating minimal scan point set done, set size: ' + str(len(scan_points)))

    # We need a list of simple (lat,lon) tuples
    points = list(map(lambda scan_point: (scan_point['x'], scan_point['y']), scan_points))

    # save the calculations
    filename = _pointset_storage_filename()
    pickle.dump(points, open(filename, "wb" ))

    # and return the scan point set distributes over the available workers
    return distribute_pointset(points)



def inside_radius(p1, p2):
    """
    Checks if the distance of two points is smaller than the scan radius
    """
    return distance.distance((p1['x'], p1['y']), (p2['x'],p2['y'])).meters <= config.SCAN_RADIUS
