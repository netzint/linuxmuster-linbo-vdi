#!/usr/bin/env python3
#
# getConnection.py
#
# joanna.meinelt@netzint.de
#
# 20201122
#

import random
import string
import sys
from globalValues import node,proxmox,hvIp,timeoutConnectionRequest
from getVmStates import mainClones
import json
from datetime import datetime
import getVmStates
import logging

logger = logging.getLogger(__name__)


def sendConnection(node, vmid, user):
    ### change description
    apiInfos = proxmox.nodes(node).qemu(vmid).config.get()
    description = apiInfos['description']
    descriptionJSON = json.loads(description)
    #print("Set user for Connection: " + user)
    descriptionJSON['lastConnectionRequestUser'] = user
    now = datetime.now()
    now = now.strftime("%Y%m%d%H%M%S")  # => "20201102141556"
    descriptionJSON['lastConnectionRequestTime'] = now
    description = json.dumps(descriptionJSON)
    proxmox.nodes(node).qemu(vmid).config.post(description=description)

    ### send connection
    virtViewerDictionary = proxmox.nodes(node).qemu(vmid).spiceproxy.post(proxy=hvIp)

    timestamp = datetime.now()
    dateOfCreation = timestamp.strftime("%Y%m%d%H%M%S")

    configFilePath = "/tmp/vdi/start-vdi-" + str(dateOfCreation) + "-" + ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=6)) + ".vv"
    with open(configFilePath, "w") as outfile:
        outfile.write("[virt-viewer]" + "\n")
        outfile.write("type" + "=" + str(virtViewerDictionary["type"]) + "\n")
        outfile.write("host-subject" + "=" + str(virtViewerDictionary["host-subject"]) + "\n")
        outfile.write("delete-this-file" + "=" + str(virtViewerDictionary["delete-this-file"]) + "\n")
        outfile.write("secure-attention" + "=" + str(virtViewerDictionary["secure-attention"]) + "\n")
        outfile.write("toggle-fullscreen" + "=" + str(virtViewerDictionary["toggle-fullscreen"]) + "\n")
        outfile.write("title" + "=" + str(virtViewerDictionary["title"]) + "\n")
        outfile.write("tls-port" + "=" + str(virtViewerDictionary["tls-port"]) + "\n")
        outfile.write("proxy" + "=" + str(virtViewerDictionary["proxy"]) + "\n")
        outfile.write("password" + "=" + str(virtViewerDictionary["password"]) + "\n")
        outfile.write("release-cursor" + "=" + str(virtViewerDictionary["release-cursor"]) + "\n")
        outfile.write("host" + "=" + str(virtViewerDictionary["host"]) + "\n")
        outfile.write("ca" + "=" + str(virtViewerDictionary["ca"]) + "\n")
    outfile.close()

    connectionconfig = {"configFile" : configFilePath}
    return (json.dumps(connectionconfig))


def main(arguments):

    group = arguments[1]
    requestUser = arguments[2]

    vmStates = getVmStates.mainClones(group,quiet=True)
    del vmStates['summary']

    ########################
    now = datetime.now()
    now = float(now.strftime("%Y%m%d%H%M%S"))  # => "20201102141556"

    ######## 1) if user already had a spice connection under 10 minutes
    for vmid in vmStates:
        try:
            if vmStates[vmid]['buildstate'] == "finished":
                if vmStates[vmid]['lastConnectionRequestUser'] == requestUser:
                        #print(vmid)
                        if  vmStates[vmid]['lastConnectionRequestTime'] != "":
                            passedTime = now - float(vmStates[vmid]['lastConnectionRequestTime'])
                            passedTime = 0
                            if float(passedTime) < float(timeoutConnectionRequest):
                                return(sendConnection(node, vmid, requestUser))
        except Exception as err:
            #print(err) # => vm doenst exist => besser auf existierende loopen
            continue

    ######## 2) try giving neverUsed Vmid
    neverUsedVmids = []
    for vmid in vmStates:
        try:
            if vmStates[vmid]['buildstate'] == "finished":
                if vmStates[vmid]['lastConnectionRequestTime'] == "" and vmStates[vmid]['user'] == "":
                    neverUsedVmids.append(vmid)
        except Exception:
            continue
    try:
        vmid = random.choice(neverUsedVmids)
        return(sendConnection(node, vmid, requestUser))
    except Exception as err:
        #print(err)
        pass


    #print(float(timeoutConnectionRequest))

    ######### 3) try giving not any more used Vmid
    availableVmids = []
    for vmid in vmStates:
        try:
            if vmStates[vmid]['buildstate'] == "finished":
                if vmStates[vmid]['lastConnectionRequestTime'] != "" and vmStates[vmid]['user'] == "":
                    lastTime = float(vmStates[vmid]['lastConnectionRequestTime'])
                    passedTime = now - lastTime
                    if passedTime > float(timeoutConnectionRequest):
                            availableVmids.append(vmid)
        except Exception:
            continue
    try:
        vmid = random.choice(availableVmids)
        sendConnection(node, vmid, requestUser)
        return(sendConnection(node, vmid, requestUser))

    except Exception as err:
        #print(err)
        pass

    logger.info("*** No desktop available ***")
    logger.info("*** Exiting. ***")
    sys.exit()

if __name__ == "__main__":
    print(main(sys.argv))
