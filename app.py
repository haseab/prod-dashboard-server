import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS

from src.analyzer import Analyzer
from src.dataloader import DataLoader
from src.helper import Helper
from datetime import datetime, timedelta
from src.constants import TIME_MAP
import sys
import os
import pytz


sys.path.append(os.path.dirname(os.path.realpath(__file__)))


import json

app = Flask(__name__)
CORS(app)

historical_view = False
timezone = "America/New_York"

@app.route("/")
def hello_world():
    return "Hello, World!"


@app.route("/metricsdate")
def metricsdate():

    l = DataLoader()
    a = Analyzer()
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")

    print("start date", start_date, "end date", end_date)

    current_task = l.get_toggl_current_task()
    current_activity = (
        current_task.iloc[0]["Project"] if not current_task.empty else "No Activity"
    )

    now_df = pd.DataFrame(
        columns=[
            "Id",
            "Project",
            "Description",
            "Start date",
            "Start time",
            "End date",
            "End time",
            "Tags",
            "SecDuration",
        ]
    )
    
    start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
    end_datetime = datetime.strptime(end_date, "%Y-%m-%d")

    start_datetime = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    end_datetime = end_datetime.replace(hour=23, minute=59, second=59, microsecond=0)
    
    start_date, end_date = str(start_datetime)[:10], str(end_datetime)[:10]
    time_df = l.fetch_data(start_date, end_date, timezone=timezone)
    
    master_df = pd.concat([time_df, now_df]).reset_index(drop=True)
    master_df["TagProductive"] = master_df["Tags"].str.contains("Productive")
    master_df["TagUnavoidable"] = master_df["Tags"].str.contains("Unavoidable")
    master_df["Carryover"] = master_df["Tags"].str.contains("Carryover")
    master_df["FlowExempt"] = master_df["Tags"].str.contains("FlowExempt")

    flow_df = a.group_df(master_df)
    flow = (
        round(flow_df.iloc[-1]["SecDuration"] / 3600, 3) if not historical_view else 0
    )
    master_df = master_df.drop(
        columns=["TagProductive", "TagUnavoidable", "Carryover", "FlowExempt"], axis=1
    )
    unplanned_time = a.calculate_unplanned_time(start_date, end_date, week=True)
    p1HUT, n1HUT, nw1HUT, w1HUT = a.calculate_1HUT(master_df, week=True).values()
    hours_free, efficiency, inefficiency, productive, neutral, wasted, non_wasted = (
        a.efficiency(l, master_df, week=True).values()
    )
    oneHUT = {
        date: round(
            n1HUT.get(date, 0)
            + nw1HUT.get(date, 0)
            + p1HUT.get(date, 0)
            + w1HUT.get(date, 0),
            3,
        )
        for date in n1HUT
    }

    distraction_counts = a.calculate_distraction_counts(start_date, end_date, week=True)

    return_object = {
        "unplannedTimeList": unplanned_time,
        "totalFlowList": oneHUT,
        "productiveFlowList": p1HUT,
        "n1HUTList": n1HUT,
        "nw1HUTList": nw1HUT,
        "w1HUTList": w1HUT,
        "unproductiveList": wasted,
        "hoursFreeList": hours_free,
        "efficiencyList": efficiency,
        "productiveList": productive,
        "distractionCountList": distraction_counts,
        "inefficiencyList": inefficiency,
        "flow": flow,
        "startDate": start_date,
        "endDate": end_date,
        "currentActivity": TIME_MAP[current_activity],
        "currentActivityStartTime": pd.Timestamp(f"{flow_df.iloc[-1]['Start date']} {flow_df.iloc[-1]['Start time']}").tz_localize(timezone).isoformat(),
    }

    pretty_json = json.dumps(return_object, indent=4)
    print(pretty_json)
    return {"status": 200, "data": return_object}




@app.route("/metrics")
def metrics():
    # response = jsonify({"message": "Data from Python serveOr"})
    # response.headers.add("Access-Control-Allow-Origin", "*")
    ## Getting Toggl & Calendar Data
    l = DataLoader()
    a = Analyzer()

    personal = request.args.get("personal")

    now_utc = datetime.now(pytz.utc)
    est = pytz.timezone(timezone)
    now = now_utc.astimezone(est)

    current_task = l.get_toggl_current_task(timezone=timezone)
    current_activity = (
        current_task.iloc[0]["Project"] if not current_task.empty else "No Activity"
    )

    if historical_view:
        now_df = pd.DataFrame(
            columns=[
                "Id",
                "Project",
                "Description",
                "Start date", 
                "Start time",
                "End date",
                "End time",
                "Tags",
                "SecDuration",
            ]
        )
        start_date, end_date = "2024-06-17", "2024-06-23"
        start_date, end_date = a.prev_week(start_date, end_date, times=0)
        # print("start date", start_date, "end date", end_date)
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        now_df = current_task
        if personal == "true":
            ## set start and end date to the beginning and current time of the week
            start_datetime, end_datetime = now - timedelta(days=now.weekday()), now
        else:
            ## set start date to the beggining of 7 days ago and end date to current time
            start_datetime, end_datetime = now - timedelta(days=6), now

    start_datetime = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    end_datetime = end_datetime.replace(hour=23, minute=59, second=59, microsecond=0)
    
    start_date, end_date = str(start_datetime)[:10], str(end_datetime)[:10]
    time_df = l.fetch_data(start_date, end_date, timezone=timezone)
    master_df = pd.concat([time_df, now_df]).reset_index(drop=True)
    master_df["TagProductive"] = master_df["Tags"].str.contains("Productive")
    master_df["TagUnavoidable"] = master_df["Tags"].str.contains("Unavoidable")
    master_df["Carryover"] = master_df["Tags"].str.contains("Carryover")
    master_df["FlowExempt"] = master_df["Tags"].str.contains("FlowExempt")

    flow_df = a.group_df(master_df)
    flow = (
        round(flow_df.iloc[-1]["SecDuration"] / 3600, 3) if not historical_view else 0
    )
    master_df = master_df.drop(
        columns=["TagProductive", "TagUnavoidable", "Carryover", "FlowExempt"], axis=1
    )
    unplanned_time = a.calculate_unplanned_time(start_date, end_date, week=True)
    task_pile = a.calculate_task_pile()
    p1HUT, n1HUT, nw1HUT, w1HUT = a.calculate_1HUT(master_df, week=True).values()
    hours_free, efficiency, inefficiency, productive, neutral, wasted, non_wasted = (
        a.efficiency(l, master_df, week=True).values()
    )
    oneHUT = {
        date: round(
            n1HUT.get(date, 0)
            + nw1HUT.get(date, 0)
            + p1HUT.get(date, 0)
            + w1HUT.get(date, 0),
            3,
        )
        for date in n1HUT
    }

    distraction_counts = a.calculate_distraction_counts(start_date, end_date, week=True)

    return_object = {
        "unplannedTimeList": unplanned_time,
        "totalFlowList": oneHUT,
        "productiveFlowList": p1HUT,
        "n1HUTList": n1HUT,
        "nw1HUTList": nw1HUT,
        "w1HUTList": w1HUT,
        "unproductiveList": wasted,
        "hoursFreeList": hours_free,
        "efficiencyList": efficiency,
        "productiveList": productive,
        "distractionCountList": distraction_counts,
        "inefficiencyList": inefficiency,
        "flow": flow,
        "taskPile": task_pile,
        "startDate": start_date,
        "endDate": end_date,
        "neutralActivity": current_activity in a.neutral,
        "currentActivity": TIME_MAP[current_activity],
        "currentActivityStartTime": pd.Timestamp(f"{flow_df.iloc[-1]['Start date']} {flow_df.iloc[-1]['Start time']}").tz_localize(timezone).isoformat(),
    }

    pretty_json = json.dumps(return_object, indent=4)
    print(pretty_json)
    return {"status": 200, "data": return_object}


if __name__ == "__main__":
    app.run(debug=True, port=3002)
