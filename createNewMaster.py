#!/usr/bin/env python3
#
# createNewMaster.py
#
# joanna@linuxmuster.net
# 20200930
#

import sys
import json
import nmap
import re
import time
from datetime import datetime
from proxmoxer import ProxmoxAPI
from globalValues import node,proxmox,dbprint,vdiLocalService,getMasterDetails,getFileContent,getCommandOutput,setCommand
if vdiLocalService == False:
    from globalValues import ssh

# returns dict with cloop infos
def getMasterDescription(vdiGroup):
    cloopValues = {}
    remotePath = "/srv/linbo/start.conf." + str(vdiGroup)
    #output = sftp.open(remotePath)
    output = getFileContent(remotePath)
    cloopline = []
    for line in output:
        if "BaseImage" in line:
            cloopline = line.split(' ')
    cloop = cloopline[2].strip()
    cloopValues["cloop"] = cloop
    dbprint("-----------------")
    dbprint(cloop)

    remotePathCloop = ("/srv/linbo/" + str(cloop) + ".info")
    dbprint(remotePathCloop)
    output2 = getFileContent(remotePathCloop)
    lines = output2.readlines()
    for line in lines:
        linex = line.split("=")
        if "timestamp" in line:
            cloopValues["timestamp"] = linex[1].rstrip("\n")
        if "imagesize" in line:
            cloopValues["imagesize"] = linex[1].rstrip("\n")

    timestamp = datetime.now()
    dateOfCreation = timestamp.strftime("%Y%m%d%H%M%S")  # => "20201102141556"
    cloopValues["dateOfCreation"] = dateOfCreation
    cloopValues["buildstate"] = "building"

    dbprint(cloopValues)
    return cloopValues


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


def checkConsistence(masterHostname, masterIp, masterMAC):
    command = "cat /etc/linuxmuster/sophomorix/default-school/devices.csv"
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


def setLinboRemoteCommand(masterHostname):
    try:
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


def createVM(masterName, masterMAC, masterNode, masterVmid, masterDesc, masterBios, masterBoot, masterCores,
             masterOsType, masterStorage, masterScsiHw, masterScsi0, masterMemory, masterNet0, masterDisplay,
             masterAudio, masterUSB, masterSpice):
    if checkMAC(masterMAC):
        dbprint("*** MAC is ok. ***")
    else:
        dbprint("MAC not ok! Reenter.")

    description = json.dumps(masterDesc)

    newContainer = {
        'name': masterName,
        'vmid': masterVmid,
        'description': description,
        'bios': masterBios,
        'boot': masterBoot,
        'cores': masterCores,
        'ostype': masterOsType,
        'memory': masterMemory,
        'storage': masterStorage,
        'scsihw': masterScsiHw,
        'scsi0': masterScsi0,
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


def checkNmap(masterNode, timeout, masterVmid, masterIP):
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
            ports = {"RPC": 135,
                     "SMB": 445,
                     "SVCHOST": 49665
                     }
            # checkedTime = time.time() - (terminate - time.time())
            checkedTime = int(time.time() - startTime)
            print("*** Checked: " + str(checkedTime) + " from " + str(timeout) + " seconds ***")
            for key in ports:
                portStr = str(ports[key])
                try:
                    portscan = scanner.scan(masterIP, portStr)
                    status = portscan['scan'][masterIP]['tcp'][ports[key]]['state']
                    dbprint("Port " + key + " : " + status)
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
                dbprint("deleted VM: " + str(vmid))
                return
                #sys.exit()
    except Exception as err:
        dbprint("*** Failed Master " + str(masterVmid) + " couldnt get removed ***")
        dbprint(err)
        return
        #sys.exit()


def prepareTemplate(masterNode, masterVmid):
    status = proxmox.nodes(masterNode).qemu(masterVmid).status.current.get()
    status = status['qmpstatus']
    if status == "running":
        proxmox.nodes(masterNode).qemu(masterVmid).status.shutdown.post()
    dbprint("*** Preparing VM to Template... ***")
    if waitForStatusStoppped(proxmox, 40, masterNode, masterVmid) == True:
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
    masterInfos = getMasterDetails(vdiGroup)
    masterName = masterInfos['name']
    masterHostname = masterInfos['hostname']
    masterIp = masterInfos['ip']
    masterNode = node
    masterVmids = masterInfos['vmids']
    masterVmid = findNewVmid(masterNode, masterVmids)
    masterBios = masterInfos['bios']
    masterBoot = masterInfos['boot']
    masterCores = masterInfos['cores']
    masterOsType = masterInfos['ostype']
    masterStorage = masterInfos['storage']
    masterScsiHw = masterInfos['scsihw']
    masterScsi0 = masterInfos['scsi0']
    masterMemory = masterInfos['memory']
    masterBridge = masterInfos['bridge']
    masterMac = masterInfos['macaddress']
    masterTag = masterInfos['tag']
    masterNet0 = "bridge=" + masterBridge + ",virtio=" + masterMac + ",tag=" + masterTag
    masterDisplay = masterInfos['display']
    masterAudio = masterInfos['audio']
    masterUSB = masterInfos['usb0']
    masterSpice = masterInfos['spice_enhancements']
    timeout = masterInfos['timeout_building_master']
    masterDescription = getMasterDescription(vdiGroup)

    # addToLinbo(masterRoom, masterHostname, masterGroup, masterMac, masterIp) # add to LINBO if not already exists
    checkConsistence(masterHostname, masterIp, masterMac)
    # and set linbo-bittorrent restart??
    setLinboRemoteCommand(masterHostname)  # and sets linbo-remote command
    createVM(masterName, masterMac, masterNode, masterVmid, masterDescription, masterBios, masterBoot, masterCores,
             masterOsType, masterStorage, masterScsiHw, masterScsi0, masterMemory, masterNet0, masterDisplay,
             masterAudio, masterUSB, masterSpice)
    startToPrepareVM(masterNode, masterVmid)  # start to get prepared by LINBO

    # if checkNmap succesful => change buildingstate finished and convert to template
    if checkNmap(masterNode, timeout, masterVmid, masterIp) == True:  # check if windows bootet succesfully
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
