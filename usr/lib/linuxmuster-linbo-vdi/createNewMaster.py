#!/usr/bin/env python3
#
# createNewMaster.py
#
# joanna.meinelt@netzint.de
# 20200930
#

import sys
import nmap
import re
import time
from datetime import datetime
#from proxmoxer import ProxmoxAPI
import logging
import vdi_common
from globalValues import node, multischool, proxmox, nmapPorts, vdiLocalService
#from globalValues import getMasterDetailsgetFileContent, getSchoolId
if vdiLocalService == False:
    from globalValues import ssh

logger = logging.getLogger(__name__)


# returns dict with image infos
def generate_master_description(vdi_group)-> dict:
    image_values = {}
    devicePath = "/srv/linbo/start.conf." + str(vdi_group)
    startConf_data = vdi_common.start_conf_loader(devicePath)
    for os in startConf_data['os']:
        image_name = os['BaseImage']
    imageInfo = vdi_common.image_info_loader(image_name)

    image_values["timestamp"] = imageInfo["timestamp"]
    image_values["imagesize"] = imageInfo["imagesize"]

    timestamp = datetime.now()
    dateOfCreation = timestamp.strftime("%Y%m%d%H%M%S")  # => "20201102141556"
    image_values["dateOfCreation"] = dateOfCreation
    image_values["buildstate"] = "building"

    logging.debug(f"[{vdi_group}] {image_values}")
    return image_values


# get alls VMIDs and checks returns first which doesnt exist on hv (no delete from oldest)
def get_available_vmid(masterNode, group_data, vdi_group)-> int:
    vmids = group_data['vmids']

    for vmid in vmids:
        try:
            if proxmox.nodes(masterNode).qemu(vmid).status.get() != "":
                logger.info(f"[{vdi_group}]Existing: {str(vmid)}")
        except Exception:
            logger.info(f"[{vdi_group}] Available VMID found for Master: {str(vmid)}")
            return vmid
    logger.info(f"[{vdi_group}] No VMID available .. aborting")
    return False


def get_master_device_info(devices, master_mac)-> dict:
    for device in devices:
        if device[3] == master_mac:
                return {'hostname':device[1],'mac':device[3],'ip': device[4]}
    return None

def send_linbo_remote_command(school_id, master_ip,vdi_group):
    try:
        command = "linbo-remote"
        if school_id != 'default-school':
            command += f" -s {school_id}"
        command += f" -i {master_ip} -p partition,format,initcache:rsync,sync:1,start:1"
        logging.info(f"[{vdi_group}] Send linbo remote command to {master_ip}")
        print (command)
        run_command(command)
    except Exception as err:
        logger.info(f"[{vdi_group}] SSH Problem ({err})")

def validate_mac(x):
    if re.match("[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", x.lower()):
        return 1
    else:
        return 0



def create_vm(parameters,vdi_group):
    if validate_mac(parameters["masterMac"]):
        logger.debug(f"[{vdi_group}] Mac address seems valid")
    else:
        logger.debug(f"[{vdi_group}] Mac address is malformed")

    proxmox.nodes(
        parameters["masterNode"]).qemu.create(**parameters["newContainer"])
    logger.info(f"[{vdi_group}] Master-VM with {str(parameters['newContainer']['vmid'])} is being created")


def start_preparing_vm(masterNode, masterVmid,vdi_group):
    try:
        proxmox.nodes(masterNode).qemu(masterVmid).status.start.post()
        if preparing_vm_watchdog(proxmox, 100, masterNode, masterVmid):
            print(f"[{vdi_group}] VM {str(masterVmid)}" +
                  " started and getting prepared by LINBO")
        return True
    except Exception as err:
        logger.info(f"[{vdi_group}] Failed to start Master VM")
        logger.info(err)
        logger.info(f"[{vdi_group}] Failed Master is getting removed")
        delete_failed_master(masterVmid)


def preparing_vm_watchdog(proxmox, timeout, node, vmid):
    terminate = time.time() + timeout
    while time.time() < terminate:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        status = status['qmpstatus']
        if status == "running":
            print("*** VM is running ***")
            return True
        time.sleep(2)
        logger.info(status)
        logger.info(
            "*** running and waiting for VM to get prepared by LINBO and boot ... ***"
        )
    return False


def checkNmap(masterNode, timeout, masterVmid, masterIP, ports):
    check = preparing_vm_watchdog(proxmox, 15, masterNode, masterVmid)
    if check == True:
        startTime = time.time()
        logger.info("Starttime: " + str(startTime))
        terminate = startTime + timeout
        # terminate = startTime + timedelta(seconds=timeout)
        logger.info("Ende " + str(terminate))

        logger.info("*** Scanning for open ports on " + str(masterVmid) + "***")
        scanner = nmap.PortScanner()
        
        windows_ports = {"RPC": "135", "SMB": "445", "SVCHOST": "49665"}
        linux_ports = {"SSH": "22"}
        while time.time() < terminate:
            # checkedTime = time.time() - (terminate - time.time())
            checkedTime = int(time.time() - startTime)
            logger.info("*** Waiting for " + str(masterVmid) + " to be synced, waited: " + str(checkedTime) + "s of " +
                        str(timeout) + "s timeout frame ***")
            for port in windows_ports:
                try:
                    portscan = scanner.scan(masterIP, windows_ports[port])
                    status = portscan['scan'][masterIP]['tcp'][int(windows_ports[port])]['state']
                    logger.debug("Port " + port + " : " + status)
                    if status == "open":
                        logger.info("*** Windows boot check on " + str(masterVmid) + " succesfully, found open port ***")
                        return True
                except KeyError as err:
                    continue
                    #logger.info(err)                
            for port in linux_ports:
                try:   
                    portscan = scanner.scan(masterIP, linux_ports[port])
                    status = portscan['scan'][masterIP]['tcp'][int(linux_ports[port])]['state']
                    logger.debug("Port " + port + " : " + status)
                    if status == "open":
                        logger.info("*** Linux boot check on " + str(masterVmid) + " succesfully, found open port ***")
                        return True
                except KeyError as err:
                    continue
                    #logger.info("*** Master seems not ready yet, no open ports found ***")
                    #logger.info(err)
            logger.info("*** Master " + str(masterVmid) + " seems not ready yet, no open ports found ***")
            time.sleep(5)
    else:
        logger.info("*** VM State is powered off, not going to check ports***")
        return False


def delete_failed_master(masterVmid,vdi_group):
    try:
        status = proxmox.nodes(node).qemu(masterVmid).status.current.get()
        status = status['qmpstatus']
        if status == "running":
            proxmox.nodes(node).qemu(masterVmid).status.stop.post()
            logger.info(f"[{vdi_group}] Failed Master " + str(masterVmid) +
                        " is getting stopped.")
            if wait_for_status_stopped(proxmox, 20, node, masterVmid) == True:
                proxmox.nodes(node).qemu(masterVmid).delete()
                logger.info(f"[{vdi_group}] deleted VM: " + str(masterVmid))
                return
    except Exception as err:
        logger.info("*** May there is an Error for deleting Master " +
                    str(masterVmid) + " ***")
        logger.info(err)
        return


def prepare_template(masterNode, masterVmid, vdi_group):
    status = proxmox.nodes(masterNode).qemu(masterVmid).status.current.get()
    status = status['qmpstatus']
    if status == "running":
        proxmox.nodes(masterNode).qemu(masterVmid).status.shutdown.post()
    logger.info(f"[{vdi_group}] Preparing VM to Template... ***")
    if wait_for_status_stopped(proxmox, 50, masterNode, masterVmid) == True:
        logger.info(f"[{vdi_group}] Converting VM to Template***")
        proxmox.nodes(masterNode).qemu(masterVmid).template.post()


def wait_for_status_stopped(proxmox, timeout, node, vmid, vdi_group):
    terminate = time.time() + timeout
    while time.time() < terminate:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        status = status['qmpstatus']
        if status == "stopped":
            logger.info(f"[{vdi_group}] VM " + str(vmid) + " stopped.")
            return True
        else:
            logger.info(f"[{vdi_group}] waiting VM to going down...")
            time.sleep(5)
    logger.info(f"[{vdi_group}] ERROR: VM couldn't get going down.")
    return False


def create_master(group_data,vdi_group):
    logger.info(f"[{vdi_group}] Creating new Master...")

    school_id = vdi_common.get_school_id(vdi_group)
    devices = vdi_common.devices_loader(school_id)


    master_node = node
    master_vmid = get_available_vmid(master_node, group_data, vdi_group)
    if not master_vmid:
        logger.error(f"[{vdi_group}] Error, no Master VM available")
        return False
    
    masterNet0 = "bridge=" + group_data['bridge'] + ",virtio=" + group_data['mac']
    if 'tag' in group_data and group_data['tag'] != 0:
        masterNet0 += ",tag="+str(group_data['tag'])


    timeout = group_data['timeout_building_master']
    master_description = generate_master_description(vdi_group)

    master_device_info = get_master_device_info(devices, group_data['mac'])


    # and set linbo-bittorrent restart??
    send_linbo_remote_command(school_id,
                          master_device_info['ip'],vdi_group)  # and sets linbo-remote command
    parameters = {
        "masterNode": master_node,
        "masterMac": group_data['mac'],
        "newContainer": {
            'name': group_data['name'],
            'vmid': master_vmid,
            #'pool' : masterPool,
            'description': master_description,
            'bios': group_data['bios'],
            'boot': group_data['boot'],
            #'bootdisk': group_data['bootdisk'],
            'cores': group_data['cores'],
            'ostype': group_data['ostype'],
            'memory': group_data['memory'],
            'storage': group_data['storage'],
            'scsihw': group_data['scsihw'],
            'sata0': f"{group_data['storage']}:{str(group_data['size'])},format={group_data['format']}",
            #'scsi0': masterScsi0,
            'net0': masterNet0,
            'vga': group_data['display'],
            'audio0': group_data['audio'],
            'usb0': group_data['usb0'],
            'spice_enhancements': group_data['spice_enhancements']
        }
    }

    create_vm(parameters,vdi_group)
    start_preparing_vm(master_node, master_vmid,vdi_group)  # start to get prepared by LINBO

    # if checkNmap succesful => change buildingstate finished and convert to template
    if checkNmap(master_node, timeout, master_vmid, master_device_info['ip'],
                 nmapPorts) == True:  # check if windows bootet succesfully
        master_description['buildstate'] = "finished"
        #description = json.dumps(master_description)
        prepare_template(master_node,
                        master_vmid)  # convert VM to Template if stopped
        proxmox.nodes(master_node).qemu(master_vmid).config.post(
            description=master_description)
        logger.info(f"[{vdi_group}] Creating new Template for group terminated succesfully.")
    # if checkNmap failed => change buildingstate failed and getting removed
    else:
        master_description['buildstate'] = "failed"
        #description = json.dumps(master_description)
        proxmox.nodes(master_node).qemu(master_vmid).config.post(
            description=master_description)
        logger.info(f"[{vdi_group}] Creating new Template for group failed.")
        logger.info(f"[{vdi_group}] Failed Master is getting removed")
        delete_failed_master(master_vmid,vdi_group)


if __name__ == "__main__":
    create_master(sys.argv[1])
