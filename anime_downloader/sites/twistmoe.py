from Crypto.Cipher import AES
import base64
from hashlib import md5
import warnings
import requests_cache
import requests
import logging

from anime_downloader.sites.anime import Anime, AnimeEpisode, SearchResult
from anime_downloader.sites import helpers
from anime_downloader.util import eval_in_node


logger = logging.getLogger(__name__)
# Don't warn if not using fuzzywuzzy[speedup]
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    from fuzzywuzzy import process

BLOCK_SIZE = 16
KEY = b"LXgIVP&PorO68Rq7dTx8N^lP!Fa5sGJ^*XK"


class TwistMoeEpisode(AnimeEpisode, sitename='twist.moe'):
    def _get_sources(self):
        return [('no_extractor', self.url)]


class TwistMoe(Anime, sitename='twist.moe'):
    """
    Twist.moe
    """
    sitename = 'twist.moe'
    QUALITIES = ['360p', '480p', '720p', '1080p']
    _api_url = "https://twist.moe/api/anime/{}/sources"

    @classmethod
    def search(self, query):
        headers = {
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.46 Safari/537.36'
        }
        first_time = helpers.soupify(helpers.get('https://twist.moe', allow_redirects=True, headers=headers))
        js = first_time.select_one('script').text
        js = "location = {'reload': ()=>true};document = {}; \n" + js + f"console.log(document.cookie)"
        cookie = eval_in_node(js).strip()
        with requests_cache.disabled():
            headers['cookie'] = cookie
            r = requests.get('https://twist.moe/', headers=headers)
            soup = helpers.soupify(r)
        all_anime = soup.select_one('nav.series').select('li')
        animes = []
        for anime in all_anime:
            animes.append(SearchResult(
                title=anime.find('span').contents[0].strip(),
                url='https://twist.moe' + anime.find('a')['href'],
            ))
        animes = [ani[0] for ani in process.extract(query, animes)]
        return animes

    def get_data(self):
        anime_name = self.url.split('/a/')[-1].split('/')[0]
        url = self._api_url.format(anime_name)
        episodes = helpers.get(
            url,
            headers={
                'x-access-token': '1rj2vRtegS8Y60B3w3qNZm5T2Q0TN2NR'
            }
        )
        episodes = episodes.json()
        logging.debug(episodes)
        self.title = anime_name
        episode_urls = ['https://eu1.twist.moe' +
                        decrypt(episode['source'].encode('utf-8'), KEY).decode('utf-8')
                        for episode in episodes]

        self._episode_urls = [(i+1, episode_url)
                              for i, episode_url in enumerate(episode_urls)]
        self._len = len(self._episode_urls)

        return self._episode_urls


# From stackoverflow https://stackoverflow.com/questions/36762098/how-to-decrypt-password-from-javascript-cryptojs-aes-encryptpassword-passphras
def pad(data):
    length = BLOCK_SIZE - (len(data) % BLOCK_SIZE)
    return data + (chr(length)*length).encode()


def unpad(data):
    return data[:-(data[-1] if type(data[-1]) == int else ord(data[-1]))]


def bytes_to_key(data, salt, output=48):
    # extended from https://gist.github.com/gsakkis/4546068
    assert len(salt) == 8, len(salt)
    data += salt
    key = md5(data).digest()
    final_key = key
    while len(final_key) < output:
        key = md5(key + data).digest()
        final_key += key
    return final_key[:output]


def decrypt(encrypted, passphrase):
    encrypted = base64.b64decode(encrypted)
    assert encrypted[0:8] == b"Salted__"
    salt = encrypted[8:16]
    key_iv = bytes_to_key(passphrase, salt, 32+16)
    key = key_iv[:32]
    iv = key_iv[32:]
    aes = AES.new(key, AES.MODE_CBC, iv)
    return unpad(aes.decrypt(encrypted[16:]))
