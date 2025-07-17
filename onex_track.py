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
# TODO: make it optional
import babel.dates


SCRIPT_NAME = os.path.splitext(os.path.basename(sys.argv[0]))[0]

LOGGER = logging.Logger(SCRIPT_NAME)
LOGGER.setLevel('WARN')
LOGGER.addHandler(logging.StreamHandler())

ONEX_HEADERS = {'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': 'Opera/13.666 (Linux amd64) Presto'}
ONEX_BASE_URL = 'https://onex.am'
ONEX_INFO_URL = f'{ONEX_BASE_URL}/onextrack/findtrackingcodeimport'
ONEX_TRACKING_URL = f'{ONEX_BASE_URL}/parcel/hub'
ONEX_PRETRACKING_URL = f'{ONEX_BASE_URL}/track/history'

PANTRY_URL_TMPL = ('https://getpantry.cloud/apiv1/'
                   'pantry/{pantry}/basket/{basket}')

DIR_DICT = {'in': "прибыла в",
            'out': "покинула"}


# TODO: get rid of multiple `ClientSession`s

async def notify(ntfy_topic, label, msg, session):
    """ Send message to `ntfy.sh` topic """
    LOGGER.info('Sending message with title "%s" to ntfy topic "%s" '
                'and body:\n"%s"', label, ntfy_topic, msg)
    await session.post(f'https://ntfy.sh/{ntfy_topic}',
                       headers={'Title': label,
                                'Tag': 'package'},
                       data=msg)


async def _post_request(url, form_data):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form_data,
                                headers=ONEX_HEADERS) as response:
            body = await response.read()
            return json.loads(body)


def parse_args():
    """ Handle CLI args """
    parser = argparse.ArgumentParser()
    parser.add_argument('-T', '--ntfy-topic', help="ntfy.sh topic to post to")
    parser.add_argument('-p', '--pantry-basket',
                        metavar="PANTRY_ID/BASKET_NAME",
                        help="Pantry basket to store JSON cache, "
                             "see https://getpantry.cloud/")
    parser.add_argument('-t', '--track', nargs='+', required=True,
                        metavar="TRACKING_NUMBER[:NAME]",
                        help="order number(s) to track, "
                             "with optional name/labels")
    parser.add_argument('-N', '--split-by-newlines', action='store_true')
    parser.add_argument('-n', '--no-notification', action='store_true')
    parser.add_argument('-c', '--no-cache', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    if args.verbose:
        LOGGER.setLevel('INFO')
        LOGGER.info("Entering verbose mode")
    if not args.ntfy_topic and not args.no_notification:
        parser.error("pass `--ntfy-topic` or use `--no-notification`")
    if args.pantry_basket:
        try:
            pantry, basket = args.pantry_basket.split('/')
            args.pantry_basket_url = PANTRY_URL_TMPL.format(pantry=pantry,
                                                            basket=basket)
        except ValueError:
            parser.error("invalid 'PANTRY_ID/BASKET_NAME'")
    elif not args.no_cache:
        parser.error("pass `--pantry-basket` or use `--no-cache`")
    return args


async def load_cache(url):
    """ Load cache info from Pantry basket """
    LOGGER.info("Loading cache data from '%s'", url)
    # TODO: handle errors
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            if not r.ok:
                sys.exit(3)
            cache_data = await r.json()
    LOGGER.info("Update data loaded:\n%s",
                pprint.pformat(cache_data, sort_dicts=False))

    def cache_wrapper(entry):
        if entry['date'] == cache_data.get(entry['no']):
            LOGGER.info("Already recorded event for %s at '%s', skipping",
                        entry['no'], entry['date'])
            return True
        cache_data[entry['no']] = entry['date']
        return False
    return cache_data, cache_wrapper


async def save_cache(url, cache_data):
    """ Save cache data to Pantry basket """
    cache_data = dict(sorted(cache_data.items(), key=lambda item: item[1]))
    LOGGER.info("Saving update to '%s':\n%s",
                url,
                pprint.pformat(cache_data, sort_dicts=False))
    async with aiohttp.ClientSession() as session:
        async with session.post(url,
                                headers={'Content-Type': 'application/json'},
                                data=json.dumps(cache_data)) as r:
            if not r.ok:
                sys.exit(3)


async def get_preonex_status(data):
    """ Get status of package before delivery to Onex warehouse """
    tno = data['tno']
    LOGGER.info("[%s] Requesting pre-Onex shipping status", tno)
    async with aiohttp.ClientSession() as session:
        async with session.post(ONEX_PRETRACKING_URL, params={'track': tno},
                                headers=ONEX_HEADERS) as response:
            track_data = json.loads(await response.read()).get('data')
    if not track_data:
        raise ValueError(f"No data collected for {tno}")
    checkpoints = track_data['checkpoints']
    if not checkpoints:
        LOGGER.info("[%s] No checkpoints reported (yet)", tno)
        msg_template = ("{courier} пока не предоставил(а) информацию "
                        "о посылке {label}")
        return msg_template, {'courier': data['track']['courier']['name'],
                              'date': data['track']['last_check']}
    last = checkpoints[0]
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
    trk_info = await _post_request(ONEX_TRACKING_URL, {'parcel_id': parcel_id,
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
    basic_info = (await _post_request(ONEX_INFO_URL, {'tcode': tno}))['data']
    basic_info['tno'] = tno
    hasestimateddate = ""
    if not basic_info['import']:
        msg_template, latest_entry = await get_preonex_status(basic_info)
    elif basic_info['import'].get('orderstatus') is None:
        LOGGER.info("[%s] Scanned at warehouse", tno)
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
    if basic_info['import']:
        estimateddate = basic_info['import'].get('estimateddate')
        if estimateddate is not None:
            latest_entry['estimateddate'] = babel.dates.format_date(
                datetime.datetime.fromisoformat(estimateddate),
                format='EE, d MMM', locale='ru')
            hasestimateddate = "ожидается в {estimateddate}, "
    latest_entry['msg_template'] = ("%s\n("
                                    "%s"
                                    "обновлено {date}, заказ № {no})"
                                    "" % (msg_template, hasestimateddate))
    return latest_entry


async def _check_connection(session, verbose=False):
    try:
        response = await session.get(ONEX_BASE_URL)
    except aiohttp.ClientConnectionError as conn_err:
        await session.close()
        if verbose:
            raise conn_err
        sys.exit(2)
    if response.ok:
        return
    LOGGER.info("Test request failed with '%d' error code", response.status)
    await session.close()
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
    if args.split_by_newlines:
        track_nos = args.track[0].splitlines()
    else:
        track_nos = args.track
    track_nos = [tno.split(':', 1) if ':' in tno else (tno, "*UNKNOWN*")
                 for tno in track_nos]
    results = await asyncio.gather(*[process_package(tno, label)
                                     for (tno, label) in track_nos],
                                   return_exceptions=True)
    status_info, errors = split_errors(results)
    if errors:
        LOGGER.info("Errors found: %s", errors)
    # TODO: load cache async-ly
    if not args.no_cache:
        cache_data, is_cached = await load_cache(args.pantry_basket_url)
        status_info = [i for i in status_info if not is_cached(i)]
        if status_info:
            await save_cache(args.pantry_basket_url, cache_data)
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
