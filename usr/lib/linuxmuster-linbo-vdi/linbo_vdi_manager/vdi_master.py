# linbo_vdi_manager/master.py
import master_handling
import getVmStates
import vdi_common

class VDIMaster:
    def __init__(self, vdi_group):
        self.vdi_group = vdi_group
        self.hostname = vdi_group.data['hostname']

        schoolId = vdi_common.get_school_id(vdi_group.name)
        devices = vdi_common.devices_loader(schoolId)
        devices_data = getVmStates.get_master_group_infos(devices, self.hostname)
        
        self.vms = getVmStates.get_vm_info_multithreaded(vdi_group,'master')



        self.room = devices_data['room']
        self.mac = devices_data['mac']
        self.ip = devices_data['ip']
        self.group = devices_data['group']
        self.schoolId = schoolId
        self.needed_image_size = getVmStates.get_needed_imagesize(vdi_group.name)


        #self.name = name
        #self.data = data
        # Add any additional attributes and methods specific to the Master class

    def build_master(self) -> dict:
        return master_handling.create_master(self)
    
    def get_master_group_infos():
        getVmStates.get_master_group_infos()
        return
    
    def delete_master(self) ->dict:
        pass