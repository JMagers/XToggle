#!/usr/bin/env python3.5

import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

# Constants
CONFIG_PATH = '/etc/X11/xorg.conf'
MONITORS_XML = os.path.join(os.environ['HOME'], '.config', 'monitors.xml')

# Arguments
parser = argparse.ArgumentParser()
parser.add_argument('action',
                    choices=['toggle', 'enable', 'disable', 'toggle-only',
                             'enable-only'],
                    help='action to apply to target monitor')
parser.add_argument('target',
                    type=int,
                    help='position of target monitor to apply action to '
                         'starting at 1 from left to right')
parser.add_argument('--verbose', '-v',
                    action='store_true',
                    help='print the command used to apply the settings '
                         'specified')
parser.add_argument('--status', '-s',
                    action='store_true',
                    help='print status of monitors')
args = parser.parse_args()


class Monitor:
    def __init__(self, command):
        self._command = command.strip()
        self.name = command.split(':')[0].strip()
        self.pos = int(command.split('+')[1])
        self.width = None
        self.is_connected = None

    def get_command(self):
        command_split = self._command.split('+')
        command_split[1] = str(self.pos)
        return '+'.join(command_split)

    def print_info(self):
        print("Name: %s" % self.name)
        print("Position: %d" % self.pos)
        print("Width: %d" % self.width)
        print("Command: '%s'" % self.get_command())
        print("Connected: %s" % self.is_connected)


# Parse config file for monitor info
monitors = {}
try:
    with open(CONFIG_PATH, 'r') as conf:
        for line in conf:
            settings_match = re.search(r'Option\s+"metamodes"\s*"(.+)"', line)
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
    sys.exit("'%s' does not exist!" % CONFIG_PATH)

# Get width of each monitor
tree = ET.parse(MONITORS_XML)
for output_tag in tree.findall('.//configuration/output'):
    try:
        name = output_tag.attrib['name']
        monitor = monitors[name]
    except KeyError:
        continue
    try:
        monitor.width = int(output_tag.find('width').text)
    except AttributeError:
        sys.exit("Monitor, '%s', has no width tag in '%s'!"
                 % (name, MONITORS_XML))
    except ValueError:
        sys.exit("Width tag for monitor, '%s', in '%s' is not an integer!"
                 % (name, MONITORS_XML))

# Check that all monitor widths were found
for name, monitor in monitors.items():
    if monitor.width is None:
        sys.exit("Could not find info for monitor, '%s', in '%s'!"
                 % (name, MONITORS_XML))

# Find out which monitors are currently connected
p = subprocess.run(['xrandr', '-q'],
                   stdout=subprocess.PIPE,
                   universal_newlines=True)
for name, monitor in monitors.items():
    query = monitor.name + r' connected (primary )?\d+x\d+\+\d+\+\d+'
    monitor.is_connected = bool(re.search(query, p.stdout))

# Sort monitors by their positions
sorted_monitors = sorted(monitors.values(), key=lambda x: x.pos)
target = sorted_monitors[args.target - 1]


def print_monitors(monitors):
    """ Print info about each monitor """
    for monitor in monitors:
        monitor.print_info()
        print()


def recalculate_positions(monitors):
    """ Recalculate positions of monitors based on widths and order of list """
    total_width = 0
    for monitor in monitors:
        monitor.pos = total_width
        total_width += monitor.width


def apply_changes(monitors):
    """ Run nvidia command to apply changes """
    SEP = ', '  # Seperator
    info = ''
    for monitor in monitors:
        if monitor.is_connected:
            info += monitor.get_command() + SEP
    command = 'nvidia-settings --assign CurrentMetaMode="%s"' % info.strip(SEP)
    subprocess.run(command, stdout=subprocess.DEVNULL, shell=True)
    if args.verbose:
        print(command)


def only_target(monitors, target):
    for monitor in monitors:
        monitor.is_connected = False
    target.is_connected = True


def enable_all(monitors):
    for monitor in monitors:
        monitor.is_connected = True


def filter_out_disconnected(monitors):
    return [mon for mon in sorted_monitors if mon.is_connected]


if args.status:
    print_monitors(sorted_monitors)

if args.action == 'toggle':
    target.is_connected = not target.is_connected
elif args.action == 'enable':
    target.is_connected = True
elif args.action == 'disable':
    target.is_connected = False
elif args.action == 'toggle-only':
    if (
        not target.is_connected
        or len(filter_out_disconnected(sorted_monitors)) > 1
    ):
        only_target(sorted_monitors, target)
    else:
        enable_all(sorted_monitors)
elif args.action == 'enable-only':
    only_target(sorted_monitors, target)

connected_monitors = filter_out_disconnected(sorted_monitors)
recalculate_positions(connected_monitors)
apply_changes(connected_monitors)
