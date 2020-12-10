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
    command = "ls /usr/lib/linuxmuster-linbo-vdi/start-vdi* 2>/dev/null"    # to just get if no error
    lines = getCommandOutput(command)

    timestamp = datetime.now()
    now = float(timestamp.strftime("%Y%m%d%H%M%S"))

    if lines:
        dbprint(lines)
        for line in lines:
                passedTime = 0
                line = str(line, 'ascii')
                #line = line.strip("/usr/lib/linuxmuster-linbo-vdi/")
                lineSplitted = line.split('-')
                dbprint(lineSplitted[4])
                if ((now - float(lineSplitted[4])) > 100):
                    command = "rm " + str(line)
                    dbprint(str(line) + " deleting..")
                    setCommand(command)
                else:
                    dbprint(str(line) + " under 1 min")

deleteDeprecatedFiles()