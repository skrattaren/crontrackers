#!/usr/bin/env python3

import argparse
import datetime
import json
import logging
import os
import sys

import requests


SCRIPT_NAME = os.path.splitext(os.path.basename(sys.argv[0]))[0]

_STATE_DIR = os.path.join(os.getenv('HOME', '.'), '.local', 'state')
_STATE_DIR = os.getenv('XDG_STATE_HOME', _STATE_DIR)
STATE_FILE = os.path.join(_STATE_DIR, f'{SCRIPT_NAME}.json')

LOGGER = logging.Logger(SCRIPT_NAME)
LOGGER.setLevel('WARN')
LOGGER.addHandler(logging.StreamHandler())

ONEX_HEADERS = {'X-Requested-With': 'XMLHttpRequest'}
ONEX_BASE_URL = 'https://onex.am'
ONEX_INFO_URL = f'{ONEX_BASE_URL}/onextrack/findtrackingcodeimport'
ONEX_TRACKING_URL = f'{ONEX_BASE_URL}/parcel/hub'

DIR_DICT = {'in': "прибыла в",
            'out': "покинула"}


def notify(ntfy_topic, label, msg):
    LOGGER.info('Sending message with title "%s" to ntfy topic "%s"',
                label, msg)
    requests.post(f'https://ntfy.sh/{ntfy_topic}',
                  headers={
                      'Title': label.encode(encoding='utf-8'),
                      'Tag': 'package'
                  },
                  data=msg.encode(encoding='utf-8'),
                  timeout=3)


def _request(url, form_data):
    r = requests.post(url, form_data, headers=ONEX_HEADERS, timeout=666)
    return r.json()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-T', '--ntfy-topic', help="ntfy.sh topic to post to")
    parser.add_argument('-t', '--track', nargs='+', metavar="TRACKING_NUMBER[:NAME]",
                        help="order numbers to track, with optional name/labels")
    parser.add_argument('-n', '--no-notification', action='store_true')
    parser.add_argument('-c', '--no-cache', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    if args.verbose:
        LOGGER.setLevel('INFO')
        LOGGER.info("Entering verbose mode")
    return args


def is_cached(tno, date):
    LOGGER.info("Trying to use '%s' as state file", STATE_FILE)
    updates = {}
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as state_file:
            updates = json.load(state_file)
        LOGGER.info("Update data loaded: %s", updates)
    else:
        LOGGER.info("No state file found")
    if updates.get(tno) == date:
        LOGGER.info("Already recorded event for '%s' at '%s', skipping", tno, date)
        return True
    updates[tno] = date
    LOGGER.info("Saving update to state file: %s", updates)
    with open(STATE_FILE, 'w', encoding='utf-8') as state_file:
        json.dump(updates, state_file)
    return False


def main():
    args = parse_args()
    track_nos = [tno.split(':', 1) if ':' in tno else (tno, "*UNKNOWN*")
                 for tno in args.track]
    for (tno, label) in track_nos:
        LOGGER.info("Processing %s (label '%s')", tno, label)
        parcel_id = _request(ONEX_INFO_URL, {'tcode': tno}
                             )['data']['import']['parcelid']
        if parcel_id == '0':
            LOGGER.info("No tracking info from Onex, skipping")
            continue
        LOGGER.info("Parcel ID: %s", parcel_id)
        trk_info = _request(ONEX_TRACKING_URL, {'parcel_id': parcel_id})
        LOGGER.info("Tracking info: %s", trk_info)
        latest_entry = max(trk_info['data'],
                           key=lambda e: datetime.datetime.fromisoformat(e['date']))
        if not args.no_cache and is_cached(tno, latest_entry['date']):
            continue
        latest_entry['label'] = label
        latest_entry['no'] = tno
        latest_entry['dir'] = DIR_DICT[latest_entry['type']]
        msg = "Посылка «{label}» {dir} {hub}\n({date}, № заказа {no})".format(**latest_entry)
        LOGGER.info('Message prepared:\n "%s"', msg)
        if not args.no_notification:
            notify(args.ntfy_topic, latest_entry['label'], msg)


if __name__ == '__main__':
    main()
