#!/usr/bin/env python3
#
# vdi-service.py
#
# joanna.meinelt@netzint.de
#
# 20201127
#

import threading
import time
import json
import logging

import master_handling as master_handling
import removeMaster
import removeClone
import buildClone
from getVmStates import get_master_states, get_clone_states
from deleteConnectionFiles import deleteDeprecatedFiles
import vdi_common
from datetime import datetime


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

if level == "ERROR":
    logging.basicConfig(format='%(asctime)s %(levelname)7s: [%(filename)19s] [l%(lineno)4s]- %(message)s',
                        datefmt='%Y-%m-%d:%H:%M:%S',
                        level=logging.ERROR)

logger = logging.getLogger(__name__)

def handle_master(vdi_group):
    
    # for group in vdiGroups:
    logger.debug(f"[{vdi_group.name}] Group Data")
    logger.debug(json.dumps(vdi_group.data, indent=2))

    # get masterStates
    master_states = vdi_group.get_master_states()
    
    if not master_states:
        return

    logger.debug(f"[{vdi_group.name}] Master States Summary for group")
    logger.debug(json.dumps(master_states['summary'], indent=2))
    
    # if no Master available
    if master_states['summary']['existing_master'] == 0:
        logger.info(f"[{vdi_group.name}]No existing master, building new Master")

        # TODO make this a function and use it again
        for thread in threading.enumerate():
            if thread.name == "create_master_"+vdi_group.name:
                logger.info('Thread already running with name: %s' % vdi_group.name)
                return
        t = threading.Thread(
            target=master_handling.create_master, args=(vdi_group,),name=f"create_master_{vdi_group.name}")
        t.start()



    # if 1 or more master, try delete one
    elif master_states['summary']['existing_master'] > 1:
        logger.debug(
            f"[{vdi_group}] Try to find failed, building or deprecated masters to delete")
        # removeMaster.remove_master(group_data,vdi_group)
        t = threading.Thread(target=removeMaster.remove_master,
                             args=(vdi_group.data, vdi_group.name,))
        t.start()

        # read masterDetails again after deleting one so deleted master is not in existing list
        master_states = vdi_group.get_master_states()

    # if a master exist
    elif master_states['summary']['existing_master'] == 1:
        # get latest from existing mastervmids:
        existing_vmids = []
        timestampLatest, vmidLatest = 1, None
        for vmid in vdi_group.data['vmids']:
            if vmid in master_states:
                if master_states[vmid] is not None:
                    existing_vmids.append(vmid)
                    if master_states[vmid]['buildstate'] != "failed":
                        if float(master_states[vmid]['dateOfCreation']) > float(timestampLatest):
                            timestampLatest = master_states[vmid]['dateOfCreation']
                            vmidLatest = vmid
        if vmidLatest is None:
            logger.info(
                f"[{vdi_group.name}] Theres no finished or building actual Master")
        logger.debug(
            f"[{vdi_group.name}] Existing Master(s): {str(existing_vmids)}")
        logger.debug(f"[{vdi_group.name}] Latest Master: {str(vmidLatest)}")

        if master_states['current_master'].buildstate == "building":
            # TODO: check if master is building for too long
            logger.info(f"[{vdi_group.name}] Master is building")
            terminate = int(master_states['current_master'].date_of_creation) + vdi_group.data['timeout_building_master']
            if time.time() < terminate:
                master_states['current_master'].delete_master()
                master_states = vdi_group.get_master_states()

        
        # check if master image is up-to-date
        if not master_states['current_master'].actual_imagesize == master_states['current_master'].needed_imagesize:
            logger.debug(
                f"[{vdi_group.name}] Current imagesize {str(master_states['current_master'].actual_imagesize)} does not match current image: {str(master_states['current_master'].needed_imagesize)}")
            logger.debug(
                f"[{vdi_group.name}] Master Image is not up-to-date => creating new Master")

            # TODO make this a function and use it again
            for thread in threading.enumerate():
                if thread.name == "create_master_"+vdi_group.name:
                    logger.info('Thread already running with name: %s' % vdi_group.name)
                    return
            t = threading.Thread(
                target=master_handling.create_master, args=(vdi_group,),name=f"create_master_{vdi_group.name}")
            t.start()

        # image in master is up-to-date, check hardware attributes
        else:
            # check if hv hardware and options changed
            vm_attributes = ['bios','cores','memory','ostype','name','usb0','spice_enhancements','bridge','tag','storage','size']


            for attribute in vm_attributes:
                if not vdi_group.data[attribute] == master_states['current_master'].attributes[attribute]:
                    logger.info(
                        f"[{vdi_group.name}] Master Ressources {str(vmidLatest)} are not up to date, {attribute} changed! Try building new master")
                    master_handling.create_master(vdi_group.data, vdi_group.name)

            logger.info(f"[{vdi_group.name}] Master Ressources " +
                        str(master_states['current_master'].vmid) + " are up to date")


def handle_clones(group_data, vdi_group):
    # for group in vdiGroups:
    master_states = get_master_states(group_data, vdi_group)
    if not master_states:
        logger.warning(f"[{vdi_group}] No master states for this host, probably no entry in devices.csv")
        return
    finished_masters = ((int(master_states['summary']['existing_master']) - int(
        master_states['summary']['building_master'])))
    if finished_masters >= 1:
        clone_states = get_clone_states(group_data, vdi_group)
        master_vm_id = master_states['current_master']['vmid']
        logger.debug(
            f"[{vdi_group}] Clone States Summary for Group {vdi_group}")
        logger.debug(json.dumps(clone_states['summary'], indent=62))

        # Get the current state of the group
        existing_vms = clone_states['summary']['existing_vms']
        building_vms = clone_states['summary']['building_vms']
        available_vms = clone_states['summary']['available_vms']
        # Extract the group's min/max/prestarted settings
        min_vms = group_data['minimum_vms']
        max_vms = group_data['maximum_vms']
        prestarted_vms = group_data['prestarted_vms']

        # function to build new clone
        not_enough_min_clones = existing_vms < min_vms and building_vms < (min_vms - existing_vms)
        not_enough_prestarted_clones = available_vms < prestarted_vms and existing_vms < max_vms and building_vms < (prestarted_vms - available_vms)

        if not_enough_min_clones or not_enough_prestarted_clones:
            logger.debug(f"[{vdi_group}] Try to build new Clone ...")
            t = threading.Thread(target=buildClone.build_clone, args=(
                clone_states, group_data, master_states['current_master']['vmid'], vdi_group,))
            t.start()

   
   
        too_much_clones = available_vms > prestarted_vms and existing_vms > min_vms

        #elif clone_states['summary']['available_vms'] > group_data['prestarted_vms']\
        #        and clone_states['summary']['existing_vms'] > group_data['minimum_vms']:
        if too_much_clones:
            vm_amount_to_delete = clone_states['summary']['existing_vms'] - group_data['minimum_vms']
            logger.debug(f"[{vdi_group}] Try to remove clone...")
            removeClone.remove_clone(vm_amount_to_delete, clone_states, vdi_group,)
            #t = threading.Thread(
            #    target=removeClone.remove_clone, args=(clone_states, vdi_group,))
            #t.start()

        # update outdated clones
        outdated_clones = []
        if 'summary' in clone_states:
            del clone_states['summary']
        
        # Set building timeout to 10 minutes
        BUILDING_TIMEOUT_MINUTES = 10

        # Get the current datetime
        now = datetime.now()

        # Iterate over the clones
        for clone, clone_state in clone_states.items():
            # Get the clone's creation datetime and calculate the time since creation
            date_of_creation = datetime.strptime(clone_state['dateOfCreation'], "%Y%m%d%H%M%S")
            minutes_since_building = (now - date_of_creation).seconds / 60
        
            # Check if the clone is outdated based on its state and creation time
            if (clone_state['master'] != master_vm_id or
                clone_state['imagesize'] != master_states[master_vm_id]['imagesize'] or
                (clone_state['buildstate'] == "building" and minutes_since_building > BUILDING_TIMEOUT_MINUTES)):
                # Add the outdated clone to the list
                outdated_clones.append(clone_state)
        
        # Remove any outdated clones
        if outdated_clones:
            removeClone.remove_outdated_clones(outdated_clones, clone_states, vdi_group)


    else:
        logger.info(f"[{vdi_group}] No master ready for clone handling")



def run_service():
    logger.info("***** VDI-Service initiated ... *****")

    while True:
        logger.debug(
            "********************************************************")
        while not vdi_common.check_connection():
            vdi_common.check_connection()

        vdi_groups = vdi_common.get_vdi_groups()



        # Write a function which checks if there is any object in die vdi_groups which is activated

        for vdi_group in vdi_groups:
            if vdi_group.activated:
                handle_master(vdi_group)
                #try:
                #    handle_master(vdi_group)
                #except Exception as e:
                #    logger.error("Master failed: " + str(e))
                #try:
                #    handle_clones(vdi_groups['groups'][vdi_group], vdi_group)
                #except Exception as e:
                #    logger.error("Clone failed: " + str(e))



        ### delete deprecated connection files ###
        deleteDeprecatedFiles()
        time.sleep(5) # waiting 5 seconds is good for handling masters, otherwise a created vm could not have a description yet


if __name__ == "__main__":
    run_service()
