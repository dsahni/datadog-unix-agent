# Unless explicitly stated otherwise all files in this repository are licensed
# under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2018 Datadog, Inc.

import re
import logging
import subprocess
import socket

from config import config


VALID_HOSTNAME_RFC_1123_PATTERN = re.compile(r"^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$")
MAX_HOSTNAME_LEN = 255

log = logging.getLogger(__name__)


class HostnameException(Exception):
    pass

def is_valid_hostname(hostname):
    if hostname.lower() in [
        'localhost',
        'localhost.localdomain',
        'localhost6.localdomain6',
        'ip6-localhost',
    ]:
        log.warning("Hostname: %s is local" % hostname)
        return False
    if len(hostname) > MAX_HOSTNAME_LEN:
        log.warning("Hostname: %s is too long (max length is  %s characters)" % (hostname, MAX_HOSTNAME_LEN))
        return False
    if VALID_HOSTNAME_RFC_1123_PATTERN.match(hostname) is None:
        log.warning("Hostname: %s is not complying with RFC 1123" % hostname)
        return False
    return True


def get_hostname():
    """
    Get the canonical host name this agent should identify as. This is
    the authoritative source of the host name for the agent.

    Tries, in order:

      * agent config (datadog.yaml, "hostname:")
      * 'hostname -f' (on unix)
      * socket.gethostname()
    """
    # first, try the config
    config_hostname = config.get('hostname')
    if config_hostname and is_valid_hostname(config_hostname):
        return config_hostname

    try:
        # try fqdn
        fqdn = subprocess.check_output(['/bin/hostname', '-s']).strip()
        if fqdn and is_valid_hostname(fqdn):
            return fqdn
    except Exception:
        return None

    # fall back on socket.gethostname(), socket.getfqdn() is too unreliable
    try:
        socket_hostname = socket.gethostname()
        if socket_hostname and is_valid_hostname(socket_hostname):
            return socket_hostname
    except socket.error:
        socket_hostname = None

    raise HostnameException('Unable to reliably determine hostname or hostname not RFC1123 compliant.')
