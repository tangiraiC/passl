#Purpose: Orchestrator / decision pipeline (the “engine”).
#Calls modules in order:
#candidate_filter (hard gates)
#routing.geofence (reachability gates)
#scoring (rank/choose)
#offer sequencing / fallback handling (timeouts, re-offers) — even if basic in v1
#Owns the control flow:
#If no candidates → fail state / expand radius policy
#If top rider declines → try next
#Stop conditions
#This is the file that implements the “dispatch loop” logic, while other files provide reusable primitives


#dediaceted riders for some orders 
 #if yes - we can skip geofence and directly score them (assuming they are always eligible)
# if order has many riders dedicated