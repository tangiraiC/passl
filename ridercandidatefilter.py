
available_drivers = [] #list of available drivers
order_id= 0 #order id for the order to be assigned to a driver  



class RiderCandidateFilter:

    # the initiator 
    def __init__(self,available_drivers, order_id,timestamp):
        self.available_drivers = available_drivers
        self.order_id = order_id

# function to build candidate list of drivers for the order
    def build_candidate_list(self, order):
        pass

#function haversineMeters to calculate the distance between two points given their latitude and longitude
    def haversineMeters(self, lat1, lon1, lat2, lon2):
        pass

#function to check if rider is allowed in the zone
    def is_rider_allowed_in_zone(self, rider, zone):
        pass

#function to see if the driver violates any restrictions for the order
    def violates_restrictions(self, driver, order):
        pass

#function to assign the order to the best candidate driver
    def assign_order_to_driver(self, order):
        pass
