# Detailed System Architecture Schematic

Here is a highly structural, colored Mermaid diagram replicating the layout logic from your visual schema. It maps the full lifecycle: Order Arrival `->` Batching `->` Ready Jobs `->` Driver Selection `->` Publishing to Smartphone!

```mermaid
graph TD
    %% Define external endpoints
    DB[("External <br/> System / DB")]
    FIREBASE(["Push Notification <br/> Service / Firebase"])

    %% Flow: DB to push service
    DB <--> FIREBASE

    %% Subgraph 1: Orders / Queue
    subgraph Queue ["Orders/Queue Lifecycle"]
        RAW["Order Status: RAW"]
        BATCHING["Order Status: BATCHING"]
        READY["Order Status: READY <br> + Assigned to Job"]
    end

    %% Subgraph 2: Batching Engine
    subgraph Batching ["Batching Engine"]
        CLUSTER["clustering.py <br> Group by Location"]
        SCORE["scoring.py <br> Greedy Insertion Heuristic"]
        FEAS["feasibility.py <br> Test OSRM Routes"]
        GEN_JOB["4. Generate Optimized Job <br> Payload: Job(job_id, order_ids, stops)"]
    end

    %% Subgraph 3: Dispatcher
    subgraph Dispatcher ["5-Wave Dispatcher"]
        SELECTION["drivers/selection.py <br> build_driver_waves"]
        DISPATCH_LOOP["dispatch/dispatcher.py <br> dispatch_job_async_loop"]
        LOCK["db_lock_manager <br> resolve_driver_acceptance"]
    end

    %% Draw Connections matching the user's diagram

    %% Input to Queue
    DB -->|"1. enqueue_raw_order"| RAW
    
    %% Internal Queue Flow
    RAW -.->|"2. Rolling Horizon <br> moves ripe orders"| BATCHING
    
    %% Queue out to Batching
    BATCHING --> CLUSTER
    
    %% Internal Batching Flow
    CLUSTER <--> SCORE
    SCORE <--> FEAS
    FEAS --> GEN_JOB
    
    %% Batching out to Ready Queue
    GEN_JOB --> READY
    
    %% Ready Queue pops to Dispatcher
    READY -.->|"5. External App Pops <br> Ready Job"| SELECTION
    
    %% Fetching drivers from DB
    DB -.->|"6. Fetch all 60 <br> Online Drivers"| SELECTION
    
    %% Dispatcher internal workflow
    SELECTION -.->|"7. Generate Wave Array <br> Payload: [[D1..], [], [D3], [], []]"| DISPATCH_LOOP
    DISPATCH_LOOP -.->|"8. Loop through Waves 1-5 <br> & Publish Order"| FIREBASE
    
    %% Firebase to Lock Manager upon Driver Action
    FIREBASE -->|"9. Driver Taps Accept"| LOCK
    
    %% Lock Manager validates to DB
    LOCK -.->|"10. Update DB Capacity"| DB

    %% Color & Styling classes matching the image
    classDef yellowBox fill:#fffde7,stroke:#fbc02d,stroke-width:2px,color:#000;
    classDef lightGreenBox fill:#e8f5e9,stroke:#4caf50,stroke-width:2px,color:#000;
    classDef orangeBox fill:#ffe0b2,stroke:#f57c00,stroke-width:2px,color:#000;
    classDef greyWhiteBox fill:#ffffff,stroke:#9e9e9e,stroke-width:2px,color:#000;
    classDef blueCyl fill:#64b5f6,stroke:#1976d2,stroke-width:2px,color:#000;
    classDef firebaseNode fill:#ffcc80,stroke:#e65100,stroke-width:2px,color:#000;

    class RAW,BATCHING yellowBox;
    class READY lightGreenBox;
    class GEN_JOB orangeBox;
    class CLUSTER,SCORE,FEAS,SELECTION,DISPATCH_LOOP,LOCK greyWhiteBox;
    class DB blueCyl;
    class FIREBASE firebaseNode;
```
