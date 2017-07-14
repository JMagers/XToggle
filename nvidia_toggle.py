#!/usr/bin/env python3.5

import re
import sys

CONFIG_PATH = '/etc/X11/xorg.conf'

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
                monitor_elements = monitor_string.split(':')
                mon_id, mon_setting = [x.strip() for x in monitor_elements]
                monitors[mon_id] = mon_setting
        if not monitors:
            sys.exit("No monitors found.")
except FileNotFoundError:
    sys.exit("'%s' does not exist" % CONFIG_PATH)

# Get set of connected monitors
connected_monitors = set()
