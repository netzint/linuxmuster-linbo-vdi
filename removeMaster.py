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
from globalValues import node,dbprint,proxmox,getMasterDetails
from datetime import datetime
import time
import getVmStates


# finds existing master VMs and sorts them by dateOfCreation
# so the oldest can be deleted first
def findRemoveableMaster(masterStates, masterVmids):
    removeables = {}
    vmids = masterVmids.split(',')
    dbprint(vmids)
    for vmid in vmids:
        if masterStates[vmid] is not None \
                and masterStates[vmid] != "summary" \
                and masterStates[vmid] != "basic":
            try:
                dateOfCreation = masterStates[vmid]['dateOfCreation']
                removeables[vmid] = dateOfCreation
            except Exception:
                pass
    if len(removeables) == 0:
        dbprint("*** No Master exists! ***")
        return

    dbprint(removeables)

    if len(removeables) == 1:
        dbprint("*** Just one Master exists ***")
        return removeables

    elif len(removeables) != 0 and len(removeables) >= 2:
        # delete latest, because maybe there are still no Clones from the latest Master, and then it could be deleted
        removeablesSorted = {k: v for k, v in sorted(removeables.items(), key=operator.itemgetter(1))}
        dbprint(removeablesSorted)
        return removeablesSorted
    return


def waitForStatusStoppped(proxmox, timeout, node, vmid):
    terminate = time.time() + timeout
    while time.time() < terminate:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        status = status['qmpstatus']
        if status == "stopped":
            dbprint("*** VM " + str(vmid) + " stopped. ***")
            return True
        else:
            dbprint("*** waiting VM to going down... ***")
            time.sleep(5)
    dbprint("*** ERROR: VM couldn't get going down. ***")
    return False


def main(vdiGroup):

    masterStates = getVmStates.mainMaster(vdiGroup)
    masterGroupInfos = getMasterDetails(vdiGroup)
    timeoutBuildingMaster = masterGroupInfos['timeout_building_master']
    masterVmids = masterGroupInfos['vmids']
    removeables = findRemoveableMaster(masterStates, masterVmids)

    if (removeables is None):
        dbprint("*** No Master couldnt get removed from group " + str(vdiGroup) + " . ***")
    else:
        # if only 1 master exists and failed at building:
        now = datetime.now()
        now = float(now.strftime("%Y%m%d%H%M%S"))
        for vmid in removeables:
            if masterStates[vmid]['buildstate'] == "building" \
                        and (now - float(masterStates[vmid]['dateOfCreation'])) > timeoutBuildingMaster:
                dbprint("*** Builded Master failed, removing: ***")
                # here it could be checked with createNewMaster functions if just nmap check is left
                status = masterStates[vmid]['status']
                if status == "running":
                    proxmox.nodes(node).qemu(vmid).status.stop.post()
                    dbprint("*** Master " + str(vmid) + " is getting stopped.***")
                    if waitForStatusStoppped(proxmox, 20, node, vmid) == True:
                        pass
                try:
                    proxmox.nodes(node).qemu(vmid).delete()
                    dbprint("*** Try deleting failed at building VM: " + str(vmid) + " ***")
                    return
                except Exception as err:
                    dbprint("*** Master " + str(vmid) + " cant get removed.***")
                    dbprint(err)
                    return
    # if more than two master exists, try delete random:
    if len(removeables) >= 2:
        dbprint("***** Without latest: *****")
        del removeables[(max(removeables, key=lambda k: removeables[k]))]
        dbprint(removeables)

        for vmid in removeables:
            status = masterStates[vmid]['status']
            if status == "running":
                proxmox.nodes(node).qemu(vmid).status.stop.post()
                dbprint("*** Master " + str(vmid) + " is getting stopped.***")
                if waitForStatusStoppped(proxmox, 20, node, vmid) == True:
                    pass
            try:
                proxmox.nodes(node).qemu(vmid).delete()
                dbprint("*** Deleting random removeable VM: " + str(vmid)+ " ***")
                return
            except Exception as err:
                dbprint("*** Master " + str(vmid) + " cant get removed.***")
                dbprint(err)
                return
    else:
        dbprint("*** Only one master exists for " + str(vdiGroup) + " ...  deleting none. ***")



if __name__ == "__main__":
    main(sys.argv[1])
