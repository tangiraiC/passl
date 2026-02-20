#Purpose: Route computation for downstream use.
#Returns the “best route” information needed by:
#navigation guidance
#map display / polyline geometry (if you later enable overview)
#distance breakdowns (legs)
#Uses OSRM /route primarily (not /table).
#It’s the “I need an actual route” module, while geofence.py is “I need eligibility metrics”.