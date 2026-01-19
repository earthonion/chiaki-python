"""
Parser for Chiaki configuration files.
"""

import configparser
from typing import Dict, List, Optional, Any


def parse_bytearray(value: str) -> bytes:
    """
    Parse Qt ByteArray format to bytes.

    Qt ByteArray format mixes printable ASCII with hex escapes:
    - @ByteArray(d77687f8\0\0\0\0\0\0\0\0)
    - @ByteArray(\x89\f.\xdaG\x7f\xd0\xcf\xfb\x98h\xc9\xf9\xb1\x9b\xe5)

    Args:
        value: ByteArray string from Chiaki config

    Returns:
        Parsed bytes
    """
    # Remove @ByteArray( and trailing )
    if value.startswith('"@ByteArray('):
        # Handle quoted version
        value = value[12:-2]
    elif value.startswith('@ByteArray('):
        value = value[11:-1]
    else:
        return b''

    result = bytearray()
    i = 0
    while i < len(value):
        if value[i] == '\\':
            # Escape sequence
            if i + 1 < len(value):
                next_char = value[i + 1]
                if next_char == 'x':
                    # Hex escape like \x89 or \xf
                    # Try to read up to 2 hex digits
                    hex_start = i + 2
                    hex_end = hex_start
                    while hex_end < len(value) and hex_end < hex_start + 2:
                        if value[hex_end] in '0123456789abcdefABCDEF':
                            hex_end += 1
                        else:
                            break

                    if hex_end > hex_start:
                        hex_str = value[hex_start:hex_end]
                        result.append(int(hex_str, 16))
                        i = hex_end
                    else:
                        # No valid hex digits, treat as literal \x
                        result.append(ord('\\'))
                        i += 1
                elif next_char == '0':
                    # Null byte \0
                    result.append(0)
                    i += 2
                elif next_char in 'nrtfvab':
                    # Special escapes
                    escapes = {
                        'n': 0x0a, 'r': 0x0d, 't': 0x09,
                        'f': 0x0c, 'v': 0x0b, 'a': 0x07, 'b': 0x08
                    }
                    result.append(escapes[next_char])
                    i += 2
                elif next_char == '\\':
                    # Escaped backslash
                    result.append(ord('\\'))
                    i += 2
                else:
                    # Unknown escape, keep as-is
                    result.append(ord(value[i]))
                    i += 1
            else:
                result.append(ord(value[i]))
                i += 1
        else:
            # Regular character
            result.append(ord(value[i]))
            i += 1

    return bytes(result)


def parse_chiaki_config(config_path: str = "~/.config/Chiaki/Chiaki.conf") -> List[Dict[str, Any]]:
    """
    Parse Chiaki configuration file and extract registered hosts.

    Args:
        config_path: Path to Chiaki.conf

    Returns:
        List of registered host configurations
    """
    import os
    config_path = os.path.expanduser(config_path)

    config = configparser.ConfigParser()
    config.read(config_path)

    hosts = []

    if 'registered_hosts' not in config:
        return hosts

    # Find how many hosts are registered
    section = config['registered_hosts']
    num_hosts = int(section.get('size', 0))

    for i in range(1, num_hosts + 1):
        prefix = f"{i}\\"

        # Extract all fields for this host
        host_config = {}

        # Required fields
        if f"{prefix}server_nickname" in section:
            host_config['name'] = section[f"{prefix}server_nickname"]

        if f"{prefix}server_mac" in section:
            mac_bytes = parse_bytearray(section[f"{prefix}server_mac"])
            host_config['mac'] = ':'.join(f'{b:02X}' for b in mac_bytes)

        if f"{prefix}rp_key" in section:
            rp_key_bytes = parse_bytearray(section[f"{prefix}rp_key"])
            host_config['rp_key'] = rp_key_bytes.hex()

        if f"{prefix}rp_regist_key" in section:
            regist_bytes = parse_bytearray(section[f"{prefix}rp_regist_key"])
            # Only take the non-null part
            regist_key = regist_bytes.rstrip(b'\x00')
            host_config['regist_key'] = regist_key.decode('ascii', errors='ignore')

        if f"{prefix}target" in section:
            host_config['target'] = int(section[f"{prefix}target"])
            host_config['is_ps5'] = host_config['target'] >= 1000000

        # AP info (for wakeup)
        if f"{prefix}ap_ssid" in section:
            host_config['ap_ssid'] = section[f"{prefix}ap_ssid"]

        if f"{prefix}ap_key" in section:
            host_config['ap_key'] = section[f"{prefix}ap_key"]

        if f"{prefix}ap_bssid" in section:
            host_config['ap_bssid'] = section[f"{prefix}ap_bssid"]

        if f"{prefix}ap_name" in section:
            host_config['ap_name'] = section[f"{prefix}ap_name"]

        if host_config:
            hosts.append(host_config)

    # Also parse manual_hosts to get IP addresses
    if 'manual_hosts' in config:
        manual = config['manual_hosts']
        for i, host in enumerate(hosts, 1):
            if f"{i}\\host" in manual:
                host['host'] = manual[f"{i}\\host"]
            if f"{i}\\id" in manual:
                host['id'] = int(manual[f"{i}\\id"])

    return hosts


def get_host_by_name(name: str, config_path: str = "~/.config/Chiaki/Chiaki.conf") -> Optional[Dict]:
    """
    Get a specific host configuration by name.

    Args:
        name: Server nickname (e.g., "PS4-910")
        config_path: Path to Chiaki.conf

    Returns:
        Host configuration dict or None
    """
    hosts = parse_chiaki_config(config_path)
    for host in hosts:
        if host.get('name') == name:
            return host
    return None


def get_host_by_mac(mac: str, config_path: str = "~/.config/Chiaki/Chiaki.conf") -> Optional[Dict]:
    """
    Get a specific host configuration by MAC address.

    Args:
        mac: MAC address (e.g., "BC:60:A7:92:4A:46")
        config_path: Path to Chiaki.conf

    Returns:
        Host configuration dict or None
    """
    hosts = parse_chiaki_config(config_path)
    mac = mac.upper().replace(':', '')
    for host in hosts:
        host_mac = host.get('mac', '').replace(':', '')
        if host_mac == mac:
            return host
    return None
