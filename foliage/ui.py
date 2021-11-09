'''
ui.py: user interface utilities for Foliage

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.interrupt import wait
import os
from   os.path import exists, dirname, join, basename, abspath
import pywebio
from   pywebio.input import input, file_upload
from   pywebio.output import put_text, put_markdown, put_row, put_html, put_error
from   pywebio.output import toast, popup, close_popup, put_buttons
from   pywebio.output import use_scope, set_scope, clear, remove
from   pywebio.output import PopupSize
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.session import run_js, eval_js
from   rich import print
from   rich.panel import Panel
from   rich.style import Style

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
   the code uses to store the file from the file input dialog, specifically to
   set it to a known fake name when ESC is pressed.

   The solution to setting the .files property (which is a read-only FileList
   object) came from a 2019-06-04 posting by "superluminary" to Stack Overflow
   at https://stackoverflow.com/a/56447852/743730
*/
$(document).keyup(function(e) {
    if (e.keyCode == 27) {
        // Create a fake FileList object and reset the .files property.
        let tmp_list = new DataTransfer();
        let fake = new File(["content"], "%s");
        tmp_list.items.add(fake);
        let myFileList = tmp_list.files;
        $('#input-cards .custom-file')[0].firstElementChild.files = myFileList;
        console.log($('#input-cards .custom-file')[0].firstElementChild.files);

        // Pretend the user clicked reset.
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
.pywebio {
    min-height: calc(100vh - 70px);
    padding-top: 10px;
    padding-bottom: 1px; /* if set 0, safari has min-height issue */
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
.alert p {
    margin-bottom: 0
}
button {
    margin-bottom: 0 !important;
    filter: drop-shadow(2px 2px 2px #aaa);
}
.btn {
    filter: drop-shadow(2px 2px 3px #ddd);
    margin-bottom: 1px !important;
}
.btn-link {
    padding: 0
}
.btn-primary {
    /* Weird 1px vertical misalignment. Don't know why I have to do this. */
    margin-bottom: 1px
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
'''


# Exported functions
# .............................................................................

def alert(text, popup = True):
    log(f'alert: {text}')
    if popup:
        toast(text, color = 'error')
    else:
        width = 79 if len(text) > 75 else (len(text) + 4)
        print(Panel(text, style = Style.parse('red'), width = width))


def warn(text, popup = True):
    log(f'warning: {text}')
    if popup:
        toast(text, color = 'warn')
    else:
        width = 79 if len(text) > 75 else (len(text) + 4)
        print(Panel(text, style = Style.parse('yellow'), width = width))


def confirm(question):
    log(f'running JS function to confirm: {question}')
    return eval_js(f'confirm("{question}")')


def notify(msg):
    eval_js(f'alert("{msg}")')


def quit_app(ask_confirm = True):
    log(f'quitting (ask = {ask_confirm})')
    wait(0.25)
    if not ask_confirm or confirm('This will exit Foliage. Proceed?'):
        log(f'running JS function close_window()')
        run_js('close_window()')
        wait(0.5)
        os._exit(0)


def reload_page():
    log(f'running JS function to reload the page')
    run_js('reload_page()')


def image_data(file_name):
    here = dirname(__file__)
    image_file = join(here, 'data', file_name)
    if exists(image_file):
        log(f'reading image file {image_file}')
        with open(image_file, 'rb') as f:
            return f.read()
    log(f'could not find image in {image_file}')
    return b''


def user_file(msg):
    result = file_upload(msg)
    if result['filename'] != UPLOAD_CANCEL_MARKER:
        return result['content'].decode()
    return None
