#!/usr/bin/env python3

import os
import logging
import csv
import glob
import json
import configparser
import time
import subprocess
import paramiko
from linbo_vdi_manager.vdi_group import VDIGroup

from globalValues import vdiLocalService, ssh, proxmox, node

logger = logging.getLogger(__name__)


def start_conf_loader(path_to_file)-> dict:
    """Returns all info of a start.conf file
    
    :param path to the start.conf file: str
    :type image_name: str
    :return: Dict of all info in strart.conf
    :rtype: dict
    """
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

def image_info_loader(image_name) -> dict:
    """Returns all info of an image info file
    
    :param image_name: str
    :type image_name: str
    :return: Dict of all info in image file
    :rtype: dict
    """
    if image_name.endswith('.cloop'):
        devicePathImageInfo = "/srv/linbo/" + str(image_name) + ".info"
    elif image_name.endswith('.qcow2'):
        devicePathImageInfo = "/srv/linbo/images/" + image_name.split('.')[0] + '/' + image_name + ".info"
    else:
        logging.error('Unknown image format provided with '+ image_name)
    content = getFileContent(devicePathImageInfo)
    data = {}
    for line in content:
        if '=' in line:
             key,value = line.split("=")
             data[key] = value.strip()
    return data

def devices_loader(schoolId) -> list:

        devicePath = "/etc/linuxmuster/sophomorix/default-school/devices.csv"
        if schoolId and schoolId != "default-school" and schoolId != "":
            devicePath = "/etc/linuxmuster/sophomorix/" + str(schoolId) + "/" + str(schoolId) + ".devices.csv"
        
            
        #print(devicePath)
        with open (devicePath, newline='') as csvfile:
            list = []
            reader = csv.reader(csvfile, delimiter=';')
            for row in reader:
                if len(row) < 12 or row[0][0] == '#':
                    continue
                list.append(row)
            return list
            #return reader

def json_loader(path_to_file) -> dict:
        reader = open(path_to_file, 'r')
        try:
            content = json.load(reader)
        
        except Exception as err:
            logging.error("Error parsing config file")
            logging.error(err)
            return False
        return content

def getFileContent(path_to_file):
    if os.path.isfile(path_to_file):
        with open (path_to_file, 'r') as reader:
            return reader.readlines()
        #reader = open(path_to_file, 'r')
        #return reader.read()
    else:
        logging.error(path_to_file + ' not a file')     

def get_school_id(vdiGroup):
    try:
        parser = configparser.ConfigParser(strict=False)
        linboGroupConfigPath = "/srv/linbo/start.conf." + str(vdiGroup)
        parser.read(linboGroupConfigPath)
        schoolId = parser['LINBO']['School']      
        return schoolId
    except Exception as err:
        logger.error("Problem finding school ID")
        logger.error(err)
        return False


def get_vdi_groups() -> list:
    vdi_groups = {'general': {'active_groups': []}, 'groups': []}

    for vdi_file in glob.glob("/srv/linbo/*.vdi"):
        data = json_loader(vdi_file)
        if data:
            vdi_group_name = vdi_file.split("/srv/linbo/start.conf.")[1].split('.vdi')[0]
            vdi_group = VDIGroup(vdi_group_name, data)
            vdi_groups['groups'].append(vdi_group)
            if vdi_group.activated:
                vdi_groups['general']['active_groups'].append(vdi_group_name)

    return vdi_groups

####### get Collection of all VMs who are registered at school server #######
def get_vmid_range(devices,vdi_group):
    logging.debug(f"[{vdi_group}] Check VM-ID-Range for Group")
    vmidRange = []
    for device in devices:
        if vdi_group in device[2]:
            if "master" != device[1] and device[11] != "":
                vmid = device[11]
                vmidRange.append(vmid)
    return vmidRange

# get command output from shell remote or local
def run_command(command):
    if vdiLocalService == True:
        output = subprocess.Popen(command,stdout=subprocess.PIPE,shell=True)
        output = output.stdout.readlines()
        return output
    elif vdiLocalService == False: # returns ssh_stdout! not useable for ssh_stderr
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
        return ssh_stdout.readlines()

# check server connection
def check_server_connection():
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
def check_node_connection():
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
def check_connection():
    if vdiLocalService:
        if check_node_connection() == True:
            return True
    if not vdiLocalService:
        if check_server_connection() == True and check_node_connection() == True:
            return True
    logging.info("Waiting.")
    time.sleep(5)
    return False

# calculates latest master and returns VMID
def get_current_master(master_states, master_vmids, vdi_group):
    timestampLatest = 0
    vmidLatest = 0
    logging.debug(f"[{vdi_group}] All master vmids: {master_vmids}")
    
    
    for vmid in master_vmids:
        if vmid in master_states:
            timestamp = master_states[vmid]['dateOfCreation']
            if float(timestamp) >= float(timestampLatest):
                timestampLatest = timestamp
                vmidLatest = vmid

    logging.info(f"[{vdi_group}] current master vmid is {vmidLatest}, timestamp: {str(timestampLatest)}")
    return {'vmid':vmidLatest,'timestamp':timestampLatest}


###### returns dict{} loggedIn{user : { ip : ip, domain : domain}
def getSmbstatus(schoolId = "default-school"):
    smbstatus_command = "smbstatus | grep users"
    if schoolId == "default-school":
            smbstatus = run_command(smbstatus_command)
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
            netconflist = run_command(commandNetConfList)
            try: 
                for line in netconflist:
                    line = str(line, 'ascii')
                    if  schoolId in line and "msdfs proxy" in line:
                        fileserver = (line.split(' ')[3])
                        suffix = "/" + schoolId + "\n"
                        fileserver = fileserver.rstrip(str(suffix))  
                        fileserver = fileserver.lstrip("//")
                        with paramiko.SSHClient() as sshSmbstatus:
                            # TODO Figure out how to hide the paramiko logging
                            sshSmbstatus.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                            sshSmbstatus.connect(fileserver, port=22, username='root')
                            sshSmbstatus_stdin, sshSmbstatus_stdout, sshSmbstatus_stderr = sshSmbstatus.exec_command(smbstatus_command)
                            sshSmbstatus_stderr.channel.recv_exit_status()
   
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
                


## general Functions:
#def vdi_conf_loader(vdiGroup) -> dict:
#    try:
#        startConf = "/srv/linbo/start.conf." + str(vdiGroup) + ".vdi"
#        data = getJsonFile(startConf)        
#        return data
#    except Exception as err:
#        logging.error(err)
# Remote/Local Functions:

#def getActivatedVdiGroups(vdi_groups) -> list:
#    active_groups = []
#    for vdi_group in vdi_groups:
#        active_groups.append(vdi_group)
#    return active_groups


if __name__ == "__main__":
    quit()

