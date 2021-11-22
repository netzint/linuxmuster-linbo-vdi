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
import os
from proxmoxer import ProxmoxAPI
from globalValues import node,dbprint,getSchoolId,multischool,nmapPorts,vdiLocalService,proxmox,getMasterDetails,getCommandOutput,getFileContent
if vdiLocalService == False:
    from globalValues import ssh

dbprint("*** Begin Cloning Master *** ")

# calculates latest master and returns VMID
def findLatestMaster(masterNode, masterVmids):
    timestampLatest = 0
    vmidLatest = 0
    vmids = masterVmids.split(',')
    dbprint("*** all master vmids: ***")
    dbprint(vmids)

    for vmid in vmids:
        try:
            infos = proxmox.nodes(masterNode).qemu(vmid).config.get()
            description = infos['description']
            descriptionJSON = json.loads(description)
            if descriptionJSON['buildstate'] == "finished":
                timestamp = descriptionJSON['dateOfCreation']
                if float(timestamp) >= float(timestampLatest):
                    timestampLatest = timestamp
                    vmidLatest = vmid
        except Exception:
            pass
    dbprint("*** Latest timestamp: ***")
    dbprint("*** " + str(timestampLatest) + " ***")
    dbprint("*** from Master " + str(vmidLatest)+ " ***")

    return vmidLatest


# calculates range of vmids and returns them
def getVmidRange(devicePath,masterGroup):
    output = getFileContent(devicePath)
    vmidRange = []
    for line in output:
        if masterGroup in line:
            if "master" not in line.split(';')[1]:
                vmid = line.split(';')[11]
                vmidRange.append(vmid)
    return vmidRange


# searches next available VMID fpr Clone and exits if doesnt exists
def findNextAvailableVmid(devicePath,masterGroup):
    idRange = getVmidRange(devicePath,masterGroup)
    print(idRange)
    
    for id in idRange:
    
        if id != '':
            try:
                proxmox.nodes(node).qemu(id).status.get()
                print(id)
            except:
                dbprint("*** Next free VM ID: " + str(id))
                return id
    dbprint("*** No VM ID left .. create on server! ***")
    return
    #sys.exit()


# defines description for clone
def generateCloneDescription(vdiGroup, masterVmid, cloneName):
    description = {}
    timestamp = datetime.now()
    dateOfCreation = timestamp.strftime("%Y%m%d%H%M%S")         # => "20201102141556"
    dbprint("*** Timestamp new Clone: ***")
    dbprint("*** " + str(dateOfCreation) + " ***")

    description['name'] = cloneName
    description["dateOfCreation"] = dateOfCreation
    description['master'] = masterVmid
    description['lastConnectionRequestUser'] = ""
    description['lastConnectionRequestTime'] = ""
    #description['user'] = ""

    remotePath = "/srv/linbo/start.conf." + str(vdiGroup)
    output = getFileContent(remotePath)
    cloopline = []
    for line in output:
        if "BaseImage" in line:
            cloopline = line.split(' ')
    cloop = cloopline[2].strip()

    description["cloop"] = cloop

    description["buildstate"] = "building"
    return description


def cloneMaster(masterNode, masterVmid, cloneVmid, cloneName, cloneDescription):
    description = json.dumps(cloneDescription)    ### important! sonst liest nur die Haelfte
    dbprint("*** Clone-VM-Name: " + cloneName + " ***")
    proxmox.nodes(masterNode).qemu(masterVmid).clone.post(newid=cloneVmid,name=cloneName,description=description)
    print("*** Template is getting cloned to VM with next free VM-ID: " + str(cloneVmid) + " ***")


####### starts clone and checks 10 Seconds if succesfully running
def startClone(cloneNode, cloneVmid):
    proxmox.nodes(cloneNode).qemu(cloneVmid).status.start.post()
    dbprint("*** VM started ***")
    try:
        if waitForStatusRunning(10,cloneNode, cloneVmid) == True:
            dbprint("*** VM is running ***")
    except Exception:
        dbprint("*** VM couldn't get started, script is terminating.***")
        return


####### returns dict[] desctops{ vmid {ip : ip, mac : mac}}
def getDeviceConf(devicePath,masterGroup):
    #command = "cat /etc/linuxmuster/sophomorix/default-school/devices.csv"
    command  = "cat " + str(devicePath)
    devicesCsv = getCommandOutput(command)
    desctops = {}
    for line in devicesCsv:
        line = str(line)
        ip = line.split(';')[4]
        vmid = line.split(';')[11]
        mac = line.split(';')[3]
        if line.split(';')[2] == masterGroup:
            desctops[vmid] = {}
            desctops[vmid] = {"ip": ip, "mac": mac}
    dbprint(desctops)
    return desctops


# checks if windows bootet succesfully and waits multischool time
def checkNmap(timeout, cloneVmid, cloneIp, ports):
    terminate = time.time() + timeout
    scanner = nmap.PortScanner()
    dbprint("*** Scanning for open ports on " + cloneVmid + " ***")
    while time.time() < terminate:
        for port in ports:
            #print(port)
            status = scanner.scan(cloneIp, str(port))
            try:
                status = status['scan'][cloneIp]['tcp'][str(port)]['state']
                dbprint("*** - Port " + str(port) + " :" + status + " ***")
                #print(status)
                if status == "open":
                    dbprint("*** Found open port! ***")
                    return True
            except Exception as err:
                if err == str(cloneIp):
                    return True
                else:
                    print(" NMAP Error: ")
                    print(err)
                    dbprint("*** Waiting for ping to " + cloneIp + " ***")
    return False


def waitForStatusRunning(timeout, cloneNode, cloneVmid):
    terminate = time.time() + timeout
    while time.time() < terminate:
        status = proxmox.nodes(cloneNode).qemu(cloneVmid).status.current.get()
        status = status['qmpstatus']
        if status == "running":
            return True
        time.sleep(2)
        dbprint("*** Status: " + str(status) + " ***")
        dbprint("*** waiting VM to run ... ***")
    return False


def main(vdiGroup):

# get basic information:
    vdiGroupInfos = getMasterDetails(vdiGroup)
    masterNode = node
    masterName = vdiGroupInfos['name']
    masterVmids = vdiGroupInfos['vmids']
    masterVmid = findLatestMaster(masterNode, masterVmids)
    masterGroup = vdiGroup
    masterBridge = vdiGroupInfos['bridge']
    #masterPool = pool

# get school environment and calculate devices path     
    schoolId = getSchoolId(vdiGroup)
    devicePath = str
    if schoolId != "" or schoolId != "default-school":
        devicePath = "/etc/linuxmuster/sophomorix/" + str(schoolId) + "/" + str(schoolId) + ".devices.csv"
    else:
        devicePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"
    
# fuer proxmox:
    cloneNode = masterNode
    cloneVmid = findNextAvailableVmid(devicePath,masterGroup)
    cloneNamePrefix = masterName.replace("master", "")
    cloneName = cloneNamePrefix + "clone-" + str(cloneVmid)
    cloneDescription = generateCloneDescription(vdiGroup, masterVmid, cloneName)

# Cloning:
    cloneMaster(masterNode, masterVmid, cloneVmid, cloneName, cloneDescription)

# change correct MAC address:  ### change MAC  address as registered !!!! get net0 from master and only change mac  # net0 = bridge=vmbr0,virtio=62:0C:5A:A0:77:FF,tag=29
    cloneConf = getDeviceConf(devicePath, masterGroup)
    cloneMac = cloneConf[cloneVmid]['mac']
    if "tag" in vdiGroupInfos:
        masterTag = vdiGroupInfos['tag']
        if masterTag != 0:
            cloneNet = "bridge=" + masterBridge + ",virtio=" + cloneMac + ",tag=" + str(masterTag)
        else:
            cloneNet = "bridge=" + masterBridge + ",virtio=" + cloneMac
    else:
        cloneNet = "bridge=" + masterBridge + ",virtio=" + cloneMac
    dbprint("*** Assigning MAC " + str(cloneMac) + " ***")
    proxmox.nodes(cloneNode).qemu(cloneVmid).config.post(net0=cloneNet)

# Lock removing - not tested:
# try:
    #     proxmox.nodes(cloneNode).qemu(cloneVmid).config.post()
    #     # proxmox.nodes(cloneNode).qemu(cloneVmid).config.post(delete=lock)
    #     print ("Removed Lock ")
    # except Exception as err:
    #     print(err)
    #     pass

# startClone:
    startClone(cloneNode, cloneVmid)
    cloneIp = cloneConf[cloneVmid]['ip']
    timeoutBuilding = vdiGroupInfos['timeout_building_clone']
# if checkNmap succesful => change buildingstate finished
    if checkNmap(timeoutBuilding, cloneVmid, cloneIp, ports=nmapPorts) == True:
        cloneDescription['buildstate'] = "finished"
        description = json.dumps(cloneDescription)
        proxmox.nodes(cloneNode).qemu(cloneVmid).config.post(description=description)
        dbprint("*** Creating new Clone for group " + vdiGroup + " terminated succesfully. ****")
# if checkNmap failed => change buildingstate failed
    else:
        cloneDescription['buildstate'] = "failed"
        description = json.dumps(cloneDescription)
        proxmox.nodes(cloneNode).qemu(cloneVmid).config.post(description=description)
        dbprint("*** Creating new Clone for group " + vdiGroup + " failed. Deleting ... ****")


if __name__ == "__main__":
    main(sys.argv[1])

