#Purpose: Non-routing hard eligibility filtering (rule gates).
#Builds the base candidate set before routing/scoring.
#Typical responsibilities:
#online/available
#capacity / current workload
#verification/compliance
#vehicle type compatibility
#service zone membership
#cooldowns, bans, suspensions

#Output: “rule-qualified riders” (still not ranked).
nearbyDrivers = [] #list of available drivers
order_id= 0 #order id for the order to be assigned to a driver  
driverStatus = ["available", "transittoCollect",
                "transittoDropoff", "paused", "offline",
                "unregistered"] #list of possible driver statuses

# a class to filter and assign drivers to rider orders
class RiderCandidateFilter:

    # the constructor for the class takes in the list of nearby drivers, 
    # the order id and the timestamp of the order 
    def __init__(self,nearbyDrivers, order_id,timestamp,driverStatus):
        self.nearbyDrivers = nearbyDrivers
        self.order_id = order_id
        self.timestamp = timestamp
        self.driverStatus = driverStatus

# function to build candidate list of drivers for the order
    def build_candidate_list(self, nearbyDrivers):
        #instantiated available drivers list so that from the list we can filter 
        # out drivers that are not eligible
        candidate_list = []
        for driver in nearbyDrivers:
            #logic to filter drivers based on certain criteria
            if driver in nearbyDrivers: #placeholder condition
                candidate_list.append(driver)

#function that uses OSRM (Open Source Routing Machine)
# to calculate the distance and time from the driver to the pickup 
# location and from the pickup location to the dropoff location ,
# the functions also can  geofence the pickup and dropoff locations to ensure they are within serviceable areas
    def calculate_distance_and_time(self, driver, pickup_location, dropoff_location):
        #the geofencing to check if the driver is within the serviceable area

        #we need to calculate the drivers within a certain distance from the pick up location 
        

    

#function to check if rider is allowed in the zone
    def is_rider_allowed_in_zone(self, rider, zone):
        pass

#function to see if the driver violates any restrictions for the order
    def violates_restrictions(self, driver, order):
        pass

#function to assign the order to the best candidate driver
    def assign_order_to_best_driver(self, order):
        pass
