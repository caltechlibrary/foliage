import pytest


class _FakeHeaders(dict):
    def get_all(self, key):
        value = self.get(key)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]


class _FakeResponse:
    def __init__(self, status_code, text = '', headers = None):
        self.status_code = status_code
        self.text = text
        self.headers = _FakeHeaders(headers or {})
        self.raw = type('Raw', (), {'headers': self.headers})()


@pytest.fixture
def define_env_vars(monkeypatch):
    from os import path
    monkeypatch.chdir(path.dirname(__file__))

    from decouple import Config, RepositoryIni
    source = Config(RepositoryIni(source = 'settings.ini'))
    url = source.get('FOLIO_OKAPI_URL')
    tenant = source.get('FOLIO_OKAPI_TENANT_ID')
    token = source.get('FOLIO_OKAPI_TOKEN')

    monkeypatch.setenv('FOLIO_OKAPI_URL', url)
    monkeypatch.setenv('FOLIO_OKAPI_TENANT_ID', tenant)
    monkeypatch.setenv('FOLIO_OKAPI_TOKEN', token)


def test_record_id_type(define_env_vars):
    from foliage.folio import Folio, IdKind
    folio = Folio()
    assert folio.id_kind('35047019219716') == IdKind.ITEM_BARCODE
    assert folio.id_kind('d893839b-0309-4856-b496-0db89a0a6a04') == IdKind.ITEM_ID
    assert folio.id_kind('it00002135242') == IdKind.ITEM_HRID
    assert folio.id_kind('946cce1b-0451-460e-816f-51436182efaa') == IdKind.HOLDINGS_ID
    assert folio.id_kind(r'\35047018212589') == IdKind.ITEM_BARCODE
    assert folio.id_kind(r'\35047019565233') == IdKind.ITEM_BARCODE
    assert folio.id_kind('nobarcode1') == IdKind.ITEM_BARCODE
    assert folio.id_kind('nobarcode10') == IdKind.ITEM_BARCODE
    assert folio.id_kind('nobarcode10000') == IdKind.ITEM_BARCODE
    assert folio.id_kind('nobarcode10001') == IdKind.ITEM_BARCODE
    assert folio.id_kind('nobarcode10002') == IdKind.ITEM_BARCODE
    assert folio.id_kind('350470106306') == IdKind.ITEM_BARCODE
    assert folio.id_kind('350470106969') == IdKind.ITEM_BARCODE
    assert folio.id_kind('93') == IdKind.ITEM_BARCODE
    assert folio.id_kind('95') == IdKind.ITEM_BARCODE
    assert folio.id_kind('101') == IdKind.ITEM_BARCODE
    assert folio.id_kind('TEMP-D1234') == IdKind.ITEM_BARCODE
    assert folio.id_kind('TEMP-FFF123') == IdKind.ITEM_BARCODE
    assert folio.id_kind('tmp-21924070') == IdKind.ITEM_BARCODE
    assert folio.id_kind('cit.oai.caltech.folio.ebsco.com.fs00001057.17c5c348.8796.4b11.90a8.6b31ff9509ed') == IdKind.ACCESSION
    assert folio.id_kind('cit.oai.edge.caltech.folio.ebsco.com.fs00001057.17c5c348.8796.4b11.90a8.6b31ff9509ed') == IdKind.ACCESSION


def test_extracting_instance_id():
    from foliage.folio import instance_id_from_accession
    instance_id_from_accession('cit.oai.caltech.folio.ebsco.com.fs00001057.17c5c348.8796.4b11.90a8.6b31ff9509ed') == '17c5c348-8796-4b11-90a8-6b31ff9509ed'
    instance_id_from_accession('cit.oai.edge.caltech.folio.ebsco.com.fs00001057.17c5c348.8796.4b11.90a8.6b31ff9509ed') == '17c5c348-8796-4b11-90a8-6b31ff9509ed'


def test_new_login_with_expiry_parses_cookies(monkeypatch):
    from foliage import folio as folio_module

    calls = []

    def fake_net(op, url, headers = None, data = None):
        calls.append(url)
        return _FakeResponse(
            201,
            '{"accessTokenExpiration":"2026-05-12T12:00:00Z","refreshTokenExpiration":"2026-05-19T12:00:00Z"}',
            headers = {
                'Set-Cookie': [
                    'folioAccessToken=access.jwt; Path=/; HttpOnly',
                    'folioRefreshToken=refresh.jwt; Path=/authn; HttpOnly',
                ]
            }
        ), None

    monkeypatch.setattr(folio_module, 'net', fake_net)

    auth, error = folio_module.Folio.new_login('https://example', 'diku', 'user', 'pw')

    assert error is None
    assert auth['token'] == 'access.jwt'
    assert auth['refresh_token'] == 'refresh.jwt'
    assert auth['access_token_expires'] == '2026-05-12T12:00:00Z'
    assert auth['refresh_token_expires'] == '2026-05-19T12:00:00Z'
    assert calls[0].endswith('/authn/login-with-expiry')


def test_refresh_token_if_needed(monkeypatch):
    from foliage import folio as folio_module
    from foliage.credentials import current_credentials, use_credentials

    def fake_net(op, url, headers = None, data = None):
        assert url.endswith('/authn/refresh')
        assert headers['Cookie'] == 'folioRefreshToken=refresh.jwt'
        return _FakeResponse(
            201,
            '{"accessTokenExpiration":"2026-05-12T13:00:00Z","refreshTokenExpiration":"2026-05-19T13:00:00Z"}',
            headers = {
                'Set-Cookie': [
                    'folioAccessToken=new-access.jwt; Path=/; HttpOnly',
                    'folioRefreshToken=new-refresh.jwt; Path=/authn; HttpOnly',
                ]
            }
        ), None

    monkeypatch.setenv('USE_KEYRING', 'false')
    monkeypatch.setenv('FOLIO_OKAPI_URL', 'https://example')
    monkeypatch.setenv('FOLIO_OKAPI_TENANT_ID', 'diku')
    monkeypatch.setenv('FOLIO_OKAPI_TOKEN', 'old-access.jwt')
    monkeypatch.setenv('FOLIO_OKAPI_REFRESH_TOKEN', 'refresh.jwt')
    monkeypatch.setenv('FOLIO_OKAPI_ACCESS_TOKEN_EXPIRES', '2026-05-12T11:00:00Z')
    monkeypatch.setenv('FOLIO_OKAPI_REFRESH_TOKEN_EXPIRES', '2026-05-19T13:00:00Z')
    monkeypatch.setattr(folio_module, 'net', fake_net)

    assert folio_module.Folio()._refresh_token_if_needed(force = False)
    creds = current_credentials()
    assert creds.token == 'new-access.jwt'
    assert creds.refresh_token == 'new-refresh.jwt'
    assert creds.access_token_expires == '2026-05-12T13:00:00Z'
    assert creds.refresh_token_expires == '2026-05-19T13:00:00Z'
