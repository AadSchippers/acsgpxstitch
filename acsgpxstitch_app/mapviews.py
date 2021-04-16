from django.conf import settings
import os
import gpxpy
import gpxpy.gpx
import folium
from folium.features import DivIcon
from decimal import *
from datetime import datetime
from pytz import timezone
from dateutil.parser import parse
import time
from haversine import haversine, Unit
import csv
from django.http import HttpResponse
import io


def process_gpx_file(request, file, atrack):
    reader = io.BufferedReader(file.file)
    wrapper = io.TextIOWrapper(reader)
    gpx_file = wrapper.read() 

    gpx = gpxpy.parse(gpx_file)

    points = []
    timezone_info = timezone(settings.TIME_ZONE)   
    previous_point = None
    distance = 0
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:

                point_distance = calculate_using_haversine(point, previous_point)
                distance += point_distance

                previous_point = point

                points.append(tuple([point.latitude,
                                    point.longitude,
                                    point.elevation,
                                    ]))

        atrack["distance"] = round(distance/1000, 2)
        atrack["points"] = points

    return atrack


def make_map(request, tracks, map_filename):
    ave_lats = []
    ave_lons = []
    for t in tracks:
        ave_lats.append(sum(float(p[0]) for p in t["points"])/len(t["points"]))
        ave_lons.append(sum(float(p[1]) for p in t["points"])/len(t["points"]))
    
    ave_lat = sum(float(p) for p in ave_lats) / len(ave_lats)
    ave_lon = sum(float(p) for p in ave_lons) / len(ave_lons)

    # Load map centred on average coordinates
    my_map = folium.Map(location=[ave_lat, ave_lon], zoom_start=12)

    min_lat = float(9999999)
    max_lat = float(-9999999)
    min_lon = float(9999999)
    max_lon = float(-9999999)
    for t in tracks:
        for p in t["points"]:
                if min_lat > p[0]:
                    min_lat = p[0]
                if max_lat < p[0]:
                    max_lat = p[0]
                if min_lon > p[1]:
                    min_lon = p[1]
                if max_lon < p[1]:
                    max_lon = p[1]

    sw = tuple([min_lat, min_lon])
    ne = tuple([max_lat, max_lon])

    my_map.fit_bounds([sw, ne])

    i = 0
    for track in tracks:
        my_map = draw_map(request, my_map, track, settings.MARKER_COLORS[i], settings.MARKER_COLORS[i+1])
        i += 1

    folium.LayerControl(collapsed=True).add_to(my_map)

    # Save map
    mapfilename = os.path.join(
            settings.MAPS_ROOT,
            map_filename
        )
    my_map.save(mapfilename)

    return


def draw_map(request, my_map, track, start_color, end_color): 
    print("Filename: ", track["filename"], "start_color: ", start_color, "end_color: ", end_color)

    points = []
    if track["reversed"] == True:
        for p in range(len(track["points"]), 0, -1):
            points.append(tuple([track["points"][p-1][0], track["points"][p-1][1]]))
    else:
        for p in track["points"]:
            points.append(tuple([p[0], p[1]]))

    # start marker
    tooltip_text = 'Start ' + track["filename"]
    tooltip_style = 'color: #700394; font-size: 0.85vw'
    tooltip = folium.Tooltip(tooltip_text, style=tooltip_style)
    folium.Marker(points[0], icon=folium.Icon(color=start_color), tooltip=tooltip).add_to(my_map)

    # finish marker
    tooltip_text = 'Finish ' + track["filename"]
    tooltip_style = 'color: #700394; font-size: 0.85vw'
    tooltip = folium.Tooltip(tooltip_text, style=tooltip_style)
    folium.Marker(points[-1], icon=folium.Icon(color=end_color), tooltip=tooltip).add_to(my_map)
 
    # add lines
    folium.PolyLine(points, color=settings.LINE_COLOR, weight=3.5, opacity=1).add_to(my_map)

    return my_map


def download_gpx(request, trackname, points, points_info):
    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type='text/csv')
    gpxfilename = trackname+".gpx"
    response['Content-Disposition'] = 'attachment; filename="'+gpxfilename+'"'

    writer = csv.writer(response)

    writer.writerow([str("<?xml version='1.0' encoding='UTF-8'?>")])

    writer.writerow([
        str("<gpx version='1.1' creator='acsgpxstitch' " +
        "xmlns='http://www.topografix.com/GPX/1/1' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' "+ 
        "xsi:schemaLocation='http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd'>")
        ])
    writer.writerow([str("  <trk>")])
    writer.writerow([str("    <name>"+trackname+"</name>")])
    writer.writerow([str("    <trkseg>")])

    row = 0
    while row < len(points):
        writer.writerow([str("      <trkpt lat='"+str(points[row][0])+"' lon='"+str(points[row][1])+"'>")])
        writer.writerow([str("        <ele>"+str(round(points_info[row][9], 2))+"</ele>")])
        writer.writerow([str("      </trkpt>")])
        row += 1

    writer.writerow([str("    </trkseg>")])
    writer.writerow([str("  </trk>")])
    writer.writerow([str("</gpx>")])

    return response


def calculate_using_haversine(point, previous_point):
    distance = float(0.00)

    if previous_point:
        previous_location = (previous_point.latitude, previous_point.longitude)
        current_location = (point.latitude, point.longitude)
        distance = haversine(current_location, previous_location, unit='m')

    return distance

