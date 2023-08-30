#!/usr/bin/env python3
#
# createNewMaster.py
#
# joanna.meinelt@netzint.de
# 20200930
#

import nmap
import re
import time
from datetime import datetime
import json
# from proxmoxer import ProxmoxAPI
import logging
import vdi_common
from globalValues import proxmox_node, multischool, proxmox, nmapPorts, vdiLocalService
# from globalValues import getMasterDetailsgetFileContent, getSchoolId
if vdiLocalService == False:
    from globalValues import ssh
from vdi_master import VDIMaster


logger = logging.getLogger(__name__)


# returns dict with image infos
def generate_master_description(vdi_group) -> dict:
    image_values = {}
    devicePath = "/srv/linbo/start.conf." + str(vdi_group.name)
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
    image_values["group"] = vdi_group.data['group']

    logging.debug(f"[{vdi_group.name}] {image_values}")
    return image_values


# get alls VMIDs and checks returns first which doesnt exist on hv (no delete from oldest)
def get_available_vmid(masterNode, devices, vdi_group) -> int:

    for vmid in vdi_group.data['vmids']:
        try:
            if proxmox.nodes(masterNode).qemu(vmid).status.get() != "":
                logger.info(f"[{vdi_group}]Existing: {str(vmid)}")
        except Exception:
            logger.info(
                f"[{vdi_group.name}] Available VMID found for Master: {str(vmid)}")
            if check_configured_group_for_vmid(vmid, devices, vdi_group):
                return vmid
            else:
                logger.warning(f"[{vdi_group.name}] Warning, host {vmid} is not configured for group {vdi_group.name}")
    logger.info(f"[{vdi_group.name}] No VMID available .. aborting")
    return False


def get_master_device_info(devices, master_mac) -> dict:
    for device in devices:
        if device[3] == master_mac:
            return {'hostname': device[1], 'mac': device[3], 'ip': device[4]}
    return None


def send_linbo_remote_command(school_id, master_ip, vdi_group):
    try:
        command = "linbo-remote"
        if school_id != 'default-school':
            command += f" -s {school_id}"
        command += f" -i {master_ip} -p partition,format,initcache:rsync,sync:1,start:1"
        logging.info(f"[{vdi_group.name}] Send linbo remote command to {master_ip}")
        print(command)
        vdi_common.run_command(command)
    except Exception as err:
        logger.info(f"[{vdi_group.name}] SSH Problem ({err})")


def validate_mac(x):
    if re.match("[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", x.lower()):
        return 1
    else:
        return 0

def check_vm_parameters(parameters):
    storage_repos = proxmox.nodes(parameters["masterNode"]).storage.get()
    storage_repo_names = []
    for storage in storage_repos:
        storage_repo_names.append(storage['storage'])

    if parameters['vm_configuration']['storage'] not in storage_repo_names:
        raise ValueError(f"Configured storage {parameters['vm_configuration']['storage']} is not available on {parameters['masterNode']}")
    return True

def create_vm(parameters, vdi_group):
    if validate_mac(parameters["masterMac"]):
        logger.debug(f"[{vdi_group}] Mac address seems valid")
    else:
        logger.debug(f"[{vdi_group}] Mac address is malformed")

    # check vm parameters before creating
    if check_vm_parameters(parameters):
        vm_config = proxmox.nodes(parameters["masterNode"]).qemu(7101).config.get()
        for c in vm_config:
            print (f"{c}: {vm_config[c]}")
        for c in parameters["vm_configuration"]:
            print (f'{c}: {str(parameters["vm_configuration"][c])}')
        proxmox.nodes(parameters["masterNode"]).qemu.create(**parameters["vm_configuration"])
        
        logger.info(f"[{vdi_group.name}] Master-VM with {str(parameters['vm_configuration']['vmid'])} is being created")
        return


def start_preparing_vm(masterNode, masterVmid, vdi_group):
    try:
        proxmox.nodes(masterNode).qemu(masterVmid).status.start.post()
        if preparing_vm_watchdog(proxmox, 100, masterNode, masterVmid, vdi_group):
            print(f"[{vdi_group.name}] VM {str(masterVmid)}" +
                  " started and getting prepared by LINBO")
        return True
    except Exception as err:
        logger.info(f"[{vdi_group.name}] Failed to start Master VM")
        logger.info(err)
        logger.info(f"[{vdi_group.name}] Failed Master is getting removed")
        delete_failed_master(masterVmid)


def preparing_vm_watchdog(proxmox, timeout, node, vmid, vdi_group):
    terminate = time.time() + timeout
    while time.time() < terminate:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        status = status['qmpstatus']
        if status == "running":
            logger.debug(f"[{vdi_group.name}] VM {vmid} is running")
            return True
        time.sleep(2)
        logger.info(status)
        logger.info(f"[{vdi_group.name}] running and waiting for VM to get prepared by LINBO and boot ..."
        )
    return False


def checkNmap(masterNode, timeout, masterVmid, masterIP, ports, vdi_group):
    check = preparing_vm_watchdog(proxmox, 15, masterNode, masterVmid, vdi_group)
    if check == True:
        startTime = time.time()
        logger.info("Starttime: " + str(startTime))
        terminate = startTime + timeout
        # terminate = startTime + timedelta(seconds=timeout)
        logger.info("Ende " + str(terminate))

        logger.debug(f"[{vdi_group.name}] Scanning for open ports on {str(masterVmid)}")
        scanner = nmap.PortScanner()

        windows_ports = {"RPC": "135", "SMB": "445", "SVCHOST": "49665"}
        linux_ports = {"SSH": "22"}
    
        while time.time() < terminate:
            # checkedTime = time.time() - (terminate - time.time())
            checkedTime = int(time.time() - startTime)
            logger.info(f"[{vdi_group.name}] Waiting for {str(masterVmid)} to be synced, waited: {str(checkedTime)}s of " +
                        f"{str(timeout)}s timeout frame")
            for port in windows_ports:
                try:
                    portscan = scanner.scan(masterIP, windows_ports[port])
                    status = portscan['scan'][masterIP]['tcp'][int(
                        windows_ports[port])]['state']
                    logger.debug("Port " + port + " : " + status)
                    if status == "open":
                        logger.info(f"[{vdi_group.name}] Windows boot check on " +
                                    f"{str(masterVmid)} succesfully, found open port")
                        return True
                except KeyError as err:
                    continue
                    # logger.info(err)
            for port in linux_ports:
                try:
                    portscan = scanner.scan(masterIP, linux_ports[port])
                    status = portscan['scan'][masterIP]['tcp'][int(
                        linux_ports[port])]['state']
                    logger.debug("Port " + port + " : " + status)
                    if status == "open":
                        logger.info(f"[{vdi_group.name}] Linux boot check on " +
                                    f"{str(masterVmid)} succesfully, found open port")
                        return True
                except KeyError as err:
                    continue
                    # logger.info("*** Master seems not ready yet, no open ports found ***")
                    # logger.info(err)
            logger.info(f"[{vdi_group.name}] Master " + str(masterVmid) +
                        " seems not ready yet, no open ports found")
            time.sleep(5)
    else:
        logger.info(f"[{vdi_group.name}] {str(masterVmid)} VM State is powered off, not going to check ports")
        return False


def delete_failed_master(masterVmid, vdi_group):
    try:
        status = proxmox.nodes(proxmox_node).qemu(masterVmid).status.current.get()
        status = status['qmpstatus']
        if status == "running":
            proxmox.nodes(proxmox_node).qemu(masterVmid).status.stop.post()
            logger.info(f"[{vdi_group}] Failed Master " + str(masterVmid) +
                        " is getting stopped.")
            if wait_for_status_stopped(proxmox, 20, proxmox_node, masterVmid) == True:
                proxmox.nodes(proxmox_node).qemu(masterVmid).delete()
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
    if wait_for_status_stopped(proxmox, 50, masterNode, masterVmid, vdi_group) == True:
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
            logger.info(f"[{vdi_group}] Wait vor VM {vmid} to shutdown")
            time.sleep(5)
    logger.error(f"[{vdi_group}] ERROR: Could not shutdown VM {vmid} ")
    return False

def check_configured_group_for_vmid(master_vmid, devices, vdi_group):
    '''Checks if the configured group in devices is also configured in vdi config'''
    # TODO: This does not make sure linuxmuster-import-devices has been run

    # get sure configured group in devices is also configured in vdi config
    for device in devices:
        if device[11] == master_vmid:
            if device[2] == vdi_group.name:      
                return True
            else:
                return False

def create_master(vdi_group) -> bool: 
    logger.info(f"[{vdi_group.name}] Creating new Master...")
    school_id = vdi_common.get_school_id(vdi_group.name)
    devices = vdi_common.devices_loader(school_id)

    master_vmid = get_available_vmid(proxmox_node, devices, vdi_group)
    if not master_vmid:
        logger.error(f"[{vdi_group.name}] Error, no Master VM available")
        return False
    



    masterNet0 = "bridge=" + \
        vdi_group.data['bridge'] + ",virtio=" + vdi_group.data['mac']
    if 'tag' in vdi_group.data and vdi_group.data['tag'] != 0:
        masterNet0 += ",tag="+str(vdi_group.data['tag'])

    timeout = vdi_group.data['timeout_building_master']
    master_description = generate_master_description(vdi_group)

    master_device_info = get_master_device_info(devices, vdi_group.data['mac'])
    # TODO Fix this to work with uefi
    # TODO improve whole config process
    parameters = {
        "masterNode": proxmox_node,
        "masterMac": vdi_group.data['mac'],
        "vm_configuration": {
            'name': vdi_group.data['name'],
            'vmid': master_vmid,
            # 'pool' : masterPool,
            'description': json.dumps(master_description),
            'bios': vdi_group.data['bios'],
            #'boot': group_data['boot'],
            # 'bootdisk': group_data['bootdisk'],
            'cores': vdi_group.data['cores'],
            'ostype': vdi_group.data['ostype'],
            'memory': vdi_group.data['memory'],
            'storage': vdi_group.data['storage'],
            #'scsihw': group_data['scsihw'],
            'sata0': f"{vdi_group.data['storage']}:{str(vdi_group.data['size'])},format={vdi_group.data['format']}",
            # 'scsi0': masterScsi0,
            'net0': masterNet0,
            'vga': vdi_group.data['display'],
            'audio0': vdi_group.data['audio'],
            'usb0': vdi_group.data['usb0'],
            'spice_enhancements': vdi_group.data['spice_enhancements']
        }
    }

    try:
        create_vm(parameters, vdi_group)
    except Exception as err:
        logger.error(f"[{vdi_group}] Could not create vm, {err}")
        return False

    # and set linbo-bittorrent restart??
    send_linbo_remote_command(school_id,
                              master_device_info['ip'], vdi_group)  # and sets linbo-remote command
    # start to get prepared by LINBO
    start_preparing_vm(proxmox_node, master_vmid, vdi_group)

    # if checkNmap succesful => change buildingstate finished and convert to template
    if checkNmap(proxmox_node, timeout, master_vmid, master_device_info['ip'],
                 nmapPorts, vdi_group) == True:  # check if windows bootet succesfully
        master_description['buildstate'] = "finished"
        # description = json.dumps(master_description)
        # convert VM to Template if stopped
        prepare_template(proxmox_node, master_vmid, vdi_group)
        proxmox.nodes(proxmox_node).qemu(master_vmid).config.post(
            description=json.dumps(master_description))
        logger.info(
            f"[{vdi_group}] Creating new Template for group terminated succesfully.")
    # if checkNmap failed => change buildingstate failed and getting removed
    else:
        master_description['buildstate'] = "failed"
        # description = json.dumps(master_description)
        proxmox.nodes(proxmox_node).qemu(master_vmid).config.post(
            description=json.dumps(master_description))
        logger.info(f"[{vdi_group}] Creating new Template for group failed.")
        logger.info(f"[{vdi_group}] Failed Master is getting removed")
        delete_failed_master(master_vmid, vdi_group)
    return True
    


if __name__ == "__main__":
    # create_master(sys.argv[1])
    quit()
