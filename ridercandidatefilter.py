
nearbyDrivers = [] #list of available drivers
order_id= 0 #order id for the order to be assigned to a driver  

# a class to filter and assign drivers to rider orders
class RiderCandidateFilter:

    # the initiator 
    def __init__(self,nearbyDrivers, order_id,timestamp):
        self.nearbyDrivers = nearbyDrivers
        self.order_id = order_id

# function to build candidate list of drivers for the order
    def build_candidate_list(self, nearbyDrivers):
        #instantiated available drivers list so that from the list we can filter out drivers that are not eligible

        candidate_list = []
        for driver in nearbyDrivers:
            #logic to filter drivers based on certain criteria
            if 

            candidate_list.append(driver)

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
