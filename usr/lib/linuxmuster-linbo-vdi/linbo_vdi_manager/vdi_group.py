import getVmStates
import master_handling
class VDIGroup:
    def __init__(self, name, data):
        self.name = name
        self.data = data
        self.activated = data["activated"]
        #for k,v in data.items():
        #    print(f"self.{k} = data.{k}")
        #    setattr(self, k, v)

    def get_master_states(self) -> dict:
        return getVmStates.get_master_states(self)

    def create_master(self) -> bool:
        return master_handling.create_master(self.data,self.name)
