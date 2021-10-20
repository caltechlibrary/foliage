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
import pywebio
from   pywebio.input import input
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

JS_ADDITIONS = '''
  function confirm_action(msg) { return confirm(msg); }
  function confirm_exit() { return confirm("This will exit the application."); }
  function close_window() { window.close(); }
'''

CSS_ADDITIONS = ''


# Exported functions
# .............................................................................

def quit_app():
    if __debug__: log(f'user clicked the quit button')
    if eval_js('confirm_exit()'):
        if __debug__: log(f'user confirmed quitting')
        run_js('close_window()')
        wait(0.5)
        os._exit(0)


def show_error(msg):
    log(f'showing error popup: {msg}')
    popup('Error', [
        put_html(f'<p class="text-danger">{msg}</p>'),
        put_buttons(['Close'], onclick = lambda _: close_popup())
        ], implicit_close = True)


def alert(text):
    log(f'alert: {text}')
    width = 79 if len(text) > 75 else (len(text) + 4)
    print(Panel(text, style = Style.parse('red'), width = width))


def warn(text):
    log(f'warning: {text}')
    width = 79 if len(text) > 75 else (len(text) + 4)
    print(Panel(text, style = Style.parse('yellow'), width = width))
