#Purpose: ETA estimation policy.
#Converts routing outputs into ETA predictions used by:
#customer-facing “arrives in X”
#dispatch decision features
#Typical responsibilities:
#Pickup ETA: rider → shop
#Dropoff ETA: shop → customer
#Total ETA: pickup ETA + prep time + dropoff ETA
#Add buffers / heuristics (traffic time-of-day factors later)
#Keeps ETA logic separate from route computa