#!/usr/bin/env python3

"""
Track Onex shipping progress and notify about it using `ntf.sh`
"""

import argparse
import asyncio
import datetime
import json
import logging
import os
import sys

import aiohttp


SCRIPT_NAME = os.path.splitext(os.path.basename(sys.argv[0]))[0]

_STATE_DIR = os.path.join(os.getenv('HOME', '.'), '.local', 'state')
_STATE_DIR = os.getenv('XDG_STATE_HOME', _STATE_DIR)
STATE_FILE = os.path.join(_STATE_DIR, f'{SCRIPT_NAME}.json')

LOGGER = logging.Logger(SCRIPT_NAME)
LOGGER.setLevel('WARN')
LOGGER.addHandler(logging.StreamHandler())

ONEX_HEADERS = {'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': 'Opera/13.666 (Linux amd64) Presto'}
ONEX_BASE_URL = 'https://onex.am'
ONEX_INFO_URL = f'{ONEX_BASE_URL}/onextrack/findtrackingcodeimport'
ONEX_TRACKING_URL = f'{ONEX_BASE_URL}/parcel/hub'

DIR_DICT = {'in': "прибыла в",
            'out': "покинула"}


async def notify(ntfy_topic, label, msg, tno):
    """ Send message to `ntfy.sh` topic """
    LOGGER.info('[%s] Sending message with title "%s" to ntfy topic "%s" '
                'and body:\n"%s"', tno, label, ntfy_topic, msg)
    async with aiohttp.ClientSession() as session:
        await session.post(f'https://ntfy.sh/{ntfy_topic}',
                           headers={'Title': label,
                                    'Tag': 'package'},
                           data=msg)


async def _request(url, form_data):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form_data, headers=ONEX_HEADERS,
                                timeout=666) as response:
            body = await response.read()
            return json.loads(body)


def parse_args():
    """ Handle CLI args """
    parser = argparse.ArgumentParser()
    parser.add_argument('-T', '--ntfy-topic', help="ntfy.sh topic to post to")
    parser.add_argument('-t', '--track', nargs='+',
                        metavar="TRACKING_NUMBER[:NAME]",
                        help="order number(s) to track, "
                             "with optional name/labels")
    parser.add_argument('-n', '--no-notification', action='store_true')
    parser.add_argument('-c', '--no-cache', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    if args.verbose:
        LOGGER.setLevel('INFO')
        LOGGER.info("Entering verbose mode")
    if not args.ntfy_topic and not args.no_cache:
        parser.error("pass `--ntfy-topic` or use `--no-notification`")
    return args


def is_cached(tno, date):
    """ Check if event is already encountered (cached) """
    LOGGER.info("[%s] Trying to use '%s' as state file", tno, STATE_FILE)
    updates = {}
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as state_file:
            updates = json.load(state_file)
        LOGGER.info("[%s] Update data loaded: %s", tno, updates)
    else:
        LOGGER.info("[%s] No state file found")
    if updates.get(tno) == date:
        LOGGER.info("[%s] Already recorded event at '%s', skipping",
                    tno, date)
        return True
    updates[tno] = date
    LOGGER.info("[%s] Saving update to state file: %s", tno, updates)
    with open(STATE_FILE, 'w', encoding='utf-8') as state_file:
        json.dump(updates, state_file)
    return False


def get_preonex_status(data):
    """ Get status of package before delivery to Onex warehouse """
    tno = data['track']['tracking_number']
    LOGGER.info("[%s] Extracting pre-Onex shipping status", tno)
    track_data = data['track']
    if not track_data:
        msg_template = "No data collected by Onex"
        LOGGER.info("[%s] %s", tno, msg_template)
        return msg_template, {'date': ''}
    checkpoints = track_data['checkpoints']
    if not checkpoints:
        LOGGER.info("[%s] No checkpoints reported (yet)", tno)
        msg_template = ("{courier} пока не предоставил(а) информацию "
                        "о посылке {label}")
        return msg_template, {'courier': data['track']['courier']['name'],
                              'date': data['track']['last_check']}
    last = max(checkpoints,
               key=lambda e: datetime.datetime.fromisoformat(e['time']))
    LOGGER.info("[%s] Latest pre-Onex checkpoint is %s", tno, last)
    msg_template = "{label}: {status} ({place})"
    return msg_template, {'place': last['location_translated'],
                          'status': last['status_name'].lower(),
                          'date': last['time']}


def get_at_wh_status(data):
    """ Get status of package at the warehouse """
    msg_template = "Посылка «{label}» доставлена на склад Onex"
    return msg_template, {'date': data['import']['inusadate']}


async def get_parcel_status(data):
    """ Get "sub"-status from JSON data """
    tno = data['track']['tracking_number']
    parcel_id = data['import']['parcelid']
    LOGGER.info("[%s] Parcel ID: %s", tno, parcel_id)
    trk_info = await _request(ONEX_TRACKING_URL, {'parcel_id': parcel_id})
    LOGGER.info("[%s] Tracking info: %s", tno, trk_info)
    return trk_info['data']


def get_shipping_status(data):
    """ Get progress of shipping by Onex itself """
    msg_template = "Посылка «{label}» {dir} {hub}"
    trk_info = get_parcel_status(data)
    last = {'hub': 'склад Onex', 'type': 'out',
            'date': data['import']['inmywaydate']}
    if trk_info:
        last = max(trk_info,
                   key=lambda e: datetime.datetime.fromisoformat(e['date']))
    last['dir'] = DIR_DICT[last['type']]
    return msg_template, last


def get_in_am_status(data):
    """ Package is in Armenia """
    msg_template = "Посылка «{label}» прибыла в Армению и готовится к доставке"
    return msg_template, {'status': 'in Armenia',
                          'date': data['import']['inarmeniadate']}


def get_received_status(data):
    """ Package received """
    msg_template = "Посылка «{label}» доставлена и получена"
    return msg_template, {'status': 'received',
                          'date': data['import']['receiveddate']}


PROCESSOR_DICT = {'in my way': get_shipping_status,
                  '3': get_shipping_status,
                  'in USA': get_at_wh_status,
                  'received': get_received_status,
                  'in Armenia': get_in_am_status}


async def process_package(tno, label, args):
    """ Now let's process that stuff async-ly """
    LOGGER.info("[%s] Start processing (label '%s')", tno, label)
    basic_info = (await _request(ONEX_INFO_URL, {'tcode': tno}))['data']
    if not basic_info['import']:
        msg_template, latest_entry = get_preonex_status(basic_info)
    elif basic_info['import'].get('orderstatus') is None:
        msg_template, latest_entry = (
            "Посылка «{label}» получена складом ONEX",
            {'date': basic_info['import']['wo_scanneddate']}
        )
    else:
        msg_template, latest_entry = PROCESSOR_DICT[
                                        basic_info['import']['orderstatus']
                                        ](basic_info)
    LOGGER.info("[%s] Latest entry found: %s", tno, latest_entry)
    if not args.no_cache and is_cached(tno, latest_entry['date']):
        return
    latest_entry['label'] = label
    latest_entry['no'] = tno
    msg_template += "\n({date}, № заказа {no})"
    msg = msg_template.format(**latest_entry)
    LOGGER.info('[%s] Message prepared:\n "%s"', tno, msg)
    if not args.no_notification:
        await notify(args.ntfy_topic, latest_entry['label'], msg, tno)


async def main():
    """ Main control flow handler """
    args = parse_args()
    track_nos = [tno.split(':', 1) if ':' in tno else (tno, "*UNKNOWN*")
                 for tno in args.track]
    await asyncio.gather(*[process_package(tno, label, args)
                           for (tno, label) in track_nos])


if __name__ == '__main__':
    asyncio.run(main())
