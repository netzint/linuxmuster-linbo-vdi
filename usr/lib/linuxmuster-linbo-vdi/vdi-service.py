#!/usr/bin/env python3
#
# vdi-service.py
#
# joanna.meinelt@netzint.de
#
# 20201127
#

import threading
#import os,sys
#import subprocess
import time
import json
import logging


import createNewMaster
import removeMaster
import removeClone
import buildClone
from getVmStates import get_master_states, get_clone_states
from deleteConnectionFiles import deleteDeprecatedFiles
#from globalValues import vdiLocalService
#from globalValues import ,getVDIGroups,getMasterDetails
import vdi_common
#if vdiLocalService == False:
#    from globalValues import ssh

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



def handle_master(group_data,vdi_group):

    #for group in vdiGroups:
    logger.info(f"[{vdi_group}] Group Data")
    logger.debug(json.dumps(group_data, indent=2))

        
    # get masterStates
    #global masterStates # TODO muss das global sein?
    masterStates = get_master_states(group_data,vdi_group)
    logger.info(f"[{vdi_group}] Master States Summary for group")
    logger.debug(json.dumps(masterStates['summary'], indent=2))
    # if no Master available
    if masterStates['summary']['existing_master'] == 0:
        logger.info(f"[{vdi_group}] Building new Master")
        createNewMaster.create_master(group_data,vdi_group)
        #t = threading.Thread(target=createNewMaster.main , args=(group,))
        #t.start()
        
    # if 1 or more master, try delete one
    if masterStates['summary']['existing_master'] >= 1:
        logger.info(f"[{vdi_group}] Try to find failed, building or deprecated masters to delete")
        removeMaster.remove_master(group_data,vdi_group)
        # TODO watch over this
        #t = threading.Thread(target=removeMaster.main, args=(group,))
        #t.start()
        #time.sleep(5)
        #t.join()
        # read masterDetails again after deleting one
        # so deleted master is not in existing list
        masterStates = get_master_states(group_data,vdi_group)
    # if a master exist
    if masterStates['summary']['existing_master'] >= 0:
        # get latest from existing mastervmids:
        master_vmids = group_data['vmids']
        existing_vmids = []
        timestampLatest, vmidLatest = 1, None
        for vmid in master_vmids:
            if masterStates[vmid] is not None :
                existing_vmids.append(vmid)
                if masterStates[vmid]['buildstate'] != "failed":
                    if float(masterStates[vmid]['dateOfCreation']) > float(timestampLatest):
                        timestampLatest = masterStates[vmid]['dateOfCreation']
                        vmidLatest = vmid
        if vmidLatest is None:
            logger.info("[{vdi_group}] Theres no finished or building actual Master")
        logger.info(f"[{vdi_group}] Existing Master(s): {str(existing_vmids)}")
        logger.info(f"[{vdi_group}] Latest Master: {str(vmidLatest)}")
        if masterStates[vmidLatest]['buildstate'] == "building":
            logger.info(f"[{vdi_group}] Master is building")
        # check if cloop is up 2 date
        if not masterStates['basic']['actual_imagesize'] == masterStates[vmidLatest]['imagesize']:
            logger.info(f"[{vdi_group}] Current imagesize {str(masterStates[vmidLatest]['imagesize'])} does not match current image: {str(masterStates['basic']['actual_imagesize'])}")
            logger.info(f"[{vdi_group}] Master Image is not up-to-date => creating new Master")
            createNewMaster.create_master(group_data,vdi_group)
            #t = threading.Thread(target=createNewMaster.main, args=(group,))
            #t.start()
        # check if hv hardware and options changed
        if group_data['bios'] == masterStates[vmidLatest]['bios'] \
            and group_data['boot'] == masterStates[vmidLatest]['boot'] \
            and group_data['cores'] == masterStates[vmidLatest]['cores'] \
            and group_data['memory'] == masterStates[vmidLatest]['memory'] \
            and group_data['ostype'] == masterStates[vmidLatest]['ostype'] \
            and group_data['name'] == masterStates[vmidLatest]['name'] \
            and group_data['scsihw'] == masterStates[vmidLatest]['scsihw'] \
            and group_data['usb0'] == masterStates[vmidLatest]['usb0'] \
            and group_data['spice_enhancements'] == masterStates[vmidLatest]['spice_enhancements']:
                logger.info(f"[{vdi_group}] Master Ressources " + str(vmidLatest) + " are up to date")
                pass
        else:
            logger.info(f"[{vdi_group}] Master Ressources {str(vmidLatest)} are not up to date, try building new master")
            createNewMaster.create_master(group_data,vdi_group)
            #t = threading.Thread(target=createNewMaster.main(), args=[group])
            #t.start()

def handle_clones(group_data, vdi_group):
    #for group in vdiGroups:
    masterStates = get_master_states(group_data, vdi_group)
    finishedMasters =(( int(masterStates['summary']['existing_master']) - int(masterStates['summary']['building_master']) ))
    if finishedMasters >= 1:
        cloneStates = get_clone_states(group_data,vdi_group)
        
        logger.info("***** Clone States Summary for Group " + vdi_group + ": *****")
        logger.info(json.dumps(cloneStates['summary'],indent=62))
        
        # if under minimum  ||  if available < prestarted  &&  existing < maximum
        # create clone
        if ( (cloneStates['summary']['existing_vms']) < group_data['minimum_vms']) \
                or ( cloneStates['summary']['available_vms'] < group_data['prestarted_vms']
                and ( cloneStates['summary']['existing_vms'] < group_data['maxmimum_vms']) ):
            logger.info(f"[{vdi_group}]Try to build new Clone ...")
            buildClone.main(vdi_group)
            #t = threading.Thread(target=buildClone.main, args=(vdi_group,))
            #t.start()
            #time.sleep(5)
        # if (available > prestarted) || existing > minimum)
        # delete clones
        elif (cloneStates['summary']['available_vms'] > group_data['prestarted_vms']
                and cloneStates['summary']['existing_vms'] > group_data['minimum_vms']):
            logger.info(f"[{vdi_group}] Try to remove clone...")
            removeClone.main(vdi_group)
            #t = threading.Thread(target=removeClone.main, args=(group,), daemon = True)
            #t.start()
    else:
        logger.info(f"[{vdi_group}] No master ready for clone handling")


def masterThreading(vdiGroups):
    master_threads = []
    
    for vdiGroup in vdiGroups:
        groupDetails=vdiGroups[vdiGroup]
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
            groupDetails=vdiGroups[vdiGroup]
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
        while not vdi_common.check_connection():
            vdi_common.check_connection()
        #active_vdi_groups = vdi_common.getActivatedVdiGroups(getVDIGroups())
        vdi_groups = vdi_common.get_vdi_groups()

        while len(vdi_groups['general']['active_groups']) == 0:
            logger.info("***** No active VDI Groups available! *****")
            time.sleep(5)
            vdi_groups = vdi_common.get_vdi_groups()
            



        ### Master Handling ###
        #try: 
        #    masterThread
        #except NameError:
        #    masterThread = threading.Thread(target=masterThreading,args=(vdi_groups['groups'],))
        #    masterThread.start()
        #if not masterThread.is_alive():
        #    logging.info("Starting new MasterThread")
        #    masterThread = threading.Thread(target=masterThreading,args=(vdi_groups['groups'],))
        #    masterThread.start()
        #

        ##
        #### Clone Handling: ###
        #try:
        #    cloneThread
        #except NameError:
        #    cloneThread = threading.Thread(target=clonesThreading,args=(vdi_groups['groups'],))
        #    cloneThread.start()
        #if not cloneThread.is_alive():
        #    logging.info("Starting new CloneThread")
        #    cloneThread = threading.Thread(target=clonesThreading,args=(vdi_groups['groups'],))
        #    cloneThread.start()
        for vdi_group in vdi_groups['groups']:
            handle_master(vdi_groups['groups'][vdi_group],vdi_group)
        for vdi_group in vdi_groups['groups']:
            handle_clones(vdi_groups['groups'][vdi_group],vdi_group)
        


        ### delete deprecated connection files ###
        deleteDeprecatedFiles()
        time.sleep(5)

if __name__ == "__main__":
    run_service()