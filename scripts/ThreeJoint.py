class ThreeJoint:
    def __init__(self, name, parent, radius):
        self.name = name
        self.parent = parent
        self.child = name + '2'
        self.radius = radius
        self.set = False
        self.prev_x = 0.0
        self.prev_y = 0.0
        self.prev_z = 0.0
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.yaw = 0.0
        self.pitch = 0.0
        self.roll = 0.0