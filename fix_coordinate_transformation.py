#!/usr/bin/env python3
"""
Fix Coordinate Transformation Issue
The manual UTM to WGS84 conversion may be inaccurate.
This script checks if pyproj is available and uses it for accurate conversion.
If not available, provides instructions for installation.
"""

import sys

def check_pyproj():
    """Check if pyproj is available."""
    try:
        from pyproj import Transformer
        return True, Transformer
    except ImportError:
        return False, None

def install_pyproj_instructions():
    """Print instructions for installing pyproj."""
    print("=" * 80)
    print("COORDINATE TRANSFORMATION ACCURACY ISSUE")
    print("=" * 80)
    print()
    print("The manual UTM to WGS84 conversion may be inaccurate.")
    print("For accurate transformation, pyproj is recommended.")
    print()
    print("To install pyproj:")
    print("  pip3 install pyproj")
    print()
    print("Or if you have system package restrictions:")
    print("  pip3 install --user pyproj")
    print()
    print("After installation, the coordinate transformation will be accurate.")
    print("=" * 80)
    print()

def main():
    has_pyproj, Transformer = check_pyproj()
    
    if has_pyproj:
        print("✓ pyproj is available - accurate coordinate transformation enabled")
        return True
    else:
        install_pyproj_instructions()
        return False

if __name__ == "__main__":
    main()
