from flask import Flask, render_template, jsonify
import requests
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# --- CONFIGURATION: Train List (Tenkasi <-> Kila Kadaiyam) ---
# Times are scheduled departure from the STARTING station of this segment.
# Direction: TSI_TO_TEN (Tenkasi -> Pavurchatram)
# Direction: TEN_TO_TSI (Pavurchatram -> Tenkasi)

TRAINS = [
    # --- Tenkasi (TSI) -> Tirunelveli (TEN) ---
    {"no": "16792", "name": "Palaruvi Exp", "time": "03:05", "dir": "TSI_TO_TEN", "days": "Daily"},
    {"no": "06029", "name": "MTP TEN Spl", "time": "05:00", "dir": "TSI_TO_TEN", "days": "Mon/Tue"},
    {"no": "16846", "name": "Sengottai Erode Exp", "time": "05:25", "dir": "TSI_TO_TEN", "days": "Daily"},
    {"no": "06686", "name": "Sengottai Passenger", "time": "06:55", "dir": "TSI_TO_TEN", "days": "Daily"},
    {"no": "06658", "name": "SCT TEN Passenger", "time": "14:50", "dir": "TSI_TO_TEN", "days": "Daily"},
    {"no": "20684", "name": "SCT TBM SF Exp", "time": "16:44", "dir": "TSI_TO_TEN", "days": "Mon, Wed, Fri"},
    {"no": "06688", "name": "SCT TEN Passenger", "time": "18:15", "dir": "TSI_TO_TEN", "days": "Daily"},

    # --- Tirunelveli (TEN) -> Tenkasi (TSI) ---
    # Times approx at Pavurchatram (PCM) for logic
    {"no": "16791", "name": "Palaruvi Exp", "time": "00:23", "dir": "TEN_TO_TSI", "days": "Daily"},
    {"no": "06685", "name": "TEN SCT Passenger", "time": "07:45", "dir": "TEN_TO_TSI", "days": "Daily"},
    {"no": "20683", "name": "TBM SCT SF Exp", "time": "09:47", "dir": "TEN_TO_TSI", "days": "Mon, Wed, Fri"},
    {"no": "06657", "name": "TEN SCT Passenger", "time": "18:50", "dir": "TEN_TO_TSI", "days": "Daily"}
]

def get_live_delay_mock(train_no):
    # In a real app, this would scrape 'Where Is My Train' or NTES
    # For now, returning 0 or random small delays for demo
    return 0

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    current_mins = now.hour * 60 + now.minute
    
    # Initialize Status
    response = {
        "gates": {
            "ariapuram": {"status": "OPEN", "color": "green", "msg": "No trains nearby"},
            "mettur": {"status": "OPEN", "color": "green", "msg": "No trains nearby"},
            "pavurchatram": {"status": "OPEN", "color": "green", "msg": "No trains nearby"}
        },
        "upcoming": []
    }

    # Station Offsets (Minutes from Start)
    # TSI (0) -> Ariapuram Gate (8) -> Mettur Stn (12) -> Mettur Gate (14) -> PCM (18)
    ROUTE_MAP = {
        "TSI_TO_TEN": {"start": "TSI", "ariapuram_gate": 8, "mettur_stn": 12, "mettur_gate": 14, "pcm": 18},
        "TEN_TO_TSI": {"start": "PCM", "mettur_gate": 4, "mettur_stn": 6, "ariapuram_gate": 10, "tsi": 18}
    }

    for train in TRAINS:
        # Parse Time
        h, m = map(int, train['time'].split(':'))
        sched_mins = h * 60 + m
        delay = get_live_delay_mock(train['no'])
        actual_start_mins = sched_mins + delay
        
        # Calculate Position relative to now
        time_diff = actual_start_mins - current_mins
        
        # 1. ADD TO UPCOMING LIST (If train is in next 4 hours)
        if -20 < time_diff < 240:
            est_time = now.replace(hour=0, minute=0, second=0) + timedelta(minutes=actual_start_mins)
            response["upcoming"].append({
                "name": train["name"],
                "time": est_time.strftime("%I:%M %p"),
                "delay": f"{delay} min delay" if delay > 0 else "On Time",
                "direction": "Towards Tirunelveli" if train['dir'] == "TSI_TO_TEN" else "Towards Tenkasi"
            })

        # 2. CALCULATE GATE LOGIC
        # Logic: We check if the train is currently impacting any gate
        
        if train['dir'] == "TSI_TO_TEN":
            # --- Sequence: TSI -> Ariapuram Gate -> Mettur Stn -> Mettur Gate -> PCM ---
            
            # Ariapuram Gate Logic: Closes when train leaves TSI, Opens when train reaches Mettur Stn
            t_leave_tsi = time_diff
            t_reach_mettur_stn = time_diff + 12
            
            if 0 < t_leave_tsi <= 15: # 15 mins before TSI departure
                response["gates"]["ariapuram"] = {"status": "CLOSING SOON", "color": "orange", "msg": f"{train['name']} departing TSI soon"}
            elif t_leave_tsi <= 0 and t_reach_mettur_stn > 0: # Train is between TSI and Mettur Stn
                response["gates"]["ariapuram"] = {"status": "CLOSED", "color": "red", "msg": f"{train['name']} crossing now"}
            
            # Mettur Gate Logic: Closes when train reaches Mettur Stn, Opens when train reaches PCM
            t_reach_pcm = time_diff + 18
            
            if 0 < t_reach_mettur_stn <= 10: 
                response["gates"]["mettur"] = {"status": "CLOSING SOON", "color": "orange", "msg": f"{train['name']} near Ariapuram"}
            elif t_reach_mettur_stn <= 0 and t_reach_pcm > 0: # Train is between Mettur Stn and PCM
                response["gates"]["mettur"] = {"status": "CLOSED", "color": "red", "msg": f"{train['name']} crossing now"}

        elif train['dir'] == "TEN_TO_TSI":
            # --- Sequence: PCM -> Mettur Gate -> Mettur Stn -> Ariapuram Gate -> TSI ---
            
            # Mettur Gate Logic: Closes when train leaves PCM
            t_leave_pcm = time_diff
            t_reach_mettur_stn = time_diff + 6
            
            if 0 < t_leave_pcm <= 15:
                response["gates"]["mettur"] = {"status": "CLOSING SOON", "color": "orange", "msg": f"{train['name']} near Pavurchatram"}
            elif t_leave_pcm <= 0 and t_reach_mettur_stn > 0:
                response["gates"]["mettur"] = {"status": "CLOSED", "color": "red", "msg": f"{train['name']} crossing now"}
                
            # Ariapuram Gate Logic: Closes when train reaches Mettur Stn
            t_reach_tsi = time_diff + 18
            
            if 0 < t_reach_mettur_stn <= 5:
                 response["gates"]["ariapuram"] = {"status": "CLOSING SOON", "color": "orange", "msg": f"{train['name']} at Mettur Stn"}
            elif t_reach_mettur_stn <= 0 and t_reach_tsi > 0:
                 response["gates"]["ariapuram"] = {"status": "CLOSED", "color": "red", "msg": f"{train['name']} crossing now"}

    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
