#!/usr/bin/env python3
"""Rebuild the recorded custom action; never send hardware commands."""
import argparse
import json
import pathlib
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=pathlib.Path,
                        default=pathlib.Path(__file__).with_name('custom_forward_down_v1.d6a'))
    args = parser.parse_args()
    frame = json.loads(pathlib.Path(__file__).with_name('action_frame.json').read_text(encoding='utf-8'))
    for row in frame['rows']:
        if (len(row) != 8 or any(type(value) is not int for value in row) or
                not 1 <= row[1] <= 10000 or any(not 0 <= value <= 1000 for value in row[2:])):
            raise ValueError('Invalid action frame')
    with args.output.open('xb'):
        pass
    with sqlite3.connect(args.output) as db:
        db.execute('CREATE TABLE ActionGroup ([Index] INTEGER PRIMARY KEY AUTOINCREMENT, '
                   'Time INT, Servo1 INT, Servo2 INT, Servo3 INT, Servo4 INT, Servo5 INT, Servo6 INT)')
        db.executemany('INSERT INTO ActionGroup VALUES (?,?,?,?,?,?,?,?)', frame['rows'])
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Action database integrity check failed')
    print('Created', args.output)
    print('No hardware commands sent')


if __name__ == '__main__':
    main()
