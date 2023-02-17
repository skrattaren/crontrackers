#!/usr/bin/env python3

import argparse
import json
import logging
import os
import re
import sys

import requests
import lxml
from lxml.html import soupparser as html

SCRIPT_NAME = os.path.splitext(os.path.basename(sys.argv[0]))[0]
BASE_URL = 'https://ablforpeople.com/game'
MEDIA_SUFFIX = 'media'
GAME_URL = '%s/{}/%s' % (BASE_URL, MEDIA_SUFFIX)
URL_RE = r'%s/([0-9]+)[/a-z]+' % BASE_URL
NTFY_TOPIC = 'skrattaren-ntfy'
YT_SHRTURL_TMPL = 'https://youtu.be/{}'
# courtesy of Soufiane Sakhi: https://stackoverflow.com/a/61033353/9288580
YT_URL_RE = re.compile(r'(?:https?:\/\/)?(?:www\.)?youtu(?:\.be\/|be.com\/\S*'
                       r'(?:watch|embed)(?:(?:(?=\/[-a-zA-Z0-9_]{11,}(?!\S))\/)'
                       r'|(?:\S*v=|v\/)))([-a-zA-Z0-9_]{11,})')

_STATE_DIR = os.path.join(os.getenv('HOME', '.'), '.local', 'state')
_STATE_DIR = os.getenv('XDG_STATE_HOME', _STATE_DIR)
STATE_FILE = os.path.join(_STATE_DIR, f'{SCRIPT_NAME}.json')

LOGGER = logging.Logger(SCRIPT_NAME)
LOGGER.setLevel('WARN')
LOGGER.addHandler(logging.StreamHandler())


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
    if args.verbose:
        LOGGER.setLevel('INFO')
        LOGGER.info("Entering verbose mode")
    if args.id_or_url.isdigit():
        args.game_id = args.id_or_url
    elif arg_match := re.match(URL_RE, args.id_or_url):
        args.game_id = arg_match.groups()[0]
    else:
        LOGGER.critical("Unable to parse argument: %s", args.id_or_url)
        sys.exit(1)
    args.game_url = GAME_URL.format(args.game_id)
    args.game_id = int(args.game_id)
    LOGGER.info("Game ID: %s", args.game_id)
    LOGGER.info("Game URL: %s", args.game_url)
    return args


def check_cache(game_id):
    LOGGER.info("Trying to use '%s' as state file", STATE_FILE)
    games = []
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as state_file:
            games = json.load(state_file)
        LOGGER.info("List of game IDs loaded: %s", games)
    else:
        LOGGER.info("No state file found")
    if game_id in games:
        LOGGER.info("Game ID %s found in cache, exiting", game_id)
        sys.exit(0)
    games.append(game_id)
    LOGGER.info("Saving games to state file: %s", games)
    with open(STATE_FILE, 'w', encoding='utf-8') as state_file:
        json.dump(games, state_file)


def main():
    args = parse_args()
    r = requests.get(args.game_url, timeout=13)
    doc = html.fromstring(r.text)
    video_elem = doc.find('body//div[@class="video-records"]/div/iframe')
    if video_elem is None:
        LOGGER.info("No video found on page (yet)")
        return
    LOGGER.info("Found video <iframe>:\n%s",
                lxml.html.tostring(video_elem).decode('utf-8'))
    yt_url = video_elem.attrib['src']
    yt_url = YT_SHRTURL_TMPL.format(YT_URL_RE.match(yt_url).groups()[0])
    LOGGER.info("YouTube link found: %s", yt_url)
    if not args.no_cache:
        check_cache(args.game_id)
    if not args.no_notification:
        notify(yt_url)


if __name__ == '__main__':
    main()
