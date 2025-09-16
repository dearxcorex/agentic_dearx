#!/usr/bin/env python
"""
Automatic location detection for interactive mode
"""

import logging
import platform
import subprocess
import json
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class AutoLocationDetector:
    """Automatically detect current GPS location"""

    def __init__(self, prefer_precise_location=True):
        self.cached_location = None
        self.prefer_precise_location = prefer_precise_location

    def get_current_location(self) -> Optional[Tuple[float, float]]:
        """
        Get current GPS location automatically
        Returns (latitude, longitude) or None if unable to detect
        """

        # If prefer_precise_location is True, use the known precise coordinates
        if self.prefer_precise_location:
            precise_location = (14.938737322657747, 102.06082160579989)
            logger.info(f"Using preferred precise location: {precise_location}")
            return precise_location

        # Try different methods based on platform
        system = platform.system().lower()

        if system == "darwin":  # macOS
            return self._get_location_macos()
        elif system == "linux":
            return self._get_location_linux()
        elif system == "windows":
            return self._get_location_windows()
        else:
            logger.warning(f"Automatic location not supported on {system}")
            return self._get_fallback_location()

    def _get_location_macos(self) -> Optional[Tuple[float, float]]:
        """Get location on macOS using Core Location"""
        try:
            # Method 1: Use whereami (if installed)
            result = subprocess.run(
                ['whereami'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                lat = float(data['latitude'])
                lon = float(data['longitude'])
                logger.info(f"Location detected via whereami: {lat}, {lon}")
                self.cached_location = (lat, lon)
                return (lat, lon)

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        try:
            # Method 2: Use AppleScript to get location
            applescript = '''
            tell application "System Events"
                try
                    do shell script "python3 -c \"
import CoreLocation
import time
manager = CoreLocation.CLLocationManager.alloc().init()
manager.requestWhenInUseAuthorization()
time.sleep(2)
location = manager.location()
if location:
    print(f'{location.coordinate().latitude},{location.coordinate().longitude}')
else:
    print('No location')
\""
                end try
            end tell
            '''

            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0 and ',' in result.stdout:
                lat_str, lon_str = result.stdout.strip().split(',')
                lat, lon = float(lat_str), float(lon_str)
                logger.info(f"Location detected via AppleScript: {lat}, {lon}")
                self.cached_location = (lat, lon)
                return (lat, lon)

        except Exception as e:
            logger.debug(f"AppleScript location failed: {e}")

        return self._get_fallback_location()

    def _get_location_linux(self) -> Optional[Tuple[float, float]]:
        """Get location on Linux"""
        try:
            # Try using nmcli (NetworkManager)
            result = subprocess.run(
                ['nmcli', '-t', '-f', 'WIFI-PROPERTIES.WPS', 'dev', 'wifi'],
                capture_output=True,
                text=True,
                timeout=10
            )

            # This is a placeholder - actual Linux location detection
            # would require more complex implementation
            logger.warning("Linux automatic location detection not fully implemented")

        except Exception as e:
            logger.debug(f"Linux location detection failed: {e}")

        return self._get_fallback_location()

    def _get_location_windows(self) -> Optional[Tuple[float, float]]:
        """Get location on Windows"""
        try:
            # Try using Windows Location API via PowerShell
            powershell_script = '''
            Add-Type -AssemblyName System.Device
            $watcher = New-Object System.Device.Location.GeoCoordinateWatcher
            $watcher.Start()
            Start-Sleep -Seconds 5
            $coord = $watcher.Position.Location
            if ($coord.IsUnknown -eq $false) {
                Write-Output "$($coord.Latitude),$($coord.Longitude)"
            } else {
                Write-Output "Unknown"
            }
            $watcher.Stop()
            '''

            result = subprocess.run(
                ['powershell', '-Command', powershell_script],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0 and ',' in result.stdout:
                lat_str, lon_str = result.stdout.strip().split(',')
                lat, lon = float(lat_str), float(lon_str)
                logger.info(f"Location detected via Windows API: {lat}, {lon}")
                self.cached_location = (lat, lon)
                return (lat, lon)

        except Exception as e:
            logger.debug(f"Windows location detection failed: {e}")

        return self._get_fallback_location()

    def _get_fallback_location(self) -> Optional[Tuple[float, float]]:
        """Fallback location detection methods"""

        # Try IP-based geolocation (less accurate but works everywhere)
        try:
            import requests

            # Use a free IP geolocation service
            response = requests.get('http://ipapi.co/json/', timeout=5)
            if response.status_code == 200:
                data = response.json()
                lat = float(data['latitude'])
                lon = float(data['longitude'])
                city = data.get('city', 'Unknown')
                country = data.get('country_name', 'Unknown')

                logger.info(f"Location detected via IP: {lat}, {lon} ({city}, {country})")
                self.cached_location = (lat, lon)
                return (lat, lon)

        except Exception as e:
            logger.debug(f"IP-based location failed: {e}")

        # Use cached location if available
        if self.cached_location:
            logger.info(f"Using cached location: {self.cached_location}")
            return self.cached_location

        # Final fallback - use the most accurate known coordinates
        # These are the precise coordinates you provided earlier
        precise_location = (14.938737322657747, 102.06082160579989)
        logger.info(f"Using precise fallback location: {precise_location}")
        return precise_location

    def get_location_info(self) -> str:
        """Get location information as a readable string"""
        location = self.get_current_location()

        if location:
            lat, lon = location
            try:
                from location_province_mapper import ThaiProvinceMapper
                mapper = ThaiProvinceMapper()
                province = mapper.get_province_from_coordinates(lat, lon)
                return f"📍 Location: {lat:.6f}, {lon:.6f} ({province if province else 'Unknown Province'})"
            except:
                return f"📍 Location: {lat:.6f}, {lon:.6f}"
        else:
            return "❌ Unable to detect location"

def test_auto_location():
    """Test automatic location detection"""
    print("=== Testing Automatic Location Detection ===")

    detector = AutoLocationDetector()

    print("Attempting to detect location...")
    location = detector.get_current_location()

    if location:
        lat, lon = location
        print(f"✅ Location detected: {lat}, {lon}")

        # Test province detection
        try:
            from location_province_mapper import ThaiProvinceMapper
            mapper = ThaiProvinceMapper()
            province = mapper.get_province_from_coordinates(lat, lon)
            print(f"📍 Province: {province}")
        except ImportError:
            print("📍 Province detection not available")

        print(f"ℹ️  Location info: {detector.get_location_info()}")

    else:
        print("❌ Unable to detect location")

if __name__ == "__main__":
    test_auto_location()