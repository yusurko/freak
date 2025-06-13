"""
PSA: this module is for the LEGACY (v2) iding.

For the SIQ-based ID's (upcoming 0.4), see suou.iding <https://github.com/sakuragasaki46/suou>
"""

import base64
import os
import time

epoch = 1577833200000
machine_id = int(os.getenv("MACHINE_ID", "0"))
machine_counter = 0

def new_id(*, from_date = None):
    global machine_counter

    if from_date:
        curtime = from_date.timestamp()
    else:
        curtime = time.time()

    return (
        ((int(curtime * 1000) - epoch) << 22) | 
        ((machine_id % 32) << 17) |
        ((os.getpid() % 32) << 12) |
        ## XXX two digits are not getting employed!
        ((machine_counter := machine_counter + 1) % 1024)
    )

def id_to_b32l(n):
    return (
        '_' if n < 0 else ''
    ) + base64.b32encode(
        (-n if n < 0 else n).to_bytes(10, 'big')
    ).decode().lstrip('A').lower()

def id_from_b32l(s, *, n_bytes=10):
   return (-1 if s.startswith('_') else 1) * int.from_bytes(
       base64.b32decode(s.lstrip('_').upper().rjust(16, 'A').encode()), 'big'
   )

