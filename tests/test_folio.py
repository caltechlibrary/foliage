import pytest


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
