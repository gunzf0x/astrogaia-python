#!/usr/bin/python3

import argparse
import sys

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

    
    # parse the command-line arguments
    args = parser.parse_args()

    return parser, args

# Check if Python version running is at least 3.10
def checkPythonVersion() -> None:
    """
    Since this script uses some functions defined only since Python 3.10, it is required to run. Otherwise it will throw an errors while running
    """
    if sys.version_info < (3,10):
        print("{colors['L_RED']}[!] This script requires Python 3.10 (or higher) to run{colors['NC']}")
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


def main() -> None:
    # Check if the user is using Python3.10 or higher, which is required for some functions
    checkPythonVersion()

    # Parse the command-line arguments/get flags and their values provided by the user
    parser, args = parseArgs()

    # Check that user has provided arguments, otherwise print help message
    checkUserHasProvidedArguments(parser, args, len(sys.argv))


if __name__ == "__main__":
    main()
