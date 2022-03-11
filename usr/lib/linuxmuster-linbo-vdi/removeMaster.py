#!/usr/bin/env python3
#
# removeMaster.py
#
# joanna@linuxmuster.net
#
# 20201119
#

import json
import paramiko
import sys
import operator
from datetime import datetime
import time
import logging
import getVmStates
from globalValues import node,proxmox,getMasterDetails

logger = logging.getLogger(__name__)


# finds existing master VMs and sorts them by dateOfCreation
# so the oldest can be deleted first
# returns if no master found
def find_and_sort_Existing_Masters(masterStates, masterVmids):
    existing_master = {}
    vmids = masterVmids.split(',')
    logger.info(vmids)
    for vmid in vmids:
        if masterStates[vmid] is not None \
                and masterStates[vmid] != "summary" \
                and masterStates[vmid] != "basic":
            try:
                dateOfCreation = masterStates[vmid]['dateOfCreation']
                existing_master[vmid] = dateOfCreation
            except Exception:
                pass
    if len(existing_master) == 0:
        logger.info("*** No Master exists! ***")
        return
    logger.info("Removeable Masters:")
    logger.info(existing_master)

    if len(existing_master) == 0:
        return False

    if len(existing_master) == 1:
        logger.info("*** Just one Master exists ***")
        return existing_master

    elif len(existing_master) != 0 and len(existing_master) >= 2:
        # delete latest, because maybe there are still no Clones from the latest Master, and then it could be deleted
        existing_masters_Sorted = {k: v for k, v in sorted(existing_master.items(), key=operator.itemgetter(1))}
        logger.info(existing_masters_Sorted)
        return existing_masters_Sorted
    return


def waitForStatusStoppped(proxmox, timeout, node, vmid):
    terminate = time.time() + timeout
    while time.time() < terminate:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        status = status['qmpstatus']
        if status == "stopped":
            logger.info("*** VM " + str(vmid) + " stopped. ***")
            return True
        else:
            logger.info("*** waiting VM to going down... ***")
            time.sleep(5)
    logger.info("*** ERROR: VM couldn't get going down. ***")
    return False


def main(vdiGroup):

    masterStates = getVmStates.mainMaster(vdiGroup)
    masterGroupInfos = getMasterDetails(vdiGroup)
    timeoutBuildingMaster = masterGroupInfos['timeout_building_master']
    masterVmids = masterGroupInfos['vmids']
    removeables = find_and_sort_Existing_Masters(masterStates, masterVmids)

    if (removeables is None):
        logger.info("*** No Master available from group " + str(vdiGroup) + " . ***")
        return
    else:
        # check if master and failed at building:
        now = datetime.now()
        now = float(now.strftime("%Y%m%d%H%M%S"))
        for vmid in removeables:
            if ( masterStates[vmid]['buildstate'] == "failed" ) \
                    or ( masterStates[vmid]['buildstate'] == "building" \
                    and (now - float(masterStates[vmid]['dateOfCreation'])) ) > timeoutBuildingMaster:
                logger.info("*** Builded Master failed, removing: ***")
                # here it could be checked with createNewMaster functions if just nmap check is left
                status = masterStates[vmid]['status']
                if status == "running":
                    proxmox.nodes(node).qemu(vmid).status.stop.post()
                    logger.info("*** Master " + str(vmid) + " is getting stopped.***")
                    if waitForStatusStoppped(proxmox, 20, node, vmid) == True:
                        pass
                    else: 
                        logger.info(" *** Stop failed ***")
                        # return 
                try:
                    logger.info("*** Try to delete VM which failed during building: " + str(vmid) + " ***")
                    proxmox.nodes(node).qemu(vmid).delete()
                    return
                except Exception as err:
                    logger.info("*** Master " + str(vmid) + " cant get removed.***")
                    logger.info(err)
                    return
    if len(removeables) == 1:
        logger.info("*** Only one master exists for " + str(vdiGroup) + " ...  deleting none. ***")
        return
    # if more than two master exists, try delete random:
    elif len(removeables) >= 2:
        logger.info("***** Without latest: *****")
        del removeables[(max(removeables, key=lambda k: removeables[k]))]
        logger.info(removeables)

        # HERE: CHECK IF MASTER IS REFERNCED .....
        cloneStates = getVmStates.mainClones(vdiGroup)
        linkedMasters = []
        for vm in cloneStates:
                if vm != "summary":
                    if "master" in cloneStates[vm]:
                        linkedMasters.append(cloneStates[vm]['master'])
        linkedMasters = list(dict.fromkeys(linkedMasters))
        logger.info("Linked Masters:")
        logger.info(linkedMasters)
        
        for vmid in removeables:
            if vmid not in linkedMasters:
                status = masterStates[vmid]['status']
                if status == "running":
                    proxmox.nodes(node).qemu(vmid).status.stop.post()
                    logger.info("*** Master " + str(vmid) + " is getting stopped.***")
                    if waitForStatusStoppped(proxmox, 20, node, vmid) == True:
                        pass
                try:
                    proxmox.nodes(node).qemu(vmid).delete()
                    logger.info("*** Try deleting failed at building VM: " + str(vmid) + " ***")
                    return
                except Exception as err:
                    logger.info("*** Master " + str(vmid) + " cant get removed.***")
                    logger.info(err)
                    return
        logger.info("No Master was deleted")
        return

if __name__ == "__main__":
    main(sys.argv[1])
