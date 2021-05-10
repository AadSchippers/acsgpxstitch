from django.shortcuts import render, redirect
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib.messages import get_messages
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
import copy
import random


def track_list(request):
    map_filename_random = "_" + str(random.randint(0, 9))
    map_filename = (
        settings.TRACK_MAP.replace('.html', map_filename_random) + '.html'
        )
    basemap_filename = settings.BASE_MAP
    trackname = None
    gpxdownload = None
    intelligent_stitch = None
    split_file = None
    start_selection = 0
    end_selection = 9999999
    tracks = []
    original_tracks = []

    if request.method == 'POST':
        files = request.FILES.getlist('gpxfile')
        if files:
            original_tracks = []
        for file in files:
            new_track = []
            try:
                new_track = (process_gpx_file(request, file))
                if new_track:
                    original_tracks.append(copy.deepcopy(new_track))
                else:
                    # error processing file, file skipped
                    messages.error(
                        request,
                        "Error processing " +
                        file.name +
                        ", file skipped.")
            except Exception:
                pass

        gpxdownload = request.POST.get('gpxdownload')
        try:
            start_selection = int(request.POST.get('start_selection'))
        except Exception:
            pass
        try:
            end_selection = int(request.POST.get('end_selection'))
        except Exception:
            pass
        if not original_tracks:
            try:
                original_tracks = ast.literal_eval(
                    request.POST.get('original_tracks')
                    )
            except Exception:
                return redirect('track_list')

        if len(original_tracks) == 0:
            return redirect('track_list')

        if len(original_tracks) == 1:
            intelligent_stitch = None
        else:
            intelligent_stitch = request.POST.get('intelligent_stitch')

        if len(original_tracks) == 1:
            split_file = request.POST.get('split_file')
        else:
            split_file = None

        if intelligent_stitch:
            tracks = order_tracks(request, original_tracks)
        else:
            tracks = original_tracks.copy()

        if gpxdownload == 'True':
            trackname = request.POST.get('trackname')
            if trackname:
                if not is_input_valid(trackname):
                    # invalid characters in input have been skipped
                    messages.error(
                        request,
                        "Invalid characters in track name."
                    )
                    gpxdownload = False

        if gpxdownload == 'True':
            return download_gpx(
                request, trackname, tracks, start_selection, end_selection
                )

        make_map(
            request,
            tracks,
            map_filename,
            start_selection,
            end_selection,
            split_file,
            )

    total_distance = 0
    for t in tracks:
        total_distance += t["distance"]

    return render(request, 'acsgpxstitch_app/track_list.html', {
        "tracks": tracks,
        "original_tracks": original_tracks,
        "intelligent_stitch": intelligent_stitch,
        "split_file": split_file,
        "start_selection": start_selection,
        "end_selection": end_selection,
        "total_distance": round(total_distance, 2),
        "map_filename": "/static/maps/" + map_filename,
        "basemap_filename": "/static/maps/" + basemap_filename,
        "trackname": trackname,
        }
    )


def is_input_valid(input=None):
    pattern = (r"^[A-z0-9\- +\ ]+$")
    try:
        return re.match(pattern, input) is not None
    except Exception:
        return None
