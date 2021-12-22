'''
ui.py: user interface utilities for Foliage

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.interrupt import wait
from   commonpy.string_utils import antiformat
from   contextlib import contextmanager
from   decouple import config
import os
from   os.path import exists, dirname, join, basename, abspath
from   PyQt5.QtWidgets import QApplication, QMessageBox
import pywebio
from   pywebio.input import input, file_upload
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import toast, popup, close_popup, put_buttons
from   pywebio.output import put_success, put_warning, put_error
from   pywebio.output import use_scope, set_scope, clear, remove
from   pywebio.output import PopupSize, put_loading
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.session import run_js, eval_js
from   rich.panel import Panel
from   rich.style import Style
import sys
import threading

if __debug__:
    from sidetrack import set_debug, log


# Exported constants.
# .............................................................................

UPLOAD_CANCEL_MARKER = "_fake_foliage_fake_.txt"

JS_CODE = '''
function close_window() { window.close() }
function reload_page() { location.reload() }


/* Make the escape key work in file upload dialogs.  The natural action (IMHO)
   for ESC is to cancel the dialog, but there's no "cancel" functionality in
   PyWebIO's file_upload() dialog.  In fact, if you click the "reset" button
   then click "submit", you still get a file!  Very undesirable behavior.
   There's no good way to fix it short of rewriting file.ts in the PyWebIO
   code, so the following is an egregious hack: muck with the variable that
   the code uses to store the file from the file input dialog, specifically by
   setting the variable to a known fake name when ESC is pressed.

   The solution to setting the .files property (which is a read-only FileList
   object) came from a 2019-06-04 posting by "superluminary" to Stack Overflow
   at https://stackoverflow.com/a/56447852/743730
*/
$(document).keyup(function(e) {
    /* Ignore this key press if it's not the escape key. */
    if (e.keyCode != 27) return;

    /* Case of PyWebIO modal dialogs with a cancel button. */
    if ($('.modal-content button.btn-secondary').length) {
        $('.modal-content button.btn-secondary').click();
    }

    /* Case of PyWebIO file_upload() dialog, which lacks a cancel button. */
    if ($('.ws-form-submit-btns button[type="reset"]').length) {
        // Create a fake FileList object and reset the .files property.
        let tmp_list = new DataTransfer();
        let fake = new File(["content"], "%s");
        tmp_list.items.add(fake);
        let myFileList = tmp_list.files;
        $('#input-cards .custom-file')[0].firstElementChild.files = myFileList;
        console.log($('#input-cards .custom-file')[0].firstElementChild.files);

        // Pretend the user clicked the "reset" button.
        $('.ws-form-submit-btns button[type="reset"]').click();

        // Give it a short time for JavaScript actions to work, and submit.
        setTimeout(() => { $('.custom-file input').submit() }, 200);
    }
});
''' % UPLOAD_CANCEL_MARKER

# Hiding the footer is only done because in my environment, the footer causes
# the whole page to scroll down, thus hiding part of the top.  I don't mind
# the mention of PyWebIO in the footer, but the page behavior is a problem.

# The footer height and pywebio min-height interact. I found these numbers by
# trial and error.

CSS_CODE = '''
html {
    position: relative;
}

body {
    padding-bottom: 66px;
}

pre {
    background-color: #f8f8f8;
    padding: 5px;
    border: 1px solid #eee;
    border-radius: .25rem;
}

.pywebio {
    min-height: calc(100vh - 70px);
    padding-top: 10px;
    padding-bottom: 1px; /* if set 0, safari has min-height issue */
}

#output-container {
    margin-bottom: 40px;
}

footer {
    position: absolute;
    width: 100%;
    bottom: -1px;
    height: 58px !important;
    background-color: white !important;
}

.markdown-body table {
    display: inline-table;
}

.markdown-body table td {
    padding: 3px;
    padding-right: 6px;
}

.alert p {
    margin-bottom: 0
}

button {
    margin-bottom: 0 !important;
    filter: drop-shadow(1px 1px 2px #eee);
}

.btn {
    margin-bottom: 1px !important;
    min-width: 85px;
}

.btn-link {
    padding: 0
}

/* Weird 1px vertical misalignment. Don't know why I have to do this. */

.btn-danger, .btn-primary, .btn-secondary {
    margin-bottom: 1pt !important;
}

/* Special case for danger buttons, to adjust due to effects of red color. */
.btn-danger {
    filter: drop-shadow(1px 1px 2px #dadada);
}

.webio-tabs-content {
    padding-bottom: 0 !important;
}

#input-container {
    border-radius: .25rem;
    box-shadow: 10px 10px 20px #aaa;
    position: absolute;
    padding-left: 0;
    padding-right: 0;
    top: 190px;
    width: 500px;
    left: calc(50% - 250px);
}

#input-cards.container {
    padding-left: 0 !important;
    padding-right: 0 !important;
    border-radius: .25rem;
}

textarea.form-control[readonly] {
    background: repeating-linear-gradient(-45deg, #fff, #f6f6f6 8px);
}

.spinner-border {
    position: absolute;
    left: calc(50% - 1em);
    top: 7em;
}

.modal-lg {
    max-width: 90%;
}
'''


# Exported functions
# .............................................................................

def inside_pyinstaller_app():
    '''Return True if we are running as an app created using PyInstaller.'''
    # This function is for the sake of making code more readable, because
    # the purpose of testing the following condition is not at all obvious.
    return getattr(sys, 'frozen', False)


def close_splash_screen():
    '''Close the PyInstaller-based splash screen shown during startup.'''
    if not inside_pyinstaller_app():
        return
    if sys.platform.startswith('darwin'):
        # PyInstaller does not currently support splash screens on macOS.
        return
    log('closing splash screen')
    try:
        # pyi_splash only exists inside the PyInstaller-produced executable.
        import pyi_splash
        pyi_splash.close()
    except Exception as ex:
        # Only log an error if running the PyInstaller-produced app.
        if inside_pyinstaller_app():
            log('exception trying to close splash screen: ' + str(ex))


def confirm(question, danger = False):
    log(f'asking user to confirm: {antiformat(question)}')

    event = threading.Event()
    clicked_ok = False

    def clk(val):
        nonlocal clicked_ok
        clicked_ok = val
        event.set()

    ok_color = 'danger' if danger else 'primary'
    pins = [
        put_buttons([
            {'label': 'Cancel', 'value': False, 'color': 'secondary'},
            {'label': 'OK',     'value': True, 'color': ok_color},
        ], onclick = clk).style('float: right')
    ]
    popup(title = '⚠️ ' + question, content = pins, closable = False)
    event.wait()
    close_popup()
    wait(0.25)                           # Give time for popup to go away.

    log(f'user clicked {"OK" if clicked_ok else "Cancel"}')
    return clicked_ok


def notify(msg):
    log(f'notifying user with message "{antiformat(msg)}"')

    event = threading.Event()

    def clk(val):
        event.set()

    pins = [
        put_buttons([{'label': 'OK', 'value': True}],
                    onclick = clk).style('float: right')
    ]
    popup(title = '✋ ' + msg, content = pins, closable = True)
    event.wait()
    close_popup()
    wait(0.25)                           # Give time for popup to go away.
    log(f'notification popup closed explicitly')


def stop_processbar():
    '''Stop the animation of the PyWebIO process bar.'''
    eval_js('''$("#webio-processbar-bar").removeClass("progress-bar-animated");''')


def quit_app(ask_confirm = True):
    log(f'quitting (ask = {ask_confirm})')
    if ask_confirm:
        wait(0.25)
    if not ask_confirm or confirm('Exit Foliage?', danger = True):
        log(f'running JS function close_window()')
        run_js('close_window()')
        wait(0.5)
        raise SystemExit('User quit application')


def reload_page():
    log(f'running JS function to reload the page')
    run_js('reload_page()')


def image_data(file_name):
    here = dirname(__file__)
    image_file = join(here, 'data', file_name)
    if exists(image_file):
        log(f'reading image file {antiformat(image_file)}')
        with open(image_file, 'rb') as f:
            return f.read()
    log(f'could not find image in {antiformat(image_file)}')
    return b''


def user_file(msg):
    result = file_upload(msg)
    if result and result['filename'] != UPLOAD_CANCEL_MARKER:
        return result['content'].decode()
    return None


# Summary of the scheme below:
#   - "tell" functions print a message in the output area
#   - "note" functions print a "toast" message shown temporarily across the top.
# Warning & error note functions print to the console if popup == False.
# The info note function just doesn't print anything if popup == False.
#
# Since note_* functions may be called before the PyWebIO GUI system has
# started, we need alternative approaches for different cases.
#
#                 Has the PyWebIO GUI started?
#                          /           \
#                       yes            no
#                       /               \
#    Use PyWebIO functions     Are we in the PyInstaller-built app?
#                                        /        \
#                                      yes        no
#                                      /           \
#                                 Use PyQt      Print to command line

qtapp = QApplication([''])

def tell_success(text):
    '''Wrapper around put_success(...) that also formats markdown.'''
    log(antiformat(text))
    put_success(put_markdown(text).style('margin-left: -3px'))


def tell_warning(text):
    '''Wrapper around put_warning(...) that also formats markdown.'''
    log(antiformat(text))
    put_warning(put_markdown(text).style('margin-left: -3px'))


def tell_failure(text):
    '''Wrapper around put_failure(...) that also formats markdown.'''
    log(antiformat(text))
    put_error(put_markdown(text).style('margin-left: -3px'))


def note_info(text):
    '''Show an informational toast message.'''
    log(antiformat(text))
    if os.environ.get('FOLIAGE_GUI_STARTED', 'False') == 'True':
        toast(text, color = 'green')
    elif inside_pyinstaller_app():
        # We don't print info-level msgs in this case.
        pass
    else:
        from rich import print
        print('[green]' + text + '[/]')


def note_warn(text):
    '''Show a warning toast message.'''
    log(antiformat(text))
    if os.environ.get('FOLIAGE_GUI_STARTED', 'False') == 'True':
        toast(text, color = 'warn')
    elif inside_pyinstaller_app():
        # Close the PyInstaller app splash screen if it's still visible.
        close_splash_screen()
        title = 'Foliage' if os.name == 'nt' else 'Foliage warning'
        QMessageBox.warning(None, title, 'Warning: ' + text)
    else:
        from rich import print
        width = 79 if len(text) > 75 else (len(text) + 4)
        print(Panel(text, style = Style.parse('yellow'), width = width))


def note_error(text):
    '''Show an error toast message.'''
    log(antiformat(text))
    if os.environ.get('FOLIAGE_GUI_STARTED', 'False') == 'True':
        toast(text, color = 'error')
    elif inside_pyinstaller_app():
        # Close the PyInstaller app splash screen if it's still visible.
        close_splash_screen()
        title = 'Foliage' if os.name == 'nt' else 'Foliage error'
        QMessageBox.critical(None, title, 'Error: ' + text)
    else:
        from rich import print
        width = 79 if len(text) > 75 else (len(text) + 4)
        print(Panel(text, style = Style.parse('red'), width = width))
