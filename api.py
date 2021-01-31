import os
import json
import shutil
import hashlib
from enum import Enum
from datetime import datetime

from constant import PixivConstant
from pixiv_object.token import Token

import cloudscraper
from requests.models import Response
from urllib3.exceptions import HTTPError


class HTTPMethod(Enum):
    GET = 'GET'
    POST = 'POST'


class PixivClient:
    client = cloudscraper.create_scraper()

    # region constructor
    def __init__(self, token: Token):
        self.token = token
        self.client.headers = {
            'User-Agent': 'PixivIOSApp/7.6.2 (iOS 12.2; iPhone9,1)',
            'Accept-Language': 'en-US',
            'App-OS': 'ios',
            'App-OS-Version': '12.2',
            'App-Version': '7.6.2',
            'Referer': 'https://app-api.pixiv.net/',
            'Authorization': f'Bearer {token.access_token}'
        }

    # endregion

    # region requests
    @staticmethod
    def ensure_sucess_status_code(res: Response) -> bool:
        if 200 <= res.status_code < 300:
            return True
        else:
            raise HTTPError(res.status_code, res.text)

    @staticmethod
    def unescape(text: str) -> str:
        return bytes(text, 'utf8').decode()

    def post(self, url: str, data: dict, object_hook: staticmethod):
        res = self.client.post(url, data=data)
        self.ensure_sucess_status_code(res)

        return json.loads(self.unescape(res.text), object_hook=object_hook)

    def get(self, url: str, object_hook: staticmethod = None):
        pass

    # endregion

    # region oauth
    @staticmethod
    def get_token(data: dict) -> Token:
        local = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00')
        data.update({
            'get_secure_url': 1,
            'client_id': PixivConstant.CLIENT_ID,
            'client_secret': PixivConstant.CLIENT_SECRET,
        })
        headers = {
            'User-Agent': 'PixivAndroidApp/5.0.115 (Android 6.0; PixivBot)',
            'X-Client-Time': local,
            'X-Client-Hash': hashlib.md5((local + PixivConstant.HASH_SECRET).encode('utf8')).hexdigest(),
            'Accept-Language': 'en-US',
        }
        res = PixivClient.client.post('https://oauth.secure.pixiv.net/auth/token', data=data, headers=headers)
        if res.status_code == 200:
            res = json.loads(res.text, object_hook=Token.object_hook)
            # Pixiv still keeps 'response' for backwards compatibility
            del res['response']
            return Token(**res)
        else:
            raise HTTPError(res.status_code, res.text)

    @staticmethod
    def login(email: str, password: str):
        data = {
            'grant_type': 'password',
            'username': email,
            'password': password
        }
        return PixivClient(PixivClient.get_token(data))

    @staticmethod
    def refresh(refresh_token: str):
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        return PixivClient(PixivClient.get_token(data))

    # endregion

    # region download
    def download(self, url: str, filename: str, override: bool):
        res = self.client.get(url, stream=True, headers={'Referer': 'https://app-api.pixiv.net/'})
        if override and os.path.exists(filename):
            raise FileExistsError

        with open(filename, 'wb') as f:
            shutil.copyfileobj(res.raw, f)
        del res

    # endregion

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
