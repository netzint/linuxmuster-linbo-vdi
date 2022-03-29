#!/usr/bin/env python3
#
# globalValues.py
#
# joanna@linuxmuster.net
#
# 20201116
#

import json
from proxmoxer import ProxmoxAPI
import paramiko

# returns ssh and proxmox api connection and
# returns global values

file = open("/etc/linuxmuster/linbo-vdi/vdiConfig.json", 'r')
vdiConfigStr = file.read()
vdiConfig = json.loads(vdiConfigStr)

global node
node = vdiConfig['node']
#global pool
#pool = vdiConfig['pool']
global mutlischool
multischool = vdiConfig['multischool']
hvIp = vdiConfig['hvIp']
hvUser = vdiConfig['hvUser']
password = vdiConfig['password']
global timeoutConnectionRequest
timeoutConnectionRequest = vdiConfig['timeoutConnectionRequest']
global vdiLocalService # True => running service on server VM,# False => remote
vdiLocalService = vdiConfig['vdiLocalService']
global nmapPorts
nmapPorts = vdiConfig['nmapPorts'].split(',')
global ssh
ssh = paramiko.SSHClient()


# set local or remote option
if vdiLocalService == False:
    #global serverIp
    serverIp = vdiConfig['serverIp']
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(serverIp, port=22, username='root')

global proxmox
proxmox = ProxmoxAPI(hvIp, user=hvUser, password=password, verify_ssl=False)