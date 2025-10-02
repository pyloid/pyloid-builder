#!/usr/bin/env python3
"""Test script for the new rich UI optimizer"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pyloid_builder.optimizer import optimize

# Test the optimizer with the existing test1 build
if __name__ == '__main__':
	print('Testing optimizer with rich UI...')
	optimize('test1', 'dist', ['*.dll'])
