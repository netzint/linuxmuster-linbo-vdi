#!/usr/bin/env python3
#
# getConnection.py
#
# joanna@linuxmuster.net
#
# 20201122
#

import random
import sys
from globalValues import node,proxmox,hvIp,timeoutConnectionRequest
from getVmStates import mainClones
import json
from datetime import datetime
import getVmStates


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
    #print(type(spiceConfig))
    #virtViewerDictionary = spiceConfig
    # print(type(virtViewerDictionary))  # => dict
    # nach /tmp/   hash als filename.vv 16 hash (Letters numbers)
    #print(json.dumps(virtViewerDictionary, indent=2))

    # ALS NAMEN HASH 8 stellig?
    with open("SPICECONF.vv", "w") as outfile:
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


def main(arguments):

    group = arguments[1]
    requestUser = arguments[2]

    vmStates = getVmStates.mainClones(group)
    del vmStates['summary']

    ########################
    now = datetime.now()
    now = float(now.strftime("%Y%m%d%H%M%S"))  # => "20201102141556"


    ######## 1) if user already had a spice connection under 10 minutes
    for vmid in vmStates:
        try:
            if vmStates[vmid]['buildstate'] == "finished":
                if vmStates[vmid]['lastConnectionRequestUser'] == requestUser:
                    ##and ( vmStates[vmid]['user'] == "" or (vmStates[vmid]['user']) == requestUser ):## could be asked too!: or ((vmStates[vmid]['user']).split('\\')[1]) == requestUser
                        # double check:
                        if  vmStates[vmid]['lastConnectionRequestTime'] != "":
                            passedTime = now - float(vmStates[vmid]['lastConnectionRequestTime'])
                            #print(int(passedTime))
                            if passedTime < float(timeoutConnectionRequest):
                                sendConnection(node, vmid, requestUser)
                                print("*** Found already assigned desctop VM " + str(vmid) + " and sending Connection again ***")
                                sys.exit()
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
        print(" *** Sending never used desctop VM:" + str(vmid) + " ***")
        sendConnection(node, vmid, requestUser)
        sys.exit()
    except Exception:
        pass


    ######### 3) try giving not any more used Vmid
    availableVmids = []
    for vmid in vmStates:
        try:
            if vmStates[vmid]['buildstate'] == "finished":
                if vmStates[vmid]['lastConnectionRequestTime'] != "" and vmStates[vmid]['user'] == "":
                    lastTime = float(vmStates[vmid]['lastConnectionRequestTime'])
                    passedTime = now - lastTime
                    if vmStates[vmid]['buildstate'] == "finished" \
                        and passedTime > float(timeoutConnectionRequest) \
                        and vmStates[vmid]['user'] == "":
                            availableVmids.append(vmid)
        except Exception:
            continue
    try:
        vmid = random.choice(availableVmids)
        sendConnection(node, vmid, requestUser)
        print("*** Found free desktop VM: " + str(vmid) + " ***")
        sys.exit()
    except Exception:
        pass

    print("*** No desktop available ***")
    print("*** Exiting. ***")
    sys.exit()

if __name__ == "__main__":
    main(sys.argv)
