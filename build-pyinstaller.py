#!/usr/bin/env python

import PyInstaller.__main__

PyInstaller.__main__.run([
    './set-vm-guestinfo/set-vm-guestinfo.py',
    '--name=%s' % "set-vm-guestinfo.py",
    '--onefile',
])