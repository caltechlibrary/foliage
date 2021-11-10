'''
other_tab.py: implementation of the "Other" tab
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait
from   pywebio.input import input, select, checkbox, radio
from   pywebio.input import NUMBER, TEXT, input_update, input_group
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import toast, popup, close_popup, put_buttons, put_button, put_error
from   pywebio.output import use_scope, set_scope, clear, remove, put_warning
from   pywebio.output import put_success, put_info, put_table, put_grid, span
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code, put_link
from   pywebio.output import put_processbar, set_processbar, put_loading
from   pywebio.output import put_column
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   sidetrack import set_debug, log
import threading
import webbrowser

from   .credentials import credentials_from_user, credentials_from_keyring
from   .credentials import save_credentials, credentials_complete
from   .credentials import credentials_from_file
from   .folio import Folio, RecordKind, RecordIdKind, TypeKind, NAME_KEYS
from   .ui import quit_app, reload_page, alert, warn, confirm, notify
from   .ui import image_data, user_file, JS_CODE, CSS_CODE, alert, warn


# Tab creation function.
# .............................................................................

def other_tab(log_file, backup_dir):
    return [
        put_grid([[
            put_markdown('Foliage stores the FOLIO credentials you provide the'
                         + ' first time it runs, so that you don\'t have to'
                         + ' enter them again. Click this button to update the'
                         + ' stored credentials.'),
            put_button('Edit credentials', onclick = lambda: edit_credentials(),
                       color = 'primary').style('margin-left: 20px; text-align: left'),
        ], [
            put_markdown('Before performing destructive operations, Foliage'
                         + ' saves copies of the records as they exist before'
                         + ' modification. Click this button to open the folder'
                         + ' containing the files. (Note: a given record may'
                         + ' have multiple backups with different time stamps.)'),
            put_button('Show backups',
                       onclick = lambda: webbrowser.open_new("file://" + backup_dir),
                       color = 'primary').style('margin-left: 20px; margin-top: 0.8em'),
        ], [
            put_markdown('The debug log file contains a detailed trace of'
                         + ' every action that Foliage takes. This can be'
                         + ' useful when trying to resolve bugs and other'
                         + ' problems.'),
            put_button('Show log file',
                       onclick = lambda: show_log_file(log_file),
                       color = 'primary').style('margin-left: 20px; text-align: left'),
        ]], cell_widths = 'auto 170px', cell_heights = '29% 42% 29%'),
    ]


# Miscellaneous helper functions.
# .............................................................................

def edit_credentials():
    log(f'updating credentials')
    folio = Folio()
    current_creds = folio.current_credentials()
    creds = credentials_from_user(warn_empty = False, initial_creds = current_creds)
    if current_creds != creds:
        log(f'user provided updated credentials')
        save_credentials(creds)
        folio.use_credentials(creds)
    else:
        log(f'credentials unchanged')


def show_log_file(log_file):
    if log_file and exists(log_file):
        if readable(log_file):
            webbrowser.open_new("file://" + log_file)
        else:
            alert(f'Log file is unreadable -- please report this error.')
    elif not log_file:
        warn('No log file -- log output is being directed to the terminal.')
