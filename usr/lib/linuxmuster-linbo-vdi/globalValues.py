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
import os
import time
import subprocess

# returns ssh and proxmox api connection and
# returns global values

#file = open("/etc/netzint/vdiConfig.json", 'r')
file = open("/etc/linuxmuster/linbo-vdi/vdiConfig.json", 'r')
vdiConfigStr = file.read()
vdiConfig = json.loads(vdiConfigStr)

global node
node = vdiConfig['node']
global hvIp
hvIp = vdiConfig['hvIp']
global hvUser
hvUser = vdiConfig['hvUser']
global password
password = vdiConfig['password']
global timeoutConnectionRequest
timeoutConnectionRequest = vdiConfig['timeoutConnectionRequest']
global vdiLocalService # True => running service on server VM,# False => remote
vdiLocalService = vdiConfig['vdiLocalService']
global debugging
debugging = vdiConfig['debugging']

# set debugging options
def dbprint(println):
    if debugging:
        print (println)

# set local or remote option
if vdiLocalService == False:
    global serverIp
    serverIp = vdiConfig['serverIp']
    global ssh
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(serverIp, port=22, username='root', password=password)
#else:
    #ssh = "Plätzchen"

global proxmox
proxmox = ProxmoxAPI(hvIp, user=hvUser, password=password, verify_ssl=False )
# proxmox = ProxmoxAPI(hvIp, user=hvUser,token_name='vdiserver',token_value='9f711699-99d1-423c-b2f5-cdb5748b3e5c')

# Remote/Local Functions:
def getFileContent(pathToFile):
    if vdiLocalService == True:
        output = open(pathToFile, 'r')
        return output
    elif vdiLocalService == False:
        sftp = ssh.open_sftp()
        output = sftp.open(pathToFile)
        return output

# get command output from shell remote or local
def getCommandOutput(command):
    if vdiLocalService == True:
        #output = subprocess.check_output(command)
        output = subprocess.Popen(command,stdout=subprocess.PIPE,shell=True)
        #output = process.communicate()[0]
        output = output.stdout.readlines()
        return output
    elif vdiLocalService == False: # returns ssh_stdout! not useable for ssh_stderr
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
        return ssh_stdout.readlines()

# set a command remote or local
def setCommand(command):
    if vdiLocalService == True:
        os.system(command)
    elif vdiLocalService == False:
        ssh.exec_command(command)
#    if vdiServiceLocal == True: <3

# general Functions:
def getMasterDetails(vdiGroup):
    try:
        remotePath = "/srv/linbo/start.conf." + str(vdiGroup) + ".vdi"
        output = getFileContent(remotePath)
        data = json.load(output)
        return data
    except Exception as err:
        print(err)

# check server connection
def serverCheck():
    try:
        if ssh.get_transport() is not None:
            ssh.get_transport().is_active()
            return True
        else:
            print("*** Connection to Server failed! ***")
            return False
    except Exception as err:
        print(err)

# check hv connection
def nodeCheck():
    try:
        proxmox.nodes(node).status.get()
        return True
    except Exception as err:
        print("*** Connection to Node failed! ***")
        print(err)
        return False

# check connections to hv and if remote to server
def checkConnections():
    while True:
        if vdiLocalService == False:
            if serverCheck() == True and nodeCheck() == True:
                break
        elif vdiLocalService:
            if nodeCheck() == True:
                break
        else:
            print("Waiting.")
            time.sleep(5)

# get all vdi groups
def getVDIGroups():
    command = "ls /srv/linbo/*.vdi"
    #ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
    files = getCommandOutput(command)
    #files = ssh_stdout.readlines()
    vdiGroups = []
    for file in files:
        file = str(file, 'ascii') # bei local Subprocess Abfrage wird Byte Object returned, bei ssh testen!
        #print(file)
        if file != "":
            file = file.strip()
            file = file.rstrip('\\n')
            file = file.lstrip('/srv/linbo/start.conf.')
            file = file.rstrip('.vdi')
            vdiGroups.append(file)
    print("***** Groups: *****")
    print ("***** " + str(vdiGroups) + " *****")
    return vdiGroups
