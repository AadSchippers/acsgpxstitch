from django.conf import settings
import os
import gpxpy
import gpxpy.gpx
import folium
from django.shortcuts import render, redirect
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
import copy


def process_gpx_file(request, file):
    try:
        atrack = {
            "filename": file.name,
            "distance": 0,
            "reversed": False
        }
        reader = io.BufferedReader(file.file)
        wrapper = io.TextIOWrapper(reader)
        gpx_file = wrapper.read() 

        gpx = gpxpy.parse(gpx_file)

        points = []
        timezone_info = timezone(settings.TIME_ZONE)   
        previous_point = None
        distance = 0
        trackname = ""
        for track in gpx.tracks:
            trackname = track.name
            for segment in track.segments:
                for point in segment.points:

                    points.append(tuple([point.latitude,
                                        point.longitude,
                                        point.elevation,
                                        ]))

                    point_distance = calculate_using_haversine(points[len(points)-1], previous_point)
                    distance += point_distance

                    previous_point = points[len(points)-1]

            atrack["trackname"] = trackname
            atrack["distance"] = round(distance/1000, 2)
            atrack["points"] = points
    except:
        atrack = None

    return atrack


def order_tracks(request, original_tracks):
    tracks = copy.deepcopy(original_tracks)
    number_of_tracks = len(tracks)
    ordered_tracks = []
    ordered_tracks.append(tracks.pop(0))

    while len(ordered_tracks) < number_of_tracks:
        i = 0
        last_track = ordered_tracks[len(ordered_tracks)-1]
        previous_point = last_track["points"][len(last_track["points"])-1]
        point_distance = 9999999999
        ti = 0
        for t in tracks:
            point_first = t["points"][0]
            point_last = t["points"][len(t["points"])-1]
            point_distance_first = calculate_using_haversine(point_first, previous_point)
            point_distance_last = calculate_using_haversine(point_last, previous_point)
            if point_distance_last < point_distance_first:
                if point_distance_last < point_distance:
                    t["points"].reverse()
                    t["reversed"] = True
                    point_distance = point_distance_last
                    tpop = ti
            elif point_distance_first < point_distance:
                t["reversed"] = False
                point_distance = point_distance_first
                tpop = ti

            ti += 1
        ordered_tracks.append(tracks.pop(tpop))

        i += 1

    return ordered_tracks


def make_map(request, tracks, map_filename, start_selection, end_selection):
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

    points = []
    for track in tracks:
        for p in track["points"]:
            points.append(tuple([p[0], p[1]]))

    # add lines
    folium.PolyLine(points, color=settings.CONNECT_COLOR , weight=2.5, opacity=1).add_to(my_map)

    if len(tracks) > 1:
        i = 0
        for track in tracks:
            if i == 0:
                start_color = settings.START_COLOR
            else:
                start_color = settings.MARKER_COLOR
            if i == (len(tracks) - 1):
                end_color = settings.END_COLOR
            else:
                end_color = settings.MARKER_COLOR
            my_map = draw_map(request, my_map, track, start_color, end_color, False, start_selection, end_selection)
            i += 1
    else:
        my_map = draw_map(request, my_map, track, settings.START_COLOR, settings.END_COLOR, True, start_selection, end_selection)


    folium.LayerControl(collapsed=True).add_to(my_map)

    # Save map
    mapfilename = os.path.join(
            settings.MAPS_ROOT,
            map_filename
        )
    my_map.save(mapfilename)

    return


def draw_map(request, my_map, track, start_color, end_color, show_all_markers, start_selection, end_selection):
    if end_selection > len(track["points"]) - 1:
        end_selection = len(track["points"]) - 1

    points = []
    for p in track["points"]:
        points.append(tuple([p[0], p[1]]))

    points_selected = []
    if show_all_markers:
        ip = 0
        for p in points:
            tooltip_text = 'Point ' + str(ip)
            tooltip_style = 'color: #700394; font-size: 0.85vw'
            tooltip = folium.Tooltip(tooltip_text, style=tooltip_style)
            marker_color = settings.NOT_SELECTED_COLOR
            if ip >= start_selection:
                if ip <= end_selection:
                    marker_color = settings.LINE_COLOR
                    points_selected.append(p)
            # folium.Marker(p, icon=folium.Icon(color=marker_color), tooltip=tooltip).add_to(my_map)
            folium.vector_layers.CircleMarker(
                    location=[p[0], p[1]],
                    radius=7,
                    color="white",
                    weight=1,
                    fill_color=marker_color,
                    fill_opacity=1,
                    tooltip=tooltip,
                ).add_to(my_map)

            ip += 1

    # start marker
    tooltip_text = 'Start ' + track["filename"]
    tooltip_style = 'color: #700394; font-size: 0.85vw'
    tooltip = folium.Tooltip(tooltip_text, style=tooltip_style)
    folium.Marker(points[start_selection], icon=folium.Icon(color=start_color), tooltip=tooltip).add_to(my_map)

    # finish marker
    tooltip_text = 'Finish ' + track["filename"]
    tooltip_style = 'color: #700394; font-size: 0.85vw'
    tooltip = folium.Tooltip(tooltip_text, style=tooltip_style)
    folium.Marker(points[end_selection], icon=folium.Icon(color=end_color), tooltip=tooltip).add_to(my_map)           
 
    # add lines
    if len(points_selected) > 0:
        folium.PolyLine(points, color=settings.NOT_SELECTED_COLOR, weight=2.5, opacity=1).add_to(my_map)
        folium.PolyLine(points_selected, color=settings.LINE_COLOR, weight=2.5, opacity=1).add_to(my_map)
    else:
        folium.PolyLine(points, color=settings.LINE_COLOR, weight=2.5, opacity=1).add_to(my_map)

    return my_map


def download_gpx(request, trackname, tracks, start_selection, end_selection):
    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type='text/csv')
    if not trackname:
        trackname = tracks[0]["trackname"]
    gpxfilename = trackname+".gpx"
    response['Content-Disposition'] = 'attachment; filename="'+trackname+'.gpx'+'"'

    writer = csv.writer(response)

    writer.writerow([str("<?xml version='1.0' encoding='UTF-8'?>")])

    writer.writerow([
        str("<gpx version='1.1' creator='acsgpxstitch' " +
        "xmlns='http://www.topografix.com/GPX/1/1' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' "+ 
        "xsi:schemaLocation='http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd'>")
        ])
    writer.writerow([str("  <trk>")])
    writer.writerow([str("    <name>"+trackname+"</name>")])

    for t in tracks:
        writer.writerow([str("    <trkseg>")])
        points = t["points"]
        row = 0
        while row < len(points):
            if row >= start_selection:
                if row <= end_selection:
                    writer.writerow([str("      <trkpt lat='"+str(points[row][0])+"' lon='"+str(points[row][1])+"'>")])
                    writer.writerow([str("        <ele>"+str(points[row][2])+"</ele>")])
                    writer.writerow([str("      </trkpt>")])
            row += 1

        writer.writerow([str("    </trkseg>")])

    writer.writerow([str("  </trk>")])
    writer.writerow([str("</gpx>")])

    return response


def calculate_using_haversine(point, previous_point):
    distance = float(0.00)

    if previous_point:
        previous_location = (previous_point[0], previous_point[1])
        current_location = (point[0], point[1])
        distance = haversine(current_location, previous_location, unit='m')

    return distance

