#!/usr/bin/env python3

import os
import logging

def start_conf_loader(path_to_file):
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

def image_info_loader(image_name):
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
    
def getFileContent(path_to_file):
    if os.path.isfile(path_to_file):
        with open (path_to_file, 'r') as reader:
            return reader.readlines()
        #reader = open(path_to_file, 'r')
        #return reader.read()
    else:
        logging.error(path_to_file + ' not a file')     



if __name__ == "__main__":
    quit()

