#Purpose: Ranking/selection model (the “who is best” layer).
#Takes candidates (already eligible) + features (ETA, distance, rating, fairness, etc.)
#Produces:
#a score per rider OR an ordered list
#Typical responsibilities:
#weighted scoring function (v1)
#tie-breaking rules (deterministic)
#fairness constraints (avoid starvation of low-rank riders)
#policy knobs (optimize acceptance vs ETA vs cost)
#Output: ranked riders for offer sequence.