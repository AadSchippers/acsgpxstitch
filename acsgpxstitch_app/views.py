from django.shortcuts import render, redirect
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.shortcuts import HttpResponseRedirect
from django import forms
import xml.etree.ElementTree as ET
import os
from dateutil.parser import parse
from decimal import *
from datetime import datetime
import time
from .mapviews import *
import re
import hashlib
import ast


def track_list(request):   
    map_filename = settings.TRACK_MAP
    basemap_filename = settings.BASE_MAP 
    gpxdownload = None
    intelligent_stitch = None

    try:
        if not tracks:
            tracks = []
    except:
        tracks = []
    try:
        if not original_tracks:
            try:
                original_tracks = ast.literal_eval(request.POST.get('original_tracks'))
            except:
                original_tracks = []
    except:
        original_tracks = []

    if request.method == 'POST':
        files = request.FILES.getlist('gpxfile')
        if files:
            original_tracks = []
        i = 0
        for file in files:
            original_tracks.append({
                "filename": file.name,
                "distance": 0,
                "reversed": False
            })
            original_tracks[i] = process_gpx_file(request, file, original_tracks[i])
            i += 1

        gpxdownload = request.POST.get('gpxdownload')
        trackname = request.POST.get('trackname')
        if not original_tracks:
            try:
                original_tracks = ast.literal_eval(request.POST.get('original_tracks'))
            except:
                return redirect('track_list')

        if gpxdownload == 'True':
            return download_gpx(request, trackname, tracks)
    
        intelligent_stitch = request.POST.get('intelligent_stitch')
        if intelligent_stitch:
            tracks = order_tracks(request, original_tracks)
        else:
            tracks = original_tracks.copy()

        make_map(request, tracks, map_filename)
    
    total_distance = 0
    for t in tracks:
        total_distance += t["distance"]

    return render(request, 'acsgpxstitch_app/track_list.html', {
        "tracks": tracks,
        "original_tracks": original_tracks,
        "intelligent_stitch": intelligent_stitch,
        "total_distance": round(total_distance, 2),
        "map_filename": "/static/maps/" + map_filename,
        "basemap_filename": "/static/maps/" + basemap_filename,
        }
    )


def is_input_valid(input=None):
    pattern = (r"^[A-z0-9\- +\ ]+$")
    try:
        return re.match(pattern, input) is not None
    except:
        return None
