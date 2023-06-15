#!/usr/bin/python3

import argparse
import sys
import logging
import astropy.units as u
from astropy.coordinates import SkyCoord
from astroquery.gaia import Gaia
from astropy.coordinates.name_resolve import NameResolveError
from astropy.units.core import UnitsError
from astropy.coordinates import Angle
from astropy.table import Table
from pwn import log
import shutil
from tabulate import tabulate
import random
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.offsetbox import AnchoredText
import matplotlib
import re
from typing import List
import time
import os
from dataclasses import dataclass, field
import requests
from pathlib import Path
import signal
import copy
import numpy as np
from tqdm import tqdm
import warnings


# ANSI escape codes dictionary
colors = {
        "BLACK": '\033[30m',
        "RED": '\033[31m',
        "GREEN": '\033[32m',
        "BROWN": '\033[33m',
        "BLUE": '\033[34m',
        "PURPLE": '\033[35m',
        "CYAN": '\033[36m',
        "WHITE": '\033[37m',
        "GRAY": '\033[1;30m',
        "L_RED": '\033[1;31m',
        "L_GREEN": '\033[1;32m',
        "YELLOW": '\033[1;33m',
        "L_BLUE": '\033[1;34m',
        "PINK": '\033[1;35m',
        "L_CYAN": '\033[1;36m',
        "NC": '\033[0m'
        }
script_version = 'v1.0.0'


# Define simple characters
sb: str = f'{colors["L_CYAN"]}[{colors["YELLOW"]}*{colors["L_CYAN"]}]{colors["NC"]}' # [*]
sb_v2: str = f'{colors["RED"]}[{colors["YELLOW"]}+{colors["RED"]}]{colors["NC"]}' # [*]
whitespaces: str = " "*(len(sb)+1) # '    '
warning: str = f'{colors["YELLOW"]}[{colors["RED"]}!{colors["YELLOW"]}]{colors["NC"]}' # [!]


# Ctrl-C
def signal_handler(signal, frame):
    print(f"{warning} {colors['L_RED']}Ctrl-C. Exiting...{colors['NC']}")
    sys.exit(1)


# Redirect the signal handler to trigger Ctrl-C custom function
signal.signal(signal.SIGINT, signal_handler)


# Filter warnings thrown by numpy
# Since not always all the magnitudes will be measured for all the filters, this will throw a warning when
# when attempting to pass them as an array
warnings.filterwarnings('ignore')


# Get user flags
def parseArgs():
    """
    Get commands and flags provided by the user
    """
    # General description / contact info
    general_description = f"{colors['L_CYAN']}Gaia DR3 tool written in Python 💫{colors['NC']} -- "
    general_description += f"{colors['L_GREEN']}Contact: {colors['GREEN']}Francisco Carrasco Varela \
                             (ffcarrasco@uc.cl) ⭐{colors['NC']}"

    parser = argparse.ArgumentParser(description=f"{general_description}", epilog=f"example: {sys.argv[0]} extract")

    # Define commands
    commands = parser.add_subparsers(dest='command')

    ### 'extract' command
    str_extract_command: str = 'extract'
    extract_command = commands.add_parser(str_extract_command, help=f'{colors["RED"]}Different modes to extract data{colors["NC"]}', 
                    description=f'{colors["L_RED"]}Extract data from Gaia{colors["NC"]}', epilog=f"example: {sys.argv[0]} extract raw")
    parser_sub_extract = extract_command.add_subparsers(dest='subcommand', 
                                                        help=f"{colors['RED']}Select the source/method to extract data{colors['NC']}")

    # Sub-command extract - raw
    str_extract_subcommand_raw: str = 'raw'
    extract_raw_subcommand_help = f"{colors['L_RED']}Extract raw Gaia data directly from Archive{colors['NC']}"
    extract_subcommand_raw = parser_sub_extract.add_parser(str_extract_subcommand_raw, description=extract_raw_subcommand_help,
                                                           help=f"{colors['RED']}Extract raw Gaia data directly from Archive{colors['NC']}",
                                                           epilog=f"example: {sys.argv[0]} extract raw rectangle")
    # Sub-subcommand: extract - raw - cone
    extract_raw_cone_subsubcommand_help = f"{colors['RED']}Extract data in 'cone search' mode{colors['NC']}"
    parser_sub_extract_raw = extract_subcommand_raw.add_subparsers(dest='subsubcommand', help=f"{colors['RED']}Shape to extract data{colors['NC']}")

    str_extract_subcommand_raw_subsubcommand_cone = 'cone'
    epilog_str_extract_raw_cone_example = rf'''examples: {sys.argv[0]} extract raw cone -n "47 Tuc" -r 2.1 {colors["GRAY"]}# Extract data for "47 Tucanae" or "NGC104"{colors["NC"]}
          {sys.argv[0]} extract raw cone --right-ascension "210" --declination "-60" -r 1.2 -n "myObject" {colors["GRAY"]}# Use a custom name/object, but you have to provide coords{colors["NC"]}
          {sys.argv[0]} extract raw cone --right-ascension="20h50m45.7s" --declination="-5d23m33.3s" -r=3.3 {colors["GRAY"]}# Search for negative coordinates{colors["NC"]}
          '''
    extract_subcommand_raw_subsubcommand_cone = parser_sub_extract_raw.add_parser(str_extract_subcommand_raw_subsubcommand_cone,
                                                                          help=f"{colors['RED']}Extract data in 'cone search' mode{colors['NC']}",
                                                                          description=extract_raw_cone_subsubcommand_help,
                                                                          epilog=epilog_str_extract_raw_cone_example, formatter_class=argparse.RawTextHelpFormatter)
    extract_subcommand_raw_subsubcommand_cone.add_argument('-n', '--name', type=str, required=True,
                                                           help="Object name. Ideally how it is found in catalogs and no spaces. Examples: 'NGC104', 'NGC_6121', 'Omega_Cen', 'myObject'")
    extract_subcommand_raw_subsubcommand_cone.add_argument('-r', '--radii', type=float, required=True,
                                                           help="Radius to extract data. Default units: arcmin (see '--radius-units' to change this)")
    extract_subcommand_raw_subsubcommand_cone.add_argument('--right-ascension', type=str,
                                                           help="Right ascension J2000 coordinates center. Default units: degrees. Not required if you provide a name found in catalogs.")
    extract_subcommand_raw_subsubcommand_cone.add_argument('--declination', type=str,
                                                           help="Declination J2000 coordinates center. Default units: degrees. Not required if you provide a name found in catalogs.")
    extract_subcommand_raw_subsubcommand_cone.add_argument('-o', '--outfile', type=str,
                                                           help="Output filename to save data. File extension is automatically added, so '-o example' creates 'example.dat' file")
    extract_subcommand_raw_subsubcommand_cone.add_argument('--skip-extra-data', action="store_true", help='Skip online Gaia-based extra data for your object')
    extract_subcommand_raw_subsubcommand_cone.add_argument('--gaia-release', default='gdr3', type=str,
                                                           help="Select the Gaia Data Release you want to display what type of data contains\nValid options: {gdr3, gaiadr3, g3dr3, gaia3dr3, gdr2, gaiadr2} (Default: Gaia DR3)")
    extract_subcommand_raw_subsubcommand_cone.add_argument('--radius-units', default='arcmin', type=str,
                                                           help="Units for radius in Cone Search. Options: {arcsec, arcmin, degree} (Default: arcmin)")
    extract_subcommand_raw_subsubcommand_cone.add_argument('--row-limit', type=int, default=-1,
                                                            help='Limit of rows/data to retrieve from Archive. Default = -1 (which means "NO LIMIT")')
    extract_subcommand_raw_subsubcommand_cone.add_argument('--data-outfile-format', type=str, default='ascii.ecsv',
                                                           help="Data file format (not extension) to save data. Default: 'ascii.ecsv'\nFor more info, check: https://docs.astropy.org/en/stable/io/unified.html#built-in-table-readers-writers")
    extract_subcommand_raw_subsubcommand_cone.add_argument('--no-print-data-requested', action="store_true", help='Print requested data to Archive')
    extract_subcommand_raw_subsubcommand_cone.add_argument('--force-overwrite-outfile', action="store_true", help='Forces overwriting/replace old file without asking to the user')
    extract_subcommand_raw_subsubcommand_cone.add_argument('--force-create-directory', action="store_false", help='Forces (do not ask) creating a folder where all data output will be stored')
    extract_subcommand_raw_subsubcommand_cone.add_argument('--no-save-raw-data', action="store_true", help="Do not save raw data")

    # Sub-subcommand: extract - raw - rectangle
    str_extract_subcommand_raw_subsubcommand_rect = 'rectangle'
    extract_subcommand_raw_subsubcommand_rect_example = f"example: {sys.argv[0]} extract raw rectangle -ra '210' -dec '-60' -w 6.5 -ht 5"
    extract_subcommand_raw_subsubcommand_rect = parser_sub_extract_raw.add_parser(str_extract_subcommand_raw_subsubcommand_rect,
                                                                                  help=f"{colors['RED']}Extract data in 'rectangle search' mode{colors['NC']}",
                                                                                  description=f"{colors['L_RED']}Extract data in rectangle shape/mode{colors['NC']}",
                                                                                  epilog=extract_subcommand_raw_subsubcommand_rect_example)
    extract_subcommand_raw_subsubcommand_rect.add_argument('-n', '--name', type=str, required=True,
                                                           help="Object name. Ideally how it is found in catalogs and no spaces. Examples: 'NGC104', 'NGC_6121', 'Omega_Cen', 'myObject'")
    extract_subcommand_raw_subsubcommand_rect.add_argument('-w', '--width', type=float, required=True,
                                                           help="Width to extract data. Default units: arcmin (see '--width-units' to change this)")
    extract_subcommand_raw_subsubcommand_rect.add_argument('-ht', '--height', type=float, required=True,
                                                           help="Height to extract data. Default units: arcmin (see '--height-units' to change this)")
    extract_subcommand_raw_subsubcommand_rect.add_argument('--right-ascension', type=str,
                                                           help="Right ascension J2000 coordinates center. Default units: degrees. Not required if you provide a name found in catalogs.")
    extract_subcommand_raw_subsubcommand_rect.add_argument('--declination', type=str,
                                                           help="Declination J2000 coordinates center. Default units: degrees. Not required if you provide a name found in catalogs.")
    extract_subcommand_raw_subsubcommand_rect.add_argument('-o', '--outfile', help="output file")
    extract_subcommand_raw_subsubcommand_rect.add_argument('--skip-extra-data', action="store_true", help='Skip online Gaia-based extra data for your object')
    extract_subcommand_raw_subsubcommand_rect.add_argument('--gaia-release', default='gdr3', type=str,
                                                           help="Select the Gaia Data Release you want to display what type of data contains\nValid options: {gdr3, gaiadr3, g3dr3, gaia3dr3, gdr2, gaiadr2} (Default: Gaia DR3)")
    extract_subcommand_raw_subsubcommand_rect.add_argument('--width-units', default='arcmin', type=str,
                                                           help="Units for width in Rectanguñar Search. Options: {arcsec, arcmin, degree} (Default: arcmin)")
    extract_subcommand_raw_subsubcommand_rect.add_argument('--height-units', default='arcmin', type=str,
                                                           help="Units for height in Rectangular Search. Options: {arcsec, arcmin, degree} (Default: arcmin)")
    extract_subcommand_raw_subsubcommand_rect.add_argument('--row-limit', type=int, default=-1,
                                                            help='Limit of rows/data to retrieve from Archive. Default = -1 (which means "NO LIMIT")')
    extract_subcommand_raw_subsubcommand_rect.add_argument('--data-outfile-format', type=str, default='ascii.ecsv',
                                                           help="Data file format (not extension) to save data. Default: 'ascii.ecsv'\nFor more info, check: https://docs.astropy.org/en/stable/io/unified.html#built-in-table-readers-writers")
    extract_subcommand_raw_subsubcommand_rect.add_argument('--no-print-data-requested', action="store_true", help='Print requested data to Archive')
    extract_subcommand_raw_subsubcommand_rect.add_argument('--force-overwrite-outfile', action="store_true", help='Forces overwriting/replace old file without asking to the user')
    extract_subcommand_raw_subsubcommand_rect.add_argument('--force-create-directory', action="store_false", help='Forces (do not ask) creating a folder where all data output will be stored')
    extract_subcommand_raw_subsubcommand_rect.add_argument('--no-save-raw-data', action="store_true", help="Do not save raw data")


    # Sub-subcommand: extract - raw - annulus
    str_extract_subcommand_raw_subsubcommand_ring = 'ring'
    extract_subcommand_raw_subsubcommand_ring_example = f"example: {sys.argv[0]} extract raw ring -ra '210' -dec '-60.5' -i 7.0 -e 6.5"
    extract_subcommand_raw_subsubcommand_ring = parser_sub_extract_raw.add_parser(str_extract_subcommand_raw_subsubcommand_ring,
                                                                                  help=f"{colors['RED']}Extract data in 'Annulus/Ring Search' mode{colors['NC']}",
                                                                                  description=f"{colors['L_RED']}Extract data in annulus/ring shape/mode using 2 Cones with different radius{colors['NC']}",
                                                                                  epilog=f"example: {extract_subcommand_raw_subsubcommand_ring_example}")
    extract_subcommand_raw_subsubcommand_ring.add_argument('-n', '--name', type=str, required=True,
                                                           help="Object name. Ideally how it is found in catalogs and no spaces. Examples: 'NGC104', 'NGC_6121', 'Omega_Cen', 'myObject'")
    extract_subcommand_raw_subsubcommand_ring.add_argument('-i', '--inner-radius', type=float, required=True,
                                                           help="Inner radius cone to extract data. Default units: arcmin (see '--internal-units' to change this)")
    extract_subcommand_raw_subsubcommand_ring.add_argument('-e', '--external-radius', type=float, required=True,
                                                           help="External/outer radius cone to extract data. Default units: arcmin (see '--external-units' to change this)")
    extract_subcommand_raw_subsubcommand_ring.add_argument('--right-ascension', type=str,
                                                           help="Right ascension J2000 coordinates center. Default units: degrees. Not required if you provide a name found in catalogs.")
    extract_subcommand_raw_subsubcommand_ring.add_argument('--declination', type=str,
                                                           help="Declination J2000 coordinates center. Default units: degrees. Not required if you provide a name found in catalogs.")
    extract_subcommand_raw_subsubcommand_ring.add_argument('-o', '--outfile', help="output file")
    extract_subcommand_raw_subsubcommand_ring.add_argument('--skip-extra-data', action="store_true", help='Skip online Gaia-based extra data for your object')
    extract_subcommand_raw_subsubcommand_ring.add_argument('--gaia-release', default='gdr3', type=str,
                                                           help="Select the Gaia Data Release you want to display what type of data contains\nValid options: {gdr3, gaiadr3, g3dr3, gaia3dr3, gdr2, gaiadr2} (Default: Gaia DR3)")
    extract_subcommand_raw_subsubcommand_ring.add_argument('--inner-rad-units', default='arcmin', type=str,
                                                           help="Units for Inner Radius in Cone Search. Options: {arcsec, arcmin, degree} (Default: arcmin)")
    extract_subcommand_raw_subsubcommand_ring.add_argument('--external-rad-units', default='arcmin', type=str,
                                                           help="Units for External Radius in Cone Search. Options: {arcsec, arcmin, degree} (Default: arcmin)")
    extract_subcommand_raw_subsubcommand_ring.add_argument('--row-limit', type=int, default=-1,
                                                            help='Limit of rows/data to retrieve from Archive. Default = -1 (which means "NO LIMIT")')
    extract_subcommand_raw_subsubcommand_ring.add_argument('--data-outfile-format', type=str, default='ascii.ecsv',
                                                           help="Data file format (not extension) to save data. Default: 'ascii.ecsv'\nFor more info, check: https://docs.astropy.org/en/stable/io/unified.html#built-in-table-readers-writers")
    extract_subcommand_raw_subsubcommand_ring.add_argument('--no-print-data-requested', action="store_true", help='Print requested data to Archive')
    extract_subcommand_raw_subsubcommand_ring.add_argument('--force-overwrite-outfile', action="store_true", help='Forces overwriting/replace old file without asking to the user')
    extract_subcommand_raw_subsubcommand_ring.add_argument('--force-create-directory', action="store_false", help='Forces (do not ask) creating a folder where all data output will be stored')
    extract_subcommand_raw_subsubcommand_ring.add_argument('--no-save-raw-data', action="store_true", help="Do not save raw data")

    # Sub-command extract - filter
    str_extract_subcommand_filter: str = 'filter'
    extract_filter_subcommand_help = f"{colors['L_BLUE']}Filter Gaia data applying different methods{colors['NC']}"
    extract_subcommand_filter = parser_sub_extract.add_parser(str_extract_subcommand_filter, description=extract_filter_subcommand_help,
                                                           help=f"{colors['BLUE']}Filter Gaia data applying different methods{colors['NC']}",
                                                           epilog=f"example: {sys.argv[0]} extract filter parameters")

    
    extract_filter_subsubcommand_help = f"{colors['BLUE']}Filter data from Gaia{colors['NC']}"
    parser_sub_filter = extract_subcommand_filter.add_subparsers(dest='subsubcommand', help=f"{extract_filter_subsubcommand_help}")

    # Sub-subcommand: extract - filter - parameters
    str_extract_subcommand_filter_subsubcommand_parameters = 'parameters'
    extract_filter_parameters_subsubcommand_help = f"{colors['PURPLE']}Filter Gaia data based on its parameters such as errors, magnitudes, etc{colors['NC']}"
    epilog_str_extract_filter_parameters_example = rf'''examples: {sys.argv[0]} extract filter cone -n "47 Tuc" -r 2.1 {colors["GRAY"]}# Extract data for "47 Tucanae" or "NGC104"{colors["NC"]}
          {sys.argv[0]} extract raw cone --right-ascension "210" --declination "-60" -r 1.2 -n "myObject" {colors["GRAY"]}# Use a custom name/object, but you have to provide coords{colors["NC"]}
          {sys.argv[0]} extract raw cone --right-ascension="20h50m45.7s" --declination="-5d23m33.3s" -r=3.3 {colors["GRAY"]}# Search for negative coordinates{colors["NC"]}
          '''
    extract_subcommand_filter_subsubcommand_parameters = parser_sub_filter.add_parser(str_extract_subcommand_filter_subsubcommand_parameters,
                                                                                      help=extract_filter_parameters_subsubcommand_help,
                                                                                      description=f"{colors['RED']}Filter Gaia data based on parameters returned in data{colors['NC']}",
                                                                                      epilog=epilog_str_extract_filter_parameters_example, 
                                                                                      formatter_class=argparse.RawTextHelpFormatter)
    extract_subcommand_filter_subsubcommand_parameters.add_argument('-f', '--file', type=str,
                                                           help="File containing data to read, extract and filter.\nIf not provided, name, radius, RA, and DEC parameters are required.\nData will be directly extracted from Archive in 'Cone' Search mode.")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('-n', '--name', type=str,
                                                           help="Object name. Ideally how it is found in catalogs and no spaces. Examples: 'NGC104', 'NGC_6121', 'Omega_Cen', 'myObject'.\nNot required if you provide a file containing data.")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('-r', '--radii', type=float,
                                                           help="Radius to extract data. Default units: arcmin (see '--radius-units' to change this).\nNot required if you provide a file containing data.")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--right-ascension', type=str,
                                                           help="Right ascension J2000 coordinates center. Default units: degrees.\nNot required if you provide a file containing data.")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--declination', type=str,
                                                           help="Declination J2000 coordinates center. Default units: degrees.\nNot required if you provide a file containing data.")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('-d', '--file-format', type=str, default='ascii.ecsv',
                                                           help="File format to read file containing data. Default: 'asci.ecsv'")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('-o', '--outfile', type=str,
                                                           help="Output filename to save data output.")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--filter-by-ruwe', type=float, default=1.4,
                                                                    help="Filter by Renormalised unit weight error (RUWE).\nOnly keep lower values than the filter value. Default: 1.4")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--filter-by-pm-error', type=float, default=0.35,
                                                                    help="Filter by Proper Motions errors (RA and DEC components).\nOnly keep lower values than the filter value. Default: 0.35 mas/yr")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--filter-by-g-rp-max', type=float, default=19.5,
                                                                    help="Filter by max G_RP allowed magnitude.\nOnly keep lower values than the filter value. Default: 19.5 mag")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--filter-by-g-rp-min', type=float, default=10.5,
                                                                    help="Filter by min G_RP allowed magnitude.\nOnly keep higher values than the filter value. Default: 10.5 mag")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--skip-extra-data', action="store_true", 
                                                           help='Skip online Gaia-based extra data for your object')
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--gaia-release', default='gdr3', type=str,
                                                           help="Select the Gaia Data Release you want to display what type of data contains\nValid options: {gdr3, gaiadr3, g3dr3, gaia3dr3, gdr2, gaiadr2} (Default: Gaia DR3)")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--radius-units', default='arcmin', type=str,
                                                           help="Units for radius in Cone Search. Options: {arcsec, arcmin, degree} (Default: arcmin)")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--row-limit', type=int, default=-1,
                                                            help='Limit of rows/data to retrieve from Archive. Default = -1 (which means "NO LIMIT")')
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--data-outfile-format', type=str, default='ascii.ecsv',
                                                           help="Data file format (not extension) to save data. Default: 'ascii.ecsv'\nFor more info, check: https://docs.astropy.org/en/stable/io/unified.html#built-in-table-readers-writers")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--no-print-data-requested', action="store_true", help='Print requested data to Archive')
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--force-overwrite-outfile', action="store_true", help='Forces overwriting/replace old file without asking to the user')
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--force-create-directory', action="store_false", help='Forces (do not ask) creating a folder where all data output will be stored')
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--no-save-output', action="store_true", help="Do not save data output")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--no-filter-ruwe', action="store_true",
                                                           help="Do not apply filter by Renormalised unit weight error (RUWE)")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--no-filter-pm-error', action="store_true",
                                                           help="Do not apply filter by Proper Motion errors (both components, RA and DEC)")
    extract_subcommand_filter_subsubcommand_parameters.add_argument('--no-filter-g-rp', action="store_true",
                                                           help="Do not apply filter by G_RP magnitude")


    # Sub-subcommand: extract - filter - ellipse
    str_extract_subcommand_filter_subsubcommand_ellipse = 'ellipse'
    extract_subcommand_filter_subsubcommand_ellipse_example = f"example: {sys.argv[0]} extract filter ellipse -f ngc104_raw.dat --width 5.5 10.2 --height 6.6 7.2"
    extract_subcommand_filter_subsubcommand_ellipse = parser_sub_filter.add_parser(str_extract_subcommand_filter_subsubcommand_ellipse,
                                                                                  help=f"{colors['RED']}Extract data within an ellipse in Vector Point Diagram{colors['NC']}",
                                                                                  description=f"{colors['L_RED']}Extract data in annulus/ring shape/mode using 2 Cones with different radius{colors['NC']}",
                                                                                  epilog=extract_subcommand_filter_subsubcommand_ellipse_example,
                                                                                  formatter_class=argparse.RawTextHelpFormatter)
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('-f', '--file', type=str, required=True,
                                                           help="File containing data to read, extract and filter.")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('--pmra', type=float,
                                                           help="Coordinate in Proper Motion along RA (mas/yr) where the ellipse is centered in VPD.\nRequired if you are using a \"custom\" object not obtained in GCs or OCs catalogues.")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('--pmdec', type=float,
                                                           help="Coordinate in Proper Motion along DEC (mas/yr) where the ellipse is centered in VPD.\nRequired if you are using a \"custom\" object not obtained in GCs or OCs catalogues.")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('-w', '--width', type=float, nargs='+', required=True,
                                                                 help="Minimum and maximum width to create ellipses. Example: '--width 15. 25.'\n'Width' is the axis along PMRA coordinate in VPD in 'mas/yr' units")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('-ht', '--height', type=float, nargs='+', required=True,
                                                                 help="Minimum and maximum height to create ellipses. Example: '--height 15. 30.'\n'Height' is the axis along PMDEC coordinate in VPD in 'mas/yr' units")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('-i', '--inclination', type=float, nargs='+', default=[-90.0, 90.0],
                                                                 help="Minimum and maximum angle inclination to create ellipses. Example: '--inclination -89. 89.'\n'Inclination' is the angle between the Y-axis and the width axis counterclockwise in VPD")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('-d', '--file-format', type=str, default='ascii.ecsv',
                                                                 help="File format to read file containing data. Default: 'asci.ecsv'")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('-o', '--outfile', type=str,
                                                                 help="Output filename to save data output.")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('--data-outfile-format', type=str, default='ascii.ecsv',
                                                                 help="Data file format (not extension) to save data. Default: 'ascii.ecsv'\nFor more info, check: https://docs.astropy.org/en/stable/io/unified.html#built-in-table-readers-writers")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('--n-divisions-in-width', type=int, default=10,
                                                                 help="The program will create an ellipse bewteen the minimum and maximum value of width N times. Default=10")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('--n-divisions-in-height', type=int, default=10,
                                                                 help="The program will create an ellipse bewteen the minimum and maximum value of height N times. Default=10")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('--n-divisions-in-inclination', type=int, default=360,
                                                                 help="The program will create an ellipse bewteen the minimum and maximum value of inclination N times. Default=360")
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('--no-print-data-requested', action="store_true", help='Print requested data to Archive')
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('--force-overwrite-outfile', action="store_true", help='Forces overwriting/replace old file without asking to the user')
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('--force-create-directory', action="store_false", help='Forces (do not ask) creating a folder where all data output will be stored')
    extract_subcommand_filter_subsubcommand_ellipse.add_argument('--no-save-output', action="store_true", help="Do not save data output")
    
    # Sub-subcommand: extract - filter - cordoni
    str_extract_subcommand_filter_subsubcommand_cordoni = 'cordoni'
    extract_subcommand_filter_subsubcommand_cordoni_example = f"example: {sys.argv[0]} extract filter cordoni -f ngc104_filter_ellipse.dat"
    extract_subcommand_filter_subsubcommand_cordoni = parser_sub_filter.add_parser(str_extract_subcommand_filter_subsubcommand_cordoni,
                                                                                  help=f"{colors['CYAN']}Apply Cordoni et al. (2018, ApJ, 869, 139C) filtering algorithm to data{colors['NC']}",
                                                                                  description=f"{colors['CYAN']}Apply Cordoni et al. (2018, ApJ, 869, 139C) filtering algorithm to Gaia data{colors['NC']}",
                                                                                  epilog=extract_subcommand_filter_subsubcommand_cordoni_example,
                                                                                  formatter_class=argparse.RawTextHelpFormatter)
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('-f', '--file', type=str, required=True,
                                                           help="File containing data to read, extract and filter.")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--n-divisions', type=int, default=20,
                                                                 help="Number of bins to divide the data into. Default=20")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--n-iterations', type=int, default=3,
                                                                 help="Number of times to apply Cordoni et al. algorithm. Default=3")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--sigma', type=float, default=3.0,
                                                                 help='Number of times to multiply standard dev. to median value for every bin. Default=3.0')
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('-d', '--file-format', type=str, default='ascii.ecsv',
                                                                 help="File format to read file containing data. Default: 'asci.ecsv'")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('-o', '--outfile', type=str,
                                                                 help="Output filename to save data output.")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--data-outfile-format', type=str, default='ascii.ecsv',
                                                                 help="Data file format (not extension) to save data. Default: 'ascii.ecsv'\nFor more info, check: https://docs.astropy.org/en/stable/io/unified.html#built-in-table-readers-writers")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--set-mag-filter', type=str, default="g_rp",
                                                                 help='Select the Gaia filter you want to use to divide data.\nOptions: {"g_rp", "g_bp", "g"}. Default="g_rp"')
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--set-limits', action="store_true", 
                                                                 help= "Apply custom upper and lower limits in magnitude for data.\nIf not provided (default), maximum and minimum mags will be used to create bins.")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--mag-upper-limit', type=float, default=19.5,
                                                                 help="Maximum magnitude to start creating bins")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--mag-lower-limit', type=float, default=10.5,
                                                                 help='Minimum magnitude to start creating bins')
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--no-print-bins', action='store_true',
                                                                 help='Do not print details for bins created')
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--pmra', type=float, default=0.0,
                                                                 help="If provided, set explicitly Median PMRA value. Usually where the data is centered in VPD.")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--pmdec', type=float, default= 0.0,
                                                                 help="If provided, set explicitly Median PMDEC value. Usually where the data is centered in VPD.")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--no-as-gof-al', action="store_true",
                                                                 help="Avoid filtering data by 'as_gof_al' parameter")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--no-mu-R', action="store_true",
                                                                 help="Avoid filtering data by 'μ_R' parameter")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--no-parallax', action="store_true",
                                                                 help="Avoid filtering data by 'parallax' parameter")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--show-all-plots', action="store_true",
                                                                 help = "Show all the plots generated in all the iterations")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--no-plot-as-gof-al', action="store_true", help="Do not plot 'astrometric_gof_al' process")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--no-plot-mu-R', action="store_true", help="Do not plot 'μ_R' process")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--no-plot-parallax', action="store_true", help="Do not plot 'parallax' process")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--plot-dark-mode', action="store_true", help="Plot in dark mode (adapt colors in plots to this mode)")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--re-compute-ellipse-center', action="store_true", help="Forces to re-compute the ellipse center even if the was found or not in Archives.")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--no-save-output', action="store_true", help="Do not save data output")
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--force-create-directory', action="store_false", help='Forces (do not ask) creating a folder where all data output will be stored')
    extract_subcommand_filter_subsubcommand_cordoni.add_argument('--force-overwrite-outfile', action="store_true", help='Forces overwriting/replace old file without asking to the user')

    ### 'plot' command
    str_plot_command: str = 'plot'
    plot_command = commands.add_parser(str_plot_command, help=f"{colors['GREEN']}Plot data{colors['NC']}")

    # Sub-command plot -> raw -- Plot data without any filter
    parser_subcommand_plot = plot_command.add_subparsers(dest='subcommand', help="Different modes to plot Gaia data")

    str_plot_subcommand_raw: str = 'raw'
    plot_subcommand_raw = parser_subcommand_plot.add_parser(str_plot_subcommand_raw,
                                                            help='Plot data directly extracted from Gaia Archive',
                                                            description=f'{colors["L_RED"]}Plot data directly extracted from Gaia Archive{colors["NC"]}')
    plot_subcommand_raw.add_argument('-n', '--name', help="Set a object name for the sample. Example: 'NGC104', 'my_sample'")
    plot_subcommand_raw.add_argument("--right-ascension", help="Right Ascension (J2000) for the center of data")
    plot_subcommand_raw.add_argument("--declination", help="Declination (J2000) for the center of data")
    plot_subcommand_raw.add_argument('-r', "--radii", help="Radius for the data centered in (RA, DEC) flags in arcmin")
    plot_subcommand_raw.add_argument('--ra-units', default="degree", type=str,  
                                      help="Specify the units to use based on 'astropy' (default: degree). Options: {deg, }")
    
    # Sub-command plot -> filter -- Plot data filtered
    str_plot_subcommand_filter : str = "from-file"
    plot_subcommand_filter = parser_subcommand_plot.add_parser(str_plot_subcommand_filter, 
                                                               help=f"Plot data from a file containing Gaia data")
    plot_subcommand_filter.add_argument("-n", "--name", help="Set a object name for the sample. Example: 'NGC104', 'my_sample'")
    ### 'show-gaia-content' command
    str_show_content_command: str = 'show-gaia-content'
    show_content_command =  commands.add_parser(str_show_content_command, 
                                                help=f"{colors['BROWN']}Show the type of content that different Gaia Releases can provide{colors['NC']}")
    show_content_command.add_argument('-r', '--gaia-release', default='gdr3',
                                      help="Select the Gaia Data Release you want to display what type of data contains. \
                                            Valid options: {gdr3, gaiadr3, g3dr3, gaia3dr3, gdr2, gaiadr2}")
    show_content_command.add_argument('-t', '--table-format', default='grid', 
                                      help="Table display format (default='grid'). To check all formats available visit: https://pypi.org/project/tabulate/")
    # parse the command-line arguments
    args = parser.parse_args()
    return parser, args


def checkUserHasProvidedArguments(parser_provided, args_provided, n_args_provided) -> None:
    """
    Display help messages if the user has not provided arguments to a command/subcommand
    """
    # If user has not provided a command
    if args_provided.command is None:
        parser_provided.parse_args(['-h'])

    # If user has not provided a subcommand  
    if args_provided.command == "extract" and args_provided.subcommand is None:
        parser_provided.parse_args(['extract', '-h'])

    
    # If user has not provided any argument for the subcommand
    if args_provided.command == "extract" and args_provided.subcommand == "raw" and n_args_provided == 3:
        parser_provided.parse_args(['extract', 'raw', '-h'])

    if args_provided.command == "extract" and args_provided.subcommand == "filter" and n_args_provided == 3:
        parser_provided.parse_args(['extract', 'filter', '-h'])

    if args_provided.command == "extract" and args_provided.subcommand == "raw" and args_provided.subsubcommand=="rectangle" and n_args_provided == 4:
        parser_provided.parse_args(['extract', 'raw', 'rectangle', '-h'])

    if args_provided.command == "plot" and args_provided.subcommand is None:
        parser_provided.parse_args(['plot', '-h'])

    if args_provided.command == "plot" and args_provided.subcommand == "raw" and n_args_provided == 3:
        parser_provided.parse_args(['plot', 'raw', '-h'])

    if args_provided.command == "plot" and args_provided.subcommand == "from-file" and n_args_provided == 3:
        parser_provided.parse_args(['plot', 'from-file', '-h'])
            

def checkNameObjectProvidedByUser(name_object) -> None:
    """
    Checks if a user has provided a valid object name. For example, object name 'NGC104' is valid, '<NGC104>' is not. 
    Also, 'NGC 104' is converted to 'NGC_104' for future functions/usage
    """
    pattern = r'^[\w ]+$'
    pass_test = bool(re.match(pattern, name_object))
    if pass_test:
        return
    if not pass_test:
        print(f"{warning} You have provided an invalid name (which may contain invalid characters): {colors['RED']}'{name_object}'{colors['NC']}")
        print(f"    Valid object names examples: NGC104  --  alessa1 -- myRandomObject -- i_love_my_dog")
        sys.exit(1)


def printBanner() -> None:
    # Color 1
    rand_number = random.randint(31,36) 
    c = f'\033[1;{rand_number}m' # color
    sh = f'\033[{rand_number}m' # shadow
    nc = colors['NC'] # no color / reset color
    # Color 2
    rand_number2 = random.randint(31,36) 
    c2 = f'\033[1;{rand_number2}m' # color
    sh2 = f'\033[{rand_number2}m' # shadow
    rand_number3 = random.randint(31,36) 
    c3 = f'\033[1;{rand_number3}m' # color
    banner = rf'''   {c}_____            __{nc}                  
 {c} /  {sh}_  {c}\   _______/  |________  ____{nc}  
{c} /  {sh}/_\  {c}\ /  ___/\   __\_  __ \/  {sh}_ {c}\{nc}  
{c}/    |    \\___ \  |  |  |  | \(  {sh}<_> {c}){nc} 
{c}\____|__  /____  > |__|  |__|   \____/{nc} 
{c}        \/     \/{nc}                      
{c2}      ________        __{nc}                   
{c2}     /  _____/_____  |__|____{nc}              
{c2}    /   \  ___\__  \ |  \__  \{nc}             
{c2}    \    \_\  \/ {sh2}__ {c2}\|  |/ {sh2}__ {c2}\_{nc}            
{c2}     \______  (____  /__(____  /{nc}           
{c2}            \/     \/        \/{nc} {colors['GRAY']} {script_version}{nc}
    '''
    print(banner)
    print(f"\n{' ' * 11}by {c3}Francisco Carrasco Varela{nc}")
    print(f"{' ' * 6}{c3} P. Universidad Católica de Chile{nc}")
    print(f"{' ' * 21}{c3}(ffcarrasco@uc.cl){nc}\n")
    return


def randomColor() -> str:
    """
    Select a random color for text
    """
    return f'\033[{random.randint(31,36)}m'


def displaySections(text, color_chosen=colors['NC'], character='#', c=randomColor()):
    """
    Displays a section based on the user option/command
    """
    nc = colors['NC']
    # Get the user's terminal width and compute its half size
    terminal_width = shutil.get_terminal_size().columns
    total_width = terminal_width // 2
    text_width = len(text) + 2
    padding_width = (total_width - text_width) // 2
    left_padding_width = padding_width
    right_padding_width = padding_width
    # If the number of characters is odd, add 1 extra character to readjust the size
    if (total_width - text_width) % 2 == 1:
        right_padding_width += 1
    left_padding = character * left_padding_width
    right_padding = character * right_padding_width
    # Create the text to display
    centered_text = f"{c}{left_padding} {color_chosen}{text} {c}{right_padding}{nc}"
    border = character * total_width
    # Print the result
    print(f"\n{c}{border}{nc}\n{centered_text}\n{c}{border}{nc}\n")


def randomChar() -> str:
    """
    Select a random character to be printed
    """
    char_list = ['#', '=', '+', '$', '@']
    # 80% to pick '#', 20% remaining distributed for other characters
    weight_list = [0.8, 0.05, 0.05, 0.05, 0.05]
    return random.choices(char_list, weights=weight_list,k=1)[0]


#######################
## show-gaia-content ##
#######################
def read_columns_in_gaia_table(output_list):
    """
    We saved each column separated by '|'. Now use that character to split every row into its respective columns
    """
    rows = []

    for line in output_list:
        col = []
        row = line.strip().split("|")
        for column in row:
            col.append(column.strip())
        rows.append(col)
    return rows


def create_table_elements(width_terminal, printable_data_rows_table):
    """
    Add colors to the table and sets their parts ready to be printed
    """
    # Headers for the table
    headers_table = ["Row", "Name" ,"Var Type", "Unit", "Description"]
    # Get the max length (the sum of them) for columns that are not the "Description column"
    max_length = 0
    extra_gap = 19
    table_to_show = [row for row in printable_data_rows_table]
    for col in printable_data_rows_table:
        new_length = len(col[0]) + len(col[1]) + len(col[2]) + len(col[3]) + extra_gap 
        if new_length > max_length:
            max_length = new_length
    # Max allowed length before 'wrapping' text
    max_allowed_length = width_terminal - max_length - extra_gap

    colors_headers_table = [f"{colors['L_CYAN']}Row{colors['NC']}",
                            f"{colors['PINK']}Name{colors['NC']}",
                            f"{colors['YELLOW']}Var Type{colors['NC']}",
                            f"{colors['L_RED']}Units{colors['NC']}",
                            f"{colors['L_GREEN']}Description{colors['NC']}"]
    # Create a table body containing ANSI escape codes so it will print in colors
    colors_row_table = []
    for column_value in printable_data_rows_table:
        color_column = []
        # 'Row' column
        color_column.append(f"{colors['CYAN']}{column_value[0]}{colors['NC']}")
        # 'Name' column
        color_column.append(f"{colors['PURPLE']}{column_value[1]}{colors['NC']}")
        # 'Var Type' column
        color_column.append(f"{colors['BROWN']}{column_value[2]}{colors['NC']}")
        # 'Unit' column
        color_column.append(f"{colors['RED']}{column_value[3]}{colors['NC']}")
        # 'Description' column
        color_column.append(f"{colors['GREEN']}{column_value[4]}{colors['NC']}")
        colors_row_table.append(color_column)
    return colors_headers_table, colors_row_table, max_allowed_length


def print_table(body_table, headers_table, max_allowed_length, table_format):
    """
    Print the final table/result
    """
    print()
    print(tabulate(body_table, 
          headers=headers_table, tablefmt=table_format, 
          maxcolwidths=[None, None, None, None, max_allowed_length]))


def select_gaia_astroquery_service(service_requested: str) -> str:
    """
    Check the service the user wants to use
    """
    service_requested = service_requested.lower()
    if 'gaiadr3' in service_requested or 'gdr3' in service_requested:
        service = 'gaiadr3.gaia_source'
    elif 'gaiaedr3' in service_requested or 'gedr3' in service_requested:
        service = 'gaiaedr3.gaia_source'
    elif 'gaiadr2' in service_requested or 'gdr2' in service_requested:
        service = 'gaiadr2.gaia_source'
    else:
        print(f"The service you provided is not valid ('{service_requested}'). Using 'GaiaDR3' (default)...")
        service = 'gaiadr3.gaia_source'
    return service
    

def get_data_via_astroquery(args, object_info, mode, purpose='normal'):
    #(args, input_ra, input_dec, mode)
    """
    Get data applying a query to Astroquery
    """
    # Get the service to request data
    service = select_gaia_astroquery_service(args.gaia_release)

    ### Get the input parameters

    # Mode for "show-gaia-content" command
    if purpose == 'content' and mode == 'cone':
        input_ra = 280
        input_dec = -60
        radius_units = u.deg
        input_radius = 1.0
        input_rows = 1

    # Mode for "normal" cone search
    if purpose == 'normal' and mode == 'cone':
        # Get the coordinates of the object in degrees
        input_ra = object_info.RA
        input_dec = object_info.DEC
        # Get the units for the radius, and check if the radius is valid (positive number)
        radius_units = decide_units_parameter(args.radii, args.radius_units) 
        # Check if the user has provided a valid number of rows to extract
        check_number_of_rows_provided(args.row_limit)
        input_radius = args.radii
        input_rows = args.row_limit
    # Mode for "normal" rectangle search
    if purpose == 'normal' and mode == 'rectangle':
        input_ra = object_info.RA
        input_dec = object_info.DEC
        width_units = decide_units_parameter(args.width, args.width_units)
        height_units = decide_units_parameter(args.height, args.height_units)
        check_number_of_rows_provided(args.row_limit)
        input_width = args.width
        input_height = args.height
        input_rows = args.row_limit
    # Mode for "normal" ring search
    if purpose == 'normal' and mode == 'ring':
        # For an annulus/ring, first get the parameters for the external radius
        # Get RA, DEC for the object
        input_ra = object_info.RA
        input_dec = object_info.DEC
        # Get the value and units for the external radius
        external_radius_units = decide_units_parameter(args.external_radius, args.external_rad_units)
        external_radius = args.external_radius
        # Check the number of row limit is valid
        check_number_of_rows_provided(args.row_limit)
        input_rows = args.row_limit
        # Get the values for inner radius and its units
        inner_radius_units = decide_units_parameter(args.inner_radius, args.inner_rad_units)
        inner_radius = args.inner_radius
        check_if_inner_and_ext_radius_are_valid(external_radius*external_radius_units, inner_radius*inner_radius_units)

    if mode == 'cone':
        ### Get data via Astroquery
        Gaia.MAIN_GAIA_TABLE = service 
        Gaia.ROW_LIMIT = input_rows 
        p = log.progress(f'{colors["L_GREEN"]}Requesting data{colors["NC"]}')
        logging.getLogger('astroquery').setLevel(logging.WARNING)

        # Make request to the service
        try:
            p.status(f"{colors['PURPLE']}Querying table for '{service.replace('.gaia_source', '')}' service...{colors['NC']}")
            coord = SkyCoord(ra=input_ra, dec=input_dec, unit=(u.degree, u.degree), frame='icrs')
            radius = u.Quantity(input_radius, radius_units)
            j = Gaia.cone_search_async(coord, radius)         
            logging.getLogger('astroquery').setLevel(logging.INFO)
        except:
            p.failure(f"{colors['RED']}Error while trying to request data{colors['NC']}")
            sys.exit(1)

        p.success(f"{colors['L_GREEN']}Data obtained!{colors['NC']}")
        # Get the final data to display its columns as a table
        r = j.get_results()
        return r 
    if mode == 'rectangle':
        ### Get data via Astroquery
        Gaia.MAIN_GAIA_TABLE = service 
        Gaia.ROW_LIMIT = input_rows 
        p = log.progress(f'{colors["L_GREEN"]}Requesting data{colors["NC"]}')
        logging.getLogger('astroquery').setLevel(logging.WARNING)
        # Make request to the service
        try:
            p.status(f"{colors['PURPLE']}Querying table for '{service.replace('.gaia_source', '')}' service...{colors['NC']}")
            coord = SkyCoord(ra=input_ra, dec=input_dec, unit=(u.degree, u.degree), frame='icrs')
            width = u.Quantity(input_width, width_units)
            height = u.Quantity(input_height, height_units)
            r = Gaia.query_object_async(coordinate=coord, width=width, height=height)
            logging.getLogger('astroquery').setLevel(logging.INFO)
        except:
            p.failure(f"{colors['RED']}Error while trying to request data{colors['NC']}")
            sys.exit(1)

        p.success(f"{colors['L_GREEN']}Data obtained!{colors['NC']}")
        return r
    if mode == 'ring':
        ### Get data via Astroquery
        Gaia.MAIN_GAIA_TABLE = service 
        Gaia.ROW_LIMIT = input_rows
        p = log.progress(f"{colors['L_GREEN']}Requesting data{colors['NC']}")
        logging.getLogger('astroquery').setLevel(logging.WARNING)
        # Make request to the service
        try:
            # First, make the request for the external radius, which is a normal cone
            p.status(f"{colors['PURPLE']}Querying table for '{service.replace('.gaia_source', '')}' service...{colors['NC']}")
            coord = SkyCoord(ra=input_ra, dec=input_dec, unit=(u.degree, u.degree), frame='icrs')
            radius = u.Quantity(external_radius, external_radius_units)
            j = Gaia.cone_search_async(coord, radius)         
            logging.getLogger('astroquery').setLevel(logging.INFO)
        except:
            p.failure(f"{colors['RED']}Error while trying to request data for cone (external radius for ring){colors['NC']}")
            sys.exit(1)
        # Get the final data to display its columns as a table
        r = j.get_results()
        # Create a mask that filters data which is inside inner radius. So it excludes it
        inner_radius_mask = create_mask_for_inner_radius(r, input_ra, input_dec, inner_radius, inner_radius_units, p)
        final_data = r[inner_radius_mask]
        p.success(f"{colors['L_GREEN']}Data obtained!{colors['NC']}")
        return final_data


def check_if_inner_and_ext_radius_are_valid(external_value, inner_value) -> None:
    """
    Check if the user provides a inner radius bigger than external radius for a ring, which cannot be possible
    """
    if external_value > inner_value:
        return
    else:
        print(f"{warning} {colors['RED']}The inner radius you provided ('{inner_value}') cannot be bigger than external radius ('{external_value}'{colors['NC']})")
        sys.exit(1)


def projected_distance_in_sky(point1_ra, point1_dec, point2_ra, point2_dec):
    """
    Projected distance in Sky
    """
    c1 = SkyCoord(point1_ra, point1_dec, unit=(u.degree, u.degree), frame='icrs')
    c2 = SkyCoord(point2_ra, point2_dec, unit=(u.degree, u.degree), frame='icrs')
    return c1.separation(c2) # separation in 'deg'


def print_percentage(total, current_value) ->str:
    """
    Simple function to print percentage process
    """
    return f"{current_value/total * 100.:.2f}%"


def create_mask_for_inner_radius(original_data, coord_ra, coord_dec, inner_radius, inner_radius_units, p, nsteps=400):
    message = f"{colors['GREEN']}Creating ring/annulus from Cone Search...{colors['NC']}"
    p.status(message)
    # Give 2 seconds to read the message
    time.sleep(2)
    filter_mask = []
    original_length = len(original_data)
    for index, element in enumerate(original_data):
        projected_distance = projected_distance_in_sky(element['ra'], element['dec'], coord_ra, coord_dec) 
        # Check if the distance of the object is minor than the inner radius
        # If it is, exclude that data; otherwise include it
        if projected_distance < inner_radius*inner_radius_units:
            filter_mask.append(False)
        else:
            filter_mask.append(True)
        # Print process every 400 steps
        if index%nsteps == 0:
            p.status(f"{message} ({colors['PURPLE']}{print_percentage(original_length, index)}{colors['NC']})")
    if original_length != len(filter_mask):
        print(f"{warning} {colors['RED']}The Mask used to filter Inner Radius data has a different size ({len(filter_mask)}) compared to original data ({len(original_data)}){colors['NC']}.")
        sys.exit(1)
    return filter_mask


def get_content_table_to_display(data):
    """
    Get the content obtained via Astroquery and set it into a table-readable format, replacing some invalid/null values
    """
    output = ""
    output_list = []
    # Clean the data
    for j in range(0, len(data.colnames)):
        prop = data.colnames[j]
        # Set a value for 'unknown'/not set units
        if data[prop].info.unit == None:
            data[prop].info.unit = "-"
        # Clean '{\rm}', '$' and '}' characters from output
        if isinstance(data[prop].info.description, str):
            data[prop].info.description = data[prop].info.description.replace('$', '').replace('{\\rm','').replace("}",'')
        # If no description is provided, say it
        if isinstance(data[prop].info.description, type(None)):
            data[prop].info.description = "No description provided"
        output_list.append(f'{j+1} | {data[prop].info.name} | {data[prop].info.dtype} | {data[prop].info.unit} | {data[prop].info.description}')
    return output_list


def check_if_filename_flag_was_provided(args)->bool | None:
    """
    Check if the user has provided a filename. If not, check if other needed flags has been provided and can be
    used in its place
    """
    # If the user has provided a filename, we can just continue
    if args.file is not None:
        return True
    # If the user has not provided it, then we will have to if some flags has been provided
    if args.file is None:
        print(f"{sb} {colors['PURPLE']}Filename not provided ('-f'). Attempting to use other parameters provided...{colors['NC']}")
    if args.name is None:
        print(f"{warning} {colors['RED']}No name provided to object ('-n' or '--name'). Provide a valid value to this parameter and retry.{colors['NC']}")
        sys.exit(1)
    if args.radii is None:
        print(f"{warning} {colors['RED']}No radius provided ('-r' or '--radii'). Provide a valid value to this parameter and retry.{colors['NC']}")
        sys.exit(1)
    # If the user has provided all of these parameters, then just return a boolean 
    # to indicate we will have to use them in future steps
    return False


def showGaiaContent(args) -> None:
    """
    Get columns to display for GaiaDR3, GaiaEDR3 or GaiaDR2
    """
    displaySections('show-gaia-content', randomColor(), randomChar())
    # Get table format to display the content
    table_format = args.table_format
    # Create a random 'objectInfo' object just to fill
    object_example = objectInfo(name='', RA=280, DEC=-60, pmra=0.0, pmdec=0.0, identifiedAs="Other")
    # Get an example data
    data = get_data_via_astroquery(args, object_example, 'cone', 'content')
    # Get the data into a table format
    output_list = get_content_table_to_display(data)
    # To display the table first we need to get terminal width
    width = shutil.get_terminal_size()[0]
    # Get the data for the table (an array where every element is a row of the table)
    printable_data_table = read_columns_in_gaia_table(output_list)
    # Create table body that will be printed
    headers_table, body_table, max_allowed_length = create_table_elements(width, printable_data_table)
    # Print the obtained table
    print_table(body_table, headers_table, max_allowed_length, table_format)


####################
##### extract ######
####################

def get_object_coordinates(object_name):
    """
    Get the coordinates using service from Strasbourg astronomical Data Center (http://cdsweb.u-strasbg.fr)
    """
    try:
        # Use the SkyCoord.from_name() function to get the coordinates
        object_coord = SkyCoord.from_name(object_name)
        found_object = True
    except NameResolveError:
        found_object = False
        return None, found_object
    return object_coord, found_object


def try_to_extract_angles(coord_parameter):
    try:
        coord_parameter_angle = Angle(coord_parameter)
        return coord_parameter_angle.dec, True
    except UnitsError:
        coord_parameter_angle = Angle(coord_parameter, unit='deg')
        return coord_parameter_angle, True
    except:
        return None, False

def decide_coords(args, print_process=True):
    """
    Based if the object provided by the user was found or not, decide what coordinates the program will use
    """
    if print_process:
        p = log.progress(f'{colors["L_GREEN"]}Obtaining coordinates for object{colors["NC"]}')
    object_coordinates, found_object = get_object_coordinates(args.name)
    if found_object:
        if print_process:
            p.success(f'{colors["GREEN"]}Coords found in Archive{colors["NC"]}')
        return object_coordinates.ra, object_coordinates.dec
    if not found_object:
        # Check if the user has provided parameters so we can extract the coordinates manually
        if args.right_ascension is None:
            print(f"{warning}{colors['RED']} Invalid object name ('{args.name}') and Right Ascension not provided ('--right-ascension')")
            sys.exit(1)
        if args.declination is None:
            print(f"{warning}{colors['RED']} Invalid object name ('{args.name}') and Declination not provided ('--declination')")
            sys.exit(1)
        # If the user has provided coordinates, use them
        if print_process:
            p.failure(f"{colors['RED']} Object could not be found in Archives (astropy). Using coordinates provided by the user instead{colors['NC']}")
        # Try to create SkyCoord with provided units
        RA, DEC = args.right_ascension, args.declination
        try:
            coord_manual = SkyCoord(RA, DEC)
        except UnitsError:
            # Assume default units (degrees) if no units are specified
            coord_manual = SkyCoord(ra=RA, dec=DEC, unit=(u.deg, u.deg))
        except:
            print(f"{warning} {colors['RED']}Unable to convert coordinates provided (RA '{args.right_ascension}' and DEC '{args.declination}') to degree units. Review your input and retry...{colors['NC']}")
            sys.exit(1)
        return coord_manual.ra.degree, coord_manual.dec.degree
            
            
@dataclass(kw_only=True)
class astroStudy:
    """
    Studies where the data is extracted from
    """
    authors: List[str]
    year: int
    magazine: str
    vol: str
    page: str
    study_url: str
    data_url: str

    def show_study(self) -> str:
        """
        Prints the classic "Author & Author 2 (2024)" or "Author et al. (2024)"
        """
        if len(self.authors) <= 2:
            author1 = self.authors[0].split(',')[0]
            author2 = self.authors[1].split(',')[0]
            return f"{author1} & {author2} ({self.year}, {self.magazine}, {self.vol}, {self.page})"
        else:
            first_author = self.authors[0].split(',')[0]
            return f"{first_author} et al. ({self.year}, {self.magazine}, {self.vol}, {self.page})"


@dataclass(kw_only=True)
class onlineVasilievObject:
    """
    Create a data structure for data obtained from Vasiliev & Baumgardt (2021, MNRAS, 505, 5978V)
    """
    name: str = '' # object name
    opt_name: str = ''# optional name if available
    ra: float  # deg J2000
    dec:float  # deg J2000
    pmra:float  # mas/yr
    e_pmra:float  # mas/yr
    pmdec:float  # mas/yr
    e_pmdec:float  # mas/yr
    parallax:float  # mas
    e_parallax:float  # mas
    rscale:float # arcmin
    nstar:int  # number of Gaia-detected cluster stars


def get_extra_object_info_globular_cluster(args, p):
    """
    Request Globular Cluster data from Vasiliev & Baumgardt (2021, MNRAS, 505, 5978V) if available
    """
    # Check data from Vasiliev & Baumgardt (2021, MNRAS, 505, 5978V)
    vasiliev_baumgardt_study = astroStudy(authors=["Vasiliev, E.", "Baumgardt, H."],
                                         year=2021, magazine="MNRAS",
                                         vol="505", page="597V",
                                         study_url='https://ui.adsabs.harvard.edu/abs/2021MNRAS.505.5978V/abstract',
                                         data_url='https://cdsarc.cds.unistra.fr/ftp/J/MNRAS/505/5978/tablea1.dat')

    p.status(f"{colors['GREEN']}Requesting data from {vasiliev_baumgardt_study.show_study()}{colors['NC']}")

    response = requests.get(vasiliev_baumgardt_study.data_url)

    # Check the HTTP status code
    if response.status_code == 200:
        # Read the content of the response
        source_code = response.text

        # Split the source code into lines
        lines = source_code.splitlines()

        # Objects with a single word name
        exceptions_object_names = ['Eridanus', 'Pyxis', 'Crater']

        # Iterate over each line
        for line in lines:
            # Split the line into columns
            columns = line.split()
            single_name_condition = columns[0].lower() == args.name.lower() and args.name.lower() in [exception_object.lower() for exception_object in exceptions_object_names]
            single_name_condition = single_name_condition and len(columns) == 12

            if single_name_condition:
                vasiliev_name = columns[0]
                vasiliev_ra = float(columns[1])
                vasiliev_dec = float(columns[2])
                vasiliev_pmra = float(columns[3])
                vasiliev_e_pmra = float(columns[4])
                vasiliev_pmdec = float(columns[5])
                vasiliev_e_pmdec = float(columns[6])
                vasiliev_parallax = float(columns[8])
                vasiliev_e_parallax = float(columns[9])
                vasiliev_rscale = float(columns[10])
                vasiliev_nstar = int(columns[11])
                vasiliev_object = onlineVasilievObject(name=vasiliev_name,
                                                       ra=vasiliev_ra,
                                                       dec=vasiliev_dec,
                                                       pmra=vasiliev_pmra,
                                                       e_pmra=vasiliev_e_pmra,
                                                       pmdec=vasiliev_pmdec,
                                                       e_pmdec=vasiliev_e_pmdec,
                                                       parallax=vasiliev_parallax,
                                                       e_parallax=vasiliev_e_parallax,
                                                       rscale=vasiliev_rscale,
                                                       nstar=vasiliev_nstar)
                p.success(f"{colors['GREEN']} Data succesfully found and extracted from {vasiliev_baumgardt_study.show_study()} {colors['NC']}")
                return True, vasiliev_object

            # There is, literally, 1 line with an alternative name with only 1 component '1636-283'
            special_case_condition =  (args.name.lower() == '1636-283' or args.name.lower == '1636 283') and columns[2] == '1636-283'
            special_case_condition = special_case_condition and len(columns) == 14
            if special_case_condition:
                vasiliev_name = f"{columns[0]} {columns[1]}"
                vasiliev_opt_name = f"{columns[2]}"
                vasiliev_ra = float(columns[3])
                vasiliev_dec = float(columns[4])
                vasiliev_pmra = float(columns[5])
                vasiliev_e_pmra = float(columns[6])
                vasiliev_pmdec = float(columns[7])
                vasiliev_e_pmdec = float(columns[8])
                vasiliev_parallax = float(columns[10])
                vasiliev_e_parallax = float(columns[11])
                vasiliev_rscale = float(columns[12])
                vasiliev_nstar = int(columns[13])
                vasiliev_object = onlineVasilievObject(name=vasiliev_name,
                                                       opt_name=vasiliev_opt_name,
                                                       ra=vasiliev_ra,
                                                       dec=vasiliev_dec,
                                                       pmra=vasiliev_pmra,
                                                       e_pmra=vasiliev_e_pmra,
                                                       pmdec=vasiliev_pmdec,
                                                       e_pmdec=vasiliev_e_pmdec,
                                                       parallax=vasiliev_parallax,
                                                       e_parallax=vasiliev_e_parallax,
                                                       rscale=vasiliev_rscale,
                                                       nstar=vasiliev_nstar)
                p.success(f"{colors['GREEN']}Data found as {colors['RED']}Globular Cluster{colors['GREEN']} from {vasiliev_baumgardt_study.show_study()} {colors['NC']}")
                return True, vasiliev_object

        
            # Objects with 2 component name, for example "NGC" and a number and an alternative name
            possible_object_names = [f"{columns[0].lower()}{columns[1].lower()}", 
                                     f"{columns[0].lower()} {columns[1].lower()}", 
                                     f"{columns[2].lower()}{columns[3].lower()}", 
                                     f"{columns[2].lower()} {columns[3].lower()}"]
            
            no_alternatives_names_condition = args.name.lower() in possible_object_names and len(columns) == 13
            if no_alternatives_names_condition:
                vasiliev_name = f"{columns[0]} {columns[1]}"
                vasiliev_ra = float(columns[2])
                vasiliev_dec = float(columns[3])
                vasiliev_pmra = float(columns[4])
                vasiliev_e_pmra = float(columns[5])
                vasiliev_pmdec = float(columns[6])
                vasiliev_e_pmdec = float(columns[7])
                vasiliev_parallax = float(columns[9])
                vasiliev_e_parallax = float(columns[10])
                vasiliev_rscale = float(columns[11])
                vasiliev_nstar = int(columns[12])
                vasiliev_object = onlineVasilievObject(name=vasiliev_name,
                                                       ra=vasiliev_ra,
                                                       dec=vasiliev_dec,
                                                       pmra=vasiliev_pmra,
                                                       e_pmra=vasiliev_e_pmra,
                                                       pmdec=vasiliev_pmdec,
                                                       e_pmdec=vasiliev_e_pmdec,
                                                       parallax=vasiliev_parallax,
                                                       e_parallax=vasiliev_e_parallax,
                                                       rscale=vasiliev_rscale,
                                                       nstar=vasiliev_nstar)
                p.success(f"{colors['GREEN']} Data found as {colors['RED']}Globular Cluster{colors['GREEN']} from {vasiliev_baumgardt_study.show_study()} {colors['NC']}")
                return True, vasiliev_object
                

            multiple_name_condition = args.name.lower() in possible_object_names and len(columns) == 15
            if multiple_name_condition:
                vasiliev_name = f"{columns[0]} {columns[1]}"
                vasiliev_opt_name = f"{columns[2]} {columns[3]}"
                vasiliev_ra = float(columns[4])
                vasiliev_dec = float(columns[5])
                vasiliev_pmra = float(columns[6])
                vasiliev_e_pmra = float(columns[7])
                vasiliev_pmdec = float(columns[8])
                vasiliev_e_pmdec = float(columns[9])
                vasiliev_parallax = float(columns[11])
                vasiliev_e_parallax = float(columns[12])
                vasiliev_rscale = float(columns[13])
                vasiliev_nstar = int(columns[14])
                vasiliev_object = onlineVasilievObject(name=vasiliev_name,
                                                       opt_name=vasiliev_opt_name,
                                                       ra=vasiliev_ra,
                                                       dec=vasiliev_dec,
                                                       pmra=vasiliev_pmra,
                                                       e_pmra=vasiliev_e_pmra,
                                                       pmdec=vasiliev_pmdec,
                                                       e_pmdec=vasiliev_e_pmdec,
                                                       parallax=vasiliev_parallax,
                                                       e_parallax=vasiliev_e_parallax,
                                                       rscale=vasiliev_rscale,
                                                       nstar=vasiliev_nstar)
                p.success(f"{colors['GREEN']} Data found as {colors['RED']}Globular Cluster{colors['GREEN']} from {vasiliev_baumgardt_study.show_study()} {colors['NC']}")
                return True, vasiliev_object

    if response.status_code != 200:
        p.status(f"{colors['RED']}Unable to reach the data source website ('{vasiliev_baumgardt_study.data_url}'). Check your internet connection and retry.{colors['NC']}")
        time.sleep(2)
        return False, None
    p.status(f"{colors['RED']}Data not found for '{args.name}' in {vasiliev_baumgardt_study.show_study()}. Continuing...{colors['NC']}")
    time.sleep(2)
    return False, None


@dataclass(kw_only=True)
class onlineCantanObject:
    """
    Object to store data extracted from Cantat-Gaudin et al. (2020, A&A, 640, A1)
    For more info check: https://cdsarc.cds.unistra.fr/ftp/J/A+A/640/A1/ReadMe
    """
    name: str
    ra: float # deg, J2000
    dec: float # deg, J2000
    r50: float # deg - Radius containing half the members
    n_stars: int # Number of stars with a probability over 0.7
    pmra: float # mas / yr
    e_pmra: float # mas / yr
    pmdec: float # mas / yr
    e_pmdec: float # mas / yr
    parallax: float # mas
    e_parallax: float # mas
    log_age: float # Age (logt) of the cluster in years
    a_v: float # Extinction Av of the cluster (mag)
    d_modulus: float # Distance modulus of the cluster (mag)
    distance: float # pc
    rgc : float # distance from galaxy center, assuming the distance is 8340 pc (pc)

    
def get_extra_object_info_open_cluster(args, p, set_warning=True):
    """
    Request Open Cluster data from Cantat-Gaudin et al. (2020, A&A, 640, A1) if available
    """
    cantat_gaudin_study = astroStudy(authors=["Cantat-Gaudin, T.", "Anders, F.", "Castro-Ginard, A.","Jordi, C.",
                                              "Romero-Gómez, M.","Soubiran, C.","Casamiquela, L.","Tarricq, Y."
                                              ,"Moitinho, A.","Vallenari, A.","Bragaglia, A.","Krone-Martins, A.",
                                              "Kounkel, M."], 
                                     year=2020, 
                                     magazine="A&A", 
                                     vol="640", 
                                     page="A1",
                                     study_url='https://ui.adsabs.harvard.edu/abs/2020A%26A...640A...1C/abstract',
                                     data_url='https://cdsarc.cds.unistra.fr/ftp/J/A+A/640/A1/table1.dat')
    p.status(f"{colors['GREEN']}Requesting data from {cantat_gaudin_study.show_study()}{colors['NC']}")
    # Request data
    response = requests.get(cantat_gaudin_study.data_url)
    # Check the HTTP status code
    if response.status_code == 200:
        # Read the content of the response
        source_code = response.text

        # Split the source code into lines
        lines = source_code.splitlines()

        for line in lines:
            columns = line.split()
            # Special case
            if "coin" in columns[0].lower():
                possible_names = [columns[0].lower(), columns[0].lower().replace('-', ' ').replace('_', ' '),
                                  columns[0].lower().replace('-', '').replace('_', '')]
            # All the posible options
            possible_names = [columns[0].lower(), columns[0].lower().replace('_', ' '),
                              columns[0].lower().replace('_', ''), columns[0].lower().replace('_', '-')]

            if args.name.lower() in possible_names:
                columns = line.split()
                name = columns[0].replace('_',' ')
                ra = float(columns[1])
                dec = float(columns[2])
                r50 = float(columns[5])
                n_stars = int(columns[6])
                pmra = float(columns[7])
                e_pmra = float(columns[8])
                pmdec = float(columns[9])
                e_pmdec = float(columns[10])
                parallax = float(columns[11])
                e_parallax = float(columns[12])
                # Since some values in Cantat-Gaudin et al. study are filled with '---' values, if it that is the case
                # fill them with -9999 (similar as was done for APOGEE survey)
                try:
                    log_age = float(columns[14])
                    a_v = float(columns[15])
                    d_modulus=float(columns[16])
                    distance=float(columns[17])
                    rgc=float(columns[-1])
                except ValueError:
                    if set_warning:
                        print(f"{warning} {colors['RED']}Some parameters are not defined in {cantat_gaudin_study.show_study()}. Filling with '-9999' those values{colors['NC']}")
                    log_age = -9999.
                    a_v = -9999.
                    d_modulus= -9999.
                    distance= -9999.
                    rgc= -9999.
                cantat_object = onlineCantanObject(name=name,
                                                   ra = ra,
                                                   dec = dec,
                                                   r50 = r50,
                                                   n_stars=n_stars,
                                                   pmra = pmra,
                                                   e_pmra = e_pmra,
                                                   pmdec = pmdec,
                                                   e_pmdec = e_pmdec,
                                                   parallax = parallax,
                                                   e_parallax = e_parallax,
                                                   log_age = log_age,
                                                   a_v = a_v,
                                                   d_modulus=d_modulus,
                                                   distance=distance,
                                                   rgc=rgc)

                p.success(f"{colors['GREEN']} Data found as {colors['RED']}Open Cluster{colors['GREEN']} from {cantat_gaudin_study.show_study()} {colors['NC']}")
                return True, cantat_object
    if response.status_code != 200:
        p.failure(f"{colors['RED']}Unable to reach the data source website ('{cantat_gaudin_study.data_url}'). Check your internet connection and retry.{colors['NC']}")
        time.sleep(2)
        return False, None
    p.failure(f" {colors['RED']}Could not find online data available for '{args.name}' object. Continuing...")
    return False, None


def decide_units_parameter(value, units):
    """
    Check if the radius provided by the user, along with its units, is valid
    """
    # Check if the value provided by the user is valid
    if value < 0:
        print("{warning} Radius must be a positive number. Check '-r' flag provided and retry")
        sys.exit(1)
    # Check which unit should we use to make the request
    unit = units.lower()
    if unit == 'deg' or unit == 'degree' or unit == 'degs' or unit == 'degrees':
        return u.deg
    if unit  == 'arcmin' or unit  == 'arcmins' or unit  == 'arcminute' or unit == 'arcminutes':
        return u.arcmin
    if unit == 'arcsec' or unit == 'arcsecs' or unit == 'arcsecond' or unit == 'arcseconds':
        return u.arcsec
    print(f"{warning} {colors['RED']}You have provided an invalid value for radii (--radius-units='{units}'). Using default value: 'arcmin'{colors['NC']}")
    return u.arcmin


def check_number_of_rows_provided(rows):
    """
    Check if the user has provided a valid number of rows to retrieve data, which must be a positive integer or -1 ('NO LIMIT')
    """
    if rows == -1 or rows > 0:
        return
    print(f"{warning} {colors['RED']}You have provided an invalid number of rows (--row-limit= {rows}). Value must be a positive integer or -1 ('NO LIMIT'){colors['NC']}")
    sys.exit(1)


def print_elapsed_time(start_time, text_to_print)->None:
    """
    Checks how much time a process has taken
    """
    elapsed_time = time.time() - start_time
    color1 = randomColor()

    # If the time took more than a minute, print it in format MM m SS.S s
    if elapsed_time >= 60.:
        # Convert elapsed time to minutes and seconds
        minutes = int(elapsed_time // 60)
        seconds = elapsed_time % 60
        text_elapsed_time = f"Elapsed time {text_to_print}: {minutes}m {seconds:.1f}s"
        len_text = len(text_elapsed_time) + 4
        text_elapsed_time = f"{sb} {randomColor()}{text_elapsed_time}{colors['NC']}"
    # If the execution time is less than a minute, then print only in second format   
    else:
        text_elapsed_time = f"Elapsed time {text_to_print}: {elapsed_time:.1f}s"
        len_text = len(text_elapsed_time) + 4 
        text_elapsed_time = f"{sb} {randomColor()}{text_elapsed_time}{colors['NC']}"
    print()
    print(f"{color1}"+"-"*len_text+f"{colors['NC']}")
    print(text_elapsed_time)
    print(f"{color1}"+"-"*len_text+f"{colors['NC']}")
    return


@dataclass(kw_only=True)
class objectInfo:
    name: str
    RA: float
    DEC: float
    pmra: float
    pmdec: float
    identifiedAs: str

    def __post_init__(self):
        """
        Check which type of object has the data been identified as
        """
        allowed_values = ["GlobularCluster", "OpenCluster", "Other"]
        if self.identifiedAs not in allowed_values:
            raise ValueError(f"Invalid identifiedAs value. Allowed values are: {allowed_values}")


def get_RA_and_DEC(args, fill=False, print_decide_coords=True):
    """
    Get coordinates of the object in degrees
    """
    object_online_found = False
    if args.skip_extra_data:
        print(f"{sb} 'Skip extra data' enabled. Skipping online data extract steps...")
    # if the flag '--skip-extra-data' is not provided, get Gaia-based data online
    if not args.skip_extra_data:
        p = log.progress(f"{colors['L_GREEN']}Searching data online{colors['NC']}")
        # Check is the object is found as a Globular cluster
        object_online_found, object_online_data = get_extra_object_info_globular_cluster(args, p)
        identified="GlobularCluster"
        # If the object has not been found as a Globular Cluster, search if it is a Open Cluster
        if not object_online_found:
            object_online_found, object_online_data = get_extra_object_info_open_cluster(args, p)
            identified = "OpenCluster"
    # If the object was found online, use those coords. Otherwise search for coords using astropy and, lastly, the ones provided by the user
    if not object_online_found:
        if not fill:
            RA, DEC = decide_coords(args, print_process=print_decide_coords)
            pmra, pmdec = 0.0, 0.0 # If the object was not found, fill the proper motion with some values
            identified = "Other"
        else: # fill the data with anything
            RA, DEC = 0.0, 0.0
            pmra, pmdec = 0.0, 0.0
            identified = "Other"
    else: # if object_online_found
        RA, DEC = object_online_data.ra, object_online_data.dec
        pmra, pmdec = object_online_data.pmra, object_online_data.pmdec
    object_info = objectInfo(name=args.name, RA=RA, DEC=DEC, pmra=pmra, pmdec= pmdec, identifiedAs=identified)

    return object_info


def print_data_requested(data, start_time, show_n_rows=13):
    """
    Print the data that has been extracted via Astroquery using pprint
    """
    print(f"{sb} Small extract of data requested:\n\n")
    data.pprint(max_lines=show_n_rows)
    print()
    print_elapsed_time(start_time, "requesting data")


def check_if_save_file_exists():
    """
    A file should be located/created as $HOME/.astrogaia-python/working.txt. 
    The content of this file should be where would you liketo save all the outputs 
    for this program. If the file is blank/empty then we use that path to save all 
    the data
    """
    # Get $HOME path for current user
    home_dir = os.path.expanduser("~")
    # Name of the file containing the absolute path for the working directory
    working_dir_file = "working.txt"
    try:
        with open(f"{home_dir}/.astrogaia-python/{working_dir_file}") as file:
            # Read the first line, I do not care about the rest
            working_directory = file.readline()
    except FileNotFoundError:
        return False, ''
    working_directory = working_directory.strip()
    if working_directory.endswith('/'):
        working_directory = working_directory.rstrip('/')
    return True, working_directory


def check_if_directory_exists(pre_path: str, path_to_check: str, ask_user=False)->None:
    """
    Checks if a directory exists. If it does not exist, create it
    """
    pre_path_var = str(pre_path)
    if not os.path.exists(path_to_check):
        pure_path = path_to_check.replace(pre_path_var, '', 1).replace('/','',1)
        print(f"{warning} Could not find '{pure_path}' directory in '{shortened_path(str(pre_path))}'. Creating it...")
        if ask_user:
            ask_text = f"{sb_v2} {colors['GREEN']}Do you want to create '{pure_path}' directory in '{shortened_path(str(pre_path))}' path? {colors['RED']}[Y]es/[N]o{colors['NC']}: "
            wantToCreateDir = ask_to(ask_text)
            if wantToCreateDir:
                os.makedirs(path_to_check)
            if not wantToCreateDir:
                print(f"{warning} Exiting. You need to create a folder called '{pure_path}' in '{pre_path}'")
                print(f"    Or use '-o' flag to provide your own/custom outfile name and skip this step")
                sys.exit(1)
        else:
            os.makedirs(path_to_check)
    return


def get_Object_directory(args, object_path, obj_name, objectIdentifiedAs):
    results_dir_name = 'Objects'
    object_name_to_save = obj_name.lower().replace(' ','_')
    object_dir_path = f"{object_path}/{results_dir_name}"
    # Check if 'Objects' directory exists. If not, create it
    check_if_directory_exists(object_path, object_dir_path, ask_user=args.force_create_directory)
    # Check if, inside 'Objects' directory, the directories "GlobularCluster", "OpenCluster" or "Other" exist
    section_path = f"{object_dir_path}/{objectIdentifiedAs}"
    check_if_directory_exists(object_dir_path, section_path)
    # Finally, check if a directory with the object name exists within its respective type directory
    # e.g., since NGC104 is a Globular Cluster, check if 'Object/GlobularCluster/ngc104' directory exists
    path_to_save = f"{section_path}/{object_name_to_save}"
    check_if_directory_exists(section_path, path_to_save)
    return path_to_save


def shortened_path(full_path: str) -> str:
    """
    Shorten a path if it is too large to print a shorter string
    """
    # Split the path into "/"
    list_path = full_path.split('/')
    # Delete elements that are 'null'/empty strings
    list_path = [element for element in list_path if element]
    if len(list_path) <= 4:
        return full_path
    i=0
    short_path = f"/{list_path[i]}/{list_path[i+1]}/.../{list_path[-i-2]}/{list_path[-i-1]}"
    if len(full_path) <= len(short_path):
        return full_path
    return short_path
    

def where_to_save_data_if_found_in_Archive(args, command, mode, p, object_info)->str:
    if not args.outfile:
        working_dir_file_exists, working_dir = check_if_save_file_exists()
        if working_dir_file_exists:
            current_path = working_dir
            print("File exists")
        else:
            current_path = Path.cwd()
        object_path_to_save = get_Object_directory(args, current_path, object_info.name, object_info.identifiedAs)
        filename = f"{object_info.name.replace(' ', '_').lower()}_{command}_{mode}.dat"
        filename = f"{object_path_to_save}/{filename}"
        p.status(f"{colors['YELLOW']}No outfile name provided in input. {colors['GREEN']}Data will be saved as\n'{colors['L_BLUE']}{filename}{colors['GREEN']}'\ninto working directory ('{shortened_path(str(current_path))}'){colors['NC']}{colors['NC']}")
        return filename
    if args.outfile:
        possible_extensions = ['.dat', '.csv', '.txt']
        endsWithValidFileExtension = False
        for fileExtension in possible_extensions:
            if args.outfile.endswith(fileExtension):
                endsWithValidFileExtension = True
                break
        if endsWithValidFileExtension:
            filename = str(args.outfile)
        else:
            filename = f"{args.outfile}.dat"
        # Convert to a Path object
        path = Path(filename)
        current_path = Path.cwd()
        if path.is_absolute():
            p.status(f"{colors['GREEN']}Saving {command!r} data in '{filename}'")
        else:
            p.status(f"{colors['GREEN']}Saving data in '{filename}' file into current directory ('{current_path}')...")
    return filename


def ask_to(ask_text: str, max_attempts=10)->bool | None:
    """
    Asks the user with a prompt and receives a 'Yes/No' reply. Yes = True, No = False
    """
    # Regular expression patterns
    yes_pattern = re.compile(r"^(y|ye|yes)$", re.IGNORECASE)
    no_pattern = re.compile(r"^(n|no)$", re.IGNORECASE)

    # Initalize attempts
    attempts = 0

    while attempts < max_attempts:
        response = input(ask_text)
    
        if yes_pattern.match(response):
            return True
        elif no_pattern.match(response):
            return False
        else:
            print(f"{warning} {colors['YELLOW']}Invalid option. Please enter '[{colors['L_RED']}Y{colors['YELLOW']}]es' or '[{colors['L_RED']}N{colors['YELLOW']}]o'{colors['NC']}")
            print(f"    Remaining attempts: {max_attempts - attempts}")
            attempts += 1

    if attempts > max_attempts:
        print(f"{warning} {colors['L_RED']}You have reached the maximum number of attempts. Exiting...{colors['NC']}")
        sys.exit(1)


def print_before_and_after_filter_length(original_length: int, filtered_length: int, n_prints=70)->None:
    # Get the user's terminal width and compute its half size
    terminal_width = shutil.get_terminal_size().columns
    total_width = terminal_width // 2
    # Pick some random chars and colors to print
    pick_color = randomColor()
    random_char = randomChar()
    separator = f"{pick_color}{random_char*total_width}{colors['NC']}"
    print()
    print(separator)
    print(f"  {colors['BROWN']}-> {colors['RED']}Original data size: {colors['PURPLE']}{original_length}{colors['NC']}")
    print(f"  {colors['BROWN']}-> {colors['GREEN']}Filtered data size: {colors['BLUE']}{filtered_length}{colors['NC']}")
    print(f"  {colors['BROWN']}-> {colors['L_GREEN']}\"Survival\" data:    {colors['L_BLUE']}{((filtered_length/original_length)*100):.2f}%{colors['NC']}")
    print(separator)
    print()
    return None


def get_filename_in_list(word_to_split_in_a_list: str, char_to_split: str = '_'):
    """
    Searches for the words 'raw' or 'filtered' that should be separated by '_' characters in filename.
    For example, "my_example_raw" when separated/splitted by '_' chars, raw will be in position 2.
    Therefore we use the name of the object as everything that was before position 2; in our
    example the name then would be "my_example".
    If no word 'raw' or 'filtered' is present in filename, then just return the original string.
    """
    list_split = word_to_split_in_a_list.split(char_to_split)
    position = 0
    found = False
    for index, element in enumerate(list_split):
        if element.lower() == 'raw':
            position = index
            found = True
            break
        elif element.lower() == 'filter':
            position = index
            found = True
            break
    if found:
        name_list = list_split[:position]
        filename_without_extension = "_".join(map(str, name_list))
        return filename_without_extension
    else:
        return word_to_split_in_a_list.replace(' ','_')


def decide_identifiedAs_based_on_abs_path(file_Path_object)->str:
    full_path = file_Path_object.resolve()
    file_origin_directory = str(full_path.parent)
    if 'globularcluster' in file_origin_directory.lower():
        return 'GlobularCluster'
    elif 'opencluster' in file_origin_directory.lower():
        return 'OpenCluster'
    else:
        return 'Other'
    

def decide_parameters_to_save_data(args, object_info: objectInfo | None):
    """
    Decides where to save a file based on if it was provided reading a file or using Archives
    """
    # If the data was obtained reading a file, object_info will be None
    if object_info is None and args.file is not None:
        file_Path_object = Path(args.file)
        filename_original_without_extension = str(file_Path_object.stem)
        # Get the object name 
        obj_name = get_filename_in_list(filename_original_without_extension)
        # Based on where is saved the file provided, get if it is a Glob Cluster, Open Cluster, or Other
        new_object = objectInfo(name=obj_name, RA=0., DEC=0., pmra=0.0, pmdec=0.0, identifiedAs=decide_identifiedAs_based_on_abs_path(file_Path_object))
        return new_object
    else:
        return object_info


def save_data_output(args, command, mode, object_info, data):
    p = log.progress(f"{colors['L_GREEN']}Saving data{colors['NC']}")
    filename = where_to_save_data_if_found_in_Archive(args, command, mode, p, object_info)
    # If the user explicitly wants to replace the file, skip the step checking this
    if not args.force_overwrite_outfile:
        file_path = Path(filename)
        # Check if file exists
        if file_path.exists():
            print(f"{warning} {colors['GREEN']}Output file already exists ('{shortened_path(filename)}'){colors['NC']}")
            ask_text = f"{sb_v2} {colors['GREEN']}Do you want to replace the file? {colors['RED']}[Y]es/[N]o{colors['NC']}: "           
            replace_file = ask_to(ask_text)
            if not replace_file:
                p.failure(f"{colors['RED']}Not replacing file. Exiting...{colors['NC']}")
                sys.exit(1)
            if replace_file:
                print(f"{sb} {colors['GREEN']}Saving file as '{shortened_path(filename)}' with '{args.data_outfile_format}' data format...{colors['NC']}")
                data.write(filename, format=args.data_outfile_format, overwrite=True)
                p.success(f"{colors['L_GREEN']}Data saved{colors['NC']}")
                return
    data.write(filename, format=args.data_outfile_format, overwrite=True)
    p.success(f"{colors['GREEN']}Data saved{colors['NC']}")


@dataclass(kw_only=True)
class ellipseVPDCenter():
    pmra: float
    pmdec: float


def get_pmra_pmdec_for_VPD(args, obj_name, original_data:Table | None = None, useMedian=False, fill=False)->(ellipseVPDCenter, str):
    """
    Gets the pmra and pmdec components depending if the user has provided or not them explicitly as flags.
    If they have not been explicitly been given as flags, the program will try to get them depending if they
    are identified as Globular Cluser or Open Cluster. If the objects is a "Custom" object, then the parameters
    pmra and pmdec must be explicitly be given by the user. Otherwise quits the program
    """
    if args.pmra is None or args.pmdec is None:   
        print(f"{sb} {colors['PURPLE']}No PMRA and/or PMDEC provided. Attempting to get these parameters based on object name in Archive...{colors['NC']}")
        # Manually add the object_name found to 'args' variable
        setattr(args, 'name', obj_name)
        setattr(args, 'skip_extra_data', False)
        # Get coordiantes of the object in degrees
        object_info =  get_RA_and_DEC(args, fill=fill)
        # If the object is not found then it will return the "default" values. Check if those values match
        # If they do, it means that the user has not provided arguments for '--pmra' or '--pmdec'
        # and the user will have to explicitly provide them since the program could not get them automatically
        if object_info.pmra == 0.0 and object_info.pmdec == 0.0 and object_info.identifiedAs == "Other":
            print(f"{warning} {colors['RED']}Since you do not explicitly provided PMRA ('--pmra') and PMDEC ('--pmdec') parameters,\n    the program tried to automatically find them.{colors['NC']}")
            print(f"{colors['RED']}    However, the program could not find any parameters for your object '{obj_name}' in Archive.{colors['NC']}")
            print(f"{colors['RED']}    You will have to re-run the program providing '--pmra' and '--pmdec' parameters.{colors['NC']}")
            sys.exit(1)
        if object_info.identifiedAs == "GlobularCluster":
            print(f"{sb} {colors['BLUE']}Object found in Archives. Using values from: {colors['PURPLE']}Vasiliev & Baumgardt (2021, MNRAS, 505, 5978V){colors['NC']}")
        if object_info.identifiedAs == "OpenCluster":
            print(f"{sb} {colors['BLUE']}Object found in Archives. Using values from: {colors['PURPLE']}Cantat-Gaudin et al. (2020, A&A, 640, A1){colors['NC']}")
        print(f"    {sb_v2} pmra:  {colors['CYAN']}{object_info.pmra} (mas/yr){colors['NC']}")
        print(f"    {sb_v2} pmdec: {colors['CYAN']}{object_info.pmdec} (mas/yr){colors['NC']}")
        pmra, pmdec = object_info.pmra, object_info.pmdec
        identified = object_info.identifiedAs
    else:
        if not useMedian:
            print(f"    {sb_v2} pmra:  {colors['CYAN']}{args.pmra} (mas/yr){colors['NC']}")
            print(f"    {sb_v2} pmdec: {colors['CYAN']}{args.pmdec} (mas/yr){colors['NC']}")
            pmra, pmdec = args.pmra, args.pmdec
        else:
            print(f"{sb} {colors['BLUE']}Using median values obtained from data for 'pmra' and 'pmdec'{colors['NC']}")
            pmra, pmdec = round(np.median(original_data['pmra']),3), round(np.median(original_data['pmdec']),3)
            print(f"    {sb_v2} pmra:  {colors['CYAN']}{pmra} (mas/yr){colors['NC']}")
            print(f"    {sb_v2} pmdec:  {colors['CYAN']}{pmdec} (mas/yr){colors['NC']}")
        identified = "Other"
    ellipseCenter = ellipseVPDCenter(pmra=pmra, pmdec=pmdec)
    return ellipseCenter, identified


def check_width_and_height_provided_for_ellipse(args, max_allowed: int =2)->None:
    """
    Checks if arguments provided for "width" and "height" for the ellipse
    are exactly equal to 2. If not, tell the user this problem and an example of how to use this.
    Also checks if the user has provided exactly 2 arguments for each parameter, and sorts them;
    so the first item is the minimum and the second is the maximum
    """
    if len(args.width) != max_allowed:
        print(f"{warning} {colors['RED']}You have provided an invalid number of parameters for ellipse width ('--width').{colors['NC']}")
        print(f"{colors['RED']}    Maximum allowed number of parameters are {max_allowed}. However, you have provided {len(args.width)} params{colors['NC']}")
        print(f"{colors['PURPLE']}    Example usage: --width 5.5 10.5{colors['NC']}")
        sys.exit(1)
    if len(args.height) != max_allowed:
        print(f"{warning} {colors['RED']}You have provided an invalid number of parameters for ellipse heigth ('--heigth').{colors['NC']}")
        print(f"{colors['RED']}    Maximum allowed number of parameters are {max_allowed}. However, you have provided {len(args.width)} params{colors['NC']}")
        print(f"{colors['PURPLE']}    Example usage: --heigth 5.5 10.5{colors['NC']}")
        sys.exit(1)
    if len(args.inclination) != max_allowed:
        print(f"{warning} {colors['RED']}You have provided an invalid number of parameters for ellipse inclination ('--inclination').{colors['NC']}")
        print(f"{colors['RED']}    Maximum allowed number of parameters are {max_allowed}. However, you have provided {len(args.width)} params{colors['NC']}")
        print(f"{colors['PURPLE']}    Example usage: --inclination -89.9 89.9{colors['NC']}")
        sys.exit(1)
    # Also check that the parameters are positive numbers
    # or inclination is a valid number, between -90 and 90
    for width in args.width:
        if width <= 0:
            print(f"{warning} {colors['RED']}Widths provided must be positive{colors['NC']}")
            print(f"{colors['RED']}    Invalid value: {width}{colors['NC']}")
            sys.exit(1)
    for height in args.height:
        if height <= 0:
            print(f"{warning} {colors['RED']}Heights provided must be positive{colors['NC']}")
            print(f"{colors['RED']}    Invalid value: {height}{colors['NC']}")
            sys.exit(1)
    for inclination in args.inclination:
        if not (-90.0 <= inclination <= 90.0):
            print(f"{warning} {colors['RED']}Inlination must have a value between -90.0 and +90 (degrees){colors['NC']}")
            print(f"{colors['RED']}    Invalid value: {inclination}{colors['NC']}")
            sys.exit(1)
    # Finally, order the lists
    args.width.sort()
    args.height.sort()
    args.inclination.sort()
    return None


@dataclass(order=True, kw_only=True)
class EllipseClass():
    """
    A class parameters of an ellipse (adapted to purposes of this code)
    """
    center_x: float # x-axis center coordinate
    center_y: float # y-axis center coordinate
    width: float # in mas / yr
    height: float # in mas / yr
    inclination: float # angle inclination in degrees


@dataclass(frozen=True, order=True, kw_only=True)
class IteratorClass():
    """
    A class used to change iterators cycles/parameters
    """
    minimum: float
    maximum: float
    n_step: int


def create_IteratorClass_objects_for_ellipse(args):
    # Get the values for ellipse width
    width_min, width_max, width_nsteps = np.min(args.width), np.max(args.width), args.n_divisions_in_width
    width_it = IteratorClass(minimum=width_min, maximum=width_max, n_step=width_nsteps) 
    # Get the values for ellipse height
    height_min, height_max, height_nsteps = np.min(args.height), np.max(args.height), args.n_divisions_in_height
    height_it = IteratorClass(minimum=height_min, maximum=height_max, n_step=height_nsteps)
    # Get angle inclination for ellipse
    incl_min, incl_max, incl_nsteps = np.min(args.inclination), np.max(args.inclination), args.n_divisions_in_inclination
    incl_it = IteratorClass(minimum=incl_min, maximum=incl_max, n_step=incl_nsteps)
    return width_it, height_it, incl_it


def check_if_max_value(value: int, current_max: int):
    """
    Simple function that checks if a value is bigger than a current one.
    If the value is greater than the current maximum, it returns the value.
    Otherwise it returns the maximum.
    """
    if value > current_max:
        return value, True
    return current_max, False


def DefineEllipse(x: np.ndarray, y: np.ndarray, x_center: float, y_center: float, 
                  ell_width: float, ell_height: float, angle_inclination: float) -> np.ndarray:
    """
    Create an ellipse with center given with coordinates (x_center, y_center).
    Also, a width and height (x and y-axis, respectively) must be passed, given
    an 'incilnation' angle.
    """
    
    cos_angle = np.cos(np.radians(180.-angle_inclination))
    sin_angle = np.sin(np.radians(180.-angle_inclination))

    xc = x - x_center
    yc = y - y_center

    xct = xc * cos_angle - yc * sin_angle
    yct = xc * sin_angle + yc * cos_angle 

    rad_cc = (xct**2/(ell_width/2.)**2) + (yct**2/(ell_height/2.)**2)
    return rad_cc


def loop_Montecarlo(x: np.ndarray, y: np.ndarray,
                    w_array: np.ndarray, h_array: np.ndarray, a_array: np.ndarray,
                    pmra_center:float, pmdec_center:float, p) -> EllipseClass:
    max_in_stars = 0
    total_length = len(w_array)*len(h_array)
    p.status(f"{colors['GREEN']}Creating different ellipses and counting objects inside them ({colors['PURPLE']}{print_percentage(total_length, 0.0)}{colors['GREEN']}){colors['NC']}")
    ellipse_parameters = EllipseClass(center_x=0., center_y=0, width=0., height=0., inclination=0.)
    counter_progress = 0
    with tqdm(total=total_length, desc=f"{sb} {colors['BLUE']}Playing with ellipses{colors['NC']}", leave=False) as pbar:
        for w_it in w_array:
            for h_it in h_array:
                for angle_it in a_array:
                    if w_it == h_it:
                        continue # due to tidal forces, object in VPD will have an elliptic form
                                 # also, applying an inclination to a circle is not very useful...
                    counter_in, counter_out = 0, 0
                    ellipse_zone = DefineEllipse(x, y, pmra_center, pmdec_center, w_it, h_it, angle_it)
                    for r in ellipse_zone:
                        if r <= 1:
                            counter_in += 1
                        if r > 1:
                            counter_out += 1
                    max_in_stars, new_max_found = check_if_max_value(counter_in, max_in_stars)
                    if new_max_found:
                        ellipse_parameters = EllipseClass(center_x=pmra_center, center_y=pmdec_center, width=w_it,
                                                         height=h_it, inclination=angle_it)
                counter_progress+=1
                p.status(f"{colors['GREEN']}Creating different ellipses and counting objects inside them ({colors['PURPLE']}{print_percentage(total_length, counter_progress)}{colors['GREEN']}){colors['NC']}")
                pbar.update(1)
    p.success(f"{colors['PURPLE']}Optimal ellipse extracted{colors['NC']}")
    return ellipse_parameters


def count_stars_inside_ellipse(pmra_center: float , pmdec_center: float, original_data: Table, 
                            width_iterator, height_iterator, angle_iterator, p
                            ) -> EllipseClass:
    """
    A simple function that count stars inside an ellipse. It will return an Ellipse
    object with parameters that maximizes the numbers of stars/objects within an
    ellipse in a Vector Point Diagram; where the ellipse center will be given by
    parameters given in Vasiliev & Baumgardt (2021) or Cantat-Gaudin (2020) files 
    (if available).
    """
    # Create a copy of the arrays containing positions (x,y) in VPD
    x, y = np.asarray(original_data['pmra']), np.asarray(original_data['pmdec'])
        
    width_range = np.linspace(width_iterator.minimum, width_iterator.maximum, width_iterator.n_step)
    height_range = np.linspace(height_iterator.minimum, height_iterator.maximum, height_iterator.n_step)
    angle_range = np.linspace(angle_iterator.minimum, angle_iterator.maximum, angle_iterator.n_step)

    optimal_ellipse = loop_Montecarlo(x, y, width_range, height_range,
                                     angle_range, pmra_center, pmdec_center, p)
    return optimal_ellipse


def print_found_ellipse_attributes(ellipse: EllipseClass, ntimes=50)->None:
    nc = colors['NC']
    c1= randomColor()
    c2= randomColor()
    c3 = randomColor()
    print()
    print(f"{c3}{'='*ntimes}{nc}")
    print(f"    {c1}\"Optimized\" ellipse parameters:{nc}")
    print(f"    {c2}-> {c1}Center coordinates in VPD: ({ellipse.center_x:.2f}, {ellipse.center_y:.2f}){nc}")
    print(f"    {c2}-> {c1}Width: {ellipse.width:.2f} mas / yr{nc}")
    print(f"    {c2}-> {c1}Height: {ellipse.height:.2f} mas / yr{nc}")
    print(f"    {c2}-> {c1}Angle inclination: {ellipse.inclination:.2f} deg{nc}")
    print(f"{c3}{'='*ntimes}{nc}")
    print()
    return 


def check_if_data_lies_inside_ellipse(original_data: Table, ell: EllipseClass):
    """
    Given a data with parameters/coordinates (x,y), if the data is inside the ellipse 
    (ell) we keep it. Else, it is discarded. This function returns a boolean list 
    that will be used to mask data and a list with colors to plot.
    """
    x, y = np.asarray(original_data['pmra']), np.asarray(original_data['pmdec'])
    rad_cc = DefineEllipse(x, y, ell.center_x, ell.center_y, ell.width, 
                           ell.height, ell.inclination)

    mask_array, color_array = [], []
    for r in rad_cc:
        if r <= 1:
            mask_array.append(True)
            color_array.append('green') # Color to plot points inside ellipse
        if r > 1:
            mask_array.append(False)
            color_array.append('cyan') # Color to plot points outside ellipse
    
    if (len(x) != len(mask_array)) or (len(y) != len(mask_array)):
        print(f"{warning}{colors['RED']}Ellipse mask length does not math the original data length{colors['NC']}")
        sys.exit(1)
    mask_array = np.asarray(mask_array)
    return mask_array, color_array


def filter_data_by_mask(original_data: Table, mask_list):
    """
    Applies a mask to a Gaia Table
    """
    # Create a copy, so we avoid to touch the original data by error
    copy_original_data = copy.deepcopy(original_data)
    # Filter data
    filtered_data = copy_original_data[mask_list]
    return filtered_data
    

def plot_ellipse_in_VPD(args, obj_name: str, original_data: Table, ellipse: EllipseClass,
                        pmra_center: float, pmdec_center: float, colors_array):
    # Set the limits to plot
    x_limit = [pmra_center-5, pmra_center+5]
    y_limit = [pmdec_center-5, pmdec_center+5]
    # Create the plot
    fig, ax = plt.subplots(1)
    ax.set_aspect('equal')
    label_fontsize = 35
    ax.set_xlim(x_limit[0], x_limit[1])
    ax.set_ylim(y_limit[0], y_limit[1])
    plt.rcParams["figure.figsize"] = (28,21)
    matplotlib.rc('xtick', labelsize=32) 
    matplotlib.rc('ytick', labelsize=32)
    label_fontsize = 35
    ax.set_xlim(x_limit[0], x_limit[1])
    ax.set_ylim(y_limit[0], y_limit[1])
    plt.rcParams["figure.figsize"] = (28,21)
    matplotlib.rc('xtick', labelsize=32) 
    matplotlib.rc('ytick', labelsize=32)
    plt.rcParams["figure.figsize"] = (28,21)
    ellipse_center = (ellipse.center_x, ellipse.center_y)
    g_ellipse = patches.Ellipse(ellipse_center, ellipse.width, ellipse.height, 
                                angle=ellipse.inclination, fill=False, 
                                edgecolor='green', linewidth=0.3)
    ax.add_patch(g_ellipse)
    ax.scatter(original_data['pmra'], original_data['pmdec'], c=colors_array, linewidths=0.3, s=1.)
    ax.plot(pmra_center, pmdec_center, 'ro', markersize = 5, 
            label = 'Reference')
    anchored_text = AnchoredText(r'$r_{\mu_\alpha}$ = '+str(round(ellipse.width,2))+'\n'
                                 +r'$r_{\mu_\delta}$ = '+str(round(ellipse.height,2))+'\n'
                                 +r'$\theta $ ='+str(round(ellipse.inclination,2))
                                 +r'$^{\circ}$'
                                 +'\nC = ('+str(round(pmra_center,2))+', ' +str(round(pmdec_center,2))+')', 
                                 loc='lower left', frameon=False,
                                 prop=dict(size=38))
    ax.add_artist(anchored_text)
    ax.grid(color='gray', linestyle='--', alpha=0.5, linewidth=2)
    ax.set(xlabel=r'$\mu_{\alpha} \ \cos \delta$ ($mas \cdot yr^{-1}$)', 
           ylabel="$\mu_{\delta}$ ($mas \cdot yr^{-1}$)")
    ax.xaxis.label.set_size(label_fontsize)
    ax.yaxis.label.set_size(label_fontsize)
    ax.tick_params(which='both', width=4.5, top='on')
    ticksize = 14
    ax.tick_params(which='major',length=ticksize, direction = 'in')
    ax.tick_params(which='minor',length=ticksize/2., direction = 'in')
    ax.yaxis.set_ticks_position('both')
    plt.minorticks_on()
    plt.title(obj_name.upper(), fontsize=35)
    plt.show()
    plt.close()


def set_new_values_for_ellipse_parameters(args, var_name: str, max_attempts=10):
    """
    If the user is not happy with the result, he/she can run the program again providing new parameters for
    width, height and inclination recycling some variables previousle used; so it is no necessary to fully
    re-run the program
    """
    ask_text = f"{sb} {colors['GREEN']} Do you want to Keep values or Change values for '{colors['RED']}{var_name}{colors['GREEN']}'?{colors['NC']}"
    ask_text = f"{ask_text}\n    {colors['CYAN']}(C)hange value/(K)eep value: {colors['NC']}"
    # Regular expression patterns
    change_pattern = re.compile(r"^(c|ch|cha|chan|chang|change)$", re.IGNORECASE)
    keep_pattern = re.compile(r"^(k|ke|kee|keep)$", re.IGNORECASE)
    # Initalize attempts
    attempts = 0

    while attempts < max_attempts:
        response = input(ask_text)
    
        if change_pattern.match(response):
            wantToChange = True
            break
        elif keep_pattern.match(response):
            wantToChange = False
            break
        else:
            print(f"{warning} {colors['YELLOW']}Invalid option. Please enter '[{colors['L_RED']}C{colors['YELLOW']}]hange' or '[{colors['L_RED']}K{colors['YELLOW']}]eep'{colors['NC']}")
            print(f"    Remaining attempts: {max_attempts - attempts}")
            attempts += 1
        if attempts > max_attempts:
            print(f"{warning} {colors['L_RED']}You have reached the maximum number of attempts. Exiting...{colors['NC']}")
            sys.exit(1)
    if wantToChange:
        # Ask for minimum and maximum values
        if var_name == 'width':
            old_value_1 = args.width[0]
            old_value_2 = args.width[1]
            n_step_value = args.n_divisions_in_width
            n_step_label = 'n_divisions_in_width'
        elif var_name == 'height':
            old_value_1 = args.height[0]
            old_value_2 = args.height[1]
            n_step_value = args.n_divisions_in_height
            n_step_label = 'n_divisions_in_height'
        elif var_name == 'inclination':
            old_value_1 = args.inclination[0]
            old_value_2 = args.inclination[1]
            n_step_value = args.n_divisions_in_inclination
            n_step_label = 'n_divisions_in_inclination'
        updated_value1 = float(input(f"    -> First new value for '{var_name}' parameter (old value '{old_value_1}'): "))
        updated_value2 = float(input(f"    -> Second new value for '{var_name}' parameter (old value '{old_value_2}'): "))
        value_list = [updated_value1, updated_value2]
        value_list.sort()
        # Ask for n step updated
        updated_n_step= int(input(f"    -> New value for N steps parameter (old value '{n_step_value}'): "))
        # Update the values
        setattr(args, var_name, value_list)
        setattr(args, n_step_label, updated_n_step)
        print(f"{sb} {colors['GREEN']}Updated values for '{colors['PURPLE']}{var_name}{colors['GREEN']}' parameter")
    else:
        return


def filter_data_with_parameter(data, parameter, p, min_value=None, max_value=None):
    # Filter by parameter between 2 values
    if min_value is not None and max_value is not None:
        try:
            # First filter by min value
            mask_filter =  min_value <= data[parameter]
            data = data[mask_filter]
            # Then filter by max value
            mask_filter = data[parameter] <= max_value
            data = data[mask_filter]
            return data
        except KeyError:
            print(f"{warning} {colors['RED']}You have provided an invalid parameter that could not be found in Gaia data: '{parameter}' {colors['NC']}")
            print(f"    {colors['PURPLE']}Check columns with '{colors['BLUE']}{sys.argv[0]} show-gaia-content{colors['PURPLE']}' command to see available and valid parameters{colors['NC']}")
            p.failure(f"{colors['RED']}Data could not be retrieved{colors['NC']}")
            sys.exit(1)
    elif min_value is not None:
        try:
            mask_filter =  min_value <= data[parameter]
            data = data[mask_filter]
            return data
        except KeyError:
            print(f"{warning} {colors['RED']}You have provided an invalid parameter that could not be found in Gaia data: '{parameter}' {colors['NC']}")
            print(f"    {colors['PURPLE']}Check columns with '{colors['BLUE']}{sys.argv[0]} show-gaia-content{colors['PURPLE']}' command to see available and valid parameters{colors['NC']}")
            p.failure(f"{colors['RED']}Data could not be retrieved{colors['NC']}")
            sys.exit(1)
    elif max_value is not None:
        try:
            mask_filter =  data[parameter] <= max_value
            data = data[mask_filter]
            return data
        except KeyError:
            print(f"{warning} {colors['RED']}You have provided an invalid parameter that could not be found in Gaia data: '{parameter}' {colors['NC']}")
            print(f"    {colors['PURPLE']}Check columns with '{colors['BLUE']}{sys.argv[0]} show-gaia-content{colors['PURPLE']}' command to see available and valid parameters{colors['NC']}")
            p.failure(f"{colors['RED']}Data could not be retrieved{colors['NC']}")
            sys.exit(1)
    else:
        print(f"{warning} {colors['RED']}No filters were applied{colors['NC']}")
        return data
  

def apply_filter_to_data_with_parameters(args, data):
    original_data_length = len(data)
    p = log.progress(f"{colors['L_GREEN']}Filtering data{colors['NC']}")
    # Make a deepcopy, so we do not modify the original data
    copy_original_data = copy.deepcopy(data)
    if not args.no_filter_ruwe:
        p.status(f"{colors['GREEN']}Filtering data by RUWE (smaller than {args.filter_by_ruwe})...{colors['NC']}")
        copy_original_data = filter_data_with_parameter(copy_original_data, 'ruwe', p, max_value=args.filter_by_ruwe)
    if not args.no_filter_pm_error:
        p.status(f"{colors['GREEN']}Filtering data by Proper Motion errors (smaller than {args.filter_by_pm_error} mas/yr)...{colors['NC']}")
        copy_original_data = filter_data_with_parameter(copy_original_data, 'pmra_error', p, max_value=args.filter_by_pm_error)
        copy_original_data = filter_data_with_parameter(copy_original_data, 'pmdec_error', p, max_value=args.filter_by_pm_error)
    if not args.no_filter_g_rp:
        p.status(f"{colors['GREEN']}Filtering data by G_RP magnitude ({args.filter_by_g_rp_min} < G_RP/mag < {args.filter_by_g_rp_max})...{colors['NC']}")
        copy_original_data = filter_data_with_parameter(copy_original_data, 'phot_rp_mean_mag', p, 
                                                        max_value=args.filter_by_g_rp_max, 
                                                        min_value=args.filter_by_g_rp_min)
    p.success("Data fully filtered")
    return copy_original_data


def get_data_from_file_or_query(args, subcommand, subsubcommand, showBanner=True):
    """
    Check if the user has provided a filename containing data. If not, the data is provided querying data to Gaia Archive
    """
    # Display a banner
    if showBanner:
        displaySections(f'extract -- {subcommand} -- {subsubcommand}', randomColor(), randomChar())
    # Check if the user has provided a filename or not
    isFileProvided = check_if_filename_flag_was_provided(args)
    # If it was provided, use it to read data
    if isFileProvided:
        # Check if the filename the user provided exists
        check_if_read_file_exists(args.file)
        p = log.progress(f"{colors['L_GREEN']}Data{colors['NC']}")
        p.status(f"{colors['PURPLE']}Reading data file '{shortened_path(args.file)}'...{colors['NC']}")
        try:
            original_data = Table.read(args.file, format=args.file_format)   
        except Exception as e:
            print(f"{warning} {colors['RED']}Unable to read '{args.file}' file with format '{args.file_format}'{colors['NC']}")
            print(f"Exception details: {e}")
            p.failure(f"{colors['RED']}Could not retrieve data from file{colors['NC']}")
            sys.exit(1)
        p.success(f"{colors['GREEN']}Succesfully obtained data from file{colors['NC']}")
        return original_data, None
    else:
        checkNameObjectProvidedByUser(args.name)
        original_data, object_info = extractRawData(args, 'filter', 'cone', enableSave=False, showBanner=False)
        return original_data, object_info


def check_if_read_file_exists(filename)->None:
    """
    Check if the file containing data provided by the user exists
    """
    read_file_path = Path(filename)
    if not read_file_path.exists():
        print(f"{warning} {colors['RED']}The filename you provided ('{colors['PURPLE']}{filename}{colors['RED']}') does not exist. Maybe you mispelled it?{colors['NC']}")
        sys.exit(1)
    return


# Start classes to create bins and store data into them
@dataclass(kw_only=True)
class euclidianPoint():
    x: float
    y: float
    

@dataclass(kw_only=True)
class singlePoint():
    ID: int
    median_value: float
    std_value: float
    mag_median: float
    mag_std : float
    m: float = 0.
    c: float = 0.
    
    
@dataclass(kw_only=True)
class pointsToInterpolate():
    points: list[singlePoint] = field(default_factory=list)


@dataclass
class parameterList:
    G_BP: list[float] = field(default_factory=list)
    G_RP: list[float] = field(default_factory=list)
    G: list[float] = field(default_factory=list)
    as_gof_al: list[float] = field(default_factory=list)
    parallax: list[float] = field(default_factory=list)
    mu_R: list[float] = field(default_factory=list)
        
    
@dataclass(kw_only=True)
class Bin:
    ID: int = 0
    params: parameterList = field(default_factory=list)
    minVal_mag: float 
    maxVal_mag: float
        
    def __post_init__(self):
        self.median_G_RP = np.median(self.params.G_RP)
        self.median_G_BP = np.median(self.params.G_BP)
        self.median_G = np.median(self.params.G)
        self.median_as_gof_al = np.median(self.params.as_gof_al)
        self.median_parallax = np.median(self.params.parallax)
        self.median_mu_R = np.median(self.params.mu_R)
        self.std_dev_G_RP = np.std(self.params.G_RP, ddof=1)
        self.std_dev_G_BP = np.std(self.params.G_BP, ddof=1)
        self.std_dev_G = np.std(self.params.G, ddof=1)
        self.std_dev_as_gof_al = np.std(self.params.as_gof_al, ddof=1)
        self.std_dev_parallax = np.std(self.params.parallax, ddof=1)
        self.std_dev_mu_R = np.std(self.params.mu_R, ddof=1)
        

@dataclass(kw_only=True)
class TotalBins:
    bins: list[Bin] = field(default_factory=list)


def get_important_parameters(original_data: Table, ellipse_center: ellipseVPDCenter)->parameterList:
    """
    Extract only important parameters that will be used later for Cordoni et al. (2018, 2020) algorithm
    """
    importantParameters = parameterList()
    # Collect data parameters inside a list
    for data_it in original_data:
        importantParameters.G_RP.append(data_it["phot_rp_mean_mag"])
        importantParameters.G_BP.append(data_it["phot_bp_mean_mag"])
        importantParameters.G.append(data_it["phot_g_mean_mag"])
        importantParameters.as_gof_al.append(data_it["astrometric_gof_al"])
        importantParameters.parallax.append(data_it["parallax"])
        importantParameters.mu_R.append(estimate_mu_sub_R(PM_alpha=data_it['pmra'],
                                                          PM_delta=data_it['pmdec'],
                                                          previous_PM_alpha_median=ellipse_center.pmra,
                                                          previous_PM_delta_median=ellipse_center.pmdec))   
    # Check if lists have the same size
    list_of_lists = [importantParameters.G_BP, importantParameters.G_RP, importantParameters.G,
                     importantParameters.as_gof_al, importantParameters.parallax,
                     importantParameters.mu_R, original_data]
    if all(len(list_of_lists[0]) == len(l) for l in list_of_lists[1:]):
        pass
    else:
        print("Some of the parameters list does not have the same size as the other")
        for index, lista in enumerate(list_of_lists):
            print(f"list {index+1} with size {len(lista)}")
            sys.exit(1)
        
    return importantParameters 
     

def which_parameter(parameters_in_list: parameterList,paramName: str):
    """
    Check which parameter will be used in the current process,
    and if it is valid
    """
    if paramName == "astrometric_gof_al" or paramName == "as_gof_al":
        return parameters_in_list.as_gof_al
    if paramName == "phot_rp_mean_mag" or paramName == "G_RP":
        return parameters_in_list.G_RP
    if paramName == "phot_bp_mean_mag" or paramName == "G_BP":
        return parameters_in_list.G_BP
    if paramName == "phot_g_mean_mag" or paramName == "G":
        return parameters_in_list.G
    if paramName == "parallax":
        return parameters_in_list.parallax
    if paramName == "mu_R" or paramName == "muR":
        return parameters_in_list.mu_R
    sys.exit("No valid parameter was returned")


def estimate_mu_sub_R(PM_alpha: float,
                   PM_delta: float,
                   previous_PM_alpha_median: float,
                   previous_PM_delta_median: float
                   ) -> float:
    """
    Estimates mu_R, which is basically the distance to the cluster center in the VPD space
    """
    return np.sqrt( np.power(PM_alpha - previous_PM_alpha_median, 2) + 
                    np.power(PM_delta - previous_PM_delta_median, 2) )


def check_min_and_max_values(minValue: float, maxValue: float, useCustomLimits: bool,
                             lower_mag: float, upper_mag: float,
                             default_lower_mag: float =10.5, default_upper_mag: float =19.5)->(float, float):
    """
    As suggested by Cordoni et al. (2018, 2020), values for Gaia magnitudes
    should have an upper and lower limit. If the min/max value is
    lower/bigger than these values, then simply "cut" min/max values
    in those limits.
    """
    if useCustomLimits: # if the user wants to use custom values for upper and lower limits...
        Cordoni_lower_mag = lower_mag
        Cordoni_upper_mag = upper_mag
        
        
    if not useCustomLimits: # if not, check if they surpass acceptables values. 
                            # If they do, replace them...
         Cordoni_lower_mag = default_lower_mag
         Cordoni_upper_mag = default_upper_mag
    
    if maxValue > Cordoni_lower_mag:
        maxValue = Cordoni_upper_mag
    if minValue < Cordoni_lower_mag:
        minValue = Cordoni_lower_mag
    
    return minValue, maxValue


def get_bin_size(args, values: list[float], numberOfDivisions: int) -> (float, float, float):
    """
    Obtains the maximum and minimum value of a list and returns the difference value
    between each number that results dividing the max - min divided into N parts,
    i.e., bin size. 
    Returns the minimum, maximum and size of each bin after dividing this interval
    into N parts.
    """
    assert (numberOfDivisions != 0), "You cannot divide by zero. You are attempting to create 0 bins."
    assert (numberOfDivisions != 1),  "Dividing data into 1 bin just does not make sense..."
    
    maxValue: float = np.amax(values)
    minValue: float = np.amin(values)
    
    minValue, maxValue = check_min_and_max_values(minValue, maxValue, args.set_limits, 
                                                  args.mag_lower_limit, args.mag_upper_limit)
    return maxValue, minValue, (maxValue - minValue)/ (1.0*numberOfDivisions)


def get_mag_filter_name(filter_name: str) -> str | None:
    mag_filter: str = filter_name.replace('_','').lower()
    if mag_filter == 'grp':
        return "G_RP"
    elif mag_filter == 'gbp':
        return "G_BP"
    elif mag_filter == 'g':
        return "G"
    else:
        print(f"{warning} {colors['RED']}You have provided an invalid Gaia filter: '{filter_name}'{colors['NC']}")
        print(f"{colors['RED']}    Valid filters are: 'g_rp', 'g_bp' or 'g' (in capital letters are also valid).\n    Please retry{colors['NC']}")
        sys.exit(1)


def print_values_bins(maxValue: float, minValue: float, nBins: int,
                      binValue: float, totalBins: TotalBins, mag_filter_name: str,
                      print_more_details: bool = True) -> None:
    """
    A simple print statement to check values obtained from
    getBinSize function.
    """
    # Pick a random color to print later
    rand_number = random.randint(31,36) 
    c = f'\033[1;{rand_number}m' # color
    sh = f'\033[{rand_number}m' # shadow
    nc = colors['NC'] # no color / reset color
    filter_name = get_mag_filter_name(mag_filter_name)

    if print_more_details:
        print()
        len_marker: int = 90
        print(len_marker*"=")
        text: str = "Estimated values are: "
        for j in range(1, 5):
            if j == 1:
                print(f"{text}{j}) Max Value {filter_name} (mag): {maxValue:.3f} {colors['GRAY']}# Maximum value for G_RP magnitude{colors['NC']}")
            if j != 1:
                print(len(text)*" " + f"{j}) ", end='')
                if j == 2:
                    print(f"Min Value {filter_name} (mag): {minValue:.3f} {colors['GRAY']}# Minimum value for {filter_name} magnitude{colors['NC']}")
                if j == 3:
                    print(f"Number of req. Bins: {nBins} {colors['GRAY']}# Number of requested Bins{colors['NC']}")
                if j == 4:
                    print(f"Bin length {filter_name} (mag): {binValue:.3f} {colors['GRAY']}# Value of size/range for every bin{colors['NC']}")
        print(len_marker*"=", end="\n")

    # Create a table that will store data to print
    table_data_list = []

    for data in totalBins.bins:
        if filter_name == "G_RP":
            data_median_mag: float = data.median_G_RP
            data_median_mag_stddev: float = data.std_dev_G_RP
            len_data_mag = len(data.params.G_RP)
        elif filter_name == "G_BP":
            data_median_mag: float = data.median_G_BP
            data_median_mag_stddev: float = data.std_dev_G_BP
            len_data_mag = len(data.params.G_BP)
        elif filter_name == "G":
            data_median_mag: float = data.median_G
            data_median_mag_stddev: float = data.std_dev_G
            len_data_mag = len(data.params.G)
        else:
            print(f"{warning}{colors['RED']}Invalid filter name: {filter_name}. Exiting...{colors['NC']}")
            sys.exit(1)
        temp_list = []
        temp_list.append(f"{sh}{data.ID}{nc}")
        temp_list.append(f"{sh}[{data.minVal_mag:.2f}, {data.maxVal_mag:.2f}]{nc}")
        temp_list.append(f"{sh}{len_data_mag}{nc}")
        temp_list.append(f"{sh}{data_median_mag:.2f} ± {data_median_mag_stddev:.2f}{nc}")
        temp_list.append(f"{sh}{data.median_as_gof_al:.2f} ± {data.std_dev_as_gof_al:.2f}{nc}")
        temp_list.append(f"{sh}{data.median_mu_R:.2f} ± {data.std_dev_mu_R:.2f}{nc}")
        temp_list.append(f"{sh}{data.median_parallax:.2f} ± {data.std_dev_parallax:.2f}{nc}")
        table_data_list.append(temp_list)
    print()

    # Print the table with 'tabulate' library
    headers_list = [f"{c}Bin{nc}", f"{c}Range {filter_name} (mag){nc}", f"{c}N{nc}", f"{c}<{filter_name}> (mag){nc}", 
                     f"{c}<as_gof_al>{nc}", f"{c}<μ_R> (mas/yr){nc}", f"{c}<π> (mas){nc}"]
    print(tabulate(table_data_list, headers=headers_list, tablefmt='grid'))
    return None


def check_if_total_bins_has_at_least_2_elems_or_more(totalBins: TotalBins, filter_name: str, nDivisions: int,
                                                     minimum_per_bin: int = 2) -> bool:
    """
    Counts the number of elements inside every bin, which should be equal or bigger than 2
    """
    for index, bin_it in enumerate(totalBins.bins):
        if filter_name == "G_RP":
            params_data_median_mag: float = bin_it.params.G_RP
        elif filter_name == "G_BP":
            params_data_median_mag: float = bin_it.params.G_BP
        elif filter_name == "G":
            params_data_median_mag: float = bin_it.params.G
        else:
            print(f"{warning}{colors['RED']}Invalid filter name: {filter_name}. Exiting...{colors['NC']}")
            sys.exit(1)
        # Check the length of 2 parameters
        if len(bin_it.params.as_gof_al) < minimum_per_bin:
            print(f"{warning}{colors['RED']} Bin #{index+1} has {len(bin_it.params.as_gof_al)} elements{colors['NC']}")
            print(f"    {colors['RED']}At least 2 elements are required per bin")
            return False
        if len(params_data_median_mag) < minimum_per_bin:
            print(f"{warning}{colors['RED']} Bin #{index+1} has {len(params_data_median_mag)} elements{colors['NC']}")
            print(f"    {colors['RED']}At least 2 elements are required per bin")
            return False
    return True


def select_gaia_filter_key_param(filter_name: str)-> str | None:
    if filter_name == 'G_RP':
        return 'phot_rp_mean_mag'
    elif filter_name == 'G_BP':
        return 'phot_bp_mean_mag'
    elif filter_name == 'G':
        return 'phot_g_mean_mag'
    else:
        print(f"{warning}{colors['RED']}You have provided an invalid Gaia filter name ('{filter_name}'). Exiting...{colors['NC']}")
        sys.exit(1)
    

def create_bins(args, astrodata: Table, nDivision: int, ellipse_center: ellipseVPDCenter, p, 
               ) -> (TotalBins, float, float, float):
    """
    Data will be splitted into nDivision bins. This functions creates
    those bins.
    """
    # Select magnitude column
    mag_filter_name = get_mag_filter_name(args.set_mag_filter)
    key_gaia_table = select_gaia_filter_key_param(mag_filter_name)
    # Make a deepcopy, so if this data is modified the orginal data is not
    mag_gaia_data = copy.deepcopy(astrodata[key_gaia_table])
    # Estimate bin sizes
    maxVal, minVal, binVal = get_bin_size(args, mag_gaia_data, nDivision)
    totBins = TotalBins()
    
    # mu_R uses median for pmra and pmdec, so use them
    previous_median_PM_RA = ellipse_center.pmra
    previous_median_PM_DEC = ellipse_center.pmdec

    
    
    # Add data for every bin
    for j in range(0, nDivision):
        minMag_mag_bin: float = minVal + (binVal * j)
        maxMag_mag_bin: float = minVal + (binVal *(j+1))
        p.status(f"{colors['PURPLE']} {j+1}/{nDivision} for '{mag_filter_name}' mag in range [{minMag_mag_bin:.3f}, {maxMag_mag_bin:.3f}]{colors['NC']}")
        tempParamater = parameterList()
        tempPM_RA, tempPM_DEC = [], []
        for tempData in astrodata:
            # Main condition to define a bin, given by Cordoni et al. (2020)
            # If data is between the maximum and minimim value for the current bin, keep it
            mainCondition = minMag_mag_bin <= tempData[key_gaia_table] < maxMag_mag_bin
            # Second simple condition to avoid masked numpy null values in Color Mag Diagram
            secondCondition = -25. < tempData[key_gaia_table] <= 25.
            # If the value lies inside the range of values of the expected bin, then... 
            if mainCondition and secondCondition:
                tempParamater.G_BP.append(tempData['phot_bp_mean_mag'])
                tempParamater.G_RP.append(tempData['phot_rp_mean_mag'])
                tempParamater.G.append(tempData['phot_g_mean_mag'])
                tempParamater.as_gof_al.append(tempData['astrometric_gof_al'])
                tempParamater.parallax.append(tempData['parallax'])
                tempPM_RA.append(tempData['pmra'])
                tempPM_DEC.append(tempData['pmdec'])
                tempParamater.mu_R.append(estimate_mu_sub_R(PM_alpha=tempData['pmra'],PM_delta=tempData['pmdec'],
                                                            previous_PM_alpha_median=previous_median_PM_RA,
                                                            previous_PM_delta_median=previous_median_PM_DEC))                                 
        newBin = Bin(ID=j+1, params=tempParamater, minVal_mag=minMag_mag_bin, maxVal_mag=maxMag_mag_bin)
        totBins.bins.append(newBin)
    return totBins, maxVal, minVal, binVal


def get_and_check_created_bins(args, astrodata: Table, ellipse_center: ellipseVPDCenter)->TotalBins:
    """
    Count the number of elements inside every bin. If a bin has 0 or only 1 element, then we will
    have to reduce the number of bins in N-1 and create them again. This is repeated until every bin
    has at least 2 or more elements
    """
    n_divisions_for_bins = copy.deepcopy(args.n_divisions)
    p = log.progress(f"{colors['L_BLUE']}Creating Bins{colors['NC']}")
    mag_filter_name = get_mag_filter_name(args.set_mag_filter)
    counter = 0
    while True:
        if counter > 0:
            print(f"{colors['L_RED']}[-] {colors['RED']}Failed with {n_divisions_for_bins+1} bins. Attempting with {n_divisions_for_bins} bins...{colors['NC']}")
        totalCustomBins, maxVal, minVal, binVal = create_bins(args, astrodata=astrodata,
                                                          nDivision=n_divisions_for_bins, 
                                                          ellipse_center=ellipse_center,
                                                          p=p) 
        validElementsNumbInBins = check_if_total_bins_has_at_least_2_elems_or_more(totalCustomBins, 
                                                                                   mag_filter_name,
                                                                                   n_divisions_for_bins)
        if validElementsNumbInBins:
            p.success(f"{colors['PURPLE']}Bins created{colors['NC']}")
            break
        n_divisions_for_bins -= 1
        counter +=1
        if n_divisions_for_bins < 2:
            p.failure(f"{colors['RED']}Was not possible to create bins{colors['NC']}")
            sys.exit(1)
    if not args.no_print_bins:
        print_values_bins(maxVal, minVal, n_divisions_for_bins, binVal, totalCustomBins, mag_filter_name)
    setattr(args, 'n_divisions', n_divisions_for_bins)
    return totalCustomBins


def eq_straight_line(P1, P2: euclidianPoint) -> (float, float):
    "Return the equation of a straight line given two points with coordinates P1 = (x1, y1) and P2 = (x2,y2)"
    points = [(P1.x, P1.y),(P2.x, P2.y)]
    x_coords, y_coords = zip(*points)
    A = np.vstack([x_coords, np.ones(len(x_coords))]).T
    m, c = np.linalg.lstsq(A, y_coords, rcond=None)[0]
    # print("Line Solution is y = {m}x + {c}".format(m=m,c=c))
    return m, c


def create_points_to_interpolate(args, totalBins: TotalBins, varToInterpolate: str,
                                 sigma: float) -> pointsToInterpolate:
    """
    Create points that will be used to create interpolation lines that
    will be used to filter data
    """
    # Get the magnitude we are working with
    filter_name = get_mag_filter_name(args.set_mag_filter)
    # Create a list that will store the points to interpolate
    points = pointsToInterpolate()
    paramsToInterpolate=["as_gof_al", "astrometric_gof_al", "mu_R", "parallax"]
    # Create basic points to interpolate
    for index, data in enumerate(totalBins.bins):
        # Check what Gaia filter are we using
        if filter_name == "G_RP":
            data_median_mag: float = data.median_G_RP
            data_median_mag_stddev: float = data.std_dev_G_RP
        elif filter_name == "G_BP":
            data_median_mag: float = data.median_G_BP
            data_median_mag_stddev: float = data.std_dev_G_BP
        elif filter_name == "G":
            data_median_mag: float = data.median_G
            data_median_mag_stddev: float = data.std_dev_G
        else:
            print(f"{warning}{colors['RED']}Invalid filter name: {filter_name}. Exiting...{colors['NC']}")
            sys.exit(1)
        if varToInterpolate == "as_gof_al" or varToInterpolate == "astrometric_gof_al":
            temp_median_var = data.median_as_gof_al
            temp_std_var = data.std_dev_as_gof_al
        if varToInterpolate == "mu_R":
            temp_median_var = data.median_mu_R
            temp_std_var = data.std_dev_mu_R
        if varToInterpolate == "parallax":
            temp_median_var = data.median_parallax
            temp_std_var = data.std_dev_parallax
        if varToInterpolate not in paramsToInterpolate:
            print("Invalid parameter to filter!")
            sys.exit(1)

        tempPoint = singlePoint(
                    ID=index+1,
                    median_value=temp_median_var,
                    std_value=temp_std_var,
                    mag_median=data_median_mag,
                    mag_std=data_median_mag_stddev)
        points.points.append(tempPoint)

    # Check that both list have the same size at this point
    if not len(totalBins.bins) == len(points.points):
        print(f"{warning}{colors['RED']}Bins list and point list must have the same size!{colors['NC']}")
        sys.exit() 
    
    for index in range(0, len(points.points)-1):
        p1 = euclidianPoint(y=points.points[index].median_value \
                                + sigma*points.points[index].std_value, 
                            x=points.points[index].mag_median)
        p2 = euclidianPoint(y=points.points[index+1].median_value \
                                + sigma*points.points[index+1].std_value, 
                            x=points.points[index+1].mag_median)
        inclination, intersection = eq_straight_line(P1=p1, P2=p2)
        points.points[index].m = inclination
        points.points[index].c = intersection
        
    # Append first and last points
    firstPoint = points.points[0]
    # Check what Gaia filter are we using
    if filter_name == "G_RP":
        min_value_mag: float = np.amin(totalBins.bins[0].params.G_RP)
        max_value_mag: float = np.amax(totalBins.bins[-1].params.G_RP)
    elif filter_name == "G_BP":
        min_value_mag: float = np.amin(totalBins.bins[0].params.G_BP)
        max_value_mag: float = np.amax(totalBins.bins[-1].params.G_BP)
    elif filter_name == "G":
        min_value_mag: float = np.amin(totalBins.bins[0].params.G)
        max_value_mag: float = np.amax(totalBins.bins[-1].params.G)
    else:
        print(f"{warning}{colors['RED']}Invalid filter name: {filter_name}. Exiting...{colors['NC']}")
        sys.exit(1)
    points.points.insert(0,singlePoint(ID=0, median_value=firstPoint.median_value,
                         std_value= firstPoint.std_value,
                         mag_median= min_value_mag,
                         mag_std = 0.,
                         m= 0.,
                         c= firstPoint.median_value + args.sigma * firstPoint.std_value))
    lastPoint = points.points[-1] 
    points.points.append(singlePoint(ID=lastPoint.ID + 1,
                         median_value=lastPoint.median_value,
                         std_value=lastPoint.std_value,
                         mag_median=max_value_mag,
                         mag_std=0.,
                         m=0.,
                         c=lastPoint.median_value + args.sigma*lastPoint.std_value))
    
    # Re-compute the value for the semi-last point
    # (we could not do this since we did not have the last point until now)
    p1 = euclidianPoint(y=points.points[-2].median_value \
                              + sigma*points.points[-2].std_value, 
                            x=points.points[-2].mag_median)
    p2 = euclidianPoint(y=points.points[-1].median_value \
                              + sigma*points.points[-1].std_value, 
                            x=points.points[-1].mag_median)
    inclination, intersection = eq_straight_line(P1=p1, P2=p2)
    points.points[-2].m = inclination
    points.points[-2].c = intersection
    points.points[-1].c = points.points[-2].c
    return points


def interpolate_data_var(args, usefulData: parameterList, data_to_interpolate:Table, interPoints: pointsToInterpolate,
                         variableName: str,sigma: float, interPoints2: pointsToInterpolate = None)->np.ndarray:
    mask_array = []
    notfound=0
    parameter_to_get_list = which_parameter(parameters_in_list=usefulData,paramName=variableName)
    filter_name = get_mag_filter_name(args.set_mag_filter)
    gaia_key_mag = select_gaia_filter_key_param(filter_name) 
    if filter_name == "G_RP":
        useful_mag = usefulData.G_RP
    elif filter_name == "G_BP":
        useful_mag = usefulData.G_BP
    elif filter_name == "G":
        useful_mag = usefulData.G
    else:
        print(f"{warning} {colors['RED']}Invalid 'filter_name' in 'interpolate_data_var' (value given: '{filter_name}'){colors['NC']}")
        sys.exit(1)

    for j in range(0, len(useful_mag)):
        mag_iteration = useful_mag[j]
        parameterToCompare = parameter_to_get_list[j]
        for index in range (0, len(interPoints.points)-1):
            lower_mag = interPoints.points[index].mag_median
            upper_mag = interPoints.points[index+1].mag_median
            isInRange = lower_mag <= mag_iteration < upper_mag
            if isInRange:
                median_val = interPoints.points[index].median_value
                std_val = interPoints.points[index].std_value
                m_val = interPoints.points[index].m
                c_val = interPoints.points[index].c
                evaluate_value = m_val * mag_iteration + c_val
                # This will not be 'None' for "parallax" parameter
                if interPoints2 != None:
                    median_val2 = interPoints2.points[index].median_value
                    std_val2 = interPoints2.points[index].std_value
                    m_val2 = interPoints2.points[index].m
                    c_val2 = interPoints2.points[index].c
                    if index != 0:
                        evaluate_value2 = m_val2 * mag_iteration + c_val2
                    else:
                        evaluate_value2 = median_val2 - sigma * std_val2
                        
                    if evaluate_value2 < parameterToCompare < evaluate_value:
                        mask_array.append(True)
                    else:
                        mask_array.append(False)
                    
                # If we are only comparing with respect to one line,just keep the points at
                # the left of them
                if interPoints2 == None:
                    if parameterToCompare < evaluate_value:
                        mask_array.append(True)
                    if parameterToCompare >= evaluate_value:
                        mask_array.append(False)
                break
            if index == len(interPoints.points)-2:
                notfound+=1
                mask_array.append(True)
            
    checkLengths = len(mask_array) == len(data_to_interpolate[gaia_key_mag])
    if not checkLengths:
        print(f"{warning} {colors['RED']}Mask length and data length are not equal!{colors['NC']}")
        print(f"    {colors['RED']}Mask length: {len(mask_array)}{colors['NC']}")
        print(f"    {colors['RED']}{len(data_to_interpolate[gaia_key_mag])}{colors['NC']}")
        sys.exit(1)
    return  np.asarray(mask_array)


def do_interpolation(args, totalBins, dataToFilter, varToInterpolate, sigma, ellipse_center):
    usefulParameters = get_important_parameters(original_data=dataToFilter, ellipse_center=ellipse_center)
    if varToInterpolate != 'parallax':
        points_to_interpolate = create_points_to_interpolate(args, totalBins=totalBins, varToInterpolate=varToInterpolate, sigma=sigma)
        interpolated_stars = interpolate_data_var(args, usefulParameters, dataToFilter, points_to_interpolate, varToInterpolate, args.sigma)
        data_filtered = dataToFilter[interpolated_stars]
        return data_filtered, points_to_interpolate
        
    if varToInterpolate == 'parallax':
        points_to_interpolate_right = create_points_to_interpolate(args, totalBins=totalBins, varToInterpolate=varToInterpolate, sigma=sigma)
        points_to_interpolate_left = create_points_to_interpolate(args, totalBins=totalBins, varToInterpolate=varToInterpolate, sigma= -1.0*sigma)
        interpolated_stars = interpolate_data_var(args, usefulParameters, dataToFilter, points_to_interpolate_right, varToInterpolate, sigma=sigma,
                                                  interPoints2=points_to_interpolate_left)
        data_filtered = dataToFilter[interpolated_stars]
        return data_filtered, points_to_interpolate_left, points_to_interpolate_right


def do_and_print_interpolation(args, totalBins: TotalBins, preData: Table, len_originalData: int,
                               varToInterpolate: str, sigma: float, ellipse_center: ellipseVPDCenter):
    if varToInterpolate.lower() == "mu_r":
        var_to_print = "μ_R"
    if varToInterpolate.lower == "astrometric_gof_al" or varToInterpolate.lower() == "as_gof_al":
        var_to_print = "as_gof_al"
    if varToInterpolate.lower() == "parallax":
        var_to_print = "parallax"
    print(f"{sb} {colors['PURPLE']}Interpolating '{var_to_print}' parameter for a value of {sigma} σ...{colors['NC']}")
    if varToInterpolate != "parallax":
        data_filtered_by_param, points_separating_param = do_interpolation(args, totalBins=totalBins,
                                                                          dataToFilter=preData,
                                                                          varToInterpolate=varToInterpolate,    
                                                                          sigma=sigma,
                                                                          ellipse_center=ellipse_center)
    if varToInterpolate == "parallax":
        data_filtered_by_param, points_right, points_left = do_interpolation(args, totalBins=totalBins,
                                                                             dataToFilter=preData,
                                                                             varToInterpolate=varToInterpolate,    
                                                                             sigma=sigma,
                                                                             ellipse_center=ellipse_center)
    print(f"    {colors['BROWN']}-> {colors['CYAN']}Data size before filtering: {len_originalData}{colors['NC']}")
    print(f"    {colors['BROWN']}-> {colors['GREEN']}Data size after filtering: {len(data_filtered_by_param)}{colors['NC']}")
    print(f"    {colors['BROWN']}-> {colors['RED']}Data discarded:", end = " ")
    print(f"{round(((len_originalData-len(data_filtered_by_param))/(1.0*len_originalData))*100,2)}%{colors['NC']}")
    if varToInterpolate != 'parallax':
        return data_filtered_by_param, points_separating_param
    else: 
        return data_filtered_by_param, points_right, points_left


def check_bin_extremes(args, data_to_check, binsToCheck):
    """
    Since only the extremes (max and min values) of bins at the top and bottom decide
    the size of the divisions/rest of the bins, it is unnecesary to create divide 
    bins if the extremes have not changed
    """
    # Select magnitude column
    mag_filter_name = get_mag_filter_name(args.set_mag_filter)
    key_gaia_table = select_gaia_filter_key_param(mag_filter_name)
    # Select G_RP column
    mag_data = copy.deepcopy(data_to_check[key_gaia_table])
    max_value, min_value = np.amax(mag_data), np.amin(mag_data)
    min_totBins = binsToCheck.bins[0].minVal_mag
    max_totBins = binsToCheck.bins[-1].maxVal_mag
    print(max_value, min_value, min_totBins, max_totBins)
    return


def plot_interpolation(args, object_name: str, filtered_data: Table, original_data: Table, center_ellipse: ellipseVPDCenter,
                       points_data, variable_name: str, axis_name : str, points_data_left=None)->None:
    """
    Plot the data interpolated and filtered using Cordoni (2018) algorithm
    """
    # Create some lists that will store the data (so we do not touch the original one)
    filter_name = get_mag_filter_name(args.set_mag_filter)
    gaia_key_mag = select_gaia_filter_key_param(filter_name)
    x = []
    y = []
    # Since mu_R is not an intrinsic variable from Gaia Release, compute it and save it
    if variable_name == 'mu_R':
        # Compute mu_R for filtered data
        data_x = [estimate_mu_sub_R(x['pmra'], x['pmdec'], center_ellipse.pmra, center_ellipse.pmdec) for x in filtered_data]
        data_y = filtered_data[gaia_key_mag]
        # Compute mu_R for original data
        gaia_x = [estimate_mu_sub_R(x['pmra'], x['pmdec'], center_ellipse.pmra, center_ellipse.pmdec) for x in original_data]
        gaia_y = original_data[gaia_key_mag]
    else:
        # Get filtered data and its respective variable to compare
        data_x = filtered_data[variable_name]
        data_y = filtered_data[gaia_key_mag]

        # Get original data and its respective variable to compare
        gaia_x = original_data[variable_name]
        gaia_y = original_data[gaia_key_mag]
    # The original data must have a size equal or bigger than filtered data, so check it
    difference = len(gaia_x) - len(data_x)
    if difference < 0:
        print("Error. The difference between original data and filtered data must be higher than 0")
        sys.exit(1)
    # Get the points that were used to interpolate
    for j in range(0, len(points_data.points)):
        y.append(points_data.points[j].mag_median)
        x.append(points_data.points[j].median_value + args.sigma * points_data.points[j].std_value)
    # If we are plotting 'parallax', we need points also at the left, so add them    
    if points_data_left is not None:
        x_left = []
        y_left = []
        for j in range(0, len(points_data_left.points)):
            y_left.append(points_data_left.points[j].mag_median)
            x_left.append(points_data_left.points[j].median_value - args.sigma * points_data_left.points[j].std_value) 
    
    fig ,ax = plt.subplots()
    label_fontsize = 35
    matplotlib.rc('xtick', labelsize=label_fontsize - 5) 
    matplotlib.rc('ytick', labelsize=label_fontsize - 5)
    plt.title(object_name.upper(), fontsize=label_fontsize)
    ax.xaxis.label.set_size(label_fontsize)
    ax.yaxis.label.set_size(label_fontsize)
    if filter_name == "G_RP":
        y_label_text = r'$G_{RP}$ $({\rm mag})$'
    if filter_name == "G_BP":
        y_label_text = r'$G_{BP}$ $({\rm mag})$'
    if filter_name == "G":
        y_label_text = r'$G$ $({\rm mag})$'
    ax.set(xlabel=axis_name, 
           ylabel=y_label_text)
    ax.tick_params(which='both', width=4.5, top='on')
    ticksize = 14
    ax.tick_params(which='major',length=ticksize, direction = 'in')
    ax.tick_params(which='minor',length=ticksize/2., direction = 'in')
    ax.yaxis.set_ticks_position('both')
    plt.minorticks_on()
    if args.plot_dark_mode:
        plt.style.use('dark_background')
        original_data_color = "#00ddff"
        filtered_data_color = "#ff4600"
        linestyle = "-g"
        color_linestyle = "#00FE08"
    else:
        plt.style.use('default')
        original_data_color = "#274e13"
        filtered_data_color = "#cc0000"
        linestyle = "-b"
        color_linestyle = "#0078ff"
    # Plot the line dividing the selected vs eliminated stars
    plt.plot(x,y, linestyle)
    plt.plot(x,y, marker='o', color=color_linestyle)
    if points_data_left is not None:
        plt.plot(x_left,y_left, linestyle)
        plt.plot(x_left,y_left, marker='o', color=color_linestyle)
        
    # Original data
    plt.scatter(gaia_x, gaia_y, s=5.0, c = original_data_color, edgecolors='none')
    # Filtered data
    plt.scatter(data_x, data_y, s=5.0, c = filtered_data_color, edgecolors='none')
    anchored_text = AnchoredText(r'$N_{original}$ = '+str(len(gaia_x))+'\n'
                                 +r'$N_{filtered}$ = '+str(len(data_x))+'\n'
                                 +r'$N_{discarded}$ = ' + str(difference)+' (' 
                                 + str(round( difference/(len(gaia_x)*1.0) * 100 ,2))
                                 +'%)', loc='upper left', frameon=False,
                                 prop=dict(size=25))
    ax.add_artist(anchored_text)
    plt.rcParams["figure.figsize"] = [13.50, 17.50]
    plt.rcParams["figure.autolayout"] = True
    plt.gca().invert_yaxis()
    plt.show()


def get_median_pmra_pmdec(data: Table)->ellipseVPDCenter:
    """
    Get the median for 'pmra' and 'pmdec' Gaia data
    """
    pmra, pmdec = round(np.median(data['pmra']),3), round(np.median(data['pmdec']),3) 
    ellipseCenter = ellipseVPDCenter(pmra=pmra, pmdec=pmdec)
    return ellipseCenter


def get_pmra_based_on_object_identification(args, obj_name, original_data:Table | None = None, fill=False)->(ellipseVPDCenter, str):
    """
    Gets the pmra and pmdec components depending if the user has provided or not them explicitly as flags.
    If they have not been explicitly been given as flags, the program will try to get them depending if they
    are identified as Globular Cluser or Open Cluster. If the objects is a "Custom" object, then the parameters
    pmra and pmdec must be explicitly be given by the user. Otherwise quits the program
    """
    
    setattr(args, 'name', obj_name)
    setattr(args, 'skip_extra_data', False)
    setattr(args, 'right_ascension', 0.0)
    setattr(args, 'declination', 0.0)
    # Get coordiantes of the object in degrees
    object_info =  get_RA_and_DEC(args, fill=fill, print_decide_coords=False)
    # If the object is not found then it will return the "default" values. Check if those values match
    # If they do, it means that the user has not provided arguments for '--pmra' or '--pmdec'
    # and the user will have to explicitly provide them since the program could not get them automatically
    if object_info.identifiedAs == "GlobularCluster":
        print(f"{sb} {colors['BLUE']}Object found in Archives. Using values from: {colors['PURPLE']}Vasiliev & Baumgardt (2021, MNRAS, 505, 5978V){colors['NC']}")
        pmra, pmdec = object_info.pmra, object_info.pmdec
    if object_info.identifiedAs == "OpenCluster":
        print(f"{sb} {colors['BLUE']}Object found in Archives. Using values from: {colors['PURPLE']}Cantat-Gaudin et al. (2020, A&A, 640, A1){colors['NC']}")
        pmra, pmdec = object_info.pmra, object_info.pmdec
    if object_info.identifiedAs == "Other":
        print(f"{sb} {colors['BLUE']}Using median values obtained from data for 'pmra' and 'pmdec'{colors['NC']}")
        pmra, pmdec = round(np.median(original_data['pmra']),3), round(np.median(original_data['pmdec']),3)
    print(f"    {sb_v2} pmra:  {colors['CYAN']}{pmra} (mas/yr){colors['NC']}")
    print(f"    {sb_v2} pmdec: {colors['CYAN']}{pmdec} (mas/yr){colors['NC']}")
    identified = object_info.identifiedAs
    ellipseCenter = ellipseVPDCenter(pmra=pmra, pmdec=pmdec)
    return ellipseCenter, identified


def check_arguments_provided_for_Cordoni_algorithm(args)->None:
    # Check if the number of iterations provided by the user is valid.
    if args.n_iterations <= 0:
        print(f"{warning} {colors['RED']} Invalid number of iterations given: {args.n_iterations}. Value must be a positive number...{colors['NC']}")
        sys.exit(1)
    # User cannot disable 3 filters applied by Cordoni algorithm. If so, exit the program...
    if args.no_as_gof_al and args.no_mu_R and args.no_parallax:
        print(f"{warning} {colors['RED']} You do not want to apply any filter to data. Are you sure?{colors['NC']}")
        print(f"    {colors['RED']} '--no-as-gof-al', '--no-mu-R' and '--no-parallax' simoutaneously enabled{colors['NC']}")
        sys.exit(1)
    # Check if the user is using custom limits
    if args.set_limits:
        print(f"{sb_v2} {colors['GREEN']}Using custom mag limits: {colors['BLUE']}[{args.mag_lower_limit}, {args.mag_upper_limit}]{colors['NC']}")
    # Lower limit cannot be a bigger upper limit
    if args.mag_lower_limit >= args.mag_upper_limit:
        print(f"{warning}{colors['RED']} Lower limit magnitude ({args.mag_lower_limit}) must be bigger than upper limit magnitude ({args.mag_upper_limit})...{colors['NC']}")
        sys.exit(1)
    # Check if the user wants to show all the plots but at the same time hide all of them:
    if args.show_all_plots and args.no_plot_mu_R and args.no_plot_as_gof_al and args.no_plot_parallax:
        print(f"{warning} {colors['RED']}...so you want to show all the plots but at the same time hide all of them?{colors['NC']}")
        print(f"    {colors['RED']} '--show-all-plots', '--no-plot-as-gof-al', '--no-plot-mu-R' and '--no-plot-parallax' simoutaneously enabled{colors['NC']}")
        sys.exit(1)
    return


def Cordoni_algorithm(args, object_name: str, totalBins: TotalBins, original_data: Table, 
                      iteration_number: int, ellipse_center: ellipseVPDCenter):
    # Create a deep copy of the original data
    data_filtered = copy.deepcopy(original_data)
    if not args.no_as_gof_al:
        pre_filter_data = copy.deepcopy(data_filtered)
        data_filtered, points_to_plot = do_and_print_interpolation(args, totalBins, data_filtered, len(data_filtered),
                                                                   'astrometric_gof_al', args.sigma, ellipse_center)
        data_filtered = copy.deepcopy(data_filtered)
        if not args.no_plot_as_gof_al:
            # If we are in the first iteration, show a plot showing original and filtered data
            if iteration_number == 1 or args.show_all_plots:
                # Plot in 'dark mode'
                if args.plot_dark_mode:
                    with plt.style.context("dark_background"):
                        plot_interpolation(args, object_name, data_filtered, original_data, ellipse_center,
                                           points_to_plot, "astrometric_gof_al", "astrometric_gof_al")
                # Plot in 'light mode' (default)
                else:
                    with plt.style.context("default"):
                        plot_interpolation(args, object_name, data_filtered, original_data, ellipse_center,
                                           points_to_plot, "astrometric_gof_al", "astrometric_gof_al")
    if not args.no_mu_R:
        pre_filter_data = copy.deepcopy(data_filtered)
        data_filtered, points_to_plot = do_and_print_interpolation(args, totalBins, data_filtered, len(data_filtered),
                                                                   'mu_R', args.sigma, ellipse_center)
        data_filtered = copy.deepcopy(data_filtered)
        if not args.no_plot_mu_R:
            if iteration_number == 1 or args.show_all_plots:
                # Plot in 'dark mode'
                if args.plot_dark_mode:
                    with plt.style.context("dark_background"):
                        plot_interpolation(args, object_name, data_filtered, pre_filter_data, ellipse_center,
                                           points_to_plot, 'mu_R', r"$\mu_{\rm R}$ $({\rm mas}\cdot{\rm yr})^{-1}$")
                # Plot in 'light mode' (default)
                else:
                    with plt.style.context("default"):
                        plot_interpolation(args, object_name, data_filtered, pre_filter_data, ellipse_center,
                                           points_to_plot, 'mu_R', r"$\mu_{\rm R}$ $({\rm mas}\cdot{\rm yr})^{-1}$")

    if not args.no_parallax:
        pre_filter_data = copy.deepcopy(data_filtered)
        data_filtered, points_right, points_left = do_and_print_interpolation(args, totalBins, data_filtered, len(data_filtered),
                                                                              'parallax', args.sigma, ellipse_center)
        if not args.no_plot_parallax:
            if iteration_number == 1 or args.show_all_plots:
                # Plot in 'dark mode'
                if args.plot_dark_mode:
                    with plt.style.context("dark_background"):
                        plot_interpolation(args, object_name, data_filtered, pre_filter_data, ellipse_center, points_right,
                                           'parallax', r"$\pi$ $({\rm mas})$", points_data_left=points_left)
                # Plot in 'light mode' (default)
                else:
                    with plt.style.context("default"):
                        plot_interpolation(args, object_name, data_filtered, pre_filter_data, ellipse_center,
                                           points_right, 'parallax', r"$\pi$ $({\rm mas})$", points_data_left=points_left)
        
    return data_filtered

        
def recycle_center_ellipse(identified: str)->bool:
    if identified == "GlobularCluster" or identified == "OpenCluster":
        return True
    elif identified == "Other":
        return False
    else:
        return False


def extractCordoniData(args, subcommand, subsubcommand):
    # Check parameters provided by the user
    check_arguments_provided_for_Cordoni_algorithm(args)
    # Check if the Gaia filter provided by the user is valid
    # Only allowed values are: {G, G_RP, G_RP}
    # If this function does not exit then the user has provided a valid Gaia filter
    _ = get_mag_filter_name(args.set_mag_filter)
    # Get the original data from file. Since the file is required 'object_info' (the second variable returned) will always be "None" variable
    original_data, object_info = get_data_from_file_or_query(args, subcommand, subsubcommand)
    # Get the name of the object name based on the filename provided
    file_Path_object = Path(args.file)
    # Get only the filename. Without its path and without its file extension
    filename_original_without_extension = str(file_Path_object.stem)
    # Get the object name from filename
    obj_name = get_filename_in_list(filename_original_without_extension)
    # Recycle ellipse found (explained below)
    recycleCenterEllipse = False
    # Start applying Cordoni et al. (2018) algorithm to data over iterations
    p = log.progress(f"{colors['PURPLE']}Data{colors['NC']}")
    for iterator in range(1, args.n_iterations+1):
        p.status(f"{colors['GREEN']}Filtering data using {colors['RED']}Cordoni et al. (2018, ApJ, 869, 139C){colors['GREEN']} algorithm ({colors['PURPLE']}{iterator}/{args.n_iterations}{colors['GREEN']}){colors['NC']}")
        cordoni_text_to_show = f"Iteration #{iterator}"
        displaySections(cordoni_text_to_show, color_chosen=randomColor(), character='#', c=randomColor())
        if iterator == 1:
            # If we are in the first cycle, we must use the original data
            data_to_work = copy.deepcopy(original_data)
            centerEllipse, identified = get_pmra_based_on_object_identification(args, obj_name, data_to_work)
            # If the ellipse is a Globular Cluster or Open Cluster, then we can recycle the center of the ellipse
            # But if the data is a ustom object, we will need to re-compute the data ellipse center
            recycleCenterEllipse = recycle_center_ellipse(identified)
        if iterator != 1:
            # If we are in a different cycle than the first one, use the data filtered in previous steps
            data_to_work = copy.deepcopy(filtered_data)
        # Re-compute the ellipse center if the data is found as "Other" or if the user wants to re-compute it...
        if (iterator != 1 and not recycleCenterEllipse) or args.re_compute_ellipse_center:
            if iterator != 1:
                print(f"{sb} {colors['GREEN']}Re-computing ellipse center...{colors['NC']}")
                print(f"    {sb_v2} {colors['CYAN']}Old Center Coords (pmra, pmdec) (mas/yr): {colors['RED']}({centerEllipse.pmra}, {centerEllipse.pmdec}){colors['NC']}")
            centerEllipse = get_median_pmra_pmdec(data_to_work)
            if iterator != 1:
                print(f"    {sb_v2} {colors['CYAN']}New Center Coords (pmra, pmdec) (mas/yr): {colors['PURPLE']}({centerEllipse.pmra}, {centerEllipse.pmdec}){colors['NC']}")
        totalCustomBins = get_and_check_created_bins(args, astrodata=data_to_work, ellipse_center=centerEllipse)
        filtered_data = Cordoni_algorithm(args, obj_name, totalCustomBins, data_to_work, iterator, centerEllipse)
    p.success(f"{colors['CYAN']} Cordoni algorithm succesfully applied to data{colors['NC']}")
    print_before_and_after_filter_length(len(original_data), len(filtered_data))
    p = log.progress(f"{colors['PINK']}Saving data{colors['NC']}")
    # If the user provided a file, try to obtain the "identifiedAs" parameter based on its path
    object_info_identified = decide_parameters_to_save_data(args, object_info)
    # Save data if needed
    if not args.no_save_output:
        save_data_output(args, subcommand, subsubcommand, object_info_identified, filtered_data)
        p.success(f"{colors['GREEN']}Data succesfully saved{colors['NC']}")
    else:
        p.failure(f"{colors['RED']}Data has not been saved{colors['NC']}")
    return filtered_data


def extractEllipseData(args, subcommand, subsubcommand):
    # Check if the user has provided the correct number of parameters for width and height, which must be 2
    # Also sort the lists so, for example, the first item of args.width is the minimum and the second is
    # the maximum value
    check_width_and_height_provided_for_ellipse(args)
    # Get the original data from file. Since the file is required 'object_info' (the second variable returned) will always be "None" variable
    original_data, object_info = get_data_from_file_or_query(args, subcommand, subsubcommand)
    # Get the name of the object name based on the filename provided
    file_Path_object = Path(args.file)
    # Get only the filename. Without its path and without its file extension
    filename_original_without_extension = str(file_Path_object.stem)
    # Get the object name from filename
    obj_name = get_filename_in_list(filename_original_without_extension)
    # Get the coordinates for ellipse center
    centerEllipse, _ = get_pmra_pmdec_for_VPD(args, obj_name)
    while True:
        width_it, height_it, incl_it = create_IteratorClass_objects_for_ellipse(args)
        # Create a simple process to track the results
        p = log.progress("Ellipse")
        # Get the "optimal ellipse", which maximizes the number of objects inside it
        ellipse = count_stars_inside_ellipse(centerEllipse.pmra, centerEllipse.pmdec, original_data, 
                                             width_it, height_it, incl_it, p)
        # Print some parameters related to this 'optimal' ellipse
        print_found_ellipse_attributes(ellipse)
        ellipse_mask, colors_array = check_if_data_lies_inside_ellipse(original_data, ellipse)
        filtered_data = filter_data_by_mask(original_data, ellipse_mask)
        print_before_and_after_filter_length(len(original_data), len(filtered_data))
        try:
            plot_ellipse_in_VPD(args, obj_name, original_data, ellipse, centerEllipse.pmra, 
                                centerEllipse.pmdec, colors_array)
        except:
            print(f"{warning} {colors['RED']}Something happened when trying to plot VPD and ellipse. Continuing without plotting...{colors['NC']}")
            break
        isUserHappy = ask_to(f"{colors['GREEN']}{sb} Are you happy with this result? {colors['RED']}[Y]es/[N]o{colors['GREEN']}: {colors['NC']}")
        if isUserHappy:
            break
        else:
            wantToContinue = ask_to(f"{colors['RED']}{sb} Do you want to continue with the program? {colors['PURPLE']}[Y]es/[N]o{colors['RED']}: {colors['NC']}")
            if not wantToContinue:
                print(f"\n{colors['L_CYAN']}Bye!{colors['NC']}")
                sys.exit(0)
            else:
                set_new_values_for_ellipse_parameters(args, 'width')
                set_new_values_for_ellipse_parameters(args, 'height')
                set_new_values_for_ellipse_parameters(args, 'inclination')
    p = log.progress(f"{colors['PINK']}Saving data{colors['NC']}")
    # If the user provided a file, try to obtain the "identifiedAs" parameter based on its path
    object_info_identified = decide_parameters_to_save_data(args, object_info)
    # Save data if needed
    if not args.no_save_output:
        save_data_output(args, subcommand, subsubcommand, object_info_identified, filtered_data)
        p.success(f"{colors['GREEN']}Data succesfully saved{colors['NC']}")
    else:
        p.failure(f"{colors['RED']}Data has not been saved{colors['NC']}")
    return filtered_data


def extractFilterParameters(args, subcommand: str, subsubcommand: str):
    original_data, object_info = get_data_from_file_or_query(args, subcommand, subsubcommand)
    original_length = len(original_data)
    filtered_data = apply_filter_to_data_with_parameters(args, original_data)
    p = log.progress(f"{colors['PINK']}Saving data{colors['NC']}")
    # If the user provided a file, try to obtain the "identifiedAs" parameter based on its path
    object_info_identified = decide_parameters_to_save_data(args, object_info)
    # Save data if needed
    if not args.no_save_output:
        save_data_output(args, subcommand, subsubcommand, object_info_identified, filtered_data)
        p.success(f"{colors['GREEN']}Data succesfully saved{colors['NC']}")
    else:
        p.failure(f"{colors['RED']}Data has not been saved{colors['NC']}")
    print_before_and_after_filter_length(original_length, len(filtered_data))
    return filtered_data


def extractRawData(args, subcommand, search_mode_var: str, enableSave=True, showBanner=True):
    # Get coordiantes of the object in degrees
    object_info =  get_RA_and_DEC(args)
    # Display a message
    if showBanner:
        displaySections(f'extract -- {subcommand} -- {search_mode_var}', randomColor(), randomChar())
    # Start a timer to check execution time
    start_time = time.time()
    # Get data via astroquery
    if search_mode_var == "cone":
        raw_data = get_data_via_astroquery(args, object_info, 'cone', 'normal')
    if search_mode_var == "rect":
        raw_data = get_data_via_astroquery(args, object_info, 'rectangle', 'normal')
    if search_mode_var == "ring":
        raw_data = get_data_via_astroquery(args, object_info, 'ring', 'normal')
    if enableSave:
        if not args.no_print_data_requested:
            # Print the data obtained 
            print_data_requested(raw_data, start_time)
        # Save data
        if not args.no_save_raw_data:
            save_data_output(args, subcommand, search_mode_var, object_info, raw_data)
        else:
            print(f"{warning} Raw data extracted has not been saved")
    # And we are done
    print(f"{sb} {colors['GREEN']}Data succesfully obtained from Archives{colors['NC']}")
    return raw_data, object_info


def extractCommand(args)->None:
    """
    If the user has selected the command "extract" choose the mode to extract data
    """
    # 'raw' subcommand
    if args.subcommand == "raw":
        # Check that user has provided a valid format for name
        checkNameObjectProvidedByUser(args.name)
        # 'cone' subcommand
        if args.subsubcommand == "cone":
            raw_data,_ = extractRawData(args, "raw", "cone")
            sys.exit(0)
        if args.subsubcommand == "rectangle":
            raw_data,_ = extractRawData(args, "raw" ,"rect")
            sys.exit(0)
        if args.subsubcommand == "ring":
            raw_Data,_ = extractRawData(args, "raw", "ring")
            sys.exit(0)
    # 'filter' subcommand
    if args.subcommand == "filter":
        if args.subsubcommand == "parameters":
            filtered_data = extractFilterParameters(args, 'filter', 'parameters')
            sys.exit(0)
        if args.subsubcommand == "ellipse":
            filtered_data = extractEllipseData(args, 'filter', 'ellipse')
            sys.exit(0)
        if args.subsubcommand == "cordoni":
            filtered_data = extractCordoniData(args, 'filter', 'cordoni')
            sys.exit(0)


####################
####### plot #######
####################

def plot_rawSubcommand(args):
    return
    

def plotCommand(args) -> None:
    """
    Plot data
    """
    print("Function still under construction. Come later...")
    if args.subcommand == 'raw':
        pass
    return


def main() -> None:
    # Parse the command-line arguments/get flags and their values provided by the user
    parser, args = parseArgs()

    # Check that user has provided non-empty arguments, otherwise print help message
    checkUserHasProvidedArguments(parser, args, len(sys.argv))

    printBanner()

    # Run 'show-gaia-content' command
    if args.command == 'show-gaia-content':
        showGaiaContent(args)

    # Run 'extract' command
    if args.command == 'extract':
        # Extract data using Astroquery
        extractCommand(args)

    if args.command == 'plot':
        # Check that user has provided a valid format-name
        checkNameObjectProvidedByUser(args.name)  

        plotCommand(args)
        

if __name__ == "__main__":
    main()
