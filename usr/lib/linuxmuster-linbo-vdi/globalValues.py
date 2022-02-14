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

# returns ssh and proxmox api connection and
# returns global values

file = open("/etc/linuxmuster/linbo-vdi/vdiConfig.json", 'r')
vdiConfigStr = file.read()
vdiConfig = json.loads(vdiConfigStr)

global node
node = vdiConfig['node']
#global pool
#pool = vdiConfig['pool']
#global mutlischool
#multischool = vdiConfig['multischool']
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
#global nmapPorts
#nmapPorts = vdiConfig['nmapPorts'].split(',')

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

global proxmox
proxmox = ProxmoxAPI(hvIp, user=hvUser, password=password, verify_ssl=False )

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

def start_conf_loader(path_to_file):
        if os.path.isfile(path_to_file):
            opened = open(path_to_file, 'r')
            data = {
                'config': {},
                'partitions': [],
                'os': []
            }
            for line in opened:
                line = line.split('#')[0].strip()
                if line.startswith('['):
                    section = {}
                    section_name = line.strip('[]')
                    if section_name == 'Partition':
                        data['partitions'].append(section)
                    elif section_name == 'OS':
                        data['os'].append(section)
                    else:
                        data['config'][section_name] = section
                elif '=' in line:
                    k, v = line.split('=', 1)
                    v = v.strip()
                    if v in ['yes', 'no']:
                        v = v == 'yes'
                    section[k.strip()] = v
            return data

def getFileContent(path_to_file):
    if vdiLocalService == True:
        if os.path.isfile(path_to_file):
            reader = open(path_to_file, 'r')
            return reader.read()
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
        print(err)

def getSchoolId(vdiGroup):
    try:
        parser = configparser.ConfigParser(strict=False)
        linboGroupConfigPath = "/srv/linbo/start.conf." + str(vdiGroup)
        parser.read(linboGroupConfigPath)
        schoolId = parser['LINBO']['School']      
        return schoolId
    except Exception as err:
        print("Problem finding school ID")
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


###### returns dict{} logedIn{user : { ip : ip, domain : domain}
def getSmbstatus(schoolId = "default-school"):
    commandSmbstatus = "smbstatus | grep users"
    if schoolId == "default-school":
            smbstatus = getCommandOutput(commandSmbstatus)
            logedIn = {}
            for line in smbstatus:
                line = str(line, 'ascii')
                ip = line.split()[3]
                user = line.split()[1]
                domain, user = user.split("\\")
                if line.split()[2] == "users":
                    logedIn[user]= {"ip": ip, "domain": domain, "full": r"{}\{}".format(domain,user)}
            return logedIn
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
                        sshSmbstatus = paramiko.SSHClient()
                        sshSmbstatus.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        sshSmbstatus.connect(fileserver, port=22, username='root', password=password)
                        sshSmbstatus_stdin, sshSmbstatus_stdout, sshSmbstatus_stderr = sshSmbstatus.exec_command(commandSmbstatus)      
                        
                        logedIn = {}
                        for line in sshSmbstatus_stdout.readlines():
                            #line = str(line, 'ascii')
                            ip = line.split()[4]
                            user = line.split()[1]
                            domain, user = user.split("\\")
                            if line.split()[3] == "users":
                                logedIn[user]= {"ip": ip, "domain": domain, "full": r"{}\{}".format(domain,user)}
                        return logedIn
            except Exception as err:
                print("Some Error while net conf list to fileserver")
                print(err)
                
