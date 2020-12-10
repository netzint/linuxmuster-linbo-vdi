#!/usr/bin/env python3 -u
#
# vdi-service.py
#
# joanna.meinelt@netzint.de
#
# 20201127
#

import threading
import os,sys
import subprocess
import time
import getVmStates
import json
from deleteConnectionFiles import deleteDeprecatedFiles
import createNewMaster,removeMaster,removeClone,buildClone
from globalValues import checkConnections,vdiLocalService,dbprint,getVDIGroups,getMasterDetails
if vdiLocalService == False:
    from globalValues import ssh

print("***** VDI-Service initiated ... *****")

while True:

    print("********************************************************")
    checkConnections()
    vdiGroups = getVDIGroups()

    if len(vdiGroups) == 0:
        print("***** No VDI Groups available! *****")
        continue

    ### Master Handling ###
    for group in vdiGroups:

        groupData = getMasterDetails(group)
        dbprint("*** Group Data: ***")
        dbprint(json.dumps(groupData, indent=2))

        # check if group is activated
        if groupData['activated'] == "yes":
            print("***** VDI Group " + str(group) + " is activated! *****")
            pass
        elif groupData['activated'] == "no":
            print("***** VDI Group " + str(group) + " is not activated! *****")
            continue

        # get masterStates
        masterStates = getVmStates.mainMaster(group)
        print("***** Master States Summary: *****")
        print(json.dumps(masterStates['summary'], indent=2))

        # if no Master available
        if masterStates['summary']['existing_master'] == 0:
            print("***** Building new Master: *++**")
            t = threading.Thread(target=createNewMaster.main , args=(group,))
            t.start()
            continue

        # if 1 or more master, try delete one
        if masterStates['summary']['existing_master'] >= 1:
            print("***** Try to find failed building or deprecated Master to delete from group " + str(group) + " ****")
            t = threading.Thread(target=removeMaster.main, args=(group,))
            t.start()
            time.sleep(5)
            # read masterDetails again after deleting one
            # so deleted master is not in existing list
            masterStates = getVmStates.mainMaster(group)

        # is more than one master, check from latest master
        if masterStates['summary']['existing_master'] >= 1:
            # get latest from existing mastervmids:
            masterVmids = groupData['vmids'].split(',')
            existingVmids = []
            timestampLatest, vmidLatest = 1, None
            for vmid in masterVmids:
                if masterStates[vmid] is not None :
                    existingVmids.append(vmid)
                    if masterStates[vmid]['buildstate'] != "failed":
                        if float(masterStates[vmid]['dateOfCreation']) > float(timestampLatest):
                            timestampLatest = masterStates[vmid]['dateOfCreation']
                            vmidLatest = vmid

            if vmidLatest is None:
                print("***** Theres no finished or building actual Master.. *****")
                continue

            print("***** Existing Master: *****")
            print("***** " + str(existingVmids) + " *****")
            print("***** Latest Master: *****")
            print("***** " + str(vmidLatest) + " *****")

            if masterStates[vmidLatest]['buildstate'] == "building":
                print("***** Master from " + str(group) + "is building *****")
                break

            # check if cloop is actual
            if masterStates['basic']['actual_imagesize'] == masterStates[vmidLatest]['imagesize']:
                pass
            else:
                print("***** Image from Master " + str(vmidLatest) + " with imagesize: " + str(masterStates[vmidLatest]['imagesize']) + " has not the actual imagesize: " + str(masterStates['basic']['actual_imagesize']) + " *****")
                print("***** Master Image is not actual => Creating new Master *****")
                t = threading.Thread(target=createNewMaster.main, args=(group,))
                t.start()
                break
            # check if hv hardware and options changed
            if groupData['bios'] == masterStates[vmidLatest]['bios'] \
                and groupData['boot'] == masterStates[vmidLatest]['boot'] \
                and groupData['cores'] == masterStates[vmidLatest]['cores'] \
                and groupData['memory'] == masterStates[vmidLatest]['memory'] \
                and groupData['ostype'] == masterStates[vmidLatest]['ostype'] \
                and groupData['name'] == masterStates[vmidLatest]['name'] \
                and groupData['scsihw'] == masterStates[vmidLatest]['scsihw'] \
                and groupData['usb0'] == masterStates[vmidLatest]['usb0'] \
                and groupData['spice_enhancements'] == masterStates[vmidLatest]['spice_enhancements']:
                    print("***** Master Ressources " + str(vmidLatest) + " are actual *****")
                    pass
            else:
                print("***** Master Ressources " + str(vmidLatest) + " are not actual ***")
                print("***** Try building new Master: ...")
                t = threading.Thread(target=createNewMaster.main(), args=[group])
                t.start()
                break

    ### Clone Handling: ###
    for group in vdiGroups:

        if (( int(masterStates['summary']['existing_master']) - int(masterStates['summary']['existing_master']) ) >= 1):
            groupData = getMasterDetails(group)
            cloneStates = getVmStates.mainClones(group)

            print("***** Clone States Summary: *****")
            print(json.dumps(cloneStates['summary'],indent=2))

            # if under minimum  ||  if available < prestarted  &&  existing < maximum
            if ( (cloneStates['summary']['existing_vms']) < groupData['minimum_vms']) \
                    or ( cloneStates['summary']['available_vms'] < groupData['prestarted_vms']
                    and ( cloneStates['summary']['existing_vms'] < groupData['maxmimum_vms']) ):
                print("***** Try building new Clone ... *****")
                t = threading.Thread(target=buildClone.main, args=(group,))
                t.start()
            # if (available > prestarted) || existing > minimum)
            elif (cloneStates['summary']['available_vms'] > groupData['prestarted_vms']
                    and cloneStates['summary']['existing_vms'] > groupData['minimum_vms']):
                print("***** Try removing Clone ... *****")
                t = threading.Thread(target=removeClone.main, args=(group,), daemon = True)
                t.start()

    ### delete deprecated connection files ###
    deleteDeprecatedFiles()

time.sleep(5)
