#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys

import requests
from lxml.html import soupparser as html
# from lxml import etree

BASE_URL = 'https://ablforpeople.com/game'
MEDIA_SUFFIX = 'media'
GAME_URL = '%s/{}/%s' % (BASE_URL, MEDIA_SUFFIX)
URL_RE = r'%s/([0-9]+)[/a-z]+' % BASE_URL
NTFY_TOPIC = 'skrattaren-ntfy'

_STATE_DIR = os.path.join(os.getenv('HOME', '.'), '.local', 'state')
_STATE_DIR = os.getenv('XDG_STATE_HOME', _STATE_DIR)
STATE_FILE = os.path.join(_STATE_DIR, 'abl_yt_ping.json')


def err(msg, exit_code=1):
    print(msg, file=sys.stderr)
    sys.exit(exit_code)


def notify(url):
    r = requests.get(url, timeout=13)
    doc = html.fromstring(r.text)
    title = doc.find('head//meta[@name="title"]').attrib['content']
    requests.post(f'https://ntfy.sh/{NTFY_TOPIC}',
                  headers={
                      'Title': f'"{title}" YouTube link is ready',
                      'Tag': 'basketball'
                  },
                  data=url,
                  timeout=3)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('id_or_url')
    parser.add_argument('-n', '--no-notification', action='store_true')
    parser.add_argument('-c', '--no-cache', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    if args.id_or_url.isdigit():
        args.game_id = args.id_or_url
    elif arg_match := re.match(URL_RE, args.id_or_url):
        args.game_id = arg_match.groups()[0]
    else:
        err(f"Unable to parse argument: {args.id_or_url}")
    args.game_url = GAME_URL.format(args.game_id)
    return args


def check_cache(game_id):
    games = []
    game_id = int(game_id)
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as state_file:
            games = json.load(state_file)
    if game_id in games:
        print(f"Game ID {game_id} found in cache, exiting")
        sys.exit(0)
    games.append(game_id)
    with open(STATE_FILE, 'w', encoding='utf-8') as state_file:
        json.dump(games, state_file)


def main():
    args = parse_args()
    r = requests.get(args.game_url, timeout=13)
    doc = html.fromstring(r.text)
    video_elem = doc.find('body//div[@class="video-records"]/div/iframe')
    if video_elem is None:
        return
    if not args.no_cache:
        check_cache(args.game_id)
    yt_url = video_elem.attrib['src']
    yt_url = yt_url.replace('embed/', 'watch?v=')
    if args.no_notification:
        print(f"YouTube link found: {yt_url}")
    else:
        notify(yt_url)


if __name__ == '__main__':
    main()
