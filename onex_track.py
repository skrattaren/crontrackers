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
import pprint
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


async def notify(ntfy_topic, label, msg, session):
    """ Send message to `ntfy.sh` topic """
    LOGGER.info('Sending message with title "%s" to ntfy topic "%s" '
                'and body:\n"%s"', label, ntfy_topic, msg)
    await session.post(f'https://ntfy.sh/{ntfy_topic}',
                       headers={'Title': label,
                                'Tag': 'package'},
                       data=msg)


async def _request(url, form_data):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form_data,
                                headers=ONEX_HEADERS) as response:
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


def load_cache():
    """ Load cache info from STATE_FILE """
    LOGGER.info("Trying to use '%s' as state file", STATE_FILE)
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as state_file:
            cache_data = json.load(state_file)
        LOGGER.info("Update data loaded:\n%s",
                    pprint.pformat(cache_data, sort_dicts=False))
    else:
        LOGGER.info("No state file found")
        cache_data = {}

    def cache_wrapper(entry):
        if entry['date'] == cache_data.get(entry['no']):
            LOGGER.info("Already recorded event for %s at '%s', skipping",
                        entry['no'], entry['date'])
            return True
        cache_data[entry['no']] = entry['date']
        return False
    return cache_data, cache_wrapper


def save_cache(cache_data):
    """ Save cache data to STATE_FILE """
    cache_data = dict(sorted(cache_data.items(), key=lambda item: item[1]))
    LOGGER.info("Saving update to state file:\n%s",
                pprint.pformat(cache_data, sort_dicts=False))
    with open(STATE_FILE, 'w', encoding='utf-8') as state_file:
        json.dump(cache_data, state_file, indent=2)


def get_preonex_status(data):
    """ Get status of package before delivery to Onex warehouse """
    tno = data['tno']
    LOGGER.info("[%s] Extracting pre-Onex shipping status", tno)
    track_data = data['track']
    if not track_data:
        raise ValueError(f"No data collected for {tno}")
    checkpoints = track_data['checkpoints']
    if not checkpoints:
        LOGGER.info("[%s] No checkpoints reported (yet)", tno)
        msg_template = ("{courier} пока не предоставил(а) информацию "
                        "о посылке {label}")
        return msg_template, {'courier': data['track']['courier']['name'],
                              'date': data['track']['last_check']}
    last = checkpoints[-1]
    LOGGER.info("[%s] Latest pre-Onex checkpoint is %s", tno, last)
    msg_template = "{label}: {status} ({place})"
    return msg_template, {'place': last['location_translated'],
                          'status': last['status_name'].lower(),
                          'date': last['time']}


async def get_at_wh_status(data):
    """ Get status of package at the warehouse """
    msg_template = "Посылка «{label}» доставлена на склад Onex"
    return msg_template, {'date': data['import']['inusadate']}


async def get_parcel_status(data):
    """ Get "sub"-status from JSON data """
    tno = data['tno']
    parcel_id = data['import']['parcelid']
    id_box = data['import']['idbox']
    LOGGER.info("[%s] Parcel ID: %s", tno, parcel_id)
    trk_info = await _request(ONEX_TRACKING_URL, {'parcel_id': parcel_id,
                                                  'idbox': id_box})
    LOGGER.info("[%s] Tracking info: %s", tno, trk_info)
    return trk_info['data']


async def get_shipping_status(data):
    """ Get progress of shipping by Onex itself """
    msg_template = "Посылка «{label}» {dir} {hub}"
    trk_info = await get_parcel_status(data)
    last = {'hub': 'склад Onex', 'type': 'out',
            'date': data['import']['inmywaydate']}
    if trk_info:
        last = trk_info[-1]
    last['dir'] = DIR_DICT[last['type']]
    return msg_template, last


async def get_in_am_status(data):
    """ Package is in Armenia """
    msg_template = "Посылка «{label}» прибыла в Армению и готовится к доставке"
    return msg_template, {'status': 'in Armenia',
                          'date': data['import']['inarmeniadate']}


async def get_received_status(data):
    """ Package received """
    msg_template = "Посылка «{label}» доставлена и получена"
    return msg_template, {'status': 'received',
                          'date': data['import']['receiveddate']}


PROCESSOR_DICT = {'in my way': get_shipping_status,
                  '3': get_shipping_status,
                  'in USA': get_at_wh_status,
                  'received': get_received_status,
                  'in Armenia': get_in_am_status}


async def process_package(tno, label):
    """ Now let's process that stuff async-ly """
    LOGGER.info("[%s] Start processing (label '%s')", tno, label)
    basic_info = (await _request(ONEX_INFO_URL, {'tcode': tno}))['data']
    basic_info['tno'] = tno
    if not basic_info['import']:
        msg_template, latest_entry = get_preonex_status(basic_info)
    elif basic_info['import'].get('orderstatus') is None:
        msg_template, latest_entry = (
            "Посылка «{label}» получена складом ONEX",
            {'date': basic_info['import']['wo_scanneddate']}
        )
    else:
        msg_template, latest_entry = await (PROCESSOR_DICT[
                                        basic_info['import']['orderstatus']
                                        ](basic_info))
    LOGGER.info("[%s] Latest entry found: %s", tno, latest_entry)
    latest_entry['label'] = label
    latest_entry['no'] = tno
    latest_entry['msg_template'] = msg_template + "\n({date}, № заказа {no})"
    return latest_entry


async def _check_connection(session, verbose=False):
    try:
        await session.get(ONEX_BASE_URL)
    except aiohttp.ClientConnectionError as conn_err:
        await session.close()
        if verbose:
            raise conn_err
        sys.exit(2)


def split_errors(result_list):
    """ Split all results into real data and errors """
    status_info, errors = [], []
    for i in result_list:
        if isinstance(i, Exception):
            errors.append(i)
        else:
            status_info.append(i)
    return status_info, errors


async def main():
    """ Main control flow handler """
    args = parse_args()
    session = aiohttp.ClientSession()
    await _check_connection(session, verbose=args.verbose)
    track_nos = [tno.split(':', 1) if ':' in tno else (tno, "*UNKNOWN*")
                 for tno in args.track]
    results = await asyncio.gather(*[process_package(tno, label)
                                     for (tno, label) in track_nos],
                                   return_exceptions=True)
    status_info, errors = split_errors(results)
    if errors:
        LOGGER.info("Errors found: %s", errors)
    if not args.no_cache:
        cache_data, is_cached = load_cache()
        status_info = [i for i in status_info if not is_cached(i)]
        if status_info:
            save_cache(cache_data)
    if not status_info:
        LOGGER.info("No new events found, exiting")
        await session.close()
        return
    LOGGER.info("Events to process:\n%s", pprint.pformat(status_info))
    messages = []
    for entry in status_info:
        msg = entry['msg_template'].format(**entry)
        LOGGER.info('Message prepared:\n "%s"', msg)
        messages.append((entry['label'], msg))
    if not args.no_notification:
        async with asyncio.TaskGroup() as ntfy_tasks:
            for (label, msg) in messages:
                ntfy_tasks.create_task(notify(args.ntfy_topic, label, msg,
                                              session))
    await session.close()


if __name__ == '__main__':
    asyncio.run(main())
