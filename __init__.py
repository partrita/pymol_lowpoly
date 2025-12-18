'''
PyMOL Low Poly Plugin
(c) 2024
'''

from __future__ import absolute_import

def __init_plugin__(app=None):
    '''
    Add an entry to the PyMOL "Plugin" menu
    '''
    # We might not need a menu item for a command-only plugin, 
    # but it's good practice or we can just import the command.
    pass

# Import the command to register it with PyMOL
import sys
import os

# Ensure local dir is in path for import if needed (usually PyMOL handles this for plugins)
# but explicitly importing the file registers the command because of the cmd.extend call at the bottom of lowpoly.py
try:
    from . import lowpoly
except ImportError:
    # If pymol is not found (e.g. during testing setup), we silence the error
    # so that pytest can collect files. The tests will mock pymol appropriately.
    pass
