#!/usr/bin/env python3
#
# createNewMaster.py
#
# joanna.meinelt@netzint.de
# 20200930
#

import sys
import json
import nmap
import re
import time
from datetime import datetime
from proxmoxer import ProxmoxAPI
import logging
import vdi_common
from globalValues import node,getSchoolId,multischool,proxmox,dbprint,nmapPorts,vdiLocalService,getMasterDetails,getFileContent,getCommandOutput,setCommand
if vdiLocalService == False:
    from globalValues import ssh

# returns dict with cloop infos
def getMasterDescription(vdiGroup):
    image_values = {}
    devicePath = "/srv/linbo/start.conf." + str(vdiGroup)
    startConf_data = vdi_common.start_conf_loader(devicePath)
    for os in startConf_data['os']:
        image_name = os['BaseImage']
    imageInfo = vdi_common.image_info_loader(image_name)
    
    #output = sftp.open(remotePath)

    logging.info("-----------------")
    logging.info(image_name)
    imageInfo = vdi_common.image_info_loader(image_name)
    
    
    image_values["timestamp"] = imageInfo["timestamp"]
    image_values["imagesize"] = imageInfo["imagesize"]


    timestamp = datetime.now()
    dateOfCreation = timestamp.strftime("%Y%m%d%H%M%S")  # => "20201102141556"
    image_values["dateOfCreation"] = dateOfCreation
    image_values["buildstate"] = "building"

    logging.info(image_values)
    return image_values
dbprint("-----------------")

# get alls VMIDs and checks returns first which doesnt exist on hv (no delete from oldest)
def findNewVmid(masterNode, masterVmids):
    vmids = masterVmids.split(',')
    dbprint(vmids)

    for vmid in vmids:
        try:
            if proxmox.nodes(masterNode).qemu(vmid).status.get() != "":
                dbprint("*** Existing: " + str(vmid))
        except Exception:
            dbprint("*** Found useable VMID for Master : " + str(vmid) + " ***")
            return vmid
    dbprint("*** No VMID available .. aborting. ***")
    return
#sys.exit()


def getDeviceConf(devicePath, masterMac):
    command = "cat " + devicePath
    devicesCsv = getCommandOutput(command)
    master = {}
    for line in devicesCsv:
        line = str(line)
        try:
            if line.split(';')[3] == masterMac:
                ip = line.split(';')[4]
                hostname = line.split(';')[1]
                master = {"ip": ip, "hostname": hostname}
        except Exception as err:
            dbprint(err)
    dbprint(master)
    return master


def checkConsistence(devicePath, masterHostname, masterIp, masterMAC):
    command = "cat " + devicePath
    devicesCsv = getCommandOutput(command)
    for line in devicesCsv:
        line = str(line)
        values = line.split(';')
        if values[1] == masterHostname:
            if (values[3] == masterMAC):
                if (values[4] == masterIp):
                    dbprint("*** Master Configuration is consistent to devices.csv ***")
                    return True
                else:
                    dbprint("*** PROBLEM: IP doesnt match with Configuration ***")
            else:
                dbprint("*** PROBLEM: MAC doesnt match with Configuration ***")
    else:
        dbprint("*** PROBLEM: Hostname doesnt exist ***")
        dbprint("*** Exiting. ****")
        return
    #sys.exit()


def setLinboRemoteCommand(schoolId, masterHostname):
    try:
        if multischool == True: # linbo-remote for one multischool school
            command2 = "linbo-remote -s " + str(schoolId) + " -i " + masterHostname + " -p partition,format,initcache:rsync,sync:1,start:1"
            setCommand(command2)
            print(command2)
            #dbprint("*** Linbo-Remote-Command is set... ***")
        else:  # just default-school
            command2 = "linbo-remote -i " + masterHostname + " -p partition,format,initcache:rsync,sync:1,start:1"
            #ssh.exec_command(command2)
            setCommand(command2)
            dbprint("*** Linbo-Remote-Command is set... ***")
    except Exception as err:
        dbprint("*** SSH Problem: ***")
        dbprint(err)


def checkMAC(x):
    if re.match("[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", x.lower()):
        return 1
    else:
        return 0


def createVM(masterName, masterMAC, masterNode, masterVmid, masterDesc, masterBios, masterBoot, masterBootDisk, masterCores,masterOsType, masterStorage, masterScsiHw, masterSata0, masterMemory, masterNet0, masterDisplay, masterAudio, masterUSB, masterSpice):
    if checkMAC(masterMAC):
        dbprint("*** MAC is ok. ***")
    else:
        dbprint("MAC not ok! Reenter.")

    description = json.dumps(masterDesc)

    newContainer = {
            'name': masterName,
            'vmid': masterVmid,
            #'pool' : masterPool,
            'description': description,
            'bios': masterBios,
            'boot': masterBoot,
            #'bootdisk': masterBootDisk,
            'cores': masterCores,
            'ostype': masterOsType,
            'memory': masterMemory,
            'storage': masterStorage,
            'scsihw': masterScsiHw,
            'sata0' : masterSata0,
            #'scsi0': masterScsi0,
            'net0': masterNet0,
            'vga': masterDisplay,
            'audio0': masterAudio,
            'usb0': masterUSB,
            'spice_enhancements': masterSpice
            }
    proxmox.nodes(masterNode).qemu.create(**newContainer)
    print("*** Master-VM with " + str(masterVmid) + " is being created... ***")


def startToPrepareVM(masterNode, masterVmid):
    try:
        proxmox.nodes(masterNode).qemu(masterVmid).status.start.post()
        if waitForStatusRunning(proxmox, 100, masterNode, masterVmid):
            print("*** VM " + str(masterVmid) + " started and getting prepared by LINBO ***")
        return True
    except Exception as err:
        dbprint("*** Failed to start Master VM ***")
        dbprint(err)
        dbprint("*** Failed Master is getting removed ***")
        deleteFailedMaster(masterVmid)


def waitForStatusRunning(proxmox, timeout, node, vmid):
    terminate = time.time() + timeout
    while time.time() < terminate:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        status = status['qmpstatus']
        if status == "running":
            print("*** VM is running ***")
            return True
        time.sleep(2)
        dbprint(status)
        dbprint("*** running and waiting for VM to get prepared by LINBO and boot ... ***")
    return False


def checkNmap(masterNode, timeout, masterVmid, masterIP, ports):
    check = waitForStatusRunning(proxmox, 15, masterNode, masterVmid)
    if check == True:
        startTime = time.time()
        dbprint("Starttime: " + str(startTime))
        terminate = startTime + timeout
        # terminate = startTime + timedelta(seconds=timeout)
        dbprint("Ende " + str(terminate))

        dbprint("*** Scanning for open ports on " + str(masterVmid) + " ***")
        scanner = nmap.PortScanner()
        while time.time() < terminate:
            #ports = {"RPC": 135,
            #        "SMB": 445,
            #        "SVCHOST": 49665
            #        }
            # checkedTime = time.time() - (terminate - time.time())
            checkedTime = int(time.time() - startTime)
            print("*** Checked: " + str(checkedTime) + " from " + str(timeout) + " seconds ***")
            for key in ports:
                try:
                    portscan = scanner.scan(masterIP, portStr)
                    status = portscan['scan'][masterIP]['tcp'][int(key)]['state']
                    dbprint("Port " + key + " : " + status)
                    print(status)
                    if status == "open":
                        dbprint("*** Windows Boot Check succesfully ***")
                        return True
                except Exception as err:
                    dbprint(err)
                    pass
            time.sleep(5)
        else:
            dbprint("*** Windows Boot Check not succesfully ***")
    else:
        dbprint("*** VM not running to check Ports ***")
        return False


def deleteFailedMaster(masterVmid):
    try:
        status = proxmox.nodes(node).qemu(masterVmid).status.current.get()
        status = status['qmpstatus']
        if status == "running":
            proxmox.nodes(node).qemu(masterVmid).status.stop.post()
            dbprint("*** Failed Master " + str(masterVmid) + " is getting stopped.***")
            if waitForStatusStoppped(proxmox, 20, node, masterVmid) == True:
                proxmox.nodes(node).qemu(masterVmid).delete()
                dbprint("deleted VM: " + str(masterVmid))
                return
            #sys.exit()
    except Exception as err:
        dbprint("*** May there is an Error for deleting Master " + str(masterVmid) + " ***")
        dbprint(err)
        return
    #sys.exit()


def prepareTemplate(masterNode, masterVmid):
    status = proxmox.nodes(masterNode).qemu(masterVmid).status.current.get()
    status = status['qmpstatus']
    if status == "running":
        proxmox.nodes(masterNode).qemu(masterVmid).status.shutdown.post()
    dbprint("*** Preparing VM to Template... ***")
    if waitForStatusStoppped(proxmox, 50, masterNode, masterVmid) == True:
        dbprint("*** Converting VM to Template and ... ***")
        proxmox.nodes(masterNode).qemu(masterVmid).template.post()


def waitForStatusStoppped(proxmox, timeout, node, vmid):
    terminate = time.time() + timeout
    while time.time() < terminate:
        status = proxmox.nodes(node).qemu(vmid).status.current.get()
        status = status['qmpstatus']
        if status == "stopped":
            dbprint("*** VM " + str(vmid) + " stopped. ***")
            return True
        else:
            dbprint("*** waiting VM to going down... ***")
            time.sleep(5)
    dbprint("*** ERROR: VM couldn't get going down. ***")
    return False


def main(vdiGroup):
    dbprint("*** Creating new Master begins for Group " + vdiGroup + " begins ***")

    vdiGroupInfos = getMasterDetails(vdiGroup)

    
    schoolId = getSchoolId(vdiGroup)
    devicePath = str
    if schoolId != "" or schoolId != "default-school":
        devicePath = "/etc/linuxmuster/sophomorix/" + str(schoolId) + "/" + str(schoolId) + ".devices.csv"
    else:
        devicePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"
    
    
    
    masterName = vdiGroupInfos['name']
    masterNode = node
    masterVmids = vdiGroupInfos['vmids']
    masterVmid = findNewVmid(masterNode, masterVmids)
    #masterPool = pool
    masterBios = vdiGroupInfos['bios']
    masterBoot = vdiGroupInfos['boot']
    masterBootDisk = vdiGroupInfos['bootdisk']
    masterCores = vdiGroupInfos['cores']
    masterOsType = vdiGroupInfos['ostype']
    masterStorage = vdiGroupInfos['storage']
    masterScsiHw = vdiGroupInfos['scsihw']
    #masterPool = vdiGroupInfos['pool']
    masterSize = vdiGroupInfos['size']
    masterFormat = vdiGroupInfos['format']
    masterSata0 = masterStorage + ":" + str(masterSize) + ",format=" + masterFormat
    #masterScsi0 = masterStorage + ":" + str(masterSize) + ",format=" + masterFormat
    #print(type(masterScsi0))
    masterMemory = vdiGroupInfos['memory']
    masterBridge = vdiGroupInfos['bridge']
    masterMac = vdiGroupInfos['mac']
    if "tag" in vdiGroupInfos:
        masterTag = vdiGroupInfos['tag']
        if masterTag != 0:
            masterNet0 = "bridge=" + masterBridge + ",virtio=" + masterMac + ",tag=" + str(masterTag)
        else:
            masterNet0 = "bridge=" + masterBridge + ",virtio=" + masterMac
    else:
        masterNet0 = "bridge=" + masterBridge + ",virtio=" + masterMac
    masterDisplay = vdiGroupInfos['display']
    masterAudio = vdiGroupInfos['audio']
    masterUSB = vdiGroupInfos['usb0']
    masterSpice = vdiGroupInfos['spice_enhancements']
    timeout = vdiGroupInfos['timeout_building_master']
    masterDescription = getMasterDescription(vdiGroup)

    masterDeviceInfos = getDeviceConf(devicePath, masterMac)
    masterIp = masterDeviceInfos['ip']
    masterHostname = masterDeviceInfos['hostname']

    checkConsistence(devicePath, masterHostname, masterIp, masterMac)
    # and set linbo-bittorrent restart??
    setLinboRemoteCommand(schoolId ,masterHostname)  # and sets linbo-remote command
    createVM(masterName, masterMac, masterNode, masterVmid, masterDescription, masterBios, masterBoot, masterBootDisk, masterCores, masterOsType, masterStorage, masterScsiHw, masterSata0, masterMemory, masterNet0, masterDisplay, masterAudio, masterUSB, masterSpice)
    startToPrepareVM(masterNode, masterVmid)  # start to get prepared by LINBO

    # if checkNmap succesful => change buildingstate finished and convert to template
    ports = nmapPorts
    if checkNmap(masterNode, timeout, masterVmid, masterIp, ports) == True:  # check if windows bootet succesfully
        masterDescription['buildstate'] = "finished"
        description = json.dumps(masterDescription)
        prepareTemplate(masterNode, masterVmid)  # convert VM to Template if stopped
        proxmox.nodes(masterNode).qemu(masterVmid).config.post(description=description)
        dbprint("*** Creating new Template for group " + vdiGroup + " terminated succesfully. ****")
    # if checkNmap failed => change buildingstate failed and getting removed
    else:
        masterDescription['buildstate'] = "failed"
        description = json.dumps(masterDescription)
        proxmox.nodes(masterNode).qemu(masterVmid).config.post(description=description)
        dbprint("*** Creating new Template for group " + vdiGroup + " failed. ****")
        dbprint("*** Failed Master is getting removed ***")
        deleteFailedMaster(masterVmid)


if __name__ == "__main__":
    main(sys.argv[1])

