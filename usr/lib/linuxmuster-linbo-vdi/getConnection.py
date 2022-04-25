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
import os
import sys
from globalValues import node,proxmox,hvIp,timeoutConnectionRequest,proxy_url
from getVmStates import get_clone_states
import vdi_common
import json
from datetime import datetime
#import getVmStates
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
    
    if not os.path.exists('/tmp/vdi'):
        os.makedirs('/tmp/vdi')
        
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
        outfile.write("proxy" + "=" + "http://" + str(proxy_url)+":3128" + "\n")
        outfile.write("password" + "=" + str(virtViewerDictionary["password"]) + "\n")
        outfile.write("release-cursor" + "=" + str(virtViewerDictionary["release-cursor"]) + "\n")
        outfile.write("host" + "=" + str(virtViewerDictionary["host"]) + "\n")
        outfile.write("ca" + "=" + str(virtViewerDictionary["ca"]) + "\n")
    outfile.close()

    connectionconfig = {"configFile" : configFilePath}
    return (json.dumps(connectionconfig))


def main(arguments):

    # TODO argparse
    vdi_group = arguments[1]
    requestUser = arguments[2]
    group_data = vdi_common.get_vdi_groups()['groups'][vdi_group]

    vm_states = get_clone_states(group_data,vdi_group)
    del vm_states['summary']

    ########################
    now = datetime.now()
    now = float(now.strftime("%Y%m%d%H%M%S"))  # => "20201102141556"

    ######## 1) if user already had a spice connection under 10 minutes
    for vmid in vm_states:
        try:
            if vm_states[vmid]['buildstate'] == "finished":
                if vm_states[vmid]['lastConnectionRequestUser'] == requestUser:
                        #print(vmid)
                        if  vm_states[vmid]['lastConnectionRequestTime'] != "":
                            passedTime = now - float(vm_states[vmid]['lastConnectionRequestTime'])
                            passedTime = 0
                            # TODO do not use float for timedifference
                            if float(passedTime) < float(timeoutConnectionRequest):
                                return(sendConnection(node, vmid, requestUser))
        except Exception as err:
            print(err) # => vm doenst exist => besser auf existierende loopen
            #continue

    ######## 2) try giving neverUsed Vmid
    unnused_vm = []
    for vmid in vm_states:
        #try:
        if vm_states[vmid]['buildstate'] == "finished":
            if vm_states[vmid]['lastConnectionRequestTime'] == "" and vm_states[vmid]['user'] == "":
                unnused_vm.append(vmid)
        #except Exception:
        #    continue
    try:
        vmid = random.choice(unnused_vm)
        return(sendConnection(node, vmid, requestUser))
    except Exception as err:
        print(err)
        


    #print(float(timeoutConnectionRequest))

    ######### 3) try giving not any more used Vmid
    availableVmids = []
    for vmid in vm_states:
        try:
            if vm_states[vmid]['buildstate'] == "finished":
                if vm_states[vmid]['lastConnectionRequestTime'] != "" and vm_states[vmid]['user'] == "":
                    lastTime = float(vm_states[vmid]['lastConnectionRequestTime'])
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
