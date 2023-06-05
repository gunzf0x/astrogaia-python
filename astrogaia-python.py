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
from pwn import log
import shutil
from tabulate import tabulate
import random
import matplotlib.pyplot as plt
import re
from typing import List
import time
import os
from dataclasses import dataclass
import requests
from pathlib import Path
import signal


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


# Redirect the signal handler
signal.signal(signal.SIGINT, signal_handler)


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
    extract_subcommand_raw_subsubcommand_cone.add_argument('-x', '--file-extension', type=str, default="dat",
                                                           help="Extension for the output file. Default = '.dat'")
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
                                                                                  epilog=f"example: {sys.argv[0]} extract raw rectangle ")
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
    extract_subcommand_raw_subsubcommand_rect.add_argument('-x', '--file-extension', type=str, default="dat",
                                                           help="Extension for the output file. Default = '.dat'")
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
    extract_subcommand_raw_subsubcommand_ring_example = f"example: {sys.argv[0]} extract raw annulus -ra '210' -dec '-i 7.0' -e 6.5"
    extract_subcommand_raw_subsubcommand_ring = parser_sub_extract_raw.add_parser(str_extract_subcommand_raw_subsubcommand_ring,
                                                                                  help=f"{colors['RED']}Extract data in 'Annulus/Ring Search' mode{colors['NC']}",
                                                                                  description=f"{colors['L_RED']}Extract data in annulus/ring shape/mode using 2 Cones with different radius{colors['NC']}",
                                                                                  epilog=f"example: {sys.argv[0]} extract raw annulus ")
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
    extract_subcommand_raw_subsubcommand_ring.add_argument('-x', '--file-extension', type=str, default="dat",
                                                           help="Extension for the output file. Default = '.dat'")
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
    print(f"\n{' ' * 11}by {colors['L_CYAN']}Francisco Carrasco Varela{colors['NC']}")
    print(f"{' ' * 21}{colors['CYAN']}(ffcarrasco@uc.cl){colors['NC']}\n\n")
    return


def displaySections(text, color_chosen=colors['NC'], character='#'):
    """
    Displays a section based on the user option/command
    """
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
    centered_text = f"{left_padding} {color_chosen}{text}{colors['NC']} {right_padding}"
    border = character * total_width
    # Print the result
    print(f"\n{border}\n{centered_text}\n{border}\n")


def randomColor() -> str:
    """
    Select a random color for text
    """
    return f'\033[{random.randint(31,36)}m'


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
        p = log.progress(f'{colors["L_GREEN"]}Requesting data')
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


def showGaiaContent(args) -> None:
    """
    Get columns to display for GaiaDR3, GaiaEDR3 or GaiaDR2
    """
    displaySections('show-gaia-content', randomColor(), randomChar())
    # Get table format to display the content
    table_format = args.table_format
    # Create a random 'objectInfo' object just to fill
    object_example = objectInfo(name='', RA=280, DEC=-60, identifiedAs="Other")
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

def decide_coords(args):
    """
    Based if the object provided by the user was found or not, decide what coordinates the program will use
    """
    p = log.progress(f'{colors["L_GREEN"]}Obtaining coordinates for object{colors["NC"]}')
    object_coordinates, found_object = get_object_coordinates(args.name)
    if found_object:
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
                p.success(f"{colors['GREEN']} Data found as {colors['RED']}Globular Cluster{colors['GREEN']} from {vasiliev_baumgardt_study.show_study()} {colors['NC']}")
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



    
def get_extra_object_info_open_cluster(args, p):
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
                cantat_object = onlineCantanObject(name=f"{columns[0].replace('_',' ')}",
                                                   ra = float(columns[1]),
                                                   dec = float(columns[2]),
                                                   r50 = float(columns[5]),
                                                   pmra = float(columns[7]),
                                                   e_pmra = float(columns[8]),
                                                   pmdec = float(columns[9]),
                                                   e_pmdec = float(columns[10]),
                                                   parallax = float(columns[11]),
                                                   e_parallax = float(columns[12]),
                                                   log_age = float(columns[14]),
                                                   a_v = float(columns[15]),
                                                   d_modulus=float(columns[16]),
                                                   distance=float(columns[17]),
                                                   rgc=float(columns[-1]))

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
    identifiedAs: str

    def __post_init__(self):
        """
        Check which type of object has the data been identified as
        """
        allowed_values = ["GlobularCluster", "OpenCluster", "Other"]
        if self.identifiedAs not in allowed_values:
            raise ValueError(f"Invalid identifiedAs value. Allowed values are: {allowed_values}")


def get_RA_and_DEC(args):
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
        RA, DEC = decide_coords(args)
        identified = "Other"
    else: # if object_online_found
        RA, DEC = object_online_data.ra, object_online_data.dec
    object_info = objectInfo(name=args.name, RA=RA, DEC=DEC, identifiedAs=identified)

    return object_info


def print_data_requested(data, start_time, show_n_rows=12):
    """
    Print the data that has been extracted via Astroquery using pprint
    """
    print(f"{sb} Small extract of data requested:\n\n")
    data.pprint(max_lines=show_n_rows)
    print()
    print_elapsed_time(start_time, "requesting data")


def replace_last_ocurrence_word(text, word_to_replace, replacement_word):
    """
    Replaces the last ocurrence of a word in a string. So, if I want to replace the word 'pizza' with 'pasta'
    the phrase 'pizza, I like pizza' becomes 'pizza, I like pasta'
    """
    # Find the last occurrence of the word
    last_occurrence_index = text.rfind(word_to_replace)
    # Replace the last occurrence
    new_text = text[:last_occurrence_index] + replacement_word + text[last_occurrence_index + len(word_to_replace):]
    return new_text


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
    Shorten a path if the string is too large
    """
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
    

def where_to_save_data(args, command, mode, p, objectIdentifiedAs)->str:
    if not args.outfile:
        working_dir_file_exists, working_dir = check_if_save_file_exists()
        if working_dir_file_exists:
            current_path = working_dir
            print("File exists")
        else:
            current_path = Path.cwd()
        object_path_to_save = get_Object_directory(args, current_path, args.name, objectIdentifiedAs)
        filename = f"{args.name.replace(' ', '_').lower()}_{command}_{mode}.{args.file_extension}"
        filename = f"{object_path_to_save}/{filename}"
        p.status(f"{colors['YELLOW']}No outfile name provided in input. {colors['GREEN']}Data will be saved as\n'{colors['L_BLUE']}{filename}{colors['GREEN']}'\ninto working directory ('{shortened_path(str(current_path))}'){colors['NC']}{colors['NC']}")
        return filename
    if args.outfile:
        if args.outfile.endswith(args.file_extension):
            filename = f"{replace_last_ocurrence_word(args.outfile, f'.{args.file_extension}', '')}_{command}_{mode}.{args.file_extension}"
        else:
            filename = f"{args.outfile}_{command}_{mode}.{args.file_extension}"
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
    Asks the user if wants to replace the current file using Regex
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


def save_data_output(args, command, mode, objectIdentifiedAs, data):
    p = log.progress(f"{colors['L_GREEN']}Saving data{colors['NC']}")
    filename = where_to_save_data(args, command, mode, p, objectIdentifiedAs)
    #p.success("we did it!")
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



def extractRawData(args, search_mode_var: str):
    # Get coordiantes of the object in degrees
    object_info =  get_RA_and_DEC(args)
    # Display a message
    displaySections(f'extract -- raw -- {search_mode_var}', randomColor(), randomChar())
    # Start a timer to check execution time
    start_time = time.time()
    # Get data via astroquery
    if search_mode_var == "cone":
        raw_data = get_data_via_astroquery(args, object_info, 'cone', 'normal')
    if search_mode_var == "rect":
        raw_data = get_data_via_astroquery(args, object_info, 'rectangle', 'normal')
    if search_mode_var == "ring":
        raw_data = get_data_via_astroquery(args, object_info, 'ring', 'normal')
    if not args.no_print_data_requested:
        # Print the data obtained 
        print_data_requested(raw_data, start_time)
    # Save data
    if not args.no_save_raw_data:
        save_data_output(args, 'raw', search_mode_var, object_info.identifiedAs, raw_data)
    else:
        print(f"{warning} Raw data extracted has not been saved")
    #save_data_output(args, 'raw', 'cone', raw_data)
    # And we are done
    print(f"{sb} {colors['GREEN']}Data succesfully obtained from Archives{colors['NC']}")
    return raw_data



def extractCommand(args)->None:
    """
    If the user has selected the command "extract - raw" choose the mode to extract data
    """
    # 'raw' subcommand
    if args.subcommand == "raw":
        # 'cone' subcommand
        if args.subsubcommand == "cone":
            raw_data = extractRawData(args, "cone")
        if args.subsubcommand == "rectangle":
            raw_data = extractRawData(args, "rect")
        if args.subsubcommand == "ring":
            raw_Data = extractRawData(args, "ring")



####################
####### plot #######
####################

def plot_rawSubcommand(args):
    return
    

def plotCommand(args) -> None:
    """
    Plot data
    """
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
        # Check that user has provided a valid format-name
        checkNameObjectProvidedByUser(args.name)

        # Extract data using Astroquery
        extractCommand(args)


    if args.command == 'plot':
        # Check that user has provided a valid format-name
        checkNameObjectProvidedByUser(args.name)  

        plotCommand(args)
        

if __name__ == "__main__":
    main()
