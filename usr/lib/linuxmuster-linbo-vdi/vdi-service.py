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
level = "INFO"

if level == "INFO":
    logging.basicConfig(format='%(asctime)s %(levelname)7s: [%(filename)19s] [l%(lineno)4s]- %(message)s',
        datefmt='%Y-%m-%d:%H:%M:%S',
        level=logging.INFO)

if level == "DEBUG":
    logging.basicConfig(format='%(asctime)s %(levelname)7s: [%(filename)19s] [l%(lineno)4s]- %(message)s',
        datefmt='%Y-%m-%d:%H:%M:%S',
        level=logging.INFO)



logger = logging.getLogger(__name__)



def handle_master(group):

    #for group in vdiGroups:
    groupData = getMasterDetails(group)
    logger.info("*** Group Data: ***")
    logger.debug(json.dumps(groupData, indent=2))

        
    # get masterStates
    global masterStates
    masterStates = mainMaster(group)
    logger.info("***** Master States Summary for group " + group + ": *****")
    logger.debug(json.dumps(masterStates['summary'], indent=2))
    # if no Master available
    if masterStates['summary']['existing_master'] == 0:
        logger.info("***** Building new Master: *++**")
        createNewMaster.main(group)
        #t = threading.Thread(target=createNewMaster.main , args=(group,))
        #t.start()
        
    # if 1 or more master, try delete one
    if masterStates['summary']['existing_master'] >= 1:
        logger.info("***** Try to find failed building or deprecated Master to delete from group " + str(group) + " ****")
        removeMaster.main(group)
        # TODO watch over this
        #t = threading.Thread(target=removeMaster.main, args=(group,))
        #t.start()
        #time.sleep(5)
        #t.join()
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
        logger.info("***** Existing Master(s): " + str(existingVmids) + " *****")
        logger.info("***** Latest Master: " + str(vmidLatest) + "*****")
        if masterStates[vmidLatest]['buildstate'] == "building":
            logger.info("***** Master from " + str(group) + " is building *****")
        # check if cloop is up 2 date
        if not masterStates['basic']['actual_imagesize'] == masterStates[vmidLatest]['imagesize']:
            logger.info("***** Image from Master " + str(vmidLatest) + " with imagesize: " + str(masterStates[vmidLatest]['imagesize']) + " has not the updated imagesize: " + str(masterStates['basic']['actual_imagesize']) + " *****")
            logger.info("***** Master Image is not up-to-date => Creating new Master *****")
            createNewMaster.main(group)
            #t = threading.Thread(target=createNewMaster.main, args=(group,))
            #t.start()
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
            createNewMaster.main([group])
            #t = threading.Thread(target=createNewMaster.main(), args=[group])
            #t.start()

def handle_clones(group):
    #for group in vdiGroups:
    masterStates = mainMaster(group)
    finishedMasters =(( int(masterStates['summary']['existing_master']) - int(masterStates['summary']['building_master']) ))
    if finishedMasters >= 1:
        groupData = getMasterDetails(group)
        cloneStates = mainClones(group)
        
        logger.info("***** Clone States Summary for Group " + group + ": *****")
        logger.info(json.dumps(cloneStates['summary'],indent=62))
        
        # if under minimum  ||  if available < prestarted  &&  existing < maximum
        # create clone
        if ( (cloneStates['summary']['existing_vms']) < groupData['minimum_vms']) \
                or ( cloneStates['summary']['available_vms'] < groupData['prestarted_vms']
                and ( cloneStates['summary']['existing_vms'] < groupData['maxmimum_vms']) ):
            logger.info("***** Try building new Clone ... *****")
            #buildClone.main(group)
            t = threading.Thread(target=buildClone.main, args=(group,))
            t.start()
            time.sleep(5)
        # if (available > prestarted) || existing > minimum)
        # delete clones
        elif (cloneStates['summary']['available_vms'] > groupData['prestarted_vms']
                and cloneStates['summary']['existing_vms'] > groupData['minimum_vms']):
            logger.info("***** Try removing Clone ... *****")
            removeClone.main(group)
            #t = threading.Thread(target=removeClone.main, args=(group,), daemon = True)
            #t.start()
    else:
        logger.info("***** No finished Master available for Clone Hanndling ******")


def masterThreading(vdiGroups):
    master_threads = []
    
    for vdiGroup in vdiGroups:
        groupDetails=getMasterDetails(vdiGroup)
        if groupDetails['activated'] == True:
            logger.info("***** VDI Group " + str(vdiGroup) + " is activated! *****")
            t = threading.Thread(target=handle_master,args=(vdiGroup,))
            master_threads.append(t)
        if groupDetails['activated'] == False:
            logger.info("***** VDI Group " + str(vdiGroup) + " is not activated! *****")
            continue
    for thread in master_threads:
        thread.start()
        time.sleep(5)
    for thread in master_threads:
        thread.join()
        return
        
def clonesThreading(vdiGroups):
        clones_threads = []
        for vdiGroup in vdiGroups:
            groupDetails=getMasterDetails(vdiGroup)
            if groupDetails['activated'] == True:
                logger.info("***** VDI Group " + str(vdiGroup) + " is activated! *****")
                t = threading.Thread(target=handle_clones,args=(vdiGroup,))
                clones_threads.append(t)
            if groupDetails['activated'] == False:
                logger.info("***** VDI Group " + str(vdiGroup) + " is not activated! *****")
                continue
        for thread in clones_threads:
            thread.start()
        for thread in clones_threads:
            print ("****+" + str(clones_threads))
            thread.join()
            return


def run_service():
    logger.info("***** VDI-Service initiated ... *****")
    
    while True:
        logger.info("********************************************************")
        while not checkConnections():
            checkConnections()
        vdiGroups = getVDIGroups()
        while len(vdiGroups) == 0:
            logger.info("***** No VDI Groups available! *****")
            time.sleep(5)
            vdiGroups = getVDIGroups()
            



        ### Master Handling ###
        try: 
            masterThread
        except NameError:
            masterThread = threading.Thread(target=masterThreading,args=(vdiGroups,))
            masterThread.start()
        if not masterThread.is_alive():
            logging.info("Starting new MasterThread")
            masterThread = threading.Thread(target=masterThreading,args=(vdiGroups,))
            masterThread.start()
        

        #handle_master(vdiGroups)
        #
        ### Clone Handling: ###
        try:
            cloneThread
        except NameError:
            cloneThread = threading.Thread(target=clonesThreading,args=(vdiGroups,))
            cloneThread.start()
        if not cloneThread.is_alive():
            logging.info("Starting new CloneThread")
            cloneThread = threading.Thread(target=clonesThreading,args=(vdiGroups,))
            cloneThread.start()
        ##handle_clones(vdiGroups)
        


        ### delete deprecated connection files ###
        deleteDeprecatedFiles()
        time.sleep(5)

if __name__ == "__main__":
    run_service()