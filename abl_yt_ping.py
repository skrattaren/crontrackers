#!/usr/bin/env python3

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


def main(url):
    r = requests.get(url, timeout=13)
    doc = html.fromstring(r.text)
    # print(r.text)
    video_elem = doc.find('body//div[@class="video-records"]/div/iframe')
    if video_elem is None:
        return
    yt_url = video_elem.attrib['src']
    yt_url = yt_url.replace('embed/', 'watch?v=')
    notify(yt_url)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        err("Only one argument is accepted")
    arg = sys.argv[1]
    if arg.isdigit():
        game_id = arg
    elif arg_match := re.match(URL_RE, arg):
        game_id = arg_match.groups()[0]
    else:
        err("Unable to parse argument")
    game_url = GAME_URL.format(game_id)
    main(game_url)
