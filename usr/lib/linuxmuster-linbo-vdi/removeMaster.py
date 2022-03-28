#!/usr/bin/env python3
#
# removeMaster.py
#
# joanna@linuxmuster.net
#
# 20201119
#


import sys
import operator
from datetime import datetime
import time
import logging
import getVmStates
from globalValues import node,proxmox
#from globalValues getMasterDetails

logger = logging.getLogger(__name__)


# finds existing master VMs and sorts them by dateOfCreation
# so the oldest can be deleted first
# returns if no master found
def find_and_sort_Existing_Masters(masterStates, masterVmids,vdi_group):
    existing_master = {}
    logger.info(f"[{vdi_group}] {masterVmids}")
    for vmid in masterVmids:
        if masterStates[vmid] is not None \
                and masterStates[vmid] != "summary" \
                and masterStates[vmid] != "basic":
            try:
                dateOfCreation = masterStates[vmid]['dateOfCreation']
                existing_master[vmid] = dateOfCreation
            except Exception:
                pass
    if len(existing_master) == 0:
        logger.info(f"[{vdi_group}] No Master exists!")
        return False
    logger.info(f"[{vdi_group}] Removeable Masters:")
    logger.info(f"[{vdi_group}] {existing_master}")

    if len(existing_master) == 1:
        logger.info(f"[{vdi_group}] Just one Master exists")
        return existing_master

    elif len(existing_master) != 0 and len(existing_master) >= 2:
        # delete latest, because maybe there are still no Clones from the latest Master, and then it could be deleted
        existing_masters_Sorted = {k: v for k, v in sorted(existing_master.items(), key=operator.itemgetter(1))}
        logger.info(f"[{vdi_group}] {existing_masters_Sorted}")
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


def remove_master(group_data,vdi_group):

    masterStates = getVmStates.get_master_states(group_data,vdi_group)
    #masterGroupInfos = getMasterDetails(vdiGroup)



    timeoutBuildingMaster = group_data['timeout_building_master']
    master_vmids = group_data['vmids']
    removeables = find_and_sort_Existing_Masters(masterStates, master_vmids,vdi_group)

    # 1. check if no master is available 
    if not removeables:
        logger.info(f"[{vdi_group}] No Master available to delete from group")
        return

    # 2. check if failed at buildung or failed vm, also if only one master exists 
    else:
        now = datetime.now()
        now = float(now.strftime("%Y%m%d%H%M%S"))
        for vmid in removeables:
            if ( masterStates[vmid]['buildstate'] == "failed" ) \
                    or ( masterStates[vmid]['buildstate'] == "building" \
                    and (now - float(masterStates[vmid]['dateOfCreation'])) ) > timeoutBuildingMaster:
                logger.info(f"[{vdi_group}] Builded Master failed, removing")
                # here it could be checked with createNewMaster functions if just nmap check is left
                status = masterStates[vmid]['status']
                if status == "running":
                    proxmox.nodes(node).qemu(vmid).status.stop.post()
                    logger.info(f"[{vdi_group}] Master " + str(vmid) + " is getting stopped.")
                    if not waitForStatusStoppped(proxmox, 20, node, vmid):
                        logger.info(f"[{vdi_group}] Could not stop vm + " + vmid)
                        raise Exception(f"[{vdi_group}] Machine could not be stopped")
                    else: 
                        logger.info(f"[{vdi_group}] Stop failed for {vmid}")
                        # return 
                try:
                    logger.info(f"[{vdi_group}] Try to delete VM which failed during building: {str(vmid)}")
                    proxmox.nodes(node).qemu(vmid).delete()
                    return
                except Exception as err:
                    logger.info(f"[{vdi_group}] Master {str(vmid)} cant get removed.")
                    logger.info(err)
                    return
    # 3. if no one was failed, skip if only one master exists
    if len(removeables) == 1:
        logger.info(f"[{vdi_group}] Only one master exists deleting none.")
        return
    # 4. if more than two master exists, try delete random:
    elif len(removeables) >= 2:
        logger.info(f"[{vdi_group}] Without latest")
        del removeables[(max(removeables, key=lambda k: removeables[k]))]
        logger.info(f"[{vdi_group}] {removeables}")

        # HERE: CHECK IF MASTER IS REFERNCED .....
        cloneStates = getVmStates.get_clone_states(group_data,vdi_group)
        linkedMasters = []
        for vm in cloneStates:
                if vm != "summary":
                    if "master" in cloneStates[vm]:
                        linkedMasters.append(cloneStates[vm]['master'])
        linkedMasters = list(dict.fromkeys(linkedMasters))
        logger.info(f"[{vdi_group}] Linked Masters:")
        logger.info(f"[{vdi_group}] {linkedMasters}")
        
        for vmid in removeables:
            if vmid not in linkedMasters:
                status = masterStates[vmid]['status']
                try: 
                    if status == "running":
                        proxmox.nodes(node).qemu(vmid).status.stop.post()
                        logger.info(f"[{vdi_group}] Master {str(vmid)} is getting stopped.")
                        if not waitForStatusStoppped(proxmox, 20, node, vmid):
                            logger.info(f"[{vdi_group}] Could not stop vm + " + vmid)
                            raise Exception(f"[{vdi_group}] Machine could not be stopped")
                
                    logger.info(f"[{vdi_group}] Try deleting failed at building VM: {str(vmid)}")
                    proxmox.nodes(node).qemu(vmid).delete()
                    return
                except Exception as err:
                    logger.info(f"[{vdi_group}] Master {str(vmid)} could not be removed because {str(err)}.")
                    logger.info(f"[{vdi_group}] {err}")
                    return

        for vmid in removeables:
                status = masterStates[vmid]['status']
                try:
                    if status == "running":
                        proxmox.nodes(node).qemu(vmid).status.stop.post()
                        logger.info(f"[{vdi_group}] Master {str(vmid)} is getting stopped.")
                        if not waitForStatusStoppped(proxmox, 20, node, vmid):
                            logger.info("Could not stop vm + " + vmid)
                            raise Exception("Machine could not be stopped")
                    
                    logger.info(f"[{vdi_group}] Try deleting failed at building VM: {str(vmid)} ")
                    proxmox.nodes(node).qemu(vmid).delete()
                    return
                except Exception as err:
                    logger.info(err)
                    return
  
        logger.info(f"[{vdi_group}] No Master was deleated.")
        return

if __name__ == "__main__":
    remove_master(sys.argv[1])
