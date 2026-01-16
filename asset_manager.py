class Asset:
    def __init__(self, id, type, current_location):
        self.id = id
        self.type = type
        self.current_location = current_location
        self.status = "IDLE"

    def can_traverse(self, water_depth_m):
        raise NotImplementedError("Subclass must implement abstract method")

class Truck(Asset):
    def __init__(self, id, current_location):
        super().__init__(id, "TRUCK", current_location)
        self.max_depth = 0.4  # meters

    def can_traverse(self, water_depth_m):
        return water_depth_m <= self.max_depth

class Okada(Asset):
    def __init__(self, id, current_location):
        super().__init__(id, "OKADA", current_location)
        self.max_depth = 0.2  # meters

    def can_traverse(self, water_depth_m):
        return water_depth_m <= self.max_depth

class Canoe(Asset):
    def __init__(self, id, current_location):
        super().__init__(id, "CANOE", current_location)
        self.min_depth = 0.3  # meters

    def can_traverse(self, water_depth_m):
        return water_depth_m >= self.min_depth

def get_asset_manager():
    return {
        "Truck": Truck,
        "Okada": Okada,
        "Canoe": Canoe
    }
