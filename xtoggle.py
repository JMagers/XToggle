#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

# Constants
XORG_CONF = '/etc/X11/xorg.conf'
MONITORS_XML = os.path.join(os.environ['HOME'], '.config', 'monitors.xml')
XRANDR = 'xrandr'
NVIDIA = 'nvidia'

# Arguments
parser = argparse.ArgumentParser()
parser.add_argument('--nvidia', '-n',
                    action='store_true',
                    help='use nvidia-settings instead of xrandr to apply '
                         'changes (%s must be configured)' % XORG_CONF)
parser.add_argument('--verbose', '-v',
                    action='store_true',
                    help='print the command used to apply the changes '
                         'specified')
parser.add_argument('--norun',
                    action='store_true',
                    help='like --verbose but changes will not be applied')
STATUS_FLAG_NAMES = ('--status', '-s')
parser.add_argument(*STATUS_FLAG_NAMES,
                    action='store_true',
                    help='print status of monitors')
actions = parser.add_subparsers(title='actions', dest='action')

TARGET_HELP = ('position of target monitor to apply action to starting at 1 '
               'from left to right')

# Toggle action
parser_toggle = actions.add_parser('toggle', help='toggle target monitor')
parser_toggle.add_argument('target', type=int, help=TARGET_HELP)

# Enable action
parser_enable = actions.add_parser('enable', help='enable target monitor')
parser_enable.add_argument('target', type=int, help=TARGET_HELP)

# Disable action
parser_disable = actions.add_parser('disable',
                                    help='disable target monitor')
parser_disable.add_argument('target', type=int, help=TARGET_HELP)

# Enable-all action
parser_enable_all = actions.add_parser('enable-all',
                                       help='enable all monitors')

# Toggle-only action
parser_toggle_only = actions.add_parser('toggle-only',
                                        help='toggle wheather or not the '
                                             'target monitor is the only '
                                             'one on')
parser_toggle_only.add_argument('target', type=int, help=TARGET_HELP)

# Enable-only action
parser_enable_only = actions.add_parser('enable-only',
                                        help='make target monitor the only '
                                             'one on')
parser_enable_only.add_argument('target', type=int, help=TARGET_HELP)

# Make actions optional if --status flag is the only argument
if len(sys.argv) == 2 and sys.argv[1] in STATUS_FLAG_NAMES:
    actions.required = False
else:
    actions.required = True

args = parser.parse_args()


class Monitor:
    def __init__(self):
        self.name = None
        self.xpos = None
        self.ypos = None
        self.rank = None
        self.width = None
        self.height = None
        self.rate = None
        self.is_enabled = None
        self.metamodes = None

    def get_new_metamodes(self):
        """
        Return metamodes where original xpos is replaced with newly
        calculated value
        """
        metamodes_split = self.metamodes.split('+')
        metamodes_split[1] = str(self.xpos)
        return '+'.join(metamodes_split)

    def print_info(self):
        connected_status = 'ON' if self.is_enabled else 'OFF'
        print("%s, connection: %s, position: %d"
              % (self.name, connected_status, self.rank))


def command_available(command):
    """ Return wheather or not the given command could be run """
    try:
        subprocess.run(command,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except (FileNotFoundError, PermissionError):
        return False
    return True


# Check that system meets requirements
session_type = subprocess.check_output('printf $XDG_SESSION_TYPE', shell=True)
if session_type != b'x11':
    sys.exit("Xorg is not being used!")
if not command_available(['xrandr', '-v']):
    sys.exit("xrandr is not installed or could not be run!")
if args.nvidia and not command_available(['nvidia-settings', '-v']):
    sys.exit("nvidia-settings is not installed or could not be run!")

# Get all connected monitors
monitor_info = subprocess.check_output(['xrandr', '-q'],
                                       universal_newlines=True)
connected_re = re.compile(r'^(?P<name>\S+) connected (?:primary )?'
                          r'(?P<other>.*)')
enabled_re = re.compile(r'^\d+x\d+\+\d+\+\d+')
monitors = {}
for line in monitor_info.splitlines():
    monitor = Monitor()
    connected_match = re.match(connected_re, line)
    try:
        monitor.name = connected_match.group('name')
    except AttributeError:
        continue
    enabled_match = re.match(enabled_re, connected_match.group('other'))
    monitor.is_enabled = bool(enabled_match)
    monitors[monitor.name] = monitor

# Parse nvidia xorg config file for metamodes settings
if args.nvidia:
    found_monitors = set()
    try:
        with open(XORG_CONF, 'r') as conf:
            all_metamodes_re = re.compile(r'Option\s+"metamodes"\s*"(.+?)"')
            for line in conf:
                all_metamodes_match = re.search(all_metamodes_re, line)
                try:
                    all_metamodes_str = all_metamodes_match.group(1)
                except AttributeError:
                    continue
                for metamodes_str in all_metamodes_str.split(','):
                    try:
                        name = metamodes_str.split(':')[0].strip()
                    except IndexError:
                        sys.exit("Missing monitor name in '%s' metamodes!"
                                 % XORG_CONF)
                    try:
                        monitors[name].metamodes = metamodes_str.strip()
                    except KeyError:
                        sys.exit("'%s' metamodes contains a disconnected "
                                 "monitor!" % XORG_CONF)
                    if name in found_monitors:
                        sys.exit("'%s' metamodes contains multiple entries ",
                                 "for monitor '%s'!" % (XORG_CONF, name))
                    found_monitors.add(monitor.name)
            if not monitors:
                sys.exit("No monitors found in '%s' metamodes!" % XORG_CONF)
    except IOError:
        sys.exit("'%s' does not exist or could not be read!" % XORG_CONF)

# Get dimensions, rate, position, and primary status of each monitor
original_primary = None
try:
    tree = ET.parse(MONITORS_XML)
except IOError:
    sys.exit("'%s' does not exist or could not be read!" % MONITORS_XML)
for monitor_tag in tree.findall('.//configuration/logicalmonitor'):
    name = monitor_tag.find('monitor/monitorspec/connector').text
    try:
        monitor = monitors[name]
    except KeyError:
        continue

    # Get dimensions and rate
    try:
        monitor.width = int(monitor_tag.find('monitor/mode/width').text)
        monitor.height = int(monitor_tag.find('monitor/mode/height').text)
        monitor.rate = float(monitor_tag.find('monitor/mode/rate').text)
    except AttributeError:
        sys.exit("Monitor, '%s', has no width/height/rate tag(s) in '%s'!"
                 % (name, MONITORS_XML))
    except ValueError:
        sys.exit("Width/height/rate tag(s) for monitor, '%s', in '%s' are not "
                 "of correct numeric type!" % (name, MONITORS_XML))

    # Get primary status
    try:
        primary_status = monitor_tag.find('primary').text
        original_primary = monitor if primary_status == 'yes' else None
    except AttributeError:
        pass

    # Get position
    try:
        monitor.xpos = int(monitor_tag.find('x').text)
        monitor.ypos = int(monitor_tag.find('y').text)
    except AttributeError:
        sys.exit("Monitor, '%s', is missing x/y positions in '%s'!"
                 % (name, MONITORS_XML))
    except ValueError:
        sys.exit("x/y position tags for monitor, '%s', in '%s' are not "
                 "integers!" % (name, MONITORS_XML))

# Check that all monitor information was found
for name, monitor in monitors.items():
    if None in (monitor.width, monitor.height, monitor.rate, monitor.xpos):
        sys.exit("Could not find info for monitor, '%s', in '%s'!"
                 % (name, MONITORS_XML))
if original_primary is None:
    print("No connected monitor is designated as the primary monitor in %s!\n"
          "The first enabled monitor will be used as the primary."
          % MONITORS_XML,
          file=sys.stderr)

# Sort monitors by their positions and apply ranks
sorted_monitors = sorted(monitors.values(), key=lambda x: x.xpos)
for i, monitor in enumerate(sorted_monitors):
    monitor.rank = i + 1


def get_new_primary(monitors, original_primary):
    if original_primary and original_primary.is_enabled:
        return original_primary
    return get_enabled(monitors)[0]


def print_monitors(monitors):
    """ Print info about each monitor """
    for i, monitor in enumerate(monitors):
        monitor.print_info()


def recalculate_positions(monitors):
    """ Recalculate positions of monitors based on widths and order of list """
    total_width = 0
    for monitor in get_enabled(monitors):
        monitor.xpos = total_width
        total_width += monitor.width


def create_nvidia_command(monitors, primary):
    """ Generate nvidia command to apply changes to monitors """
    METAMODES_SEP = ', '
    all_metamodes = []
    for monitor in get_enabled(monitors):
        all_metamodes.append(monitor.get_new_metamodes())
    args = (
        'nvidia-settings',
        '--assign CurrentMetaMode="%s"' % METAMODES_SEP.join(all_metamodes),
        '--assign XineramaInfoOrder="%s"' % primary.name,
    )
    return ' '.join(args)


def create_xrandr_command(monitors, primary):
    """ Generate xrandr command to apply changes to monitors """
    all_options = []
    for monitor in monitors:
        output = '--output \'%s\'' % monitor.name
        if monitor.is_enabled:
            mode = '--mode %dx%d' % (monitor.width, monitor.height)
            rate = '--rate %.2f' % monitor.rate
            pos = '--pos %dx%d' % (monitor.xpos, monitor.ypos)
            primary_opt = '--primary' if monitor is primary else None
            options_list = filter(None, [output, mode, rate, pos, primary_opt])
            options = ' '.join(options_list)
        else:
            options = output + ' --off'
        all_options.append(options)
    return 'xrandr ' + ' '.join(all_options)


def create_command(monitors, primary, manager):
    """
    Create command to apply changes with specified manager.
    Manager can be 'xrandr' or 'nvidia'.
    """
    if not get_enabled(monitors):
        sys.exit("At least one enabled monitor is required!")

    if manager == XRANDR:
        return create_xrandr_command(monitors, primary)
    elif manager == NVIDIA:
        return create_nvidia_command(monitors, primary)
    else:
        raise ValueError("Incorrect manager specified. "
                         "Must be '%s' or '%s'" % (XRANDR, NVIDIA))


def apply_changes(command):
    """ Run given command to apply changes to monitors. """
    try:
        subprocess.run(command,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       check=True,
                       shell=True)
    except subprocess.CalledProcessError:
        sys.exit("The following command returned non-zero exit status:\n%s"
                 % command)


def only_target(monitors, target):
    """ Enable target monitor and disable others """
    for monitor in monitors:
        monitor.is_enabled = False
    target.is_enabled = True


def enable_all(monitors):
    """ Enable all monitors """
    for monitor in monitors:
        monitor.is_enabled = True


def get_enabled(monitors):
    """ Return a new list of all enabled monitors """
    return [mon for mon in monitors if mon.is_enabled]


# Check if args.target is acceptable
try:
    if 0 < args.target <= len(sorted_monitors):
        target = sorted_monitors[args.target - 1]
    else:
        sys.exit("Target must be a number between 1 and the number of "
                 "monitors configured!")
except AttributeError:
    target = None

# Enable or disable monitor objects based on chosen action
if args.action == 'toggle':
    target.is_enabled = not target.is_enabled
elif args.action == 'enable':
    target.is_enabled = True
elif args.action == 'disable':
    target.is_enabled = False
elif args.action == 'enable-all':
    enable_all(sorted_monitors)
elif args.action == 'toggle-only':
    if target.is_enabled and len(get_enabled(sorted_monitors)) == 1:
        enable_all(sorted_monitors)
    else:
        only_target(sorted_monitors, target)
elif args.action == 'enable-only':
    only_target(sorted_monitors, target)

if args.action is not None:
    recalculate_positions(sorted_monitors)
    manager = NVIDIA if args.nvidia else XRANDR
    new_primary = get_new_primary(sorted_monitors, original_primary)
    command = create_command(sorted_monitors, new_primary, manager)
    if args.norun or args.verbose:
        print(command)
    if not args.norun:
        apply_changes(command)

if args.status:
    print_monitors(sorted_monitors)
