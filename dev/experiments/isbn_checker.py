#!/usr/bin/env python3

import sys
from   sys import exit as exit
if sys.version_info <= (3, 8):
    print('foliage requires Python version 3.8 or higher,')
    print('but the current version of Python is ' +
          str(sys.version_info.major) + '.' + str(sys.version_info.minor) + '.')
    exit(1)

from   commonpy.exceptions import NoContent, ServiceFailure, RateLimitExceeded
from   commonpy.interrupt import wait
from   commonpy.string_utils import antiformat
from   commonpy.network_utils import net
from   decouple import config
import json
import os
import plac
import pywebio
from   pywebio.input import input
from   pywebio.output import put_text, put_markdown, put_buttons, put_row, put_html
from   pywebio.output import use_scope, set_scope, clear, remove
from   pywebio.output import toast, popup, close_popup
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
# Default server is tornado, and tornado mucks with logging.
# aiohttp server does not.  Unfortunately, only tornado auto-reloads.
# from   pywebio.platform.aiohttp import start_server
from   pywebio import start_server
from   pywebio.session import run_js, eval_js
import signal
import time
import tornado

if __debug__:
    from sidetrack import set_debug, log


# Helper functions
# .............................................................................

def folio(url, retry = 0):
    '''Do HTTP GET on "url" & return results of calling result_producer on it.'''
    headers = {
        "x-okapi-token": config('FOLIO_OKAPI_TOKEN'),
        "x-okapi-tenant": config('FOLIO_OKAPI_TENANT_ID'),
        "content-type": "application/json",
    }

    get_url = config('FOLIO_OKAPI_URL') + url
    (response, error) = net('get', get_url, headers = headers)
    if not error:
        if __debug__: log(f'got result from {url}')
        return json.loads(response.text)
    elif isinstance(error, NoContent):
        if __debug__: log(f'got empty content from {url}')
        return None
    elif isinstance(error, RateLimitExceeded):
        retry += 1
        if retry > 3:
            raise FolioError(f'Rate limit exceeded for {url}')
        else:
            # Wait and then call ourselves recursively.
            if __debug__: log(f'hit rate limit; pausing 2s')
            wait(2)
            return folio(url, retry = retry)
    else:
        raise RuntimeError(f'Problem contacting {url}: {antiformat(error)}')


def checker():
    put_html('''<script type="text/javascript">
      function confirm_exit() { return confirm("Quit Foliage?"); }
      function close_window() { window.close(); }
    </script>''')

    put_markdown('## ISBN checker')
    put_text('Enter an ISBN number and click the "Check" button. This will'
             ' contact FOLIO to check if it\'s a valid ISBN number.')
    put_html('<br>')
    put_row([
        # put_html('<div class="row align-items-center">'),
        put_input('isbn'),
        None,                           # Add space between input field & button
        put_actions('button', buttons = ['Check']),
        # put_html('</div>')
        ])
    put_row([
        put_buttons([dict(label = 'Quit', value = 'q', color = 'danger')],
                    onclick = lambda _: quit_program()).style('margin-top: 5px')
        ])
    while True:
        clicked = pin_wait_change('button')
        url  = f'/isbn/validator?isbn={pin.isbn}'
        if __debug__: log(f'asking Folio to check {pin.isbn}')
        result = folio(url)
        if 'isValid' in result:
            msg = (f'{pin.isbn} is ' +
                   ('a valid' if result['isValid'] else 'not a valid')
                   + ' ISBN number')
            popup(msg, put_buttons(['OK'], onclick = lambda _: close_popup()))
            pin.isbn = ''


def quit_program():
    if __debug__: log(f'user clicked the quit button')
    if eval_js('confirm_exit()'):
        if __debug__: log(f'user confirmed quitting')
        run_js('close_window()')
        wait(0.5)
        os._exit(0)


# Main program.
# .............................................................................

# For more info about how plac works see https://plac.readthedocs.io/en/latest/
@plac.annotations(
    version    = ('print version info and exit',                'flag',   'V'),
    debug      = ('log debug output to "OUT" ("-" is console)', 'option', '@'),
)

def main(version = False, debug = 'OUT'):
    '''Foliage: FOLIo chAnGe Editor, a tool to do bulk changes in FOLIO.'''

    # Set up debug logging as soon as possible, if requested ------------------

    if debug != 'OUT':
        if __debug__: set_debug(True, debug)
        import faulthandler
        faulthandler.enable()
        if not sys.platform.startswith('win'):
            import signal
            from boltons.debugutils import pdb_on_signal
            pdb_on_signal(signal.SIGUSR1)
    else:
        debug = False

    # Preprocess arguments and handle early exits -----------------------------

    if version:
        from foliage import print_version
        print_version()
        exit()

    # Do the real work --------------------------------------------------------

    start_server(checker, port = 8080, auto_open_webbrowser = True, debug = debug)


# Main entry point.
# .............................................................................

# The following allows users to invoke this using "python3 -m handprint".
if __name__ == '__main__':
    plac.call(main)
