#!/usr/bin/env python3.5

import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

CONFIG_PATH = '/etc/X11/xorg.conf'
MONITORS_XML = os.path.join(os.environ['HOME'], '.config', 'monitors.xml')


class Monitor:
    def __init__(self, info):
        self.info = info.strip()
        self.name = info.split(':')[0].strip()
        self.pos = int(info.split('+')[1])
        self.width = None
        self.is_connected = None


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
