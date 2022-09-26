import decouple
import os
import pytest

from foliage.folio import Folio, IdKind


@pytest.fixture
def define_env_vars(monkeypatch):
    monkeypatch.setenv('FOLIO_OKAPI_URL', decouple.config('FOLIO_OKAPI_URL'))
    monkeypatch.setenv('FOLIO_OKAPI_TENANT_ID', decouple.config('FOLIO_OKAPI_TENANT_ID'))
    monkeypatch.setenv('FOLIO_OKAPI_TOKEN', decouple.config('FOLIO_OKAPI_TOKEN'))


def test_record_id_type(define_env_vars):
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
