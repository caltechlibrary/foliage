'''
list_tab.py: implementation of the "List UUIDs" tab

Copyright
---------

Copyright (c) 2021-2022 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.interrupt import reset_interrupts
from   pprint import pformat
import pyperclip
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import popup, close_popup, put_buttons, put_button
from   pywebio.output import use_scope, clear
from   pywebio.output import put_grid, put_scrollable, put_code
from   pywebio.output import put_processbar, set_processbar
from   pywebio.pin import pin, put_select
from   sidetrack import log
import threading

from   foliage.base_tab import FoliageTab
from   foliage.export import export_records
from   foliage.folio import Folio, TypeKind
from   foliage.ui import stop_processbar, note_error, tell_failure


# Tab definition class.
# .............................................................................

class ListTab(FoliageTab):
    def contents(self):
        return {'title': 'List UUIDs', 'content': tab_contents()}

    def pin_watchers(self):
        return {}


# Tab body.
# .............................................................................

def tab_contents():
    log('generating list tab contents')
    return [
        put_grid([[
            put_markdown('Select a FOLIO type to list:').style('margin-top: 6px'),
            put_select('list_type', options = [
                {'label': 'Acquisition units', 'value': TypeKind.ACQUISITION_UNIT},
                {'label': 'Address types', 'value': TypeKind.ADDRESS},
                {'label': 'Alternative title types', 'value': TypeKind.ALT_TITLE},
                {'label': 'Call number types', 'value': TypeKind.CALL_NUMBER},
                {'label': 'Classification types', 'value': TypeKind.CLASSIFICATION},
                {'label': 'Contributor types', 'value': TypeKind.CONTRIBUTOR},
                {'label': 'Contributor name types', 'value': TypeKind.CONTRIBUTOR_NAME},
                {'label': 'Department types', 'value': TypeKind.DEPARTMENT},
                {'label': 'Expense classes', 'value': TypeKind.EXPENSE_CLASS},
                {'label': 'Fixed due date schedules', 'value': TypeKind.FIXED_DUE_DATE_SCHED},
                {'label': 'Patron group types', 'value': TypeKind.GROUP},
                {'label': 'Holdings types', 'value': TypeKind.HOLDINGS},
                {'label': 'Holdings note types', 'value': TypeKind.HOLDINGS_NOTE},
                {'label': 'Holdings source types', 'value': TypeKind.HOLDINGS_SOURCE},
                {'label': 'Identifier types', 'value': TypeKind.ID},
                {'label': 'ILL policy types', 'value': TypeKind.ILL_POLICY},
                {'label': 'Instance types', 'value': TypeKind.INSTANCE},
                {'label': 'Instance format types', 'value': TypeKind.INSTANCE_FORMAT},
                {'label': 'Instance note types', 'value': TypeKind.INSTANCE_NOTE},
                {'label': 'Instance relationship types', 'value': TypeKind.INSTANCE_REL},
                {'label': 'Instance status types', 'value': TypeKind.INSTANCE_STATUS},
                {'label': 'Item note types', 'value': TypeKind.ITEM_NOTE},
                {'label': 'Item damaged status types', 'value': TypeKind.ITEM_DAMAGED_STATUS},
                {'label': 'Loan types', 'value': TypeKind.LOAN},
                {'label': 'Loan policy types', 'value': TypeKind.LOAN_POLICY},
                {'label': 'Location types', 'value': TypeKind.LOCATION},
                {'label': 'Material types', 'value': TypeKind.MATERIAL},
                {'label': 'Nature of content term types', 'value': TypeKind.NATURE_OF_CONTENT},
                # {'label': 'Order lines', 'value': TypeKind.ORDER_LINE},
                {'label': 'Organizations', 'value': TypeKind.ORGANIZATION},
                {'label': 'Service point types', 'value': TypeKind.SERVICE_POINT},
                {'label': 'Shelf location types', 'value': TypeKind.SHELF_LOCATION},
                {'label': 'Statistical code types', 'value': TypeKind.STATISTICAL_CODE},
            ]).style('margin-left: 10px; margin-bottom: 0'),
            put_button('Get list', onclick = lambda: do_list(),
                       ).style('margin-left: 10px; text-align: left'),
            put_button('Clear', outline = True, onclick = lambda: clear_tab()
                       ).style('margin-left: 10px; text-align: right'),
        ]])
    ]


# Tab implementation.
# .............................................................................

def clear_tab():
    log('clearing tab')
    clear('output')


def do_list():
    folio = Folio()
    reset_interrupts()
    with use_scope('output', clear = True):
        put_processbar('bar', init = 1/2)
        requested = pin.list_type
        log(f'getting list of {requested} types')
        try:
            types = folio.types(requested)
        except Exception as ex:         # noqa: noqa: PIE786
            import traceback
            log('Exception info: ' + str(ex) + '\n' + traceback.format_exc())
            put_html('<br>')
            tell_failure('Error: ' + str(ex))
            return
        finally:
            set_processbar('bar', 2/2)
        cleaned_name = requested.split('/')[-1].replace("-", " ")
        put_row([
            put_markdown(f'Found {len(types)} values for {cleaned_name}:'
                         ).style('margin-left: 17px; margin-top: 6px'),
            put_button('Export', outline = True,
                       onclick = lambda: export_records(types, requested),
                       ).style('text-align: right; margin-right: 17px'),
        ]).style('margin-top: 15px; margin-bottom: 14px')
        rows = []
        for item in types:
            name = item.data[TypeKind.name_key(requested)]
            title = f'Data for {cleaned_name} value "{name.title()}"'
            rows.append([name, link_button(name, item.id, title, requested),
                         copy_button(item.id).style('padding: 0; margin-right: 13px')])

        contents = [[put_markdown('**Name**'), put_markdown('**Id**'), put_text('')]]
        contents += sorted(rows, key = lambda x: x[0])
        put_grid(contents, cell_widths = 'auto auto 106px')
        stop_processbar()


def show_record(title, id_, record_type):
    folio = Folio()
    try:
        log(f'getting {record_type} record {id_} from FOLIO')
        recs  = folio.types(record_type)
    except Exception as ex:             # noqa: noqa: PIE786
        note_error(str(ex))
        return

    event = threading.Event()

    def clk(val):
        event.set()

    record  = recs[0] if isinstance(recs, list) and len(recs) > 0 else recs
    pins  = [
        put_scrollable(put_code(pformat(record.data, indent = 2)), height = 400),
        put_buttons([{'label': 'Close', 'value': 1}], onclick = clk).style('float: right'),
    ]
    popup(title = title, content = pins, size = 'large')

    event.wait()
    close_popup()


def link_button(name, id_, title, record_type):
    return put_button(id_, link_style = True,
                      onclick = lambda: show_record(title, id_, record_type),
                      ).style('margin-left: 0; margin-top: 0.25em; margin-bottom: 0.5em')


def copy_button(text):
    def copy_to_clipboard():
        log(f'copying {text} to clipboard')
        pyperclip.copy(text)

    return put_button('Copy id', onclick = lambda: copy_to_clipboard(),
                      outline = True, small = True).style('text-align: center')
