# -*- coding: utf-8 -*-
"""
A tool for enhancing the grep_ioc CLI tool for ECS-Delivery team
"""
###############################################################################
# %% Imports
###############################################################################

import argparse
import glob as gb
import json
import os.path
import re
import sys
from shutil import get_terminal_size

import pandas as pd
from colorama import Fore, Style

from constants import DEF_IMGR_KEYS, VALID_HUTCH

###############################################################################
# %% Global settings
###############################################################################
# Change max rows displayed to prevent truncating the dataframe
# We'll assume 1000 rows as an upper limit

pd.set_option("display.max_rows", 1000)

###############################################################################
# %% Functions
###############################################################################


def search_file(*, file: str, output: list = None,
                patt: str = None, prefix: str = '',
                quiet: bool = False, color_wrap: Fore = None) -> list[str]:
    """
    Searches file for regex match and appends result to list

    Parameters
    ----------
    file: str
        The file to read and search. Encoding must be utf-8
    output: list, optional
        A list to appead your results to. The default is None.
    patt: str, optional
        The regex pattern to search for. The default is None.
    prefix: str, optional
        A str prefix to add to each line. The default is ''.
    color_wrap: Fore, optional
        Color wrapping using Colorama.Fore. The default is None.
    quiet: bool, optional
        Whether to surpress the warning printed to terminal when "file"
        does not exist. The default is False.

    Returns
    -------
    list[str]
        A list of the search results with the prefix prepended.
    """
    if output is None:
        output = []
    color = ''
    reset = ''
    if color_wrap is not None:
        color = color_wrap
        reset = Style.RESET_ALL
    if os.path.isfile(file) is False:
        if not quiet:
            print(f'{file} does not exist')
        return ''
    with open(file, 'r', encoding='utf-8') as _f:
        for line in _f.readlines():
            if re.search(patt, line):
                output.append(re.sub(patt, color + r'\g<0>' + reset, line))
        return prefix + prefix.join(output)


def print_skip_comments(file: str):
    """Prints contents of a file while ignoring comments"""
    try:
        with open(file, 'r', encoding='utf_8') as _f:
            for line in _f.readlines():
                if not line.strip().startswith('#'):
                    print(line.strip())
    except FileNotFoundError:
        print(f'{Fore.RED}Could not open {Style.RESET_ALL}'
              + f'{file}.'
              + f'{Fore.RED} Does not exist{Style.RESET_ALL}')


def simple_prompt(prompt: str, default: str = 'N'):
    """Simple yes/no prompt which defaults to No"""
    while True:
        p = input(prompt).strip().lower()
        if p in ['']:
            p = default.lower()
        if p[0] == 'y':
            result = True
            break
        if p.lower()[0] == 'n':
            result = False
            break
        print('Invalid Entry. Please choose again.')
    return result


def clean_ansi(text: str = None) -> str:
    """
    Removes ANSI escape sequences from a str, including fg/bg formatting.
    """
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def fix_json(raw_data: str, keys: list[str] = None) -> list[str]:
    """
    Fixes JSON format of find_ioc/grep_ioc output.

    Parameters
    ----------
    raw_data: str
        Str output generated by find_ioc/grep_ioc, which is pseudo-JSON.
    keys: list[str]
        A list of valid keys to use for scraping the IOC.cfg file.
    Returns
    -------
    list[str]
        The list of str ready for JSON loading
    """
    if keys is None:
        valid_keys = re.compile(r'(?=\s?:\s?)|'.join(DEF_IMGR_KEYS))
    # clean empty rows and white space
    _temp = raw_data.replace(' ', '').strip()
    # capture and fix the keys not properly formatted to str
    _temp = re.sub(valid_keys, r"'\g<0>'", raw_data)
    # capture boolean tokens and fix them for json format
    _temp = re.sub("True", "true", _temp)
    _temp = re.sub("False", "false", _temp)
    # then capture and fix digits not formatted to str
    _temp = re.sub(r"(?<=:)\d+", r"'\g<0>'", _temp)
    # then properly convert to list of json obj
    result = (_temp
              .replace('\'', '\"')
              .replace('},', '}')
              .replace(' {', '{')
              .strip()
              .split('\n'))
    return result


def find_ioc(hutch: str = None, patt: str = None,
             valid_hutch: list[str] = VALID_HUTCH) -> list[dict]:
    """
    A pythonic grep_ioc for gathering IOC details from the cfg file

    Parameters
    ----------
    hutch: str, optional
        3 letter lowercase hutch code. May also include 'all'.
        The default is None.
    patt: str, optional
        Regex pattern to search for. The default is None.
    valid_hutch: list[str], optional
        List of valid hutch codes to use. The default is taken
        from the directories in '/cds/group/pcds/pyps/config'

    Raises
    ------
    ValueError
        Hutch code is invalid or regex pattern is missing.

    Returns
    -------
    list[dict]
        List of dictionaries generated by the JSON loading

    """
    # check hutches
    if (hutch is None) | (hutch not in tuple(valid_hutch)):
        print('Invalid entry. Please choose a valid hutch:\n'
              + ','.join(valid_hutch))
        raise ValueError
    # create file paths
    if hutch in tuple(valid_hutch):
        if hutch == 'all':
            path = gb.glob('/cds/group/pcds/pyps/config/*/iocmanager.cfg')
        else:
            path = [f'/cds/group/pcds/pyps/config/{hutch}/iocmanager.cfg']
    # check patt and generate the regex pattern
    if patt is None:
        print('No regex pattern supplied')
        raise ValueError
    _patt = r'{.*' + patt + r'.*}'
    # initialize output list
    result = []
    # iterate and capture results.
    for _file in path:
        prefix = ''
        if len(path) != 1:
            prefix = _file+':'
        output = search_file(file=_file, patt=_patt, prefix=prefix)
        if output != prefix:
            result.append(output)
    # reconstruct the list of str
    _temp = ''.join(result)
    if len(_temp) == 0:
        print(f'{Fore.RED}No results found for {Style.RESET_ALL}{patt}'
              + f'{Fore.RED} in{Style.RESET_ALL} '
              + f'{hutch}')
        return None
    # capture the hutch from the cfg path if hutch = all
    if hutch == 'all':
        hutch_cfgs = re.findall(r'/.*cfg\:', _temp)
        hutch_cfgs = [''.join(re.findall(r'(?<=/)\w+(?=/ioc)', s))
                      for s in hutch_cfgs]
    # strip the file information
    _temp = re.sub(r'.*cfg\:', '', _temp)
    # now convert back to json and load
    output = [json.loads(s) for s in fix_json(_temp)]
    # and add the hutches back into the dicts if searching across all cfgs
    if hutch == 'all':
        for _i, _d in enumerate(output):
            _d['hutch'] = hutch_cfgs[_i]
    return output


def fix_dir(dir_path: str) -> str:
    """
    Simple function for repairing the child release IOC path based on
    the ioc_cfg output. Returns the proper dir for the child IOC.cfg file.

    Parameters
    ----------
    dir_path : str
        The path to the child IOC's directory as a str.

    Returns
    -------
    str
        The typo-corrected path as a str.

    """

    # catches the short form path
    if dir_path.startswith('ioc/'):
        output_dir = '/cds/group/pcds/epics/'+dir_path
    # for the rare, old child IOCs that only exist in their parent's release
    elif 'common' in dir_path:
        output_dir = dir_path + '/children'
    # Otherwise fine!
    else:
        output_dir = dir_path
    # Make sure the end of the path is a folder!
    if output_dir[-1] != '/':
        output_dir += '/'
    return output_dir


def find_parent_ioc(file: str, path: str) -> str:
    """
    Searches the child IOC for the parent's release pointer
    Returns the parent's IOC as a str.

    Parameters
    ----------
    file : str, optional
        DESCRIPTION. The default is None.
    path : str, optional
        DESCRIPTION. The default is None.

    Returns
    -------
    str
        Path to the parent IOC's release.

    """
    file_dir = fix_dir(path)
    if os.path.exists(f'{file_dir}{file}.cfg') is False:
        return 'Invalid. Child does not exist.'
    parent_ioc_release = search_file(file=f'{file_dir}{file}.cfg',
                                     patt='^RELEASE').strip()
    return parent_ioc_release.rsplit('=', maxsplit=1)[-1]


def print_frame2term(dataframe: pd.DataFrame = None,):
    """Wrapper for displaying the dataframe to proper terminal size"""
    with pd.option_context('display.max_rows', None,
                           'display.max_columns', None,
                           'display.width',
                           get_terminal_size(fallback=(120, 50))[0],
                           ):
        print(dataframe)

###############################################################################
# %% Arg Parser
###############################################################################


def build_parser():
    """
    Builds the parser & subparsers for the main function
    """
    # parser obj configuration
    parser = argparse.ArgumentParser(
        prog='grep_more_ioc',
        description='Transforms grep_ioc output to json object'
                    + ' and prints in pandas.DataFrame',
        epilog='With extra utilities for daily ECS work.')
    # main command arguments
    parser.add_argument('patt', type=str)
    parser.add_argument('hutch', type=str)
    parser.add_argument('-d', '--ignore_disabled',
                        action='store_true',
                        default=False,
                        help='Flag for excluding based'
                        + ' on the "disabled" state.')
    # subparsers
    subparsers = parser.add_subparsers(
        help='Follow-up commands after grep_ioc executes'
        )
# --------------------------------------------------------------------------- #
# print subarguments
# --------------------------------------------------------------------------- #
    print_frame = (subparsers
                   .add_parser('print',
                               help='Just a simple print of the dataframe'
                               + ' to the terminal.'))

    print_frame.add_argument('print',
                             action='store_true', default=False)

    print_frame.add_argument('-c', '--skip_comments', action='store_true',
                             default=False,
                             help='Prints the IOC.cfg'
                             + ' file with comments skipped')

    print_frame.add_argument('-r', '--release', action='store_true',
                             default=False,
                             help="Adds the parent IOC's"
                             + " release to the dataframe")

    print_frame.add_argument('-s', '--print_dirs', action='store_true',
                             default=False,
                             help='Prints the child & parent IOC'
                             + ' directories as the final output')
# --------------------------------------------------------------------------- #
# search subarguments
# --------------------------------------------------------------------------- #
    search = subparsers.add_parser('search',
                                   help='For using regex-like searches in the'
                                   + ' child IOC.cfg captured by grep_ioc.'
                                   + ' Useful for quickly gathering instance'
                                   + ' information, IP addr, etc.')

    search.add_argument('search',
                        type=str, help='PATT to use for regex search in file',
                        metavar='PATT')
    search.add_argument('-q', '--quiet', action='store_true', default=False,
                        help='Surpresses file warning for paths that do not'
                        + ' exist.')
    search.add_argument('-o', '--only_search', action='store_true',
                        default=False,
                        help="Don't print the dataframe, just search results.")
    return parser

###############################################################################
# %% Main
###############################################################################


def main():
    """
    Main entry point of the program. For using with CLI tools.
    """
    parser = build_parser()
    args = parser.parse_args()
    # read grep_ioc output
    data = find_ioc(args.hutch, args.patt)

    # exit if grep_ioc finds nothing
    if (data is None or len(data) == 0):
        print(f'{Fore.RED}No IOCs were found.\nExiting . . .{Style.RESET_ALL}')
        sys.exit()

    # create the dataframe after fixing the json format
    df = pd.json_normalize(data)

    # reorder the dataframe if searching all hutches
    if args.hutch == 'all':
        df.insert(0, 'hutch', df.pop('hutch'))

    # pad the disable column based on the grep_ioc output
    if 'disable' not in df.columns:
        df['disable'] = df.index.size*[False]
    if 'disable' in df.columns:
        df.disable.fillna(False, inplace=True)

    # Fill the NaN with empty strings for rarely used keys
    for _col in df.columns:
        if _col not in ['delay']:
            df[_col].fillna('', inplace=True)
        else:
            df[_col].fillna(0, inplace=True)

    # check for the ignore_disabled flag
    if args.ignore_disabled is True:
        df = df[~df.disable].reset_index(drop=True)

# --------------------------------------------------------------------------- #
# %%% print
# --------------------------------------------------------------------------- #
    # print the dataframe
    if hasattr(args, 'print'):
        if args.release is True:
            # intialize list for adding a new column
            output_list = []
            # iterate through ioc and directory pairs
            for f, d in df.loc[:, ['id', 'dir']].values:
                search_result = find_parent_ioc(f, d)
                # catch parent IOCs running out of dev
                if 'epics-dev' in search_result:
                    output_str = search_result
                # abbreviate path for standard IOC releases
                elif 'common' in search_result:
                    output_str = (search_result
                                  .rsplit(r'common/', maxsplit=1)[-1])
                # check for children living in parent's dir
                elif '$$UP(PATH)' in search_result:
                    output_str = d.rsplit(r'/children', maxsplit=1)[0]
                # else use the full path that's found
                else:
                    output_str = search_result
                # add it to the list
                output_list.append(output_str)
            # Then, finally, add the column to the dataframe
            df['Release Version'] = output_list
            # put it next to the child dirs
            df.insert(df.columns.tolist().index('dir')+1,
                      'Release Version',
                      df.pop('Release Version'))

        print_frame2term(df)

        if args.skip_comments is True:
            for ioc, d in df.loc[:, ['id', 'dir']].values:
                # fixes dirs if ioc_manager truncates the path due to
                # common ioc dir path
                target_dir = fix_dir(d)
                print(f'{Fore.LIGHTBLUE_EX}Now in: {target_dir}'
                      + Style.RESET_ALL)
                print(f'{Fore.LIGHTYELLOW_EX}{ioc}:{Style.RESET_ALL}')
                # prints the contents of the file while ignoring comments
                print_skip_comments(file=f'{target_dir}{ioc}.cfg')

        if args.print_dirs is True:
            print(f'{Fore.LIGHTBLUE_EX}\nDumping directories:\n'
                  + Style.RESET_ALL)
            for f, d in df.loc[:, ['id', 'dir']].values:
                search_result = find_parent_ioc(f, d)
                d = fix_dir(d)
                # check for cases where child IOC.cfg DNE
                if not os.path.exists(f'{d}{f}.cfg'):
                    child_ioc = ''
                    color_prefix = Fore.LIGHTRED_EX
                else:
                    child_ioc = f'{f}.cfg'
                    color_prefix = Fore.LIGHTBLUE_EX
                # Print this for easier cd / pushd shenanigans
                print(f'{d}{Fore.LIGHTYELLOW_EX}{child_ioc}{Style.RESET_ALL}'
                      + '\n\t\t|-->'
                      + f'{Fore.LIGHTGREEN_EX}RELEASE={Style.RESET_ALL}'
                      + f'{color_prefix}{search_result}{Style.RESET_ALL}'
                      )

# --------------------------------------------------------------------------- #
# %%% search
# --------------------------------------------------------------------------- #
    # do a local grep on each file in their corresponding directory
    if hasattr(args, 'search'):
        # optionally print the dataframe
        if not args.only_search:
            print_frame2term(df)
        check_search = []
        for ioc, d in df.loc[:, ['id', 'dir']].values:
            target_dir = fix_dir(d)
            # Search for pattern after moving into the directory
            if args.search is not None:
                search_result = (search_file(file=f'{target_dir}{ioc}.cfg',
                                             patt=args.search,
                                             color_wrap=Fore.LIGHTRED_EX,
                                             quiet=args.quiet)
                                 .strip()
                                 )
                if len(search_result) > 0:
                    print(f'{Fore.LIGHTYELLOW_EX}{ioc}:{Style.RESET_ALL}')
                    print(''.join(search_result.strip()))
                    check_search.append(len(search_result))
        if len(check_search) == 0:
            print(Fore.RED + 'No search results found' + Style.RESET_ALL)
# --------------------------------------------------------------------------- #
# %%% Exit
# --------------------------------------------------------------------------- #
    sys.exit()


# --------------------------------------------------------------------------- #
# %%% Entry point
# --------------------------------------------------------------------------- #
if __name__ == '__main__':
    main()
