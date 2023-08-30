# linbo_vdi_manager/master.py
import master_handling
import getVmStates
import vdi_common

class VDIMaster:
    def __init__(self, vdi_group, api_infos):
        self.vdi_group = vdi_group
        self.hostname = vdi_group.data['hostname']
        self.buildstate = api_infos['buildstate']

        schoolId = vdi_common.get_school_id(vdi_group.name)
        devices = vdi_common.devices_loader(schoolId)
        devices_data = getVmStates.get_master_group_infos(devices, self.hostname)
        vm_attributes = ['bios','boot','cores','memory','ostype','name','usb0','spice_enhancements']

        self.vms = getVmStates.get_vm_info_multithreaded(vdi_group,'master')

        self.room = devices_data['room']
        self.mac = devices_data['mac']
        self.ip = devices_data['ip']
        self.group = devices_data['group']
        self.schoolId = schoolId
        self.needed_imagesize = getVmStates.get_needed_imagesize(vdi_group.name)
        self.actual_imagesize = api_infos['imagesize']
        self.date_of_creation = api_infos['dateOfCreation']
        self.vmid = api_infos['vmid']
        self.attributes = {}
        for attribute in vm_attributes:
            self.attributes[attribute] = api_infos[attribute]

        net0 = vdi_common.tuple_string_to_dict(api_infos['net0'])
        self.attributes['bridge'] = net0['bridge']
        self.attributes['tag'] = int(net0['tag'])
        # TODO this is ugly
        self.attributes['storage'] = api_infos['sata0'].split(':')[0]
        self.attributes['size'] = int(api_infos['sata0'].split(',')[1].split('=')[1].split('G')[0])





        #self.name = name
        #self.data = data
        # Add any additional attributes and methods specific to the Master class

    def build_master(self) -> dict:
        return master_handling.create_master(self)
    
    def get_master_group_infos():
        getVmStates.get_master_group_infos()
        return
    
    def delete_master(self) ->dict:
        print('delete_master, not implemented')
        pass