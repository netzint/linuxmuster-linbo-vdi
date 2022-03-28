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

__version__ = 'version 0.90.22'

logger = logging.getLogger(__name__)

######## tries to get information from existing VMs (Clones):  ########
def get_vm_info_by_api(node, vm_id,vdi_group)-> dict:
    """ Returns all information provided by hv API including description dict
    
    :param node: str
    :param vm_id: int
    :param vdi_group: str
    :rtype dict
    """
    try:
        vm_api_infos = proxmox.nodes(node).qemu(vm_id).config.get()
        vm_api_infos["status"] = proxmox.nodes(node).qemu(vm_id).status.current.get()['qmpstatus']
        vm_api_infos["uptime"] = proxmox.nodes(node).qemu(vm_id).status.current.get()['uptime']
        vm_api_infos['spicestatus'] = ""
    except Exception:
        logging.error(f"[{vdi_group}] failed to parse description JSON for vm {vm_id}")
        return None
    ##### split and separate description from descriptionf field from vm ######

    description_json = json.loads(vm_api_infos['description'])

    try:
        vm_api_infos['dateOfCreation'] = description_json["dateOfCreation"]
        vm_api_infos['cloop'] = description_json["cloop"]
        vm_api_infos['buildstate'] = description_json["buildstate"]
        vm_api_infos['master'] = description_json["master"]
        vm_api_infos['lastConnectionRequestUser'] = description_json['lastConnectionRequestUser']
        vm_api_infos['lastConnectionRequestTime'] = description_json['lastConnectionRequestTime']
        vm_api_infos.pop("description")

        return vm_api_infos
    except Exception:
        logging.error(f"[{vdi_group}] Failed to assign vm_api_infos")  
        return None



######## merges all vm infos to one JSON and returns it with vmid ########
def mergeInfos(vmid, apiInfos, groupInfos):
    jsonObject = {}
    apiInfos.update(groupInfos)
    jsonObject[vmid] = apiInfos
    return jsonObject 


######## returns dict devicesInfos from devices list  ########
def getGroupInfos(devices, vmid):
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


def getGroupInfosMaster(devices, master_hostname):
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



####### CLONES: ########
def get_clone_states(group_data,vdi_group)-> dict:

    vdi_common.check_connection()
    allGroups = []
    allGroups.append(vdi_group)


    clone_states = {}
    #for group in allGroups:

    school_id = vdi_common.get_school_id(vdi_group)


    ####### Get collected JSON Info File to all VMs from Group #############
    devices = vdi_common.devices_loader(school_id)
    idRange = vdi_common.get_vmid_range(devices, vdi_group)


    ####### collect API Parameter and Group Infos from each VM, merges them, and collects them in one dict #######
    #TODO this seems to take a while, improve!
    for vmid in idRange:    
        apiInfos = get_vm_info_by_api(node,vmid,vdi_group)
        if apiInfos:
            vm_infos = mergeInfos(vmid, apiInfos, group_data)
            clone_states.update(vm_infos)

    ####### adds user field if vm is used by an user #######
    loggedIn = vdi_common.getSmbstatus(school_id)
    if loggedIn:
        for user in loggedIn:
            for vmid in idRange:
                if "buildstate" in clone_states[vmid]:
                    if loggedIn[user]["ip"] == clone_states[vmid]["ip"]:
                        clone_states[vmid]["user"] = loggedIn[user]["full"]
                    #elif "user" in allallInfos[vmid]:
                    #else:# check if user already assign user with another IP!
                    #    if allallInfos[vmid]["user"] == "":
                    #        allallInfos[vmid]["user"] = ""
                    elif "user" not in clone_states[vmid]:
                        clone_states[vmid]["user"] = ""
                else:
                    clone_states[vmid]["user"] = ""
    else:
        for vmid in idRange:
            clone_states[vmid]["user"] = ""


    ####### calculates summary values 'allocated_vms', 'existing_vms', 'building_vms' #######
    allocated = 0
    existing = 0
    available = 0
    building = 0
    failed = 0
    registered = len(idRange)
    now = datetime.now()
    now = float(now.strftime("%Y%m%d%H%M%S"))
    for vmid in clone_states:
        # calculate existing
        try:
            proxmox.nodes(node).qemu(vmid).status.get()
            existing = existing + 1
            # calculate building,finished,available,allocated,failed - just from existing vms!
            try:
                if clone_states[vmid]['buildstate'] == "building":
                    building = building + 1
                elif clone_states[vmid]['buildstate'] == "finished":
                    if (clone_states[vmid]['lastConnectionRequestTime'] == ""):
                        if clone_states[vmid]['user'] == "":
                            available = available + 1
                        elif clone_states[vmid]["user"] != "":
                            allocated = allocated + 1
                    elif (clone_states[vmid]['lastConnectionRequestTime'] != ""):
                        if clone_states[vmid]['user'] == "" \
                                and (now - float(clone_states[vmid]['lastConnectionRequestTime']) > timeoutConnectionRequest):
                                    available = available + 1
                        elif clone_states[vmid]["user"] != "" \
                                or (now - float(clone_states[vmid]['lastConnectionRequestTime']) <= timeoutConnectionRequest):
                                    allocated = allocated + 1
                elif clone_states[vmid]['buildstate'] == "failed":
                    failed = failed + 1
            except Exception as err:
                #logger.info(err)
                pass
        except Exception as err:
            #print(err)
            continue


        vm_infos['summary'] = {
            'allocated_vms'     : allocated,
            'available_vms'   : available,
            'existing_vms'     : existing,
            'registered_vms': registered,
            'building_vms': building,
            'failed_vms'     : failed,
        }
        # TODO Port back all in CLI
        #if group == "all":
        #    allallGroupInfos[vdiGroup] = {}
        #    allallGroupInfos[vdiGroup]['clone_vms'] = allallInfos
        #    allallGroupInfos[vdiGroup]['summary']  = summary
        #else:
        #    allallInfos['summary'] = summary
    
####### prints the whole JSON with all information #######

        #logger.info(json.dumps(allallInfos, indent=2))
        return clone_states
    


###### get api infos to master ######
def getApiInfosMaster(node,vmid)-> dict:

    apiInfos = proxmox.nodes(node).qemu(vmid).config.get()     # => type = dict
    description = apiInfos['description']

    try:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        status = status['qmpstatus']
        apiInfos["status"] = status
    except Exception as err:
        logging.error("Failed to load JSON or api access failed:")
        logging.error(err)
        pass


    ##### split and separate description from descriptionf field from vm ######
    descriptionJSON = json.loads(description)
    try:
        apiInfos['dateOfCreation'] = descriptionJSON['dateOfCreation']
        # TODO: Check if cloop needed or what to do
        #apiInfos['cloop'] = descriptionJSON['cloop']
        apiInfos['timestamp'] = descriptionJSON['timestamp']
        apiInfos['buildstate'] = descriptionJSON['buildstate']
        apiInfos["imagesize"] = descriptionJSON['imagesize']
        apiInfos.pop("description")
        return apiInfos
    except KeyError as err:
        logger.warning('Key '+ str(err) + ' not found in Machine description')
        logger.warning("***** Failed to assign description values. *****")   # so tif error its shown immediately
    except Exception as err:
        logger.error(err)
        logger.error("***** Failed to assign description values. ******")   # so tif error its shown immediately
        pass


def getActualImagesize(vdiGroup):
    devicePath = "/srv/linbo/start.conf." + str(vdiGroup)
    startConf_data = vdi_common.start_conf_loader(devicePath)
    
    # TODO: Handle more than one os
    for os in startConf_data['os']:
        image_name = os['BaseImage']
    imageInfo = vdi_common.image_info_loader(image_name)

    return imageInfo['imagesize']




####### MASTER: #######
def get_master_states(group_data,vdiGroup) -> dict:

    vdi_common.check_connection()
    #allGroups = []
    #if group == "all":
    #    allGroups = vdi_common.get_vdi_groups() # TODO Work with dict
    #    allGroupInfos = {}
    #    #print("=======AllGroups:")
    #    #print(allGroups)
    #else:
    #allGroups.append(group)

    groupInfos = {}
    #for vdiGroup in allGroups:

    schoolId = vdi_common.get_school_id(vdiGroup)
    devices=vdi_common.devices_loader(schoolId)
    ####### Get collected JSON Info File to all VMs from Group #############
    master_vmids = group_data['vmids']
    master_hostname = group_data['hostname']
    logger.info(f"[{vdiGroup}] ID Range for imagegroup")
    logger.info(f"[{vdiGroup}] {master_vmids}" )

    #if group == "all":
    #    # general
    #    groupInfos = getGroupInfosMaster(devices, master_hostname)
    #    #groupInfos = getGroupInfosMaster(devicePath, masterName)
    #    groupInfos['actual_imagesize'] = getActualImagesize(vdiGroup)
    #    groupInfos['hostname'] = master_hostname
    #else:
    groupInfos['basic'] = getGroupInfosMaster(devices, master_hostname)
    groupInfos['basic']['actual_imagesize'] = getActualImagesize(vdiGroup)
    groupInfos['basic']['hostname'] = master_hostname
    allApiInfos = {}
    #logger.info("*** Getting information to Masters from Group " + vdiGroup + " ***")
    ####### get api Infos #######
    for vmid in master_vmids:
        #print(type(vmid)) # => 'str'
        apiInfos = {}
        try:
            apiInfos[vmid] = getApiInfosMaster(node,vmid)
        except Exception:
            apiInfos[vmid] = None
            pass
        allApiInfos.update(apiInfos)
    #if group == "all":
    #    groupInfos['master_vms'] = allApiInfos
    #else:
    groupInfos.update(allApiInfos)
    # summary
    groupInfos['summary'] = {
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
            groupInfos["summary"]["existing_master"]  = groupInfos["summary"]["existing_master"]  + 1
            # calculate buildstates - just from existing vms!
            try:
                if allApiInfos[vmid]['buildstate'] == "building":
                    groupInfos["summary"]["building_master"] = groupInfos["summary"]["building_master"] + 1
                if allApiInfos[vmid]['buildstate'] == "finished":
                    groupInfos["summary"]["finished"] = groupInfos["summary"]["finished"] + 1
                if allApiInfos[vmid]['buildstate'] == "failed":
                    groupInfos["summary"]["failed_master"] = groupInfos["summary"]["failed_master"] + 1
            except Exception:
                pass
        except Exception:
            pass

        #if group == "all":
        #    allGroupInfos[vdiGroup] = groupInfos

    #if group == "all":
    #    return allGroupInfos
    #else:
    return groupInfos


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
        # TODO Fix this for CLI
        print(json.dumps(get_master_states(args.group), indent=2))
        quit()
    if args.clones is not False:
        print(json.dumps(get_clone_states(args.group), indent=2))
        quit()
    else:
        parser.print_help()
    quit()