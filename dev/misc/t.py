#!/usr/bin/env python3

import json
import sys
import csv
from   commonpy.network_utils import net
from   decouple import config

if len(sys.argv[1:]) < 1:
    sys.exit('Missing argument: file containing list of users')

user_ids = []
try:
    with open(sys.argv[1], 'r') as csv_file:
        user_ids = [row['id'] for row in csv.DictReader(csv_file)]
except Exception as ex:
    sys.exit(ex)

print(f'Read {len(user_ids)} users from file {sys.argv[1]}')


base_url = config('FOLIO_OKAPI_URL', default = None)

headers = {
    "x-okapi-token":  config('FOLIO_OKAPI_TOKEN', default = None),
    "x-okapi-tenant": config('FOLIO_OKAPI_TENANT_ID', default = None),
    "content-type":   "application/json",
}

loans = dict()
items = dict()
users = dict()

for index, user_id in enumerate(user_ids):
    url = f'{base_url}/users?query=id={user_id}'
    (result, error) = net('get', url, headers = headers)
    if error:
        sys.exit('Got error: ' + str(error))
    users[user_id] = json.loads(result.text)['users'][0]

    url = f'{base_url}/loan-storage/loans?query=userId={user_id}'
    (result, error) = net('get', url, headers = headers)
    if error:
        sys.exit('Got error: ' + str(error))
    loans[user_id] = json.loads(result.text)['loans']

    for loan in loans[user_id]:
        item_id = loan['itemId']
        url = f'{base_url}/inventory/items?query=id={item_id}'
        (result, error) = net('get', url, headers = headers)
        if error:
            sys.exit('Got error: ' + str(error))
        items[item_id] = json.loads(result.text)['items'][0]
    print(str(index).zfill(3), flush = True)
    if index > 1:
        break


for user_id in users:
    r = users[user_id]
    cituid = r['barcode'].lstrip('0')
    print('\nuser ' + cituid + ' (' + r['personal']['lastName'] + '):')
    if user_id in loans:
        for loan in loans[user_id]:
            item = items[loan['itemId']]
            title = item['title']
            if len(title) > 60:
                title = title[0:60] + ' ...'
            print('  ' + item['barcode'] + ' ' + title)
