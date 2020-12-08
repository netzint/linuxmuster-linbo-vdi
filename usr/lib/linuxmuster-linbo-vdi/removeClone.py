#!/usr/bin/env python3
#
# removeClone.py
#
# joanna@linuxmuster.net
#
# 20201116
#

import json
import sys
import operator
import time
import random
from getVmStates import mainClones
from datetime import datetime
from globalValues import node,proxmox,getMasterDetails,timeoutConnectionRequest
from common import dbprint


def getAssignedIDs(cloneStates):
    assignedIDs = []
    now = datetime.now()
    now = float(now.strftime("%Y%m%d%H%M%S"))
    for vmid in cloneStates:
        try:
            if cloneStates[vmid]['lastConnectionRequestTime'] != "":
                passedTime = now - float(cloneStates[vmid]['lastConnectionRequestTime'])
                if passedTime < timeoutConnectionRequest:
                    assignedIDs.append(vmid)

            if cloneStates[vmid]['user'] != "":
                assignedIDs.append(vmid)
        except:
            continue
    return assignedIDs


# get last connection times and sort from small to high (old to new)
def getLastConnectionTimes(cloneStates):
    connectionTimes = {}
    #print(cloneStates)
    for vmid in cloneStates:
         if (cloneStates[vmid]['lastConnectionRequestTime']) != "":
             dbprint(vmid)
             connectionTimes[vmid] = (cloneStates[vmid]['lastConnectionRequestTime'])

    connectionTimesSorted = {k: v for k, v in sorted(connectionTimes.items(), key=operator.itemgetter(1))}
    dbprint("sorted:")
    dbprint(connectionTimesSorted)
        #### oder über oldest timestamp?:####
        # oldest = min(connectionTimes, key=connectionTimes.get)
        # print("Oldest:")
        # print(oldest) # muss noch getesten werden!
    return connectionTimesSorted


def findLatestMasterTimestamp(masterNode, masterVmids):
    timestampLatest = float(0)
    vmids = masterVmids.split(',')
    vmidLatest = 0
    for vmid in vmids:
        try:
            configMaster = proxmox.nodes(masterNode).qemu(vmid).config.get()
            description = configMaster['description']
            descriptionJSON = json.loads(description)
            timestamp = float(descriptionJSON['dateOfCreation'])
            if float(timestamp) >= float(timestampLatest):  #float weglassen nun
                timestampLatest = timestamp
                vmidLatest = vmid
        except Exception as err:
            #pass # =falsch!
            continue
    dbprint("*** Latest timestamp: ***")
    dbprint("*** " + str(timestampLatest) + " ***")
    dbprint("*** from Master " + str(vmidLatest)+ " ***")

    return timestampLatest


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

    dbprint("*** Begin removeClone.py ***")
    # get removeable Clones
        # Alternative: cloneStates = getCloneStates(vdiGroup)  # assigned VMs direkt hier erst garnicht einlesen?
    cloneStates = mainClones(vdiGroup)
    del cloneStates['summary']
    dbprint("-------------Clone states::: -----")
    dbprint(json.dumps(cloneStates, indent=2))
    assignedIDs = getAssignedIDs(cloneStates)
    removevableStates ={}
    for vmid in cloneStates:
        if vmid not in assignedIDs and 'status' in cloneStates[vmid]: # probleme bei "in" und .pop(), daher "not in"
            removevableStates[vmid] = cloneStates[vmid]

    # Check Ausgabe
    dbprint("*** Clone States: ***")
    dbprint(cloneStates.keys())
    dbprint("*** Assigned Clones: ***")
    dbprint(assignedIDs)
    dbprint("*** Removeable Clones: ***")
    dbprint(removevableStates.keys())

    # get latest Master
    masterInfos = getMasterDetails(vdiGroup)
    masterVmids = masterInfos['vmids']
    timestampLatestMaster = findLatestMasterTimestamp(node, masterVmids)

    # search for failed VMs! =>
    for vmid in removevableStates:
            if removevableStates[vmid]['buildstate'] == "failed":
                try:
                    status = removevableStates[vmid]['status']
                    if status == "running":
                        proxmox.nodes(node).qemu(vmid).status.stop.post()
                        dbprint("*** Clone " + str(vmid) + " is getting stopped.***")
                        if waitForStatusStoppped(proxmox, 20, node, vmid) == True:
                            try:
                                proxmox.nodes(node).qemu(vmid).delete()
                                print("*** Deleting failed VM: " + str(vmid) + " ***")
                                return
                                #sys.exit()
                            except Exception as err:
                                dbprint("Deleting error:")
                                dbprint(err)
                    else:
                        proxmox.nodes(node).qemu(vmid).delete()
                        print("*** Deleting failed VM: " + str(vmid) + " ***")
                        return
                        #sys.exit()
                except Exception as err:
                    dbprint(err)
    dbprint("*** No failed VMs exists ***")

    # search for failed VMs in building State for more than 10 min:
    for vmid in removevableStates:
            now = datetime.now()
            now = float(now.strftime("%Y%m%d%H%M%S"))
            if removevableStates[vmid]['buildstate'] == "building" and \
                    ( now - (float(removevableStates[vmid]['dateOfCreation'])) > 1000):   # 1000 = 10 min
                try:
                    status = removevableStates[vmid]['status']
                    if status == "running":
                        proxmox.nodes(node).qemu(vmid).status.stop.post()
                        dbprint("*** Clone " + str(vmid) + " is getting stopped.***")
                        if waitForStatusStoppped(proxmox, 20, node, vmid) == True:
                            try:
                                proxmox.nodes(node).qemu(vmid).delete()
                                print("*** Deleting failed building VM: " + str(vmid) + " ***")
                                return
                                #sys.exit()
                            except Exception as err:
                                dbprint("Deleting error:")
                                dbprint(err)
                    else:
                        proxmox.nodes(node).qemu(vmid).delete()
                        print("*** Deleting failed building VM: " + str(vmid) + " ***")
                        return
                        #sys.exit()
                except Exception as err:
                    dbprint(err)
    dbprint("*** No failed building VMs exists ***")

    # if cloop deprecated:
    for vmid in removevableStates:
            dateOfCreation = float(removevableStates[vmid]['dateOfCreation'])
            if dateOfCreation <= float(timestampLatestMaster):
                dbprint("*** Found deprecated Clone: ***")
                dbprint(vmid)
                try:
                    status = removevableStates[vmid]['status']
                    if status == "running":
                        proxmox.nodes(node).qemu(vmid).status.stop.post()
                        dbprint("*** Clone " + str(vmid) + " is getting stopped. ***")
                        if waitForStatusStoppped(proxmox, 20, node, vmid) == True:
                            try:
                                proxmox.nodes(node).qemu(vmid).delete()
                                print("*** Deleting deprecated VM: " + str(vmid) + " ***")
                                return
                            except Exception as err:
                                print("*** Deleting error: ***")
                                dbprint(err)
                    else:
                        proxmox.nodes(node).qemu(vmid).delete()
                        print("*** Deleting deprecated VM: " + str(vmid) + " ***")
                        return
                except Exception as err:
                    dbprint(err)
    dbprint("*** No deprecated VMs exists ***")
    # if vm lastConnectionTime is high
    connectionTimes = getLastConnectionTimes(removevableStates)
    for vmid in connectionTimes:
                try:
                    status = removevableStates[vmid]['status']
                    if status == "running":
                        proxmox.nodes(node).qemu(vmid).status.stop.post()
                        dbprint("*** Clone " + str(vmid) + " is getting stopped.***")
                        if waitForStatusStoppped(proxmox, 20, node, vmid) == True:
                            try:
                                proxmox.nodes(node).qemu(vmid).delete()
                                print("*** Deleting VM with hightes last Connection : " + str(vmid) + " ***")
                                return
                            except Exception as err:
                                dbprint("Deleting error:")
                                dbprint(err)
                    else:
                        try:
                            proxmox.nodes(node).qemu(vmid).delete()
                            print("*** Deleting VM with hightes last Connection: " + str(vmid) + " ***")
                            return
                        except Exception as err:
                            dbprint("*** Deleting error: ***")
                            dbprint(err)
                except Exception as err:
                    dbprint(err)

    # deleting random removeable

    try:
        vmid = random.choice(list(removevableStates.keys()))
        status = removevableStates[vmid]['status']
        if status == "running":
            proxmox.nodes(node).qemu(vmid).status.stop.post()
            dbprint("*** Clone " + str(vmid) + " is getting stopped.***")
            if waitForStatusStoppped(proxmox, 20, node, vmid) == True:
                try:
                    proxmox.nodes(node).qemu(vmid).delete()
                    print("*** Deleting random removeable VM: " + str(vmid) + " ***")
                    return
                except Exception as err:
                    dbprint("Deleting error:")
                    dbprint(err)
        else:
            try:
                proxmox.nodes(node).qemu(vmid).delete()
                print("*** Deleting random removeable VM: " + str(vmid) + " ***")
                return
            except Exception as err:
                dbprint("*** Deleting error: ***")
                dbprint(err)
    except Exception as err:
        dbprint(err)

    dbprint("*** No deletable VMs exists ***")
    dbprint("*** Exiting. ***")


if __name__ == "__main__":
    main(sys.argv[1])
