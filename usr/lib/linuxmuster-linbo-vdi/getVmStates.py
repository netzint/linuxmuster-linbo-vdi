#!/usr/bin/env python3
#
# getVmStates.py
#
# joanna.meinelt@netzint.de
#
# 20211121


import json
from datetime import datetime
from globalValues import node,getSchoolId,proxmox,dbprint,checkConnections,timeoutConnectionRequest,getMasterDetails,getFileContent,getJsonFile,getCommandOutput,getVDIGroups,getSmbstatus
import vdi_common
import argparse
import logging
logging.basicConfig(level=logging.ERROR)

__version__ = 'version 0.90.22'

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
            apiInfos['master'] = descriptionJSON["master"]
            apiInfos['lastConnectionRequestUser'] = descriptionJSON['lastConnectionRequestUser']
            apiInfos['lastConnectionRequestTime'] = descriptionJSON['lastConnectionRequestTime']
            apiInfos.pop("description")
            return apiInfos
        except Exception:
            logging.error("***** Failed to assign description values. *****")  
    except Exception as err:
        # print("Failed to load JSON or api access failed:")
        # print(err)
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
    apiInfos.update(groupInfos)
    jsonObject[vmid] = apiInfos
    return jsonObject 


####### get Collection of all VMs who are registered at school server #######
def getVmidRange(devicePath,vdiGroup):
    output = getFileContent(devicePath)
    #print("*** Check VM-ID-Range from Group ***")
    vmidRange = []
    for line in output:
        if vdiGroup in line:
            if "master" not in line and line.split(';')[11] is not "":
                vmid = line.split(';')[11]
                vmidRange.append(vmid)
    return vmidRange


######## returns dict devicesInfos from devices list  ########
def getGroupInfos(devicePath, vmid):
    output = getFileContent(devicePath)
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


def getGroupInfosMaster(devicePath, masterHostname):
    output = getFileContent(devicePath)
    vdiGroupInfos = {}
    for line in output:
        if masterHostname in line:
            vdiGroupInfos['room'] = line.split(';')[0]
            vdiGroupInfos['hostname'] = line.split(';')[1]
            vdiGroupInfos['group'] = line.split(';')[2]
            vdiGroupInfos['mac'] = line.split(';')[3]
            vdiGroupInfos['ip'] = line.split(';')[4]
            vdiGroupInfos['pxe'] = line.split(';')[10]
    return vdiGroupInfos



####### CLONES: ########
def mainClones(group = "all", quiet=False):

    checkConnections()
    allGroups = []
    if group == "all":
        allGroups = getVDIGroups()
        allallGroupInfos = {}
    else:
        allGroups.append(group)


    allallInfos = {}
    for vdiGroup in allGroups:

        vdiGroupInfos = getMasterDetails(vdiGroup)

        schoolId = getSchoolId(vdiGroup)
        if schoolId != "" or schoolId != "default-school":
            devicePath = "/etc/linuxmuster/sophomorix/" + str(schoolId) + "/" + str(schoolId) + ".devices.csv"
        else:
            devicePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"

####### Get collected JSON Info File to all VMs from Group #############
        idRange = getVmidRange(devicePath,vdiGroup)

####### collect API Parameter and Group Infos from each VM, merges them, and collects them in one list #######
        for vmid in idRange:
            apiInfos = {}
            groupInfos = getGroupInfos(devicePath, vmid)
            try:
                apiInfos = getApiInfos(node,vmid)
            except Exception as err:
                #print(err)
                pass
            allInfos = mergeInfos(vmid, apiInfos, groupInfos)
            allallInfos.update(allInfos)

####### adds user field if vm is used by an user #######
        logedIn = getSmbstatus(schoolId)
        if logedIn:
            for user in logedIn:
                for vmid in idRange:
                    if "buildstate" in allallInfos[vmid]:
                        if logedIn[user]["ip"] == allallInfos[vmid]["ip"]:
                            allallInfos[vmid]["user"] = logedIn[user]["full"]
                        #elif "user" in allallInfos[vmid]:
                        #else:# check if user already assign user with another IP!
                        #    if allallInfos[vmid]["user"] == "":
                        #        allallInfos[vmid]["user"] = ""
                        elif "user" not in allallInfos[vmid]:
                            allallInfos[vmid]["user"] = ""
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
                proxmox.nodes(node).qemu(vmid).status.get()
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
                    #dbprint(err)
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
        if not quiet:
            dbprint(json.dumps(allallGroupInfos, indent=2))
        return allallGroupInfos
    else:
        if not quiet:
            dbprint(json.dumps(allallInfos, indent=2))
        return allallInfos
    

####### MASTER: #######
def mainMaster(group="all", quiet=False):

    checkConnections()
    allGroups = []
    if group == "all":
        allGroups = getVDIGroups()
        allGroupInfos = {}
        #print("=======AllGroups:")
        #print(allGroups)
    else:
        allGroups.append(group)

    groupInfos = {}
    for vdiGroup in allGroups:

        vdiGroupInfos = getMasterDetails(vdiGroup)
        schoolId = getSchoolId(vdiGroup)
        devicePath = str
        if schoolId != "" or schoolId != "default-school":
            devicePath = "/etc/linuxmuster/sophomorix/" + str(schoolId) + "/" + str(schoolId) + ".devices.csv"
        else:
            devicePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"


        ####### Get collected JSON Info File to all VMs from Group #############
        #dbprint("*** ID Range for imagegroup: " + vdiGroup + " ***")
        masterVmids = vdiGroupInfos['vmids'].split(',')
        masterName = vdiGroupInfos['hostname']

        if group == "all":
            # general
            groupInfos = getGroupInfosMaster(devicePath, masterName)
            groupInfos['actual_imagesize'] = getActualImagesize(devicePath, vdiGroup)
            groupInfos['hostname'] = masterName
        else:
            groupInfos['basic'] = getGroupInfosMaster(devicePath, masterName)
            groupInfos['basic']['actual_imagesize'] = getActualImagesize(devicePath, vdiGroup)
            groupInfos['basic']['hostname'] = masterName

        allApiInfos = {}
        #dbprint("*** Getting information to Masters from Group " + vdiGroup + " ***")
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
                proxmox.nodes(node).qemu(vmid).status.get()
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
        if not quiet:
            dbprint(json.dumps(allGroupInfos, indent=2))
        return allGroupInfos
    else:
        if not quiet:
            dbprint(json.dumps(groupInfos, indent=2))
        return groupInfos


###### get api infos to master ######
def getApiInfosMaster(node,vmid):

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
        apiInfos['cloop'] = descriptionJSON['cloop']
        apiInfos['timestamp'] = descriptionJSON['timestamp']
        apiInfos['buildstate'] = descriptionJSON['buildstate']
        apiInfos["imagesize"] = descriptionJSON['imagesize']
        apiInfos.pop("description")
        return apiInfos
    except KeyError as err:
        logging.warning('Key '+ str(err) + ' not found in Machine description')
        logging.warning("***** Failed to assign description values. *****")   # so tif error its shown immediately
    except Exception as err:
        logging.error(err)
        logging.error("***** Failed to assign description values. *****")   # so tif error its shown immediately
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
def getVmidRange(devicePath,vdiGroup):
    #sftp = ssh.open_sftp()
    #devicePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"
    output = getFileContent(devicePath)
    #output = sftp.open(devicePath)
    #print("*** Check VM-ID-Range from Group ***")
    vmidRange = []
    for line in output:
        if vdiGroup in line:
            if "master" not in line and line.split(';')[11] is not "":
                vmid = line.split(';')[11]
                vmidRange.append(vmid)
    return vmidRange


######## returns dict devicesInfos from devices list  ########
def getGroupInfos(devicePath, vmid):
    #sftp = ssh.open_sftp()
    #devicePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"
    output = getFileContent(devicePath)
    # output = sftp.open(devicePath)
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


def getGroupInfosMaster(devicePath, masterHostname):
    # sftp = ssh.open_sftp()
    output = getFileContent(devicePath)
    # output = sftp.open(devicePath)
    vdiGroupInfos = {}
    for line in output:
        if masterHostname in line:
            vdiGroupInfos['room'] = line.split(';')[0]
            vdiGroupInfos['hostname'] = line.split(';')[1]
            vdiGroupInfos['group'] = line.split(';')[2]
            vdiGroupInfos['mac'] = line.split(';')[3]
            vdiGroupInfos['ip'] = line.split(';')[4]
            vdiGroupInfos['pxe'] = line.split(';')[10]
    return vdiGroupInfos


def getActualImagesize(devicePath, vdiGroup):
    devicePath = "/srv/linbo/start.conf." + str(vdiGroup)
    startConf_data = vdi_common.start_conf_loader(devicePath)
    
    # TODO: Handle more than one os
    for os in startConf_data['os']:
        image_name = os['BaseImage']
    imageInfo = vdi_common.image_info_loader(image_name)

    return imageInfo['imagesize']



####### CLONES: ########
def mainClones(group = "all", quiet=False):

    checkConnections()
    allGroups = []
    if group == "all":
        allGroups = getVDIGroups()
        allallGroupInfos = {}
    else:
        allGroups.append(group)


    allallInfos = {}
    for vdiGroup in allGroups:

        vdiGroupInfos = getMasterDetails(vdiGroup)

        schoolId = getSchoolId(vdiGroup)
        devicePath = str
        if schoolId != "" or schoolId != "default-school":
            devicePath = "/etc/linuxmuster/sophomorix/" + str(schoolId) + "/" + str(schoolId) + ".devices.csv"
        else:
            devicePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"

####### Get collected JSON Info File to all VMs from Group #############
        #dbprint("***** ID Range for imagegroup: " + vdiGroup + " *****")
        idRange = getVmidRange(devicePath,vdiGroup)

####### collect API Parameter and Group Infos from each VM, merges them, and collects them in one list #######
        for vmid in idRange:
            apiInfos = {}
            groupInfos = getGroupInfos(devicePath, vmid)
            try:
                apiInfos = getApiInfos(node,vmid)
            except Exception as err:
                #print(err)
                pass
            allInfos = mergeInfos(vmid, apiInfos, groupInfos)
            allallInfos.update(allInfos)

####### adds user field if vm is used by an user #######
        # grep nach users !
        logedIn = getSmbstatus(schoolId)
        
        #print(logedIn)
        if logedIn:
            for user in logedIn:
                for vmid in idRange:
                    if "buildstate" in allallInfos[vmid]:
                        if logedIn[user]["ip"] == allallInfos[vmid]["ip"]:
                            allallInfos[vmid]["user"] = logedIn[user]["full"]
                        else:
                            allallInfos[vmid]["user"] = ""
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
                proxmox.nodes(node).qemu(vmid).status.get()
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
                    #dbprint(err)
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
        if not quiet:
            dbprint(json.dumps(allallGroupInfos, indent=2))
        return allallGroupInfos
    else:
        if not quiet:
            dbprint(json.dumps(allallInfos, indent=2))
        return allallInfos
    

####### MASTER: #######
def mainMaster(group="all", quiet=False):

    checkConnections()
    allGroups = []
    if group == "all":
        allGroups = getVDIGroups()
        allGroupInfos = {}
        #print("=======AllGroups:")
        #print(allGroups)
    else:
        allGroups.append(group)

    groupInfos = {}
    for vdiGroup in allGroups:

        vdiGroupInfos = getMasterDetails(vdiGroup)
        schoolId = getSchoolId(vdiGroup)
        devicePath = str
        if schoolId != "" or schoolId != "default-school":
            devicePath = "/etc/linuxmuster/sophomorix/" + str(schoolId) + "/" + str(schoolId) + ".devices.csv"
        else:
            devicePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"


        ####### Get collected JSON Info File to all VMs from Group #############
        logging.info("*** ID Range for imagegroup: " + vdiGroup + " ***")
        masterVmids = vdiGroupInfos['vmids'].split(',')
        masterName = vdiGroupInfos['hostname']

        if group == "all":
            # general
            groupInfos = getGroupInfosMaster(devicePath, masterName)
            groupInfos['actual_imagesize'] = getActualImagesize(devicePath, vdiGroup)
            groupInfos['hostname'] = masterName
        else:
            groupInfos['basic'] = getGroupInfosMaster(devicePath, masterName)
            groupInfos['basic']['actual_imagesize'] = getActualImagesize(devicePath, vdiGroup)
            groupInfos['basic']['hostname'] = masterName

        allApiInfos = {}
        #dbprint("*** Getting information to Masters from Group " + vdiGroup + " ***")
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
                proxmox.nodes(node).qemu(vmid).status.get()
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
        if not quiet:
            dbprint(json.dumps(allGroupInfos, indent=2))
        return allGroupInfos
    else:
        if not quiet:
            dbprint(json.dumps(groupInfos, indent=2))
        return groupInfos


if __name__ == "__main__":

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
        mainMaster(args.group, quiet=args.quiet)
        quit()
    if args.clones is not False:
        mainClones(args.group, quiet=args.quiet)
        quit()
    else:
        parser.print_help()
    quit()
    
    #for x in range(len(sys.argv)):
    #    if sys.argv[x] == "-quiet":
    #        quiet = True
#
    #if sys.argv[1] == "-master":
    #    if quiet == True:
    #        mainMaster(quiet=True)
    #    else:
    #        mainMaster()
    #elif sys.argv[1] == "-clones":
    #    if quiet == True:
    #        mainClones(quiet=True)
    #    else:
    #        mainClones()
    #else:
    #    group = sys.argv[1]
    #    if sys.argv[2] == "-master":
    #        if quiet == True:
    #            mainMaster(group, quiet=True)
    #        else:
    #            mainMaster(group)
    #    elif sys.argv[2] == "-clones":
    #        if quiet == True:
    #            mainClones(group, quiet=True)
    #        else:
    #            mainClones(group)
    #    else:
    #        print("***** wrong parameter! *****")
