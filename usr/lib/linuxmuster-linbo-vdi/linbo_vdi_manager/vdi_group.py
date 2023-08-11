class VDIGroup:
    def __init__(self, name, data):
        self.name = name
        self.data = data
        self.activated = self.data.get('activated', False)

