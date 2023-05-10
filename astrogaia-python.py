#!/usr/bin/python3

import argparse
import sys
import logging
import astropy.units as u
from astropy.coordinates import SkyCoord
from astroquery.gaia import Gaia
import astroquery.utils.tap.core as tapcore
from pwn import *
import shutil
from tabulate import tabulate

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


# Define simple characters
sb: str = f'{colors["L_CYAN"]}[*]{colors["NC"]}' # [*]
sb_v2: str = f'{colors["RED"]}[{colors["YELLOW"]}+{colors["RED"]}]{colors["NC"]}' # [*]
whitespaces: str = " "*(len(sb)+1) # '    '
warning: str = f'{colors["YELLOW"]}[{colors["RED"]}!{colors["YELLOW"]}]{colors["NC"]}' # [!]


# Get user flags
def parseArgs():
    """
    Get commands and flags provided by the user
    """
    # General description / contact info
    general_description = f"{colors['L_CYAN']}Gaia DR3 tool written in Python 💫{colors['NC']} -- "
    general_description += f"{colors['L_GREEN']}Contact: {colors['GREEN']}Francisco Carrasco Varela \
                             (ffcarrasco@uc.cl) ⭐{colors['NC']}"

    parser = argparse.ArgumentParser(description=f"{general_description}")

    # Define commands
    commands = parser.add_subparsers(dest='command')

    # Command 1: extract -- Extract data from Gaia Archive
    str_extract_command: str = 'extract'
    extract_command = commands.add_parser(str_extract_command, help='Extract data from Gaia Archive')
    # main command

    # Sub-command extract - raw
    extract_raw_subcommand_help = f"{colors['RED']}Extract raw data from Gaia DR3 archive without any filter{colors['NC']}"
    parser_sub_extract = extract_command.add_subparsers(dest='subcommand', help=extract_raw_subcommand_help)

    str_extract_subcommand_raw: str = 'raw'
    extract_subcommand_raw = parser_sub_extract.add_parser(str_extract_subcommand_raw, description=extract_raw_subcommand_help)
    extract_subcommand_raw.add_argument('-f', '--file', help="some file")
    extract_subcommand_raw.add_argument('-o', '--output', help="Some output")

    # Command 2: plot -- Plot data
    str_plot_command: str = 'plot'
    plot_command = commands.add_parser(str_plot_command, help="Plot data")

    # Sub-command plot -> raw -- Plot data without any filter
    parser_subcommand_plot = plot_command.add_subparsers(dest='subcommand', help="Extract raw data from Gaia DR3 archive and plot it given a point (center) and a radius")

    str_plot_subcommand_raw: str = 'raw'
    plot_subcommand_raw = parser_subcommand_plot.add_parser(str_plot_subcommand_raw)
    plot_subcommand_raw.add_argument('-n', '--name', help="Set a object name for the sample. Example: 'NGC104', 'my_sample'")
    plot_subcommand_raw.add_argument('-ra', "--right-ascension", help="Right Ascension (J2000) for the center of data")
    plot_subcommand_raw.add_argument('-dec', "--declination", help="Declination (J2000) for the center of data")
    plot_subcommand_raw.add_argument('-r', "--radii", help="Radius for the data centered in (RA, DEC) flags in arcmin")
    
    # Sub-command plot -> filter -- Plot data filtered
    str_plot_subcommand_filter : str = "filter"
    plot_subcommand_filter = parser_subcommand_plot.add_parser(str_plot_subcommand_filter)
    plot_subcommand_filter.add_argument("-n", "--name", help="Set a object name for the sample. Example: 'NGC104', 'my_sample'")


    # Command 3: show-gaia-content
    str_show_content_command: str = 'show-gaia-content'
    show_content_command =  commands.add_parser(str_show_content_command, help="Show the type of content that different Gaia Releases can provide")
    show_content_command.add_argument('-r', '--gaia-release', default='gdr3',
                                      help="Select the Gaia Data Release you want to display what type of data contains. \
                                            Valid options: {gdr3, gaiadr3, g3dr3, gaia3dr3, gdr2, gaiadr2}")
    show_content_command.add_argument('-t', '--table-format', default='grid', 
                                      help="Table display format (default='grid'). To check all formats available visit: https://pypi.org/project/tabulate/")
    
    # parse the command-line arguments
    args = parser.parse_args()

    return parser, args

# Check if Python version running is at least 3.10
def checkPythonVersion() -> None:
    """
    Since this script uses some functions defined only since Python 3.10, it is required to run. Otherwise it will throw an errors while running
    """
    if sys.version_info < (3,10):
        print("{colors['L_RED']}[!] This function requires Python 3.10 (or higher) to run{colors['NC']}")
        sys.exit(1)
    return


def checkUserHasProvidedArguments(parser_provided, args_provided, n_args_provided) -> None:
    """
    Display help messages if the user has not provided arguments to a command/subcommand
    """
    # If user has not provided a command
    if args_provided.command is None:
        parser_provided.print_help()

    # If user has not provided a subcommand  
    if args_provided.command == "extract" and args_provided.subcommand is None:
        parser_provided.parse_args(['extract', '-h'])

    if args_provided.command == "plot" and args_provided.subcommand is None:
        parser_provided.parse_args(['plot', '-h'])
    
    if args_provided.command == 'show-gaia-content' and n_args_provided == 2:
        parser_provided.parse_args(['show-gaia-content', '-h'])

    # If user has not provided any argument for the subcommand
    if args_provided.command == "extract" and args_provided.subcommand == "raw" and n_args_provided == 3:
        parser_provided.parse_args(['extract', 'raw', '-h'])

    if args_provided.command == "plot" and args_provided.subcommand == "raw" and n_args_provided == 3:
        parser_provided.parse_args(['plot', 'raw', '-h'])

    if args_provided.command == "plot" and args_provided.subcommand == "filter" and n_args_provided == 3:
        parser_provided.parse_args(['plot', 'filter', '-h'])
            

def checkNameObjectProvidedByUser(name_object):
    """
    Checks if a user has provided a valid object name. For example, object name 'NGC104' is valid, '<NGC104>' is not. 
    Also, 'NGC 104' is converted to 'NGC_104' for future functions/usage
    """
    pattern = r'^[\w ]+$'
    name_to_test = name_object.replace(' ', '_')
    pass_test = bool(re.match(pattern, name_object))
    if pass_test:
        return name_to_test
    if not pass_test:
        print("{warning} You have provided an invalid name (which may contain invalid characters): '{name_object}'")
        sys.exit(1)


#######################
## show gaia-content ##
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
    

def get_data_via_astroquery(input_service, input_ra, input_dec, input_radius, 
                            coords_units, radius_units, input_rows):
    """
    Get data applying a query to Astroquery
    """
    ### Get data via Astroquery
    print(f"service {input_service} input_ra {input_ra} input_dec {input_dec} input_radius {input_radius} coords_units {coords_units} radius_units {radius_units} input_rows {input_rows}")
    Gaia.MAIN_GAIA_TABLE = input_service 
    Gaia.ROW_LIMIT = input_rows 
    p = log.progress(f'{colors["L_GREEN"]}Requesting data')
    logging.getLogger('astroquery').setLevel(logging.WARNING)

    # Make request to the service
    try:
        p.status(f"{colors['PURPLE']}Querying table for '{input_service.replace('.gaia_source', '')}' service...{colors['NC']}")
        coord = SkyCoord(ra=input_ra, dec=input_dec, unit=(coords_units, coords_units), frame='icrs')
        radius = u.Quantity(input_radius, radius_units)
        j = Gaia.cone_search_async(coord, radius)
        logging.getLogger('astroquery').setLevel(logging.INFO)
    except:
        p.failure(f"{colors['RED']}Error while requesting data. Check your internet connection is stable and retry...{colors['NC']}")
        sys.exit(1)

    p.success(f"{colors['L_GREEN']}Data obtained!{colors['NC']}")
    # Get the final data to display its columns as a table
    r = j.get_results()
    return r 
    

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
    # Get arguments
    service_requested = args.gaia_release
    table_format = args.table_format
    # Get which service the user wants to use
    service = select_gaia_astroquery_service(service_requested)
    # Get an example data
    data = get_data_via_astroquery(service, 280, -60, 1.0, u.degree, u.deg, 1)
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


def main() -> None:
    # Parse the command-line arguments/get flags and their values provided by the user
    parser, args = parseArgs()

    # Check that user has provided non-empty arguments, otherwise print help message
    checkUserHasProvidedArguments(parser, args, len(sys.argv))

    # Check arguments provided and run their respective commands

    # Run 'show-gaia-content' command
    if args.command == 'show-gaia-content':
        showGaiaContent(args)

    # Run 'extract' command
    if args.command == 'extract':
        # Check if the user is using Python3.10 or higher, which is required for this function
        checkPythonVersion()
            

if __name__ == "__main__":
    main()
