import requests
from urllib.parse import parse_qs, urlparse
from datetime import datetime, timedelta

auth_url = 'https://auth.bullhornstaffing.com/oauth/authorize'
token_url = 'https://auth.bullhornstaffing.com/oauth/token'
login_url = 'https://rest.bullhornstaffing.com/rest-services/login'
api_version = '2.0'


class AuthCodeError(Exception):
    pass


class AccessTokenError(Exception):
    pass


class SessionTokenError(Exception):
    pass


def get_auth_code(client_id, username, password, *args, **kwargs):
    req = requests.get(auth_url, params={
        'client_id': client_id,
        'username': username,
        'password': password,
        'response_type': 'code',
        'action': 'Login',
    })
    res_query = parse_qs(urlparse(req.url).query)
    print(res_query)
    if 'code' in res_query:
        return res_query['code'][0]

    raise AuthCodeError()


def prepare_token_request_params(client_id, client_secret, auth_code=None, refresh_token=None):
    params = {'client_id': client_id, 'client_secret': client_secret}

    if refresh_token:
        params.update({'grant_type': 'refresh_token', 'refresh_token': refresh_token})
    elif auth_code:
        params.update({'grant_type': 'authorization_code', 'code': auth_code})
    else:
        raise Exception('Required: auth_code or refresh_token')

    return params


def get_access_refresh_token(client_id, client_secret, auth_code, refresh_token=None):
    req = requests.post(token_url,
                        params=prepare_token_request_params(client_id, client_secret, auth_code, refresh_token))
    if 'access_token' in req.json():
        return req.json()['access_token'], req.json()['refresh_token']

    raise AccessTokenError()


def get_rest_session(access_token):
    req = requests.get(login_url, params={
        'version': api_version,
        'access_token': access_token,
    })
    if 'restUrl' in req.json():
        return req.json()['restUrl'], req.json()['BhRestToken']

    raise SessionTokenError()


"""
{
    "errorMessage": "Bad 'BhRestToken' or timed-out.",
    "errorMessageKey": "errors.authentication.invalidRestToken",
    "errorCode": 401
}
"""


class Bullhorn:
    def __init__(self, client_id, client_secret, username, password):
        self._client_id = client_id
        self._client_secret = client_secret
        self._username = username
        self._password = password
        self._rest_url = None
        self._auth_code = None
        self._access_token = None
        self._refresh_token = None
        self._session_token = None
        self._expired = None
        self._authenticated_time = None
        self._authenticating = False

    def _get_auth_code(self):
        return get_auth_code(self._client_id, self._username, self._password)

    def _get_access_refresh_token(self):
        return get_access_refresh_token(self._client_id, self._client_secret, self._auth_code, self._refresh_token)

    def _get_rest_session(self):
        return get_rest_session(self._access_token)

    def is_expired(self):
        if self._authenticated_time:
            print(datetime.now() - self._authenticated_time)

        return not (self._session_token
                    and self._authenticated_time
                    and datetime.now() - self._authenticated_time < timedelta(minutes=10))

    def login(self):
        self._authenticating = True
        self._authenticated_time = None
        if not self._auth_code:
            self._access_token = None
            self._refresh_token = None
            self._auth_code = self._get_auth_code()
        if not self._access_token:
            self._rest_url = None
            self._session_token = None
            self._access_token, self._refresh_token = self._get_access_refresh_token()
        if not self._session_token:
            self._rest_url, self._session_token = self._get_rest_session()
        self._authenticated_time = datetime.now()
        self._authenticating = False
        return

    def send_request(self, path, params):
        if self.is_expired():
            self._access_token = None

        while True:
            try:
                self.login()

                req = requests.get(f'{self._rest_url}{path}',
                                   params=params,
                                   headers={'BhRestToken': self._session_token})

                if req.status_code == 401:
                    raise SessionTokenError()

            except AuthCodeError:
                raise Exception('Fatal error')
            except AccessTokenError:
                self._auth_code = None
            except SessionTokenError:
                self._access_token = None
            else:
                return req.json(), req.status_code

    def entity(self, entity, entity_id, fields='*'):
        return self.send_request(f'entity/{entity}/{entity_id}', params={'fields': fields})

    def proxy(self, path, query):
        return self.send_request(path, params=query)
