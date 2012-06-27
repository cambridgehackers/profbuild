#! /usr/bin/env python
import os, sys

fin = open(sys.argv[1], 'rb')
fout = open('bboutfile', 'wb')
fout.write(fin.read(0x38))
t = fin.read(1)
fout.write('%c' % 0)
fout.write(fin.read())
fin.close()
fout.close()

open(sys.argv[1], 'wb').write(open('bboutfile', 'rb').read())
