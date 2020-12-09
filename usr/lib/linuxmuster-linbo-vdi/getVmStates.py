#!/usr/bin/env python3
#
# getVmStates.py
#
# joanna@linuxmuster.net
# 20200930


import json
from ipaddress import IPv4Network
import time
import sys
from datetime import datetime
from globalValues import node,proxmox,checkConnections,timeoutConnectionRequest,getMasterDetails,getFileContent,getCommandOutput,getVDIGroups
import re
from common import dbprint


######## tries to get information from existing VMs (Clones):  ########
def getApiInfos(node, cloneVmid):

    apiInfos = proxmox.nodes(node).qemu(cloneVmid).config.get()   # => type = dict
    status = proxmox.nodes(node).qemu(cloneVmid).status.current.get()
    status = status['qmpstatus']
    apiInfos["status"] = status

    uptime = proxmox.nodes(node).qemu(cloneVmid).status.current.get()
    uptime = uptime['uptime']
    apiInfos["uptime"] = uptime

    apiInfos['spicestatus'] = ""
    description = apiInfos['description']
##### split and separate description from descriptionf field from vm ######
    # descriptionJSON = {}
    try:
        descriptionJSON = json.loads(description)
        try:
            apiInfos['dateOfCreation'] = descriptionJSON["dateOfCreation"]
            apiInfos['cloop'] = descriptionJSON["cloop"]
            apiInfos['buildstate'] = descriptionJSON["buildstate"]
            apiInfos['lastConnectionRequestUser'] = descriptionJSON['lastConnectionRequestUser']
            apiInfos['lastConnectionRequestTime'] = descriptionJSON['lastConnectionRequestTime']
            apiInfos.pop("description")
            return apiInfos
        except Exception:
            dbprint("***** Failed to assign description values. *****")   # so tif error its shown immediately
    except Exception as err:
        # print("Failed to load JSON or api access failed:")
        # print(err)
        pass


###### get api infos to master ######
def getApiInfosMaster(node,vmid):

    apiInfos = proxmox.nodes(node).qemu(vmid).config.get()     # => type = dict
    description = apiInfos['description']

    status = proxmox.nodes(node).qemu(vmid).status.current.get()
    status = status['qmpstatus']
    apiInfos["status"] = status

    ##### split and separate description from descriptionf field from vm ######
    try:
        descriptionJSON = json.loads(description)
        try:
            apiInfos['dateOfCreation'] = descriptionJSON['dateOfCreation']
            apiInfos['cloop'] = descriptionJSON['cloop']
            apiInfos['timestamp'] = descriptionJSON['timestamp']
            apiInfos['buildstate'] = descriptionJSON['buildstate']
            apiInfos["imagesize"] = descriptionJSON['imagesize']
            apiInfos.pop("description")
            return apiInfos
        except Exception as err:
            dbprint(err)
            dbprint("***** Failed to assign description values. *****")   # so tif error its shown immediately
            pass
    except Exception as err:
        # print("Failed to load JSON or api access failed:")
        print(err)
        pass


######## if logedinuser has ip of vm, than user is set to vmid from vm ########
def addUser(vmid, logedIn):

    for user in logedIn:
        if logedIn[user]["ip"] == allallInfos[vmid]["ip"]:
            dbprint(user)
            allallInfos[vmid]["user"] = user
            dbprint(allallInfos[vmid]["user"])
        else:
             allallInfos[vmid]["user"] = ""


######## merges all vm infos to one JSON and returns it with vmid ########
def mergeInfos(vmid, apiInfos, groupInfos):
    jsonObject = {}
    # if apiInfos != {}:
    #     if apiInfos['net0'][7:24] != groupInfos['mac']:
    #         print("*** MAC Adresse von " + vmid + " stimmt nicht mit Liste ueberein! ***")
    apiInfos.update(groupInfos)
    jsonObject[vmid] = apiInfos
    return jsonObject 


####### get Collection of all VMs who are registered at school server #######
def getVmidRange(vdiGroup):
    #sftp = ssh.open_sftp()
    remotePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"
    output = getFileContent(remotePath)
    #output = sftp.open(remotePath)
    #print("*** Check VM-ID-Range from Group ***")
    vmidRange = []
    for line in output:
        if vdiGroup in line:
            if "master" not in line:
                vmid = line.split(';')[11]
                vmidRange.append(vmid)
    return vmidRange


######## returns dict devicesInfos from devices list  ########
def getGroupInfos(vmid):
    #sftp = ssh.open_sftp()
    remotePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"
    output = getFileContent(remotePath)
    # output = sftp.open(remotePath)
    devicesInfos = {}
    for line in output:
        if line.split(';')[11] == vmid:
            devicesInfos['room'] = line.split(';')[0]
            devicesInfos['hostname'] = line.split(';')[1]
            devicesInfos['group'] = line.split(';')[2]
            devicesInfos['mac'] = line.split(';')[3]
            devicesInfos['ip'] = line.split(';')[4]
            devicesInfos['pxe'] = line.split(';')[10]
    return devicesInfos


def getGroupInfosMaster(masterHostname):
    # sftp = ssh.open_sftp()
    remotePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"
    output = getFileContent(remotePath)
    # output = sftp.open(remotePath)
    masterInfos = {}
    for line in output:
        if masterHostname in line:
            masterInfos['room'] = line.split(';')[0]
            masterInfos['hostname'] = line.split(';')[1]
            masterInfos['group'] = line.split(';')[2]
            masterInfos['mac'] = line.split(';')[3]
            masterInfos['ip'] = line.split(';')[4]
            masterInfos['pxe'] = line.split(';')[10]
    return masterInfos


###### returns dict{} logedIn{user : { ip : ip, domain : domain}
def getLogedinUser():
    command = "smbstatus | grep users"
    object = getCommandOutput(command)
    logedIn = {}
    for line in object:
        line = str(line, 'ascii')
        ip = line.split()[3]
        user = line.split()[1]
        domain, user = user.split("\\")
        # Gegencheck domain and "users":
        if line.split()[2] == "users":
                logedIn[user]= {"ip": ip, "domain": domain, "full": r"{}\{}".format(domain,user)}
    dbprint("***** Assigned: *****")
    dbprint(json.dumps(logedIn, indent=2))
    return logedIn


def getActualImagesize(vdiGroup):
    #sftp = ssh.open_sftp()
    #cloopValues = {}
    remotePath = "/srv/linbo/start.conf." + str(vdiGroup)
    output = getFileContent(remotePath)
    #output = sftp.open(remotePath)
    cloopline = []
    for line in output:
        if "BaseImage" in line:
            cloopline = line.split(' ')
    cloop = cloopline[2].strip()

    remotePathCloop = ("/srv/linbo/" + str(cloop) + ".info")
    output2 = getFileContent(remotePathCloop)
    # output2 = sftp.open(remotePathCloop)
    lines = output2.readlines()
    for line in lines:
        linex = line.split("=")
        if "imagesize" in line:
            return linex[1].rstrip("\n")


####### CLONES: ########
def mainClones(group = "all"):

    checkConnections()
    allGroups = []
    if group == "all":
        allGroups = getVDIGroups()
        allallGroupInfos = {}
    else:
        allGroups.append(group)


    allallInfos = {}
    for vdiGroup in allGroups:
####### Get Group Information #########
        dbprint("***** Getting information to Clones from Group " + vdiGroup + " *****")

####### Get collected JSON Info File to all VMs from Group #############
        dbprint("***** ID Range for imagegroup: " + vdiGroup + " *****")
        idRange = getVmidRange(vdiGroup)
        dbprint(idRange)

####### collect API Parameter and Group Infos from each VM, merges them, and collects them in one list #######
        for vmid in idRange:
            apiInfos = {}
            groupInfos = getGroupInfos(vmid)
            try:
                apiInfos = getApiInfos(node,vmid)
            except Exception as err:
                #print(err)
                pass
            allInfos = mergeInfos(vmid, apiInfos, groupInfos)
            mergeInfos(vmid, apiInfos, groupInfos)
            allallInfos.update(allInfos)

####### adds user field if vm is used by an user #######
        # grep nach users !
        logedIn = getLogedinUser()
        if logedIn:
            for user in logedIn:
                for vmid in idRange:
                    if "buildstate" in allallInfos[vmid]:
                        if logedIn[user]["ip"] == allallInfos[vmid]["ip"]:
                            allallInfos[vmid]["user"] = logedIn[user]["full"]
                    else:
                        allallInfos[vmid]["user"] = ""
        else:
            for vmid in idRange:
                allallInfos[vmid]["user"] = ""



####### calculates summary values 'allocated_vms', 'existing_vms', 'building_vms' #######
        allocated = 0
        existing = 0
        available = 0
        building = 0
        failed = 0
        registered = len(idRange)

        now = datetime.now()
        now = float(now.strftime("%Y%m%d%H%M%S"))

        for vmid in allallInfos:
            # calculate existing
            try:
                proxmox.nodes('hv01').qemu(vmid).status.get()
                existing = existing + 1
                # calculate building,finished,available,allocated,failed - just from existing vms!
                try:
                    if allallInfos[vmid]['buildstate'] == "building":
                        building = building + 1
                    elif allallInfos[vmid]['buildstate'] == "finished":
                        if (allallInfos[vmid]['lastConnectionRequestTime'] == ""):
                            if allallInfos[vmid]['user'] == "":
                                    available = available + 1
                            elif allallInfos[vmid]["user"] != "":
                                allocated = allocated + 1
                        elif (allallInfos[vmid]['lastConnectionRequestTime'] != ""):
                            if allallInfos[vmid]['user'] == "" \
                                and (now - float(allallInfos[vmid]['lastConnectionRequestTime']) > timeoutConnectionRequest):
                                    available = available + 1
                            elif allallInfos[vmid]["user"] != "" \
                                or (now - float(allallInfos[vmid]['lastConnectionRequestTime']) <= timeoutConnectionRequest):
                                    allocated = allocated + 1
                    elif allallInfos[vmid]['buildstate'] == "failed":
                        failed = failed + 1
                except Exception as err:
                    dbprint(err)
                    pass
            except Exception as err:
                #print(err)
                continue

        summary = {}
        summary["allocated_vms"] = allocated
        summary["available_vms"] = available
        summary["existing_vms"] = existing
        summary["registered_vms"] = registered
        summary["building_vms"] = building
        summary["failed_vms"] = failed

        if group == "all":
            allallGroupInfos[vdiGroup] = {}
            allallGroupInfos[vdiGroup]['clone_vms'] = allallInfos
            allallGroupInfos[vdiGroup]['summary']  = summary
        else:
            allallInfos['summary'] = summary

####### prints the whole JSON with all information #######

    if group == "all":
        dbprint(json.dumps(allallGroupInfos, indent=2))
        return allallGroupInfos
    else:
        dbprint(json.dumps(allallInfos, indent=2))
        return allallInfos


####### MASTER: #######
def mainMaster(group="all"):

    checkConnections()
    allGroups = []
    if group == "all":
        allGroups = getVDIGroups()
        allGroupInfos = {}
    else:
        allGroups.append(group)

    groupInfos = {}
    for vdiGroup in allGroups:
        ####### Get collected JSON Info File to all VMs from Group #############
        dbprint("*** ID Range for imagegroup: " + vdiGroup + " ***")
        masterInfos = getMasterDetails(vdiGroup)
        masterVmids = masterInfos['vmids'].split(',')
        masterName = masterInfos['hostname']

        if group == "all":
            # general
            groupInfos = getGroupInfosMaster(masterName)
            groupInfos['actual_imagesize'] = getActualImagesize(vdiGroup)
            groupInfos['hostname'] = masterName
        else:
            groupInfos['basic'] = getGroupInfosMaster(masterName)
            groupInfos['basic']['actual_imagesize'] = getActualImagesize(vdiGroup)
            groupInfos['basic']['hostname'] = masterName

        allApiInfos = {}
        dbprint("*** Getting information to Masters from Group " + vdiGroup + " ***")
        ####### get api Infos #######
        for vmid in masterVmids:
            #print(type(vmid)) # => 'str'
            apiInfos = {}
            try:
                apiInfos[vmid] = getApiInfosMaster(node,vmid)
            except Exception:
                apiInfos[vmid] = None
                pass
            allApiInfos.update(apiInfos)

        if group == "all":
            groupInfos['master_vms'] = allApiInfos
        else:
            groupInfos.update(allApiInfos)

        # summary
        existing = 0
        finished = 0
        failed = 0
        building = 0
        registered = len(masterVmids)

        for vmid in allApiInfos:
            # calculate existing
            try:
                proxmox.nodes('hv01').qemu(vmid).status.get()
                existing = existing + 1
                # calculate buildstates - just from existing vms!
                try:
                    if allApiInfos[vmid]['buildstate'] == "building":
                        building = building + 1
                    elif allApiInfos[vmid]['buildstate'] == "finished":
                        finished = finished + 1
                    elif allApiInfos[vmid]['buildstate'] == "failed":
                        failed = failed + 1
                except Exception:
                    pass
            except Exception:
                pass

        groupInfos["summary"] = {}
        groupInfos["summary"]["existing_master"] = existing
        groupInfos["summary"]["registered_master"] = registered
        groupInfos["summary"]["building_master"] = building
        groupInfos["summary"]["failed_master"] = failed
        #allallInfos.update(groupInfos)

        if group == "all":
            allGroupInfos[vdiGroup] = groupInfos

    if group == "all":
        dbprint(json.dumps(allGroupInfos, indent=2))
        return allGroupInfos
    else:
        dbprint(json.dumps(groupInfos, indent=2))
        return groupInfos


if __name__ == "__main__":

    if sys.argv[1] == "-master":
        mainMaster()
    elif sys.argv[1] == "-clones":
        mainClones()
    else:
        group = sys.argv[1]
        if sys.argv[2] == "-master":
            mainMaster(group)
        elif sys.argv[2] == "-clones":
            mainClones(group)
        else:
            print("***** wrong parameter! *****")
