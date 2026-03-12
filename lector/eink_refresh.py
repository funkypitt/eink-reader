# eInk refresh integration with Tinta4PlusU helper daemon
# Sends refresh commands via Unix socket to clear ghosting after page turns

import socket
import struct
import json
import logging
import threading

logger = logging.getLogger(__name__)

SOCKET_PATH = '/tmp/tinta4plusu.sock'
REFRESH_TIMEOUT = 2.0  # seconds
REFRESH_INTERVAL = 10  # trigger ghost refresh every N page turns

_page_turn_count = 0


def trigger_eink_refresh(socket_path=SOCKET_PATH):
    """Send a refresh-eink command to the Tinta4PlusU helper daemon.
    Runs in a background thread to avoid blocking the UI."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(REFRESH_TIMEOUT)
        sock.connect(socket_path)

        command = json.dumps({'command': 'refresh-eink', 'params': {}}).encode('utf-8')
        sock.sendall(struct.pack('!I', len(command)) + command)

        response_length = struct.unpack('!I', sock.recv(4))[0]
        response_data = sock.recv(response_length)
        response = json.loads(response_data.decode('utf-8'))

        sock.close()

        if response.get('success'):
            logger.debug('eInk refresh completed')
        else:
            logger.warning('eInk refresh failed: %s', response.get('message', 'unknown'))
    except FileNotFoundError:
        logger.debug('Tinta4PlusU helper not running (socket not found)')
    except (ConnectionRefusedError, OSError) as e:
        logger.debug('Could not connect to Tinta4PlusU helper: %s', e)
    except Exception as e:
        logger.warning('eInk refresh error: %s', e)


def refresh_eink_async():
    """Trigger eInk refresh in a background thread every REFRESH_INTERVAL page turns."""
    global _page_turn_count
    _page_turn_count += 1
    if _page_turn_count % REFRESH_INTERVAL != 0:
        return
    thread = threading.Thread(target=trigger_eink_refresh, daemon=True)
    thread.start()
