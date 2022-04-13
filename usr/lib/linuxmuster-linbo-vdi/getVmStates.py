#!/usr/bin/env python3
#
# getVmStates.py
#
# joanna.meinelt@netzint.de
#
# 20211121


import json
from datetime import datetime
from globalValues import node,proxmox,timeoutConnectionRequest
#from globalValues import getMasterDetails
import vdi_common
import argparse
import logging

from multiprocessing.pool import ThreadPool
__version__ = 'version 0.9.9'

logger = logging.getLogger(__name__)




######## merges all vm infos to one JSON and returns it with vmid ########
def mergeInfos(vmid, apiInfos, groupInfos):
    jsonObject = {}
    apiInfos.update(groupInfos)
    jsonObject[vmid] = apiInfos
    return jsonObject 

######## returns dict devicesInfos from devices list  ########
def get_vm_group_infos(devices, vmid)-> dict:
    devicesInfos = {}
    for device in devices:
        if device[11] == vmid:
            devicesInfos['room'] = device[0]
            devicesInfos['hostname'] = device[1]
            devicesInfos['group'] = device[2]
            devicesInfos['mac'] = device[3]
            devicesInfos['ip'] = device[4]
            devicesInfos['pxe'] = device[10]
    return devicesInfos


def get_master_group_infos(devices, master_hostname)-> dict:
    vdiGroupInfos = {}
    for device in devices:
        if master_hostname in device[1]:
            vdiGroupInfos['room'] = device[0]
            vdiGroupInfos['hostname'] = device[1]
            vdiGroupInfos['group'] = device[2]
            vdiGroupInfos['mac'] = device[3]
            vdiGroupInfos['ip'] = device[4]
            vdiGroupInfos['pxe'] = device[10]
    return vdiGroupInfos

## get information from existing VMs  
def get_vm_info_by_api(node, vm_id,vdi_group,vm_type='clone')-> dict:
    """ Returns all information provided by hv API including description dict
    
    :param node: str
    :param vm_id: int
    :param vdi_group: str
    :rtype dict
    """
    try:
        vm_api_infos = proxmox.nodes(node).qemu(vm_id).config.get()
    except Exception as err:
        if err.status_code == 500 and 'does not exist' in err.content:
            logging.info(f"[{vdi_group}] VM {vm_id} does not exist on {node}")
        return None

    try:
        response = proxmox.nodes(node).qemu(vm_id).status.current.get()
        vm_api_infos["status"] = response['qmpstatus']
        vm_api_infos["uptime"] = response['uptime']
        vm_api_infos["status"] = response['qmpstatus']
        vm_api_infos['spicestatus'] = ""
    except Exception as err:
        logging.error(f"[{vdi_group}] Cannot parse VM {vm_id} information")
        return None

    ##### split and separate description from descriptionf field from vm ######
    description_json = json.loads(vm_api_infos['description'])
    try:
        if vm_type == 'clone':
            vm_api_infos['image'] = description_json["image"]
            vm_api_infos['master'] = description_json["master"]
            vm_api_infos['lastConnectionRequestUser'] = description_json['lastConnectionRequestUser']
            vm_api_infos['lastConnectionRequestTime'] = description_json['lastConnectionRequestTime']
        
        if vm_type == 'master':
            vm_api_infos['timestamp'] = description_json['timestamp']
        
        # used for all vms
        vm_api_infos["imagesize"] = description_json['imagesize']
        vm_api_infos['dateOfCreation'] = description_json["dateOfCreation"]
        vm_api_infos['buildstate'] = description_json["buildstate"]
        vm_api_infos['vmid'] = vm_id
        vm_api_infos['group'] = description_json['group']

        vm_api_infos.pop("description")

        logging.info(f"[{vdi_group}] VM {vm_id} parsed")
        return vm_api_infos
    except Exception as err:
        logging.error(f"[{vdi_group}] Failed to extrat information from description field for VM {vm_id} {str(err)}")  
        return None


####### CLONES: ########

def get_all_states(vm_type)-> dict:
    if vm_type not in ['clone', 'master']:
        logger.error("wrong vm_type provided")
        return 1
    vdi_groups = vdi_common.get_vdi_groups()
    allInfos={}
    for vdi_group in vdi_groups['groups']:
        if vm_type == 'master':
            # TODO fix this in gui and here, just use basic for god sake...
            states = get_master_states(vdi_groups['groups'][vdi_group], vdi_group)
            allInfos.update({vdi_group:{'summary':states['summary']}})
            states.pop('summary')
            allInfos[vdi_group]['current_master'] = states['current_master']
            allInfos[vdi_group]['current_master']['hostname'] = states['basic']['hostname']
            allInfos[vdi_group]['current_master']['actual_imagesize'] = states['basic']['actual_imagesize']
            allInfos[vdi_group]['current_master']['ip'] = states['basic']['ip']
            allInfos[vdi_group]['current_master']['mac'] = states['basic']['mac']
            states.pop('basic')
            states.pop('current_master')
            allInfos[vdi_group]['master_vms'] ={}
            for vm in states:
                allInfos[vdi_group]['master_vms'].update({vm: states[vm]})
 
            #allInfos[vdi_group]['master_vms'] = states
            #allInfos[vdi_group]['hostname'] = states['basic']['hostname']
            #allInfos[vdi_group]['actual_imagesize'] = states['basic']['actual_imagesize']
            #allInfos[vdi_group]['ip'] = states['basic']['ip']
            #allInfos[vdi_group]['mac'] = states['basic']['mac']

        elif vm_type == 'clone':
            states = get_clone_states(vdi_groups['groups'][vdi_group], vdi_group)
            allInfos.update({vdi_group:{'summary':states['summary']}})
            states.pop('summary')
            allInfos[vdi_group]['clone_vms'] = states



    return allInfos

def get_clone_states(group_data,vdi_group)-> dict:

    vdi_common.check_connection()

    clone_states = {}
    school_id = vdi_common.get_school_id(vdi_group)

    ####### Get collected JSON Info File to all VMs from Group #############
    devices = vdi_common.devices_loader(school_id)
    idRange = vdi_common.get_vmid_range(devices, vdi_group)

    ####### collect API Parameter and Group Infos from each VM, merges them, and collects them in one dict #######
    clone_states = get_vm_info_multithreaded(idRange,node,vdi_group,'clone')

    # expand information by devices.csv
    # TODO: move this to the get_vm_info_multithreaded function
    for vmid in clone_states:
            for device in devices:
                if vmid == device[11]:
                    clone_states[vmid]['room'] = device[0]
                    clone_states[vmid]['hostname'] = device[1]
                    clone_states[vmid]['ip'] = device[4]
                    clone_states[vmid]['mac'] = device[3]


    ####### adds user field if vm is used by an user #######
    logged_in_users = vdi_common.getSmbstatus(school_id)
    if logged_in_users:
        for user in logged_in_users:
            for vmid in clone_states:
                if logged_in_users[user]['ip'] == clone_states[vmid]['ip']:
                    clone_states[vmid]['user'] = logged_in_users[user]['full']
                if 'user' not in clone_states[vmid]:
                    clone_states[vmid]['user'] = ''


    else:
        for vmid in clone_states:
            clone_states[vmid]['user'] = ''


    ####### calculates summary values 'allocated_vms', 'existing_vms', 'building_vms' #######
    allocated = 0
    existing = len(clone_states)
    available = 0
    building = 0
    failed = 0
    registered = len(idRange)
    now = datetime.now()
    now = float(now.strftime("%Y%m%d%H%M%S"))
    for vmid in clone_states:
        try:
            if clone_states[vmid]['buildstate'] == 'building':
                building = building + 1
                continue
            if clone_states[vmid]['buildstate'] == "failed":
                failed = failed + 1
                continue
            if clone_states[vmid]['buildstate'] == 'finished':
                if (clone_states[vmid]['lastConnectionRequestTime'] == ''):
                        if clone_states[vmid]['user'] == '':
                            available = available + 1
                            continue
                        if clone_states[vmid]["user"] != '':
                            allocated = allocated + 1
                            continue
                if (clone_states[vmid]['lastConnectionRequestTime'] != ''):
                        if clone_states[vmid]['user'] == "" \
                                and (now - float(clone_states[vmid]['lastConnectionRequestTime']) > timeoutConnectionRequest):
                                    available = available + 1
                                    continue
                        if clone_states[vmid]["user"] != "" \
                                or (now - float(clone_states[vmid]['lastConnectionRequestTime']) <= timeoutConnectionRequest):
                                    allocated = allocated + 1
                
        except Exception as err:
            logger.error(err)
            pass

    clone_states['summary'] = {
        'allocated_vms'     : allocated,
        'available_vms'   : available,
        'existing_vms'     : existing,
        'registered_vms': registered,
        'building_vms': building,
        'failed_vms'     : failed,
    }
    return clone_states
    

def get_needed_imagesize(vdiGroup):
    devicePath = "/srv/linbo/start.conf." + str(vdiGroup)
    startConf_data = vdi_common.start_conf_loader(devicePath)
    
    for os in startConf_data['os']:
        image_name = os['BaseImage']
    imageInfo = vdi_common.image_info_loader(image_name)

    return imageInfo['imagesize']


def get_vm_info_multithreaded(vmids,node,vdi_group,vm_type)-> dict:
    # define Thread pool
    pool = ThreadPool(processes=5)
    processes = []
    data = {}
    for vmid in vmids:
        processes.append(pool.apply_async(func=get_vm_info_by_api, args=(node,vmid,vdi_group,vm_type,)))
    for process in processes:
        returnValue = process.get()
        if returnValue:
            #apiInfos[returnValue['vmid']].update(returnValue)
            data.update({returnValue['vmid']:returnValue})
    pool.close()
    pool.join()
    return data

####### MASTER: #######
def get_master_states(group_data,vdi_group) -> dict:

    vdi_common.check_connection()

    master_states = {}

    schoolId = vdi_common.get_school_id(vdi_group)
    devices=vdi_common.devices_loader(schoolId)
    ####### Get collected JSON Info File to all VMs from Group #############
    master_vmids = group_data['vmids']
    master_hostname = group_data['hostname']
    logger.info(f"[{vdi_group}] ID Range for imagegroup")
    logger.info(f"[{vdi_group}] {master_vmids}" )


    master_states['basic'] = get_master_group_infos(devices, master_hostname)
    master_states['basic']['actual_imagesize'] = get_needed_imagesize(vdi_group)
    master_states['basic']['hostname'] = master_hostname
    allApiInfos = {}
    #logger.info("*** Getting information to Masters from Group " + vdiGroup + " ***")
    ####### get api Infos #######

    allApiInfos = get_vm_info_multithreaded(master_vmids,node,vdi_group,'master')
    master_states.update(allApiInfos)
    # summary
    master_states['summary'] = {
        'existing_master'     : 0,
        'registered'   : len(master_vmids),
        'building_master'     : 0,
        'failed_master': 0,
        'finished'     : 0,
    }
    
    for vmid in allApiInfos:
        # calculate existing
        try:
            proxmox.nodes(node).qemu(vmid).status.get()
            master_states["summary"]["existing_master"]  = master_states["summary"]["existing_master"]  + 1
            # calculate buildstates - just from existing vms!
            try:
                if allApiInfos[vmid]['buildstate'] == "building":
                    master_states["summary"]["building_master"] = master_states["summary"]["building_master"] + 1
                if allApiInfos[vmid]['buildstate'] == "finished":
                    master_states["summary"]["finished"] = master_states["summary"]["finished"] + 1
                if allApiInfos[vmid]['buildstate'] == "failed":
                    master_states["summary"]["failed_master"] = master_states["summary"]["failed_master"] + 1
            except Exception:
                pass
        except Exception:
            pass
    
    master_states['current_master']=vdi_common.get_current_master(master_states, master_vmids, vdi_group)
    return master_states


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s:%(asctime)s %(message)s', level=logging.ERROR)

    parser = argparse.ArgumentParser(description='getVmStats.py ')
    quiet = False
    parser.add_argument('-v', dest='version', action='store_true', help='print the version and exit')
    parser.add_argument('-m', '-master', dest='master', action='store_true', help='run as master')
    parser.add_argument('-c', '-clones', dest='clones', action='store_true', help='update and push git tag')
    parser.add_argument('group', nargs='?', default='all')
    parser.add_argument('-q', '-quiet', dest='quiet', action='store_true', help='run as master')
    args = parser.parse_args()

    if args.version:
        print (__version__)
        quit()
    if args.master is not False:
        if args.group != 'all':
            group_data = vdi_common.get_vdi_groups()['groups'][args.group]
            print(json.dumps(get_master_states(group_data,args.group), indent=2))     
        else:
            print(json.dumps(get_all_states('master'), indent=2))
        quit()
    if args.clones is not False:
        if args.group != 'all':
            group_data = vdi_common.get_vdi_groups()['groups'][args.group]
            print(json.dumps(get_clone_states(group_data,args.group), indent=2))
        else:
            print (json.dumps(get_all_states('clone'), indent=2))
        quit()
    else:
        parser.print_help()
    quit()
