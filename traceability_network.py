"""Select visitor network metadata without substituting a trusted proxy's host."""
import ipaddress


def normalize_ip(candidate):
    value = str(candidate or '').strip().split(',', 1)[0].strip().strip('"')
    if value.startswith('[') and ']' in value:
        value = value[1:value.index(']')]
    elif value.count(':') == 1 and '.' in value:
        value = value.split(':', 1)[0]
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return ''


def visitor_ip(headers, trusted_proxy, configured_header, socket_host):
    if trusted_proxy:
        ip = normalize_ip(headers.get('x-visitor-ip'))
        return (ip, 'trusted-proxy') if ip else ('unknown', 'unavailable')
    candidates = []
    if configured_header:
        candidates.append((configured_header, headers.get(configured_header)))
    if configured_header != 'do-connecting-ip':
        candidates.append(('do-connecting-ip', headers.get('do-connecting-ip')))
    candidates.extend([('x-real-ip', headers.get('x-real-ip')), ('socket', socket_host)])
    for source, candidate in candidates:
        ip = normalize_ip(candidate)
        if ip:
            return ip, source
    return 'unknown', 'unavailable'


def visitor_location(headers, trusted_proxy):
    # API-edge location headers describe the website server for proxied requests.
    names = {
        'country': 'x-visitor-country' if trusted_proxy else 'cf-ipcountry',
        'region': 'x-visitor-region' if trusted_proxy else 'cf-region',
        'city': 'x-visitor-city' if trusted_proxy else 'cf-ipcity',
        'timezone': 'x-visitor-timezone' if trusted_proxy else 'cf-timezone',
    }
    limits = {'country': 120, 'region': 160, 'city': 160, 'timezone': 120}
    data = {
        key: str(headers.get(header) or '').strip()[:limits[key]]
        for key, header in names.items()
    }
    return {**data, 'latitude': 0.0, 'longitude': 0.0, 'isp': ''}
