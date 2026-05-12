def test_encoding():
    from foliage.credentials import _encoded, _decoded
    assert _decoded(_encoded('a', '1', 'c')) == ('a', '1', 'c', '', '', '')


def test_decoding_legacy_encoded_value():
    from foliage.credentials import _decoded
    assert _decoded('a\x031\x03c') == ('a', '1', 'c', '', '', '')


def test_current_credentials(monkeypatch):
    from foliage.credentials import Credentials, current_credentials
    monkeypatch.setenv('FOLIO_OKAPI_URL', 'https://foo')
    monkeypatch.setenv('FOLIO_OKAPI_TENANT_ID', '1')
    monkeypatch.setenv('FOLIO_OKAPI_TOKEN', 'abc')
    monkeypatch.setenv('FOLIO_OKAPI_REFRESH_TOKEN', 'refresh')
    monkeypatch.setenv('FOLIO_OKAPI_ACCESS_TOKEN_EXPIRES', '2026-05-12T12:00:00Z')
    monkeypatch.setenv('FOLIO_OKAPI_REFRESH_TOKEN_EXPIRES', '2026-05-19T12:00:00Z')
    assert current_credentials() == Credentials('https://foo',
                                               '1',
                                               'abc',
                                               'refresh',
                                               '2026-05-12T12:00:00Z',
                                               '2026-05-19T12:00:00Z')


def test_credentials_complete():
    from foliage.credentials import Credentials, credentials_complete
    assert credentials_complete(Credentials('https://foo', '1', 'abc'))


def test_credentials_from_file(monkeypatch, tmp_path):
    from foliage.credentials import Credentials, credentials_from_file
    d = tmp_path / 'sub'
    d.mkdir()
    p = d / 'settings.ini'
    p.write_text('''
[settings]
FOLIO_OKAPI_URL = https://foo
FOLIO_OKAPI_TENANT_ID = 1
FOLIO_OKAPI_TOKEN = abc
FOLIO_OKAPI_REFRESH_TOKEN = refresh
FOLIO_OKAPI_ACCESS_TOKEN_EXPIRES = 2026-05-12T12:00:00Z
FOLIO_OKAPI_REFRESH_TOKEN_EXPIRES = 2026-05-19T12:00:00Z
''')
    monkeypatch.chdir(d)
    assert credentials_from_file(str(p)) == Credentials('https://foo',
                                                        '1',
                                                        'abc',
                                                        'refresh',
                                                        '2026-05-12T12:00:00Z',
                                                        '2026-05-19T12:00:00Z')


def test_credentials_from_env(monkeypatch):
    from foliage.credentials import Credentials, credentials_from_env
    monkeypatch.setenv('FOLIO_OKAPI_URL', 'https://foo')
    monkeypatch.setenv('FOLIO_OKAPI_TENANT_ID', '1')
    monkeypatch.setenv('FOLIO_OKAPI_TOKEN', 'abc')
    monkeypatch.setenv('FOLIO_OKAPI_REFRESH_TOKEN', 'refresh')
    monkeypatch.setenv('FOLIO_OKAPI_ACCESS_TOKEN_EXPIRES', '2026-05-12T12:00:00Z')
    monkeypatch.setenv('FOLIO_OKAPI_REFRESH_TOKEN_EXPIRES', '2026-05-19T12:00:00Z')
    assert credentials_from_env() == Credentials('https://foo',
                                                 '1',
                                                 'abc',
                                                 'refresh',
                                                 '2026-05-12T12:00:00Z',
                                                 '2026-05-19T12:00:00Z')
