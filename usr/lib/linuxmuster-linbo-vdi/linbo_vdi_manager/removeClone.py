#!/usr/bin/env python3
#
# removeClone.py
#
# joanna@linuxmuster.net
#
# 20201116
#

import threading
import time
import argparse
import logging
from datetime import datetime
from globalValues import proxmox_node,proxmox,timeoutConnectionRequest
import vdi_common
from getVmStates import get_clone_states

logger = logging.getLogger(__name__)
__version__ = 'version 0.9.9'

def get_assigned_ids(clone_states):
    assigned_ids = []
    now = datetime.now()
    now = float(now.strftime("%Y%m%d%H%M%S"))
    for vmid in clone_states:
        try:
            if clone_states[vmid]['lastConnectionRequestTime'] != "":
                passedTime = now - float(clone_states[vmid]['lastConnectionRequestTime'])
                if passedTime < timeoutConnectionRequest:
                    assigned_ids.append(vmid)

            if clone_states[vmid]['user'] != "":
                assigned_ids.append(vmid)
        except:
            continue
    return assigned_ids


## get last connection times and sort from small to high (old to new)
#def getLastConnectionTimes(clone_states):
#    connectionTimes = {}
#    #print(cloneStates)
#    for vmid in clone_states:
#         if (clone_states[vmid]['lastConnectionRequestTime']) != "":
#             logger.info(vmid)
#             connectionTimes[vmid] = (clone_states[vmid]['lastConnectionRequestTime'])
#
#    connectionTimesSorted = {k: v for k, v in sorted(connectionTimes.items(), key=operator.itemgetter(1))}
#    logger.info("sorted:")
#    logger.info(connectionTimesSorted)
#        #### oder über oldest timestamp?:####
#        # oldest = min(connectionTimes, key=connectionTimes.get)
#        # print("Oldest:")
#        # print(oldest) # muss noch getesten werden!
#    return connectionTimesSorted



def wait_for_vm_to_stop(proxmox, timeout, node, vmid,vdi_group):
    terminate = time.time() + timeout
    while time.time() < terminate:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        status = status['qmpstatus']
        if status == "stopped":
            logger.info(f"[{vdi_group} VM {str(vmid)} stopped.")
            return True
        else:
            logger.debug(f"[{vdi_group} waiting VM to going down...")
            time.sleep(5)
    logger.warning(f"ERROR: VM couldn't get going down")
    return False

#def remove_vms(removeable_vms,node,vdi_group)-> bool:
#    for vmid in removeable_vms:
#        now = datetime.now()
#        now = float(now.strftime("%Y%m%d%H%M%S"))
#        if removeable_vms[vmid]['buildstate'] in ['finished', 'failed', 'building', 'running']:
#            if removeable_vms[vmid]['buildstate'] == "building" and \
#                    ( now - (float(removeable_vms[vmid]['dateOfCreation'])) < 1000):   # 1000 = 10 min
#                    continue
#
#            if not removeable_vms[vmid]['status'] == "stopped":
#                logger.info(f"[{vdi_group} Stop Clone {str(vmid)}...")
#                proxmox.nodes(node).qemu(vmid).status.stop.post()
#                while not wait_for_vm_to_stop(proxmox, 20, node, vmid,vdi_group):
#                    break
#            try:
#                proxmox.nodes(node).qemu(vmid).delete()
#                logger.info(f"[{vdi_group} Deleting stopped VM: {str(vmid)}")
#                return True
#            except Exception as err:
#                logger.info(f"[{vdi_group} Deleting error:")
#                logger.info(f"[{vdi_group} {str(err)}")
#                return False

def remove_vm(vmid):
    try:
        if proxmox.nodes(proxmox_node).qemu(vmid).status.current.get() != "stopped":
            proxmox.nodes(proxmox_node).qemu(vmid).status.stop.post()
            time.sleep(3)
        proxmox.nodes(proxmox_node).qemu(vmid).delete()
    except:
        return

def remove_outdated_clones(outdated_clones, clone_states, vdi_group):
        assignedIDs = get_assigned_ids(clone_states)
        threads = []
        for outdated_clone in outdated_clones:
            if outdated_clone['vmid'] not in assignedIDs:
                vmid = outdated_clone['vmid']
                t = threading.Thread(target=remove_vm, args=(vmid,))
                threads.append(t)
                t.start()
        for thread in threads:
            thread.join()
        return


def remove_clone(vm_amount_to_delete,clone_states, vdi_group):

    logger.debug(f"{vdi_group} Begin removeClone")
    del clone_states['summary']
    #logger.info(f"{vdiGroup}Clone states:")
    #logger.info(json.dumps(clone_states, indent=62))
    assignedIDs = get_assigned_ids(clone_states)
    removeable_vms ={}
    for vmid in clone_states:
        if vmid not in assignedIDs and 'status' in clone_states[vmid]:
            removeable_vms[vmid] = clone_states[vmid]
            if len(removeable_vms) >= vm_amount_to_delete:
                break

    #remove_vms(removeable_vms,node,vdi_group)
    
    for removeable_vm in removeable_vms:
        remove_vm(removeable_vm)
    #threads = []
    #for removeable_vm in removeable_vms:
    #        t = threading.Thread(target=remove_vm, args=(removeable_vm,))
    #        threads.append(t)
    #        t.start()
    #for thread in threads:
    #    thread.join()
    return

def remove_every_clone(vdi_group):
    vdi_groups = vdi_common.get_vdi_groups()
    if vdi_group in vdi_groups:
        clone_states = get_clone_states(vdi_groups['groups'][vdi_group],vdi_group)
        remove_vm(clone_states,proxmox_node,vdi_group)



if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s %(levelname)7s: [%(filename)19s] [l%(lineno)4s]- %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO)

    parser = argparse.ArgumentParser(description='removeClone.py ')
    quiet = False
    parser.add_argument('-v', dest='version', action='store_true', help='print the version and exit')
    parser.add_argument('--everything', dest='everything', action='store_true', help='remove every clone')
    parser.add_argument('--vm', dest='vm', action='store_true', help='remove every clone')
    parser.add_argument('group', nargs='?', default='all')
    args = parser.parse_args()

    if args.version:
        print (__version__)
        quit()
    if args.everything is not False:
        # TODO Fix this for CLI
        remove_every_clone(args.group)
        quit()
    if args.vm is not False:
        # TODO Fix this for CLI
        remove_vm(args.group)
        quit()
    else:
        parser.print_help()
    quit()

