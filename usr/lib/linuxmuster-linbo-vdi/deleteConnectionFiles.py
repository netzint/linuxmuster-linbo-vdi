#!/usr/bin/env python3
#
# deleteConnectionFiles.py
#
# joanna.meinelt@netzint.de
#
# 20201210
#
from datetime import datetime

import logging
import vdi_common

logger = logging.getLogger(__name__)


def deleteDeprecatedFiles():
    command = "ls /tmp/vdi/start-vdi* 2>/dev/null"    # to just get if no error
    lines = vdi_common.run_command(command)

    timestamp = datetime.now()
    now = float(timestamp.strftime("%Y%m%d%H%M%S"))

    if lines:
        logger.info(lines)
        for line in lines:
                passedTime = 0
                line = str(line, 'ascii')
                lineSplitted = line.split('-')
                #logger.info(lineSplitted[4])
                if ((now - float(lineSplitted[2])) > 60):
                    command = "rm " + str(line)
                    logger.info(str(line) + " deleting..")
                    vdi_common.run_command(command)
                else:
                    logger.info(str(line) + " under 1 min")
                return

