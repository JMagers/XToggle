# XToggle
Easily toggle the state of your individual monitors in your multi-monitor setup between enabled and disabled.
## Dependencies
GNOME 3.26

Python 3.5+

Must be using X.Org and not Wayland

~/.config/monitors.xml must be generated (automatically done after making any changes to display settings)
## Usage
Monitors are identified by numbers starting from 1 to N where N is the number of connected monitors. Monitors are given their id based on their horizontal positions in your workspace (leftmost monitor is 1, next to the right is 2, etc...).

Examples:

Toggle the state of the monitor at position 1
```
./xtoggle.py toggle 1
```
Enable
```
./xtoggle.py enable 1
```
Disable
```
./xtoggle.py disable 1
```
Make your second monitor from the left the only one on
```
./xtoggle.py enable-only 2
```
Toggle wheather or not your second monitor is the only one on
```
./xtoggle.py toggle-only 2
```

## Nvidia Users
If you need the "metamodes" settings in your /etc/X11/xorg.conf file to take effect then you can choose to have your displays changed via nvidia-settings instead of xrandr by using the --nvidia/-n flag. This is useful if you have settings specific to nvidia like "ForceCompositionPipeline = On".

Example:

```
./xtoggle.py -n enable-only 2
```

## Best Practices
Set keyboard shortcuts to your most commonly used commands to easily change states at the press of a button.

Want to watch a movie on your third monitor but don't want your other monitors light distracting you.

Set the following command to a nice useless button like 'Pause Break' or 'Scroll Lock'
```
/path/to/xtoggle.py toggle-only 3
```
Press your button and monitor 3 will be the only one on.

Another press and all your other monitors will turn back on.
