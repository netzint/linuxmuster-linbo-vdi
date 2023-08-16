class VDIGroup:
    def __init__(self, name, data):
        self.name = name
        #self.data = data
        for k,v in data.items():
            setattr(self, k, v)


