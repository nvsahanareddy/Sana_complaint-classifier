"""Step 1: create a synthetic civic complaints dataset (backend/data/complaints.csv).
Run from backend/:  python -m ml.generate_data

Replace this with a real dataset later (keep the same columns):
complaint_id, text, category, ward, status, resolution, department, resolution_days
"""
import random
import pandas as pd

from app.config import DATA_PATH

random.seed(42)

WARDS = ["Indiranagar", "Koramangala", "Jayanagar", "Whitefield", "HSR Layout",
         "Malleshwaram", "Rajajinagar", "BTM Layout", "Yelahanka", "Marathahalli"]

DATA = {
    "Roads and Potholes": {
        "dept": "Public Works Department",
        "complaints": [
            "Large pothole on the main road near {w} causing accidents for two-wheelers.",
            "The road in {w} is badly damaged after the rains and full of craters.",
            "Deep potholes near the bus stop in {w}; vehicles are getting damaged.",
            "Road surface has broken up and gravel is spreading across the lane in {w}.",
            "Speed breaker in {w} is broken and has sharp edges that damage tyres.",
            "Footpath and road edge collapsed near the junction in {w}.",
        ],
        "resolutions": [
            "Potholes filled with hot mix asphalt by the road maintenance crew.",
            "Stretch resurfaced and road markings repainted.",
            "Temporary patch work done; full resurfacing scheduled after monsoon.",
        ],
    },
    "Water Supply": {
        "dept": "Water Supply Board",
        "complaints": [
            "No water supply in {w} for the last three days.",
            "Water coming from the tap is muddy and smells bad in {w}.",
            "Low water pressure in our apartment area in {w} every morning.",
            "Main water pipeline is leaking on the street in {w} and wasting water.",
            "Tanker water was promised but never delivered to {w}.",
            "Contaminated drinking water causing stomach illness in {w}.",
        ],
        "resolutions": [
            "Leaking pipeline repaired and supply restored.",
            "Pipes flushed and chlorination done; water quality tested and cleared.",
            "Valve adjusted to fix pressure; supply schedule corrected.",
        ],
    },
    "Garbage and Sanitation": {
        "dept": "Solid Waste Management",
        "complaints": [
            "Garbage has not been collected in {w} for a week and it smells terrible.",
            "Overflowing dustbin at the corner in {w} attracting stray dogs and flies.",
            "People dumping waste on the empty plot in {w}; needs cleaning.",
            "Public toilet in {w} is filthy and has no water.",
            "Burning of garbage in the open in {w} is causing smoke.",
            "Garbage truck skips our lane in {w} regularly.",
        ],
        "resolutions": [
            "Garbage cleared and daily collection route corrected.",
            "Additional bins placed and cleaning frequency increased.",
            "Fine imposed on offenders and site cleaned by sanitation staff.",
        ],
    },
    "Street Lights": {
        "dept": "Electricity Department",
        "complaints": [
            "Street lights are not working on the main road in {w}; area is unsafe at night.",
            "Streetlight pole in {w} is flickering and switching on and off.",
            "Entire lane in {w} is dark because lamps have been dead for weeks.",
            "Street light stays on during the day in {w}, wasting electricity.",
            "Broken street light pole leaning dangerously near the park in {w}.",
        ],
        "resolutions": [
            "Faulty lamps and fuse replaced; lights working.",
            "Timer/photocell fixed so lights switch on only at night.",
            "Damaged pole replaced by the electrical maintenance team.",
        ],
    },
    "Drainage and Sewage": {
        "dept": "Sewerage Board",
        "complaints": [
            "Sewage overflowing on the road in {w} and entering houses.",
            "Blocked storm water drain in {w} causing waterlogging after rain.",
            "Open manhole without cover in {w} is a danger to pedestrians.",
            "Foul smell from clogged drain near the market in {w}.",
            "Drain water mixing with drinking water lines in {w}.",
        ],
        "resolutions": [
            "Drain desilted using a jetting machine and overflow stopped.",
            "Manhole cover replaced and area barricaded.",
            "Sewer line unblocked and area disinfected.",
        ],
    },
    "Public Transport": {
        "dept": "Transport Corporation",
        "complaints": [
            "Bus on the route through {w} is always late and overcrowded.",
            "Bus stop shelter in {w} is broken and has no seating.",
            "Bus driver was rude and did not stop at the designated stop in {w}.",
            "Need more buses during peak hours from {w} to the city centre.",
            "Bus route timings not displayed at the stop in {w}.",
        ],
        "resolutions": [
            "Additional trips added during peak hours on the route.",
            "Bus shelter repaired and timetable board installed.",
            "Driver counselled and warning issued by depot manager.",
        ],
    },
    "Noise and Pollution": {
        "dept": "Pollution Control Board",
        "complaints": [
            "Loud music from a function hall in {w} continues past midnight.",
            "Factory in {w} releasing thick black smoke every evening.",
            "Construction dust is covering our homes in {w}; no water sprinkling.",
            "Continuous honking and noise from the generator near residences in {w}.",
            "Chemical smell from a nearby unit is making it hard to breathe in {w}.",
        ],
        "resolutions": [
            "Inspection carried out and notice issued to the violator.",
            "Sound limits enforced; venue warned and monitored.",
            "Dust control measures made mandatory at the construction site.",
        ],
    },
    "Encroachment and Illegal Construction": {
        "dept": "Town Planning Department",
        "complaints": [
            "Shops have encroached on the footpath in {w}; pedestrians walk on the road.",
            "Illegal construction going on without permission in {w}.",
            "Vehicles parked permanently on the public road in {w} blocking traffic.",
            "Building extended onto the public road in {w}.",
            "Street vendors blocking the entire lane near the station in {w}.",
        ],
        "resolutions": [
            "Encroachment cleared during a joint drive with the police.",
            "Stop-work notice issued and illegal portion demolished.",
            "Vendors relocated to a designated vending zone.",
        ],
    },
}

PREFIX = [
    "", "", "", "Please help: ", "Urgent notice: ", "This has been going on for days. ",
    "Dear officials, ", "Attention ward office: ", "Severe civic issue: ",
    "Since yesterday morning, ", "Repeated grievance: ", "Immediate intervention required: "
]
SUFFIX = [
    "", "", "", " Kindly take action.", " Residents in our layout are very upset.",
    " Please resolve at the earliest.", " Can someone please look into this ASAP?",
    " It has become very hazardous for pedestrians.", " Causing huge inconvenience to the public.",
    " Situation is getting worse day by day."
]


def build(n_per_class: int = 80) -> pd.DataFrame:
    rows, cid = [], 1
    for cat, info in DATA.items():
        for _ in range(n_per_class):
            ward = random.choice(WARDS)
            text = (random.choice(PREFIX)
                    + random.choice(info["complaints"]).format(w=ward)
                    + random.choice(SUFFIX))
            resolved = random.random() < 0.7
            rows.append({
                "complaint_id": cid,
                "text": text,
                "category": cat,
                "ward": ward,
                "status": "Resolved" if resolved else "Pending",
                "resolution": random.choice(info["resolutions"]) if resolved else "",
                "department": info["dept"],
                "resolution_days": random.randint(1, 14) if resolved else None,
            })
            cid += 1
    return pd.DataFrame(rows).sample(frac=1, random_state=42).reset_index(drop=True)


if __name__ == "__main__":
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = build()
    df.to_csv(DATA_PATH, index=False)
    print(f"Saved {len(df)} complaints to {DATA_PATH}")
    print(df["category"].value_counts())
