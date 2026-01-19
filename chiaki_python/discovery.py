"""
Discovery module for finding PS4/PS5 consoles on the network.
"""

import subprocess
from typing import List, Dict, Optional


CHIAKI_CLI = '/tmp/chiaki-ng/build/cli/chiaki-cli'


def discover_consoles(timeout: int = 5) -> List[Dict[str, str]]:
    """
    Discover PlayStation consoles on the local network.

    Args:
        timeout: Discovery timeout in seconds

    Returns:
        List of discovered consoles with their information
    """
    # For now, use the Chiaki CLI for discovery
    # We can replace this with direct library calls later
    try:
        result = subprocess.run(
            [CHIAKI_CLI, 'discover'],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        consoles = []
        if result.returncode == 0:
            # Parse the output
            for line in result.stdout.split('\n'):
                if 'Host:' in line:
                    console = {}
                    # Simple parsing - we can improve this
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'Host:':
                            console['host'] = parts[i+1]
                        elif part == 'Type:':
                            console['type'] = parts[i+1]
                        elif part == 'Name:':
                            console['name'] = ' '.join(parts[i+1:])
                            break
                    if console:
                        consoles.append(console)

        return consoles
    except Exception as e:
        print(f"Discovery error: {e}")
        return []


def get_console_status(host: str) -> Optional[Dict[str, str]]:
    """
    Get detailed status of a specific console.

    Args:
        host: IP address of the console

    Returns:
        Console status information or None if unreachable
    """
    try:
        result = subprocess.run(
            [CHIAKI_CLI, 'discover', '--host', host],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return None

        # Parse chiaki-cli output
        status = {}
        for line in result.stdout.split('\n'):
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip('[I] ').strip()
                    value = parts[1].strip()

                    # Map chiaki-cli output to our format
                    if key == 'Host Name':
                        status['name'] = value
                    elif key == 'Host Type':
                        status['type'] = value
                    elif key == 'State':
                        status['state'] = value
                    elif key == 'Running App Name':
                        status['running_app'] = value
                    elif key == 'Running App Title ID':
                        status['running_app_id'] = value
                    elif key == 'Host ID':
                        status['host_id'] = value

        status['host'] = host
        status['online'] = status.get('state') == 'ready'

        return status if status else None

    except Exception as e:
        print(f"Status error: {e}")
        return None
