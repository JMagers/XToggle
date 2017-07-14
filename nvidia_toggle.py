#!/usr/bin/env python3.5

import os
import re
import subprocess
import sys

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
monitors = []
try:
    with open(CONFIG_PATH, 'r') as conf:
        for line in conf:
            settings_match = re.search(r'Option\s+"metamodes"\s*"(.+)"', line)
            try:
                settings_string = settings_match.group(1)
            except AttributeError:
                continue
            for monitor_string in settings_string.split(','):
                monitors.append(Monitor(monitor_string))
        if not monitors:
            sys.exit("No monitors found.")
except FileNotFoundError:
    sys.exit("'%s' does not exist" % CONFIG_PATH)

# Find out which monitors are currently connected
p = subprocess.run(['xrandr', '-q'],
                   stdout=subprocess.PIPE,
                   universal_newlines=True)
for monitor in monitors:
    query = monitor.name + r' connected (primary )?\d+x\d+\+\d+\+\d+'
    monitor.is_connected = bool(re.search(query, p.stdout))

# Get width of each monitor
with open(MONITORS_XML, 'r') as xml:
    text = xml.read()
    for monitor in monitors:
        query = r'name="' + monitor.name + r'"[.\s\S]*?<width>(\d+)</width>'
        monitor.width = int(re.search(query, text).group(1))
