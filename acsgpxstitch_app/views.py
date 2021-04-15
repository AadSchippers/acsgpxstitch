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


def track_list(request):   
    map_filename = "acsgpxstitch.html"

    try:
        if not tracks:
            tracks = []
    except:
        tracks = []

    if request.method == 'POST':
        files = request.FILES.getlist('gpxfile')
        tracks = []
        i = 0
        for file in files:
            tracks.append({
                "filename": file.name,
                "distance": 0,
                "reversed": False
            })
            tracks[i] = process_gpx_file(request, file, tracks[i])
            i += 1
            if i >= 5:
                break

        make_map(request, tracks, map_filename)

    return render(request, 'acsgpxstitch_app/track_list.html', {
        "tracks": tracks,
        "map_filename": "/static/maps/" + map_filename,
        }
    )


def is_input_valid(input=None):
    pattern = (r"^[A-z0-9\- +\ ]+$")
    try:
        return re.match(pattern, input) is not None
    except:
        return None
