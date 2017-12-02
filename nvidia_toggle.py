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

# Arguments
parser = argparse.ArgumentParser()
parser.add_argument('--verbose', '-v',
                    action='store_true',
                    help='print the command used to apply the settings '
                         'specified')
parser.add_argument('--status', '-s',
                    action='store_true',
                    help='print status of monitors')
subparsers = parser.add_subparsers(title='commands', dest='subparser')

TARGET_HELP = ('position of target monitor to apply action to starting at 1 '
               'from left to right')

# Toggle command
parser_toggle = subparsers.add_parser('toggle', help='toggle target monitor')
parser_toggle.add_argument('target', type=int, help=TARGET_HELP)

# Enable command
parser_enable = subparsers.add_parser('enable', help='enable target monitor')
parser_enable.add_argument('target', type=int, help=TARGET_HELP)

# Disable command
parser_disable = subparsers.add_parser('disable',
                                       help='disable target monitor')
parser_disable.add_argument('target', type=int, help=TARGET_HELP)

# Toggle-only command
parser_toggle_only = subparsers.add_parser('toggle-only',
                                           help='toggle wheather or not the '
                                                'target monitor is the only '
                                                'one on')
parser_toggle_only.add_argument('target', type=int, help=TARGET_HELP)

# Enable-only command
parser_enable_only = subparsers.add_parser('enable-only',
                                           help='Make target monitor the only '
                                                'one on')
parser_enable_only.add_argument('target', type=int, help=TARGET_HELP)

args = parser.parse_args()


class Monitor:
    def __init__(self, command):
        self._command = command.strip()
        self.name = command.split(':')[0].strip()
        self.xpos = None
        self.ypos = None
        self.rank = None
        self.width = None
        self.height = None
        self.is_enabled = None

    def get_command(self):
        command_split = self._command.split('+')
        command_split[1] = str(self.xpos)
        return '+'.join(command_split)

    def print_info(self):
        if self.is_enabled:
            connected_status = 'ON'
        else:
            connected_status = 'OFF'
        print("%s %s %d" % (self.name, connected_status, self.rank))


# Parse nvidia xorg config file for monitor info
monitors = {}
try:
    with open(XORG_CONF, 'r') as conf:
        for line in conf:
            settings_match = re.search(r'Option\s+"metamodes"\s*"(.+?)"', line)
            try:
                settings_string = settings_match.group(1)
            except AttributeError:
                continue
            for monitor_string in settings_string.split(','):
                monitor = Monitor(monitor_string)
                monitors[monitor.name] = monitor
        if not monitors:
            sys.exit("No monitors found!")
except FileNotFoundError:
    sys.exit("'%s' does not exist!" % XORG_CONF)

# Get dimensions and position of each monitor
tree = ET.parse(MONITORS_XML)
for monitor_tag in tree.findall('.//configuration/logicalmonitor'):
    name = monitor_tag.find('monitor/monitorspec/connector').text
    try:
        monitor = monitors[name]
    except KeyError:
        continue

    # Get dimensions
    try:
        monitor.width = int(monitor_tag.find('monitor/mode/width').text)
        monitor.height = int(monitor_tag.find('monitor/mode/height').text)
    except AttributeError:
        sys.exit("Monitor, '%s', has no width/height tag in '%s'!"
                 % (name, MONITORS_XML))
    except ValueError:
        sys.exit("Width/height tag for monitor, '%s', in '%s' is not an "
                 "integer!" % (name, MONITORS_XML))

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

# Check that all monitor dimensions and positions were found
for name, monitor in monitors.items():
    if None in (monitor.width, monitor.height, monitor.xpos):
        sys.exit("Could not find info for monitor, '%s', in '%s'!"
                 % (name, MONITORS_XML))

# Find out which monitors are currently enabled
p = subprocess.run(['xrandr', '-q'],
                   stdout=subprocess.PIPE,
                   universal_newlines=True)
for name, monitor in monitors.items():
    query = monitor.name + r' connected (primary )?\d+x\d+\+\d+\+\d+'
    monitor.is_enabled = bool(re.search(query, p.stdout))

# Sort monitors by their positions and apply ranks
sorted_monitors = sorted(monitors.values(), key=lambda x: x.xpos)
for i, monitor in enumerate(sorted_monitors):
    monitor.rank = i + 1


def print_monitors(monitors):
    """ Print info about each monitor """
    for monitor in monitors:
        monitor.print_info()
        print()


def recalculate_positions(monitors):
    """ Recalculate positions of monitors based on widths and order of list """
    total_width = 0
    for monitor in filter_out_disabled(monitors):
        monitor.xpos = total_width
        total_width += monitor.width


def create_nvidia_command(monitors):
    """ Generate nvidia command to apply changes to monitors """
    SEP = ', '  # Seperator
    info = ''
    for monitor in filter_out_disabled(monitors):
        info += monitor.get_command() + SEP
    return 'nvidia-settings --assign CurrentMetaMode="%s"' % info.strip(SEP)


def create_xrandr_command(monitors):
    """ Generate xrandr command to apply changes to monitors """
    monitor_settings = []
    for monitor in monitors:
        output = '--output %s' % monitor.name
        if monitor.is_enabled:
            mode = '--mode %dx%d' % (monitor.width, monitor.height)
            pos = '--pos %dx%d' % (monitor.xpos, monitor.ypos)
            monitor_setting = ' '.join([output, mode, pos])
        else:
            monitor_setting = output + ' --off'
        monitor_settings.append(monitor_setting)
    return 'xrandr ' + ' '.join(monitor_settings)


def apply_changes(monitors):
    """ Run commands to apply changes """
    # TODO: Add option to use xrandr instead
    command = create_nvidia_command(monitors)
    subprocess.run(command, stdout=subprocess.DEVNULL, shell=True)
    if args.verbose:
        print(command)


def only_target(monitors, target):
    for monitor in monitors:
        monitor.is_enabled = False
    target.is_enabled = True


def enable_all(monitors):
    for monitor in monitors:
        monitor.is_enabled = True


def filter_out_disabled(monitors):
    return [mon for mon in sorted_monitors if mon.is_enabled]


try:
    if 0 < args.target <= len(sorted_monitors):
        target = sorted_monitors[args.target - 1]
    else:
        sys.exit("Target must be a number between 1 and the number of "
                 "monitors configured!")
except AttributeError:
    target = None

if args.subparser == 'toggle':
    target.is_enabled = not target.is_enabled
elif args.subparser == 'enable':
    target.is_enabled = True
elif args.subparser == 'disable':
    target.is_enabled = False
elif args.subparser == 'toggle-only':
    if (
        not target.is_enabled
        or len(filter_out_disabled(sorted_monitors)) > 1
    ):
        only_target(sorted_monitors, target)
    else:
        enable_all(sorted_monitors)
elif args.subparser == 'enable-only':
    only_target(sorted_monitors, target)

if target is not None:
    recalculate_positions(sorted_monitors)
    apply_changes(sorted_monitors)

if args.status:
    print_monitors(sorted_monitors)
