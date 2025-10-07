#!/usr/bin/env python3
"""Test script for the new rich UI optimizer"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pyloid_builder.optimize import optimize

# Test the optimizer with the existing test1 build
if __name__ == '__main__':
	print('Testing optimizer with rich UI...')

	# Create a simple spec file for testing
	spec_content = '''# Test spec for test1 build
*.dll
!python3.dll
'''

	spec_file = 'test1_optimize.spec'
	with open(spec_file, 'w') as f:
		f.write(spec_content)

	try:
		optimize('build/test1', spec_file)
	except Exception as e:
		print(f'Optimization failed: {e}')
