#!/usr/bin/env python3
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
import json
import logging


import createNewMaster
import removeMaster
import removeClone
import buildClone
from getVmStates import mainMaster, mainClones
from deleteConnectionFiles import deleteDeprecatedFiles
from globalValues import checkConnections,vdiLocalService,getVDIGroups,getMasterDetails
if vdiLocalService == False:
    from globalValues import ssh

#logging.basicConfig(format='%(levelname)s:%(asctime)s %(message)s', level=logging.INFO)

logging.basicConfig(format='%(asctime)s %(levelname)7s: [%(filename)19s] - %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO)

logger = logging.getLogger(__name__)

#formatter = logging.Formatter('%(asctime)s %(levelname)s: %(filename)s - %(message)s')
#handler = logging.StreamHandler()
#handler.setFormatter(formatter)
#handler.setLevel(logging.INFO)
#
#package_logger = logging.getLogger(__name__.split('.')[0])
#package_logger.setLevel(logging.INFO)
#package_logger.setLevel(logging.WARNING)
#package_logger.addHandler(handler)
#
#logger = logging.getLogger(__name__)

def handle_master(vdiGroups):

     for group in vdiGroups:
        groupData = getMasterDetails(group)
        logger.info("*** Group Data: ***")
        logger.debug(json.dumps(groupData, indent=2))
        # check if group is activated
        if groupData['activated'] == "yes":
            logger.info("***** VDI Group " + str(group) + " is activated! *****")

        if groupData['activated'] == "no":
            logger.info("***** VDI Group " + str(group) + " is not activated! *****")
            
        # get masterStates
        global masterStates
        masterStates = mainMaster(group)
        logger.info("***** Master States Summary: *****")
        logger.debug(json.dumps(masterStates['summary'], indent=2))

        # if no Master available
        if masterStates['summary']['existing_master'] == 0:
            logger.info("***** Building new Master: *++**")
            t = threading.Thread(target=createNewMaster.main , args=(group,))
            t.start()
            
        # if 1 or more master, try delete one
        if masterStates['summary']['existing_master'] >= 1:
            logger.info("***** Try to find failed building or deprecated Master to delete from group " + str(group) + " ****")
            removeMaster.main(group)
            # TODO watch over this
            #t = threading.Thread(target=removeMaster.main, args=(group,))
            #threads.append(t)
            #t.start()
            #time.sleep(5)
            # read masterDetails again after deleting one
            # so deleted master is not in existing list
            masterStates = mainMaster(group)
        # if a master exist
        if masterStates['summary']['existing_master'] >= 0:
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
                logger.info("***** Theres no finished or building actual Master.. *****")
                continue
            logger.info("***** Existing Master(s): " + str(existingVmids) + " *****")
            logger.info("***** Latest Master: " + str(vmidLatest) + "*****")
            if masterStates[vmidLatest]['buildstate'] == "building":
                logger.info("***** Master from " + str(group) + "is building *****")
                break
            # check if cloop is up 2 date
            if not masterStates['basic']['actual_imagesize'] == masterStates[vmidLatest]['imagesize']:
                logger.info("***** Image from Master " + str(vmidLatest) + " with imagesize: " + str(masterStates[vmidLatest]['imagesize']) + " has not the updated imagesize: " + str(masterStates['basic']['actual_imagesize']) + " *****")
                logger.info("***** Master Image is not up-to-date => Creating new Master *****")
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
                    logger.info("***** Master Ressources " + str(vmidLatest) + " are up to date *****")
                    pass
            else:
                logger.info("***** Master Ressources " + str(vmidLatest) + " are not up to date ***")
                logger.info("***** Try building new Master: ...")
                t = threading.Thread(target=createNewMaster.main(), args=[group])
                t.start()
                break

def handle_clones(vdiGroups):
    for group in vdiGroups:
                masterStates = mainMaster(group)
                if (( int(masterStates['summary']['existing_master']) - int(masterStates['summary']['building_master']) ) >= 1):
                    groupData = getMasterDetails(group)
                    cloneStates = mainClones(group)

                    logger.info("***** Clone States Summary: *****")
                    logger.info(json.dumps(cloneStates['summary'],indent=2))

                    # if under minimum  ||  if available < prestarted  &&  existing < maximum
                    if ( (cloneStates['summary']['existing_vms']) < groupData['minimum_vms']) \
                            or ( cloneStates['summary']['available_vms'] < groupData['prestarted_vms']
                            and ( cloneStates['summary']['existing_vms'] < groupData['maxmimum_vms']) ):
                        logger.info("***** Try building new Clone ... *****")
                        t = threading.Thread(target=buildClone.main, args=(group,))
                        t.start()
                    # if (available > prestarted) || existing > minimum)
                    elif (cloneStates['summary']['available_vms'] > groupData['prestarted_vms']
                            and cloneStates['summary']['existing_vms'] > groupData['minimum_vms']):
                        logger.info("***** Try removing Clone ... *****")
                        t = threading.Thread(target=removeClone.main, args=(group,), daemon = True)
                        t.start()
                else:
                    logger.info("***** No finished Master available for Clone Hanndling ******")


def run_service():
    logger.info("***** VDI-Service initiated ... *****")
    
    while True:
        logger.info("********************************************************")
        while not checkConnections():
            checkConnections()
        vdiGroups = getVDIGroups()
        if len(vdiGroups) == 0:
            logger.info("***** No VDI Groups available! *****")
            continue

        ### Master Handling ###
        handle_master(vdiGroups)
#
        #### Clone Handling: ###
        handle_clones(vdiGroups)


        ### delete deprecated connection files ###
        deleteDeprecatedFiles()
        time.sleep(5)

if __name__ == "__main__":
    run_service()