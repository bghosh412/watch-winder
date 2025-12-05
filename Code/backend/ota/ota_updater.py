"""
OTA (Over-The-Air) Updater for ESP32 MicroPython
Downloads updates from GitHub repository with minimal memory footprint
"""

try:
    import urequests as requests
    #import ujson as json
    import uos as os
except ImportError:
    # Fallback for testing on standard Python
    import requests
    #import json
    import os

import gc

class OTAUpdater:
    def __init__(self, base_url="http://feeder-ota.surge.sh"):
        """
        Initialize OTA updater
        
        Args:
            base_url: Base URL for OTA updates (Surge, Netlify, or GitHub)
        """
        self.base_url = base_url
        self.version_url = f"{self.base_url}/version.json"
        self.local_version_file = "ota/version.json"
        
    def get_local_version(self):
        """Read local version from ota/version.json"""
        try:
            with open(self.local_version_file, 'r') as f:
                content = f.read()
                data = self._parse_json(content)
                return data.get("version", "0.0.0")
        except:
            print("No local version file found, assuming 0.0.0")
            return "0.0.0"
    
    def _parse_json(self, text):
        """Manual JSON parser for simple objects (memory efficient)"""
        # Very basic JSON parser for version.json structure
        # Expects: {"version": "1.0.0", "date": "...", "files": [...], "notes": "..."}
        result = {}
        
        # Remove outer braces and whitespace
        text = text.strip()
        if text.startswith('{'):
            text = text[1:]
        if text.endswith('}'):
            text = text[:-1]
        
        # Split by commas (simple approach, won't work with nested objects)
        in_quotes = False
        in_array = False
        current = ''
        pairs = []
        
        for char in text:
            if char == '"' and (not current or current[-1] != '\\'):
                in_quotes = not in_quotes
            elif char == '[' and not in_quotes:
                in_array = True
            elif char == ']' and not in_quotes:
                in_array = False
            elif char == ',' and not in_quotes and not in_array:
                pairs.append(current.strip())
                current = ''
                continue
            current += char
        
        if current.strip():
            pairs.append(current.strip())
        
        # Parse each key-value pair
        for pair in pairs:
            if ':' not in pair:
                continue
            
            key, value = pair.split(':', 1)
            key = key.strip().strip('"')
            value = value.strip()
            
            # Parse value
            if value.startswith('"') and value.endswith('"'):
                result[key] = value[1:-1]
            elif value.startswith('[') and value.endswith(']'):
                # Parse array
                items = []
                array_content = value[1:-1].strip()
                if array_content:
                    item_list = []
                    current_item = ''
                    in_quotes = False
                    for char in array_content:
                        if char == '"' and (not current_item or current_item[-1] != '\\'):
                            in_quotes = not in_quotes
                            if not in_quotes and current_item:
                                # End of quoted string - save it
                                item_list.append(current_item)
                                current_item = ''
                        elif in_quotes:
                            # Only collect characters while inside quotes
                            current_item += char
                        elif char == ',' and not in_quotes:
                            # Comma outside quotes - move to next item
                            continue
                    items = item_list
                result[key] = items
            elif value == 'null':
                result[key] = None
            elif value == 'true':
                result[key] = True
            elif value == 'false':
                result[key] = False
            else:
                try:
                    result[key] = int(value)
                except:
                    try:
                        result[key] = float(value)
                    except:
                        result[key] = value
        
        return result
    
    def get_remote_version(self):
        """Fetch remote version.json from GitHub"""
        try:
            print(f"Fetching version info from {self.version_url}")
            gc.collect()  # Free memory before request
            
            response = requests.get(self.version_url)
            
            if response.status_code != 200:
                print(f"Failed to fetch version.json: HTTP {response.status_code}")
                response.close()
                gc.collect()
                return None
            
            # Read content as text first (more memory efficient)
            content = response.text
            response.close()
            gc.collect()
            
            # Parse JSON manually (avoids ujson memory overhead)
            version_data = self._parse_json(content)
            
            del content
            gc.collect()
            return version_data
            
        except Exception as e:
            print(f"Error fetching remote version: {e}")
            gc.collect()
            return None
    
    def download_file(self, remote_path, local_path):
        """
        Download a single file from Surge (flattened structure with .tmp extension)
        
        Args:
            remote_path: Path on ESP32 where file should be saved (e.g., lib/stepper.py)
            local_path: Local filesystem path to save file (same as remote_path)
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Extract just the filename for Surge URL (flattened structure)
        # Surge blocks certain extensions, so files are stored with .txt extension
        filename = remote_path.split('/')[-1]
        surge_filename = filename + ".txt"
        url = self.base_url + "/" + surge_filename
        tmp_path = local_path + ".download"
        
        print("  Downloading: " + surge_filename + " -> " + remote_path)
        print("  URL: " + url)
        gc.collect()  # Free memory before download
        
        try:
            # Ensure directory exists (create nested directories one by one)
            dir_path = '/'.join(local_path.split('/')[:-1])
            if dir_path:
                parts = dir_path.split('/')
                current = ''
                for part in parts:
                    if not part:
                        continue
                    current = current + '/' + part if current else part
                    try:
                        os.mkdir(current)
                    except:
                        pass  # Directory already exists
            
            gc.collect()
            
            # Download file
            response = requests.get(url)
            
            if response.status_code != 200:
                print(f"  ✗ Failed: HTTP {response.status_code}")
                response.close()
                gc.collect()
                return False
            
            # Write to temporary file
            content = response.content
            response.close()
            gc.collect()
            
            with open(tmp_path, 'wb') as f:
                f.write(content)
            
            del content
            gc.collect()
            
            # Atomic rename: delete original, rename temp
            try:
                os.remove(local_path)
            except:
                pass  # File doesn't exist, that's fine
            
            os.rename(tmp_path, local_path)
            print(f"  ✓ Downloaded: {remote_path}")
            gc.collect()
            return True
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            # Clean up temp file
            try:
                os.remove(tmp_path)
            except:
                pass
            gc.collect()
            return False
    
    def update_local_version(self, version_data):
        """Update local version.json with new version info"""
        try:
            # Manually create JSON string
            json_str = '{\n'
            json_str += '  "version": "{}",\n'.format(version_data.get('version', ''))
            json_str += '  "date": "{}",\n'.format(version_data.get('date', ''))
            json_str += '  "notes": "{}"\n'.format(version_data.get('notes', ''))
            json_str += '}\n'
            
            with open(self.local_version_file, 'w') as f:
                f.write(json_str)
            print(f"✓ Updated local version to {version_data['version']}")
            return True
        except Exception as e:
            print(f"✗ Failed to update local version: {e}")
            return False
    
    def check_for_updates(self):
        """
        Check if updates are available
        
        Returns:
            dict: Remote version data if update available, None otherwise
        """
        print("\n=== OTA Update Check ===")
        gc.collect()
        print(f"Free RAM: {gc.mem_free()} bytes")
        
        local_version = self.get_local_version()
        print(f"Local version: {local_version}")
        
        gc.collect()  # Free memory before network request
        remote_data = self.get_remote_version()
        
        if not remote_data:
            print("✗ Could not fetch remote version")
            gc.collect()
            return None
        
        remote_version = remote_data.get("version", "0.0.0")
        print(f"Remote version: {remote_version}")
        
        if remote_version != local_version:
            print(f"✓ Update available: {local_version} → {remote_version}")
            return remote_data
        else:
            print("✓ Already up to date")
            # Return None but keep the check minimal
            del remote_data
            gc.collect()
            return None
    
    def perform_update(self):
        """
        Check for and perform OTA update
        
        Returns:
            bool: True if update was successful, False otherwise
        """
        # Check if update is available
        remote_data = self.check_for_updates()
        
        if not remote_data:
            return False
        
        files = remote_data.get("files", [])
        if not files:
            print("No files to update")
            return False
        
        print(f"\n=== Updating {len(files)} files ===")
        
        success_count = 0
        failed_files = []
        
        for file_path in files:
            if self.download_file(file_path, file_path):
                success_count += 1
            else:
                failed_files.append(file_path)
            gc.collect()
        
        print(f"\n=== Update Complete ===")
        print(f"Success: {success_count}/{len(files)} files")
        print(f"Free RAM: {gc.mem_free()} bytes")
        
        if failed_files:
            print(f"Failed files: {', '.join(failed_files)}")
            return False
        
        # Update local version file
        version_info = {
            "version": remote_data["version"],
            "date": remote_data.get("date", ""),
            "notes": remote_data.get("notes", "")
        }
        
        if self.update_local_version(version_info):
            print("\n✓ Update successful!")
            print("Please reboot to apply changes:")
            print("  import machine")
            print("  machine.reset()")
            return True
        
        return False


def check_and_update():
    """Convenience function to check and perform OTA update"""
    updater = OTAUpdater()
    return updater.perform_update()


if __name__ == "__main__":
    # For testing only
    check_and_update()
