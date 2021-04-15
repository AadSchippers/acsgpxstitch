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
    points_info = []
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

                #points_info.append(tuple([
                #    round(point.elevation, 2),
                #   ]))

        atrack["distance"] = round(distance/1000, 2)

    return atrack


def make_map(request, points, points_info, filename, map_filename):

    # print(points)
    ave_lat = sum(p[0] for p in points)/len(points)
    ave_lon = sum(p[1] for p in points)/len(points)

    # Load map centred on average coordinates
    my_map = folium.Map(location=[ave_lat, ave_lon], zoom_start=12)

    min_lat = float(9999999)
    max_lat = float(-9999999)
    min_lon = float(9999999)
    max_lon = float(-9999999)
    for p in points:
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


    # add a markers
    # for each in points:  
    #     folium.Marker(each).add_to(my_map)
    # folium.Marker(points[0], icon=folium.Icon(color='lightgray', icon='home', prefix='fa')).add_to(my_map)

    i = 0
    previous_marker_distance = 0

    # for x in range(int(len(points)/10), len(points), int(len(points)/11)):
    ip = int(intermediate_points_selected)
    if ip > 0:
        for x in range(len(points)):
            distance = float(points_info[x][1])
            if distance < previous_marker_distance + ip:
                continue
            previous_marker_distance = distance
            i = i + ip
            time = points_info[x][0]
            duration = points_info[x][2]
            moving_duration = points_info[x][3]
            speed = points_info[x][4]
            try:
                avgspeed = float((points_info[x][1] / moving_duration.seconds) * 3.6)
            except:
                avgspeed = 0
            heartrate = points_info[x][5]
            avgheartrate = points_info[x][6]
            cadence = points_info[x][7]
            avgcadence = points_info[x][8]
            tooltip_text = 'Intermediate point ' + str(i/1000) + ' km, ' + str(speed) + ' km/h'
            tooltip_style = 'color: #700394; font-size: 0.85vw'
            tooltip = folium.Tooltip(tooltip_text, style=tooltip_style)

            html_popup = make_html_popup(
                str(i),
                time,
                duration,
                moving_duration, 
                distance,
                speed,
                avgspeed,
                heartrate,
                avgheartrate,
                cadence,
                avgcadence,
                )
            popup = folium.Popup(html_popup, max_width=400)
            folium.Marker(points[x], icon=folium.Icon(color='purple'), tooltip=tooltip, popup=popup).add_to(my_map)

    # start marker
    tooltip_text = 'Start, click for details'
    tooltip_style = 'color: #700394; font-size: 0.85vw'
    tooltip = folium.Tooltip(tooltip_text, style=tooltip_style)
    html = (
        "<h3 style='color: #700394; font-weight: bold; font-size: 1.5vw'>Start</h3>" +
        "<table style='color: #700394; width: 100%; font-size: 0.85vw'><tr><td><b>Time</b></td>" +
        "<td style='text-align:right'>"+points_info[0][0]+"</td></tr>" +
        "</table>"
    )
    popup = folium.Popup(html, max_width=300)
    folium.Marker(points[0], icon=folium.Icon(color='lightgray'), tooltip=tooltip, popup=popup).add_to(my_map)

    # finish marker
    tooltip_text = 'Finish, click for details'
    tooltip_style = 'color: #700394; font-size: 0.85vw'
    tooltip = folium.Tooltip(tooltip_text, style=tooltip_style)
    # tx = datetime.strptime(points_info[-1][0], "%H:%M:%S")
    # duration = tx - t0
    duration = points_info[-1][2]
    moving_duration = points_info[-1][3]
    avgspeed = float((points_info[-1][1] / moving_duration.seconds) * 3.6)
    distance = float(points_info[-1][1]) / 1000

    html = (
        "<h3 style='color: #700394; font-weight: bold; font-size: 1.5vw'>Finish</h3>"+
        "<table style='color: #700394; width: 100%; font-size: 0.85vw'>" +
        "<tr><td><b>Time</b></td><td style='text-align:right'>"+points_info[-1][0]+"</td></tr>" +
        "<tr><td><b>Distance</b></td><td style='text-align:right'>"+str(round(distance, 2))+"</td></tr>" +
        "<tr><td><b>Average speed</b></td><td style='text-align:right'>"+str(round(avgspeed, 2))+"</td></tr>" +
        "<tr><td><b>Duration</b></td><td style='text-align:right'>"+str(duration)+"</td></tr>" +
        "<tr><td><b>Duration while moving</b></td><td style='text-align:right'>"+str(moving_duration)+"</td></tr>" +
        "</table>"
    )
    popup = folium.Popup(html, max_width=300)
    folium.Marker(points[-1], icon=folium.Icon(color='gray'), tooltip=tooltip, popup=popup).add_to(my_map)
 
    # folium.LayerControl(collapsed=True).add_to(my_map)

    # add lines
    folium.PolyLine(points, color="red", weight=2.5, opacity=1).add_to(my_map)

    # Save map
    mapfilename = os.path.join(
            settings.MAPS_ROOT,
            map_filename
        )
    my_map.save(mapfilename)

    return


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


def make_html_popup(
        intermediate_point,
        time,
        duration,
        moving_duration,
        distance,
        speed,
        avgspeed,
        heartrate,
        avgheartrate,
        cadence,
        avgcadence,
    ):
    line_title = "<h3 style='color: #700394; font-weight: bold; font-size: 1.5vw'>Intermediate point "+ str(int(intermediate_point)/1000)+" km</h3>"
    line_table_start = "<table style='color: #700394; font-size: 0.85vw'>"
    line_table_end = "</table>"
    line_time_distance = (
        "<tr><td><b>Time</b></td><td style='padding: 0 10px;text-align:right'>" +
        time+"</td>" +
        "<td><b>Distance</b></td><td style='padding: 0 10px;text-align:right'>" +
        str(round(distance/1000, 2)) + "</td></tr>"
    )
    line_duration = (
        "<tr><td><b>Duration</b></td><td style='padding: 0 10px;text-align:right'>" +
        str(duration)+"</td><td><b>Duration while moving</b></td><td style='padding: 0 10px;text-align:right'>"+
        str(moving_duration)+"</td></tr>"
    )
    line_speed = (
        "<tr><td><b>Current speed</b></td><td style='padding: 0 10px;text-align:right'>" +
        str(speed)+"</td>" +
        "<td><b>Average speed</b></td><td style='padding: 0 10px;text-align:right'>" +
        str(round(avgspeed, 2)) +
        "</td></tr>"
    )
    if heartrate:
        line_heartrate = (
            "<tr><td><b>Current heartrate</b></td><td style='padding: 0 10px;text-align:right'>" +
            str(heartrate)+"</td>" +
            "<td><b>Average heartrate</b></td><td style='padding: 0 10px;text-align:right'>" +
            str(int(round(avgheartrate, 0))) +
            "</td></tr>"
        )
    else:
        line_heartrate = ""
    if cadence:
        line_cadence = (
            "<tr><td><b>Current cadence</b></td><td style='padding: 0 10px;text-align:right'>" +
            str(round(cadence, 0)) +"</td>" +
            "<td><b>Average cadence</b></td><td style='padding: 0 10px;text-align:right'>" +
            str(int(round(avgcadence, 0))) +
            "</td></tr>"
        )
    else:
        line_cadence = ""

    html_popup = (
        line_title +
        line_table_start +
        line_time_distance +
        line_duration +
        line_speed +
        line_heartrate +
        line_cadence +
        line_table_end
    )

    return html_popup
