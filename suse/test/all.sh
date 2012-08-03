#!/bin/bash
#set -e
sudo rm -rf sandbox/bb* sandbox/lockfile* 2>/dev/null
#../master.py -l -p openSUSE:12.1 `ls ~/mirror/suse/repo/openSUSE:12.1/*._manifest | sed -e "s/\._manifest//" -e "s/.*\///"`
../master.py -l -p openSUSE:12.1 `cat packagelist.txt`
echo FAILED PACKAGES: `./badlist.sh | wc` TOTAL RPMS: `find localrpmdir -name \*.rpm | wc`
