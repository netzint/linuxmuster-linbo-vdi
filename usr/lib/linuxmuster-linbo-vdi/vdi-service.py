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


import createNewMaster
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


logger = logging.getLogger(__name__)


def handle_master(group_data, vdi_group):

    # for group in vdiGroups:
    logger.info(f"[{vdi_group}] Group Data")
    logger.debug(json.dumps(group_data, indent=2))

    # get masterStates
    master_states = get_master_states(group_data, vdi_group)
    logger.info(f"[{vdi_group}] Master States Summary for group")
    logger.debug(json.dumps(master_states['summary'], indent=2))
    # if no Master available
    if master_states['summary']['existing_master'] == 0:
        logger.info(f"[{vdi_group}] Building new Master")
        # createNewMaster.create_master(group_data,vdi_group)
        t = threading.Thread(
            target=createNewMaster.create_master, args=(group_data, vdi_group,))
        t.start()

    # if 1 or more master, try delete one
    elif master_states['summary']['existing_master'] > 1:
        logger.debug(
            f"[{vdi_group}] Try to find failed, building or deprecated masters to delete")
        # removeMaster.remove_master(group_data,vdi_group)
        t = threading.Thread(target=removeMaster.remove_master,
                             args=(group_data, vdi_group,))
        t.start()
        # read masterDetails again after deleting one
        # so deleted master is not in existing list
        master_states = get_master_states(group_data, vdi_group)
    # if a master exist
    elif master_states['summary']['existing_master'] == 1:
        # get latest from existing mastervmids:
        master_vmids = group_data['vmids']
        existing_vmids = []
        timestampLatest, vmidLatest = 1, None
        for vmid in master_vmids:
            if vmid in master_states:
                if master_states[vmid] is not None:
                    existing_vmids.append(vmid)
                    if master_states[vmid]['buildstate'] != "failed":
                        if float(master_states[vmid]['dateOfCreation']) > float(timestampLatest):
                            timestampLatest = master_states[vmid]['dateOfCreation']
                            vmidLatest = vmid
        if vmidLatest is None:
            logger.info(
                "[{vdi_group}] Theres no finished or building actual Master")
        logger.debug(
            f"[{vdi_group}] Existing Master(s): {str(existing_vmids)}")
        logger.debug(f"[{vdi_group}] Latest Master: {str(vmidLatest)}")
        if master_states[vmidLatest]['buildstate'] == "building":
            logger.info(f"[{vdi_group}] Master is building")
        # check if master image is up 2 date
        if not master_states['basic']['actual_imagesize'] == master_states[vmidLatest]['imagesize']:
            logger.debug(
                f"[{vdi_group}] Current imagesize {str(master_states[vmidLatest]['imagesize'])} does not match current image: {str(master_states['basic']['actual_imagesize'])}")
            logger.debug(
                f"[{vdi_group}] Master Image is not up-to-date => creating new Master")
            # createNewMaster.create_master(group_data,vdi_group)
            t = threading.Thread(
                target=createNewMaster.create_master, args=(group_data, vdi_group,))
            t.start()
        else:
            # check if hv hardware and options changed
            attributes = ['bios', 'boot', 'cores', 'memory', 'ostype',
                          'name', 'scsihw', 'usb0', 'spice_enhancements']
            for attribute in attributes:
                if not group_data[attribute] == master_states[vmidLatest][attribute]:
                    logger.info(
                        f"[{vdi_group}] Master Ressources {str(vmidLatest)} are not up to date, try building new master")
                    createNewMaster.create_master(group_data, vdi_group)

            logger.info(f"[{vdi_group}] Master Ressources " +
                        str(vmidLatest) + " are up to date")


def handle_clones(group_data, vdi_group):
    # for group in vdiGroups:
    master_states = get_master_states(group_data, vdi_group)
    finished_masters = ((int(master_states['summary']['existing_master']) - int(
        master_states['summary']['building_master'])))
    if finished_masters >= 1:
        clone_states = get_clone_states(group_data, vdi_group)
        master_vm_id = master_states['current_master']['vmid']
        logger.debug(
            f"[{vdi_group}] Clone States Summary for Group {vdi_group}")
        logger.debug(json.dumps(clone_states['summary'], indent=62))

        existing_vms = clone_states['summary']['existing_vms']
        building_vms = clone_states['summary']['building_vms']
        available_vms = clone_states['summary']['available_vms']
        min_vms = group_data['minimum_vms']
        max_vms = group_data['maximum_vms']
        prestarted_vms = group_data['prestarted_vms']

        not_enough_min_clones = existing_vms < min_vms and building_vms < (min_vms - existing_vms)
        not_enough_prestarted_clones = available_vms < prestarted_vms and existing_vms < max_vms and building_vms < (prestarted_vms - available_vms)

        if not_enough_min_clones or not_enough_prestarted_clones:
            logger.debug(f"[{vdi_group}] Try to build new Clone ...")
            t = threading.Thread(target=buildClone.build_clone, args=(
                clone_states, group_data, master_states['current_master']['vmid'], vdi_group,))
            t.start()

        # if under minimum  ||  if available < prestarted  &&  existing < maximum
        # create clone
        #if clone_states['summary']['existing_vms'] < group_data['minimum_vms'] and clone_states['summary']['building_vms'] < (group_data['minimum_vms'] - clone_states['summary']['existing_vms'])\
        #        or clone_states['summary']['available_vms'] < group_data['prestarted_vms'] \
        #        and clone_states['summary']['existing_vms'] < group_data['maxmimum_vms'] \
        #        and clone_states['summary']['building_vms'] < (group_data['prestarted_vms']-clone_states['summary']['available_vms']):
#
        #    logger.debug(f"[{vdi_group}]Try to build new Clone ...")
        #    # buildClone.build_clone(clone_states,group_data,master_states['current_master']['vmid'],vdi_group)
        #    t = threading.Thread(target=buildClone.build_clone, args=(
        #        clone_states, group_data, master_states['current_master']['vmid'], vdi_group,))
        #    t.start()
        #    # time.sleep(5)

        # if (available > prestarted) || existing > minimum)
        # delete clones
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
        #active_vdi_groups = vdi_common.getActivatedVdiGroups(getVDIGroups())
        vdi_groups = vdi_common.get_vdi_groups()

        while len(vdi_groups['general']['active_groups']) == 0:
            logger.info("***** No active VDI Groups available! *****")
            time.sleep(5)
            vdi_groups = vdi_common.get_vdi_groups()

        for vdi_group in vdi_groups['groups']:
            if vdi_groups['groups'][vdi_group]['activated']:
                handle_master(vdi_groups['groups'][vdi_group], vdi_group)
        for vdi_group in vdi_groups['groups']:
            if vdi_groups['groups'][vdi_group]['activated']:
                handle_clones(vdi_groups['groups'][vdi_group], vdi_group)

        ### delete deprecated connection files ###
        deleteDeprecatedFiles()
        time.sleep(2)


if __name__ == "__main__":
    run_service()
