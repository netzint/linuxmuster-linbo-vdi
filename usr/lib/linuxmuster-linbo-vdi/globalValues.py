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
import configparser
import logging
import csv

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
global hvIp
hvIp = vdiConfig['hvIp']
global hvUser
hvUser = vdiConfig['hvUser']
global timeoutConnectionRequest
timeoutConnectionRequest = vdiConfig['timeoutConnectionRequest']
global vdiLocalService # True => running service on server VM,# False => remote
vdiLocalService = vdiConfig['vdiLocalService']
global debugging
debugging = vdiConfig['debugging']
global nmapPorts
nmapPorts = vdiConfig['nmapPorts'].split(',')


# set local or remote option
if vdiLocalService == False:
    global serverIp
    serverIp = vdiConfig['serverIp']
    global ssh
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(serverIp, port=22, username='root')

global proxmox
#proxmox = ProxmoxAPI(hvIp, user=hvUser, password=password, verify_ssl=False )
proxmox = ProxmoxAPI(hvIp, user=hvUser,  backend='ssh_paramiko')


# Remote/Local Functions:
def getJsonFile(path_to_file):
    if vdiLocalService == True:
        reader = open(path_to_file, 'r')
        content = json.load(reader)
        return content
    elif vdiLocalService == False:
        sftp = ssh.open_sftp()
        output = sftp.open(path_to_file)
        return output



def getFileContent(path_to_file):
    if path_to_file.endswith('.csv'):
        with open (path_to_file, newline='') as csvfile:
            list = []
            reader = csv.reader(csvfile, delimiter=';')
            for row in reader:
                if row[0][0] == '#' or len(row) < 15:
                    continue
                list.append(row)
            return list
            #return reader
    if vdiLocalService == True:
        if os.path.isfile(path_to_file):
            reader = open(path_to_file, 'r')
            return reader
        else:
            logging.error(path_to_file + ' not a file')     
    elif vdiLocalService == False:
        sftp = ssh.open_sftp()
        output = sftp.open(path_to_file)
        return output

# get command output from shell remote or local
def getCommandOutput(command):
    if vdiLocalService == True:
        output = subprocess.Popen(command,stdout=subprocess.PIPE,shell=True)
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
        startConf = "/srv/linbo/start.conf." + str(vdiGroup) + ".vdi"
        data = getJsonFile(startConf)        
        return data
    except Exception as err:
        logging.error(err)

def getSchoolId(vdiGroup):
    try:
        parser = configparser.ConfigParser(strict=False)
        linboGroupConfigPath = "/srv/linbo/start.conf." + str(vdiGroup)
        parser.read(linboGroupConfigPath)
        schoolId = parser['LINBO']['School']      
        return schoolId
    except Exception as err:
        logging.error("Problem finding school ID")
        logging.error(err)

# check server connection
def serverCheck():
    try:
        if ssh.get_transport() is not None:
            ssh.get_transport().is_active()
            return True
        else:
            logging.error("*** Connection to Server failed! ***")
            return False
    except Exception as err:
        logging.error(err)

# check hv connection
def nodeCheck():
    try:
        proxmox.nodes(node).status.get()
        return True
    except Exception as err:
        logging.error("*** Connection to Node failed! ***")
        errorcode = str(err).split(' ')[0]
        if errorcode == '596':
            logging.error(err)
            logging.error('Possible wrong node name in vdiConfig.json, must match nodename in proxmox!')
            quit()
        logging.error(err)
        return False

# check connections to hv and if remote to server
def checkConnections():
    if vdiLocalService:
        if nodeCheck() == True:
            return True
    if not vdiLocalService:
        if serverCheck() == True and nodeCheck() == True:
            return True
    logging.info("Waiting.")
    time.sleep(5)
    return False

# get all vdi groups
def getVDIGroups():
    command = "ls /srv/linbo/*.vdi"
    files = getCommandOutput(command)
    vdiGroups = []
    for filex in files:
        line = str(filex, 'ascii') # bei local Subprocess Abfrage wird Byte Object returned, bei ssh testen!
        if line != "":
            line = line.strip()
            line = line.rstrip('\\n')
            if line.startswith('/srv/linbo/start.conf.'):
                line = line[len('/srv/linbo/start.conf.'):]
            line = line.rstrip('.vdi')
            vdiGroups.append(line)
    return vdiGroups


###### returns dict{} loggedIn{user : { ip : ip, domain : domain}
def getSmbstatus(schoolId = "default-school"):
    commandSmbstatus = "smbstatus | grep users"
    if schoolId == "default-school":
            smbstatus = getCommandOutput(commandSmbstatus)
            loggedIn = {}
            for line in smbstatus:
                line = str(line, 'ascii')
                ip = line.split()[3]
                user = line.split()[1]
                domain, user = user.split("\\")
                if line.split()[2] == "users":
                    loggedIn[user]= {"ip": ip, "domain": domain, "full": r"{}\{}".format(domain,user)}
            return loggedIn
    else:
            commandNetConfList = "net conf list"
            netconflist = getCommandOutput(commandNetConfList)
            try: 
                for line in netconflist:
                    line = str(line, 'ascii')
                    if  schoolId in line and "msdfs proxy" in line:
                        fileserver = (line.split(' ')[3])
                        suffix = "/" + schoolId + "\n"
                        fileserver = fileserver.rstrip(str(suffix))  
                        fileserver = fileserver.lstrip("//")
                        with paramiko.SSHClient() as sshSmbstatus:
                            sshSmbstatus.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                            sshSmbstatus.connect(fileserver, port=22, username='root')
                            sshSmbstatus_stdin, sshSmbstatus_stdout, sshSmbstatus_stderr = sshSmbstatus.exec_command(commandSmbstatus)      

                        
                        loggedIn = {}
                        for line in sshSmbstatus_stdout.readlines():
                            #line = str(line, 'ascii')
                            ip = line.split()[4]
                            user = line.split()[1]
                            domain, user = user.split("\\")
                            if line.split()[3] == "users":
                                loggedIn[user]= {"ip": ip, "domain": domain, "full": r"{}\{}".format(domain,user)}
                        return loggedIn
            except Exception as err:
                logging.error("Some Error while net conf list to fileserver")
                logging.error(err)
                return
                
