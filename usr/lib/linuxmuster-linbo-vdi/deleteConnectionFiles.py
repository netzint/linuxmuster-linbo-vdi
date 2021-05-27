#!/usr/bin/env python3
#
# deleteConnectionFiles.py
#
# joanna.meinelt@netzint.de
#
# 20201210
#
from datetime import datetime
from globalValues import dbprint,getCommandOutput,setCommand

def deleteDeprecatedFiles():
    command = "ls /tmp/vdi/start-vdi* 2>/dev/null"    # to just get if no error
    lines = getCommandOutput(command)

    timestamp = datetime.now()
    now = float(timestamp.strftime("%Y%m%d%H%M%S"))

    if lines:
        dbprint(lines)
        for line in lines:
                passedTime = 0
                line = str(line, 'ascii')
                lineSplitted = line.split('-')
                #dbprint(lineSplitted[4])
                if ((now - float(lineSplitted[2])) > 60):
                    command = "rm " + str(line)
                    dbprint(str(line) + " deleting..")
                    setCommand(command)
                else:
                    dbprint(str(line) + " under 1 min")

