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


def get_preonex_status(data):
    LOGGER.info("Extracting pre-Onex shipping status")
    last = max(data['track']['checkpoints'],
               key=lambda e: datetime.datetime.fromisoformat(e['time']))
    LOGGER.info("Latest pre-Onex checkpoint is %s", last)
    msg_template = "{label}: {status} ({place})"
    return msg_template, {'place': last['location_translated'],
                          'status': last['status_name'].lower(),
                          'date': last['time']}


def get_at_wh_status(data):
    msg_template = "Посылка «{label}» доставлена на склад Onex"
    return msg_template, {'date': data['import']['inusadate']}


def get_parcel_status(data):
    parcel_id = data['import']['parcelid']
    LOGGER.info("Parcel ID: %s", parcel_id)
    trk_info = _request(ONEX_TRACKING_URL, {'parcel_id': parcel_id})
    LOGGER.info("Tracking info: %s", trk_info)
    return trk_info['data']


def get_shipping_status(data):
    msg_template = "Посылка «{label}» {dir} {hub}"
    trk_info = get_parcel_status(data)
    last = {'hub': 'склад Onex', 'type': 'out',
            'date': data['import']['inmywaydate']}
    if trk_info:
        last = max(trk_info,
                   key=lambda e: datetime.datetime.fromisoformat(e['date']))
    last['dir'] = DIR_DICT[last['type']]
    return msg_template, last


def get_in_AM_status(data):
    trk_info = get_parcel_status(data)
    return trk_info


PROCESSOR_DICT = {'in my way': get_shipping_status,
                  'in USA': get_at_wh_status,
                  'in Armenia': get_in_AM_status}


def main():
    args = parse_args()
    track_nos = [tno.split(':', 1) if ':' in tno else (tno, "*UNKNOWN*")
                 for tno in args.track]
    for (tno, label) in track_nos:
        LOGGER.info("Processing %s (label '%s')", tno, label)
        basic_info = _request(ONEX_INFO_URL, {'tcode': tno})['data']
        if not basic_info['import']:
            msg_template, latest_entry = get_preonex_status(basic_info)
        else:
            msg_template, latest_entry = PROCESSOR_DICT[
                                            basic_info['import']['orderstatus']
                                            ](basic_info)
        LOGGER.info("Latest entry found: %s", latest_entry)
        if not args.no_cache and is_cached(tno, latest_entry['date']):
            continue
        latest_entry['label'] = label
        latest_entry['no'] = tno
        msg_template += "\n({date}, № заказа {no})"
        msg = msg_template.format(**latest_entry)
        LOGGER.info('Message prepared:\n "%s"', msg)
        if not args.no_notification:
            notify(args.ntfy_topic, latest_entry['label'], msg)


if __name__ == '__main__':
    main()
