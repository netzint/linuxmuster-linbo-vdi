#!/usr/bin/env python3
#
# cloneMaster.py
#
# joanna.meinelt@netzint.de
# 20200930
#

import json
from ipaddress import IPv4Network
import nmap
import time
from datetime import datetime
import sys
import logging
import vdi_common
from proxmoxer import ProxmoxAPI
from globalValues import vdiLocalService,proxmox,node
if vdiLocalService == False:
    from globalValues import ssh

logger = logging.getLogger(__name__)

#logger.info("*** Begin Cloning Master *** ")





# searches next available VMID fpr Clone and exits if doesnt exists
def get_next_available_vmid(clone_states,id_range,vdi_group):

    for id in id_range:
        if id not in clone_states:
            logger.info(f"[{vdi_group}] Next free VM ID:  {str(id)}")
            return id
    logger.warning(f"[{vdi_group} No Free VMIds left for cloning , add VMs in devices.csv on server!")
    return False




# defines description for clone
def generate_clone_description(group_data,masterVmid, cloneName, vdi_group):
    description = {}
    timestamp = datetime.now()
    dateOfCreation = timestamp.strftime("%Y%m%d%H%M%S")         # => "20201102141556"
    logger.info(f"[{vdi_group}] Timestamp new Clone: {str(dateOfCreation)}")

    description['name'] = cloneName
    description["dateOfCreation"] = dateOfCreation
    description['master'] = masterVmid
    description['lastConnectionRequestUser'] = ''
    description['lastConnectionRequestTime'] = ''
    description['group'] = group_data['group']
    #description['user'] = ""

    devicePath = "/srv/linbo/start.conf." + str(vdi_group)

    startConf_data = vdi_common.start_conf_loader(devicePath)
    for os in startConf_data['os']:
        image_name = os['BaseImage']

    description["image"] = image_name
    description["buildstate"] = "building"
    return description


def clone_master(master_node, master_vmid, clone_vmid, clone_name, clone_description,vdi_group):
    description = json.dumps(clone_description)    ### important! sonst liest nur die Haelfte
    logger.info(f"[{vdi_group} Clone-VM-Name: {clone_name}")
    proxmox.nodes(master_node).qemu(master_vmid).clone.post(newid=clone_vmid,name=clone_name,description=description)
    print(f"[{vdi_group} Template is getting cloned to VM with next free VM-ID: {str(clone_vmid)}")


####### starts clone and checks 10 Seconds if succesfully running
def start_clone(clone_node, clone_vmid,vdi_group):
    proxmox.nodes(clone_node).qemu(clone_vmid).status.start.post()
    logger.info(f"[{vdi_group} VM {clone_vmid} started")
    try:
        if waitForStatusRunning(10,clone_node, clone_vmid) == True:
            logger.info(f"[{vdi_group} VM {clone_vmid} is running")
    except Exception:
        logger.info(f"[{vdi_group} VM {clone_vmid} couldn't get started, script is terminating")
        return


####### returns dict[] desctops{ vmid {ip : ip, mac : mac}}
def get_devices_network_info(devices,clone_vmid):
    for device in devices:
        if device[11] == clone_vmid:
            return {'hostname':device[1],'mac':device[3],'ip': device[4], 'vmid': clone_vmid}
    return False


# checks if windows bootet succesfully and waits multischool time
def checkNmap(timeout, clone_vmid, clone_ip):
    windows_ports = {"RPC": "135", "SMB": "445", "SVCHOST": "49665"}
    linux_ports = {"SSH": "22"}
    terminate = time.time() + timeout
    scanner = nmap.PortScanner()
    logger.info("*** Scanning for open ports on " + clone_vmid + " ***")

    while time.time() < terminate:
        for port in windows_ports:
            try:
                portscan = scanner.scan(clone_ip, windows_ports[port])
                status = portscan['scan'][clone_ip]['tcp'][int(windows_ports[port])]['state']
                logger.debug("Port " + port + " : " + status)
                if status == "open" or status == "closed":
                        logger.info("*** Windows boot check on " + str(clone_vmid) + " succesfully, found open port ***")
                        return True
            except KeyError as err:
                continue
        for port in linux_ports:
            try:   
                portscan = scanner.scan(clone_ip, linux_ports[port])
                status = portscan['scan'][clone_ip]['tcp'][int(linux_ports[port])]['state']
                logger.debug("Port " + port + " : " + status)
                if status == "open" or status == "closed":
                    logger.info("*** Linux boot check on " + str(clone_vmid) + " succesfully, found open port ***")
                    return True
            except KeyError as err:
                continue
        logger.info("*** Clone " + str(clone_vmid) + " seems not ready yet, no open ports found ***")
        time.sleep(2)

    return False


def waitForStatusRunning(timeout, clone_node, clone_vmid):
    terminate = time.time() + timeout
    while time.time() < terminate:
        status = proxmox.nodes(clone_node).qemu(clone_vmid).status.current.get()
        status = status['qmpstatus']
        if status == "running":
            return True
        time.sleep(2)
        logger.info("*** Status: " + str(status) + " ***")
        logger.info("*** waiting VM to run ... ***")
    return False


def build_clone(clone_states, group_data, master_vmid, vdi_group):

    # get basic information:
    master_node = node
    master_name = group_data['name'] #master-name for vm on pve 
    #masterPool = pool

    # get school environment and calculate devices path     
    school_id = vdi_common.get_school_id(vdi_group)
    devices = vdi_common.devices_loader(school_id)
    id_range= vdi_common.get_vmid_range(devices,vdi_group)

    
    # fuer proxmox:
    clone_node = master_node
    clone_vmid = get_next_available_vmid(clone_states, id_range, vdi_group)
    if not clone_vmid:
        return False
    clone_name_prefix = master_name.replace("master", "")
    clone_name = clone_name_prefix + "clone-" + str(clone_vmid)
    clone_description = generate_clone_description(group_data,master_vmid, clone_name, vdi_group)

    # Cloning:
    clone_master(master_node, master_vmid, clone_vmid, clone_name, clone_description,vdi_group)

    # change correct MAC address:  ### change MAC  address as registered !!!! get net0 from master and only change mac  # net0 = bridge=vmbr0,virtio=62:0C:5A:A0:77:FF,tag=29
    clone_network_info = get_devices_network_info(devices, clone_vmid)

    cloneNet = "bridge=" + group_data['bridge'] + ",virtio=" + clone_network_info['mac'] 
    if 'tag' in group_data and group_data['tag'] != 0:
        cloneNet += ",tag="+str(group_data['tag'])   

    logger.info(f"[{vdi_group} Assigning Mac {str(clone_network_info['mac'])} to {clone_vmid}")
    proxmox.nodes(clone_node).qemu(clone_vmid).config.post(net0=cloneNet)

    # Lock removing - not tested:
    # try:
        #     proxmox.nodes(cloneNode).qemu(cloneVmid).config.post()
        #     # proxmox.nodes(cloneNode).qemu(cloneVmid).config.post(delete=lock)
        #     print ("Removed Lock ")
        # except Exception as err:
        #     print(err)
        #     pass

    # startClone:
    start_clone(clone_node, clone_vmid, vdi_group)
    timeoutBuilding = group_data['timeout_building_clone']
    # if checkNmap succesful => change buildingstate finished
    if checkNmap(timeoutBuilding, clone_vmid, clone_network_info['ip']) == True:
        clone_description['buildstate'] = "finished"
        description = json.dumps(clone_description)
        proxmox.nodes(clone_node).qemu(clone_vmid).config.post(description=description)
        logger.info(f"[{vdi_group} Creating new Clone for group {vdi_group} terminated succesfully")
# if checkNmap failed => change buildingstate failed
    else:
        clone_description['buildstate'] = "failed"
        description = json.dumps(clone_description)
        proxmox.nodes(clone_node).qemu(clone_vmid).config.post(description=description)
        logger.info(f" [{vdi_group}Creating new Clone for group {vdi_group} failed. Deleting...")


if __name__ == "__main__":
    build_clone(sys.argv[1])

