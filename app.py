import pandas as pd
from flask import Flask
from flask_cors import CORS

from analyzer import Analyzer
from dataloader import DataLoader
from helper import Helper
from datetime import datetime, timedelta

import json

app = Flask(__name__)
CORS(app)

historical_view = False


@app.route("/")
def hello_world():
    return "Hello, World!"


@app.route("/test")
def test(loader, analyzer, start_date, end_date):
    df = pd.DataFrame(
        columns=[
            "date",
            "oneHUT",
            "productiveTime",
            "p1HUT",
            "n1HUT",
            "nw1HUT",
            "hours_free",
            "unplanned_time",
            "p1hut%",
            "productive%",
            "w1HUT",
            "wastedTime",
            "nonWastedTime",
            "Np1HUT",
            "Nn1HUT",
            "Nw1HUT",
            "Nnw1HUT",
        ]
    )
    time_df = loader.fetch_data(start_date, end_date)
    # Flow calculation
    p1HUT, n1HUT, nw1HUT, w1HUT, Np1HUT, Nn1HUT, Nw1HUT, Nnw1HUT = (
        analyzer.calculate_1HUT(time_df=time_df, week=False).values()
    )
    # Unplanned time Calculation
    unplanned_time = analyzer.calculate_unplanned_time(start_date, end_date, week=False)
    # Efficiency Calculation
    hours_free, efficiency, inefficiency, productive, neutral, wasted, non_wasted = (
        analyzer.efficiency(loader, time_df, week=False).values()
    )
    oneHUT = p1HUT + n1HUT + nw1HUT + w1HUT
    df = pd.concat(
        [
            df,
            pd.DataFrame(
                [
                    [
                        start_date,
                        oneHUT,
                        productive,
                        p1HUT,
                        n1HUT,
                        nw1HUT,
                        hours_free,
                        unplanned_time,
                        efficiency,
                        round(productive / hours_free, 3),
                        w1HUT,
                        inefficiency,
                        non_wasted,
                        Np1HUT,
                        Nn1HUT,
                        Nw1HUT,
                        Nnw1HUT,
                    ]
                ],
                columns=[
                    "date",
                    "oneHUT",
                    "productiveTime",
                    "p1HUT",
                    "n1HUT",
                    "nw1HUT",
                    "hours_free",
                    "unplanned_time",
                    "p1hut%",
                    "productive%",
                    "w1HUT",
                    "wasted%",
                    "nonWastedTime",
                    "Np1HUT",
                    "Nn1HUT",
                    "Nw1HUT",
                    "Nnw1HUT",
                ],
            ),
        ]
    )
    start_date, end_date = analyzer.prev_week(start_date, end_date)


@app.route("/metrics")
def metrics():
    # response = jsonify({"message": "Data from Python serveOr"})
    # response.headers.add("Access-Control-Allow-Origin", "*")
    ## Getting Toggl & Calendar Data
    l = DataLoader()
    a = Analyzer()
    now = datetime.now()

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
        start_date, end_date = "2024-05-20", "2024-05-26"
        start_date, end_date = a.prev_week(start_date, end_date, times=0)
        print(start_date, end_date)
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        now_df = l.get_toggl_current_task()
        start_datetime, end_datetime = now - timedelta(days=now.weekday()), now

    start_datetime = start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    end_datetime = end_datetime.replace(hour=23, minute=59, second=59, microsecond=0)
    start_date, end_date = str(start_datetime)[:10], str(end_datetime)[:10]
    time_df = l.fetch_data(start_date, end_date)
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

    # Getting Distraction Data
    df = pd.read_csv(
        "/Users/haseab/Desktop/Desktop/backed-up/backed-scripts/Python/TiBA/src/keyboard_shortcut_launches.csv"
    )
    df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
    df = df[(df["Time"] >= start_datetime) & (df["Time"] <= end_datetime)]
    df.set_index("Time", inplace=True)
    command_df = df[df["Keyboard Shortcut"] == "Command + `"]
    daily_counts = command_df.resample("D").count()
    daily_counts.index = daily_counts.index.strftime("%Y-%m-%d")
    daily_counts = (daily_counts / 2).astype(int)
    daily_counts_dict = daily_counts.to_dict()["Keyboard Shortcut"]

    return_object = {
        "unplannedTimeList": unplanned_time,
        "oneHUTList": oneHUT,
        "p1HUTList": p1HUT,
        "n1HUTList": n1HUT,
        "nw1HUTList": nw1HUT,
        "w1HUTList": w1HUT,
        "unproductiveList": wasted,
        "hoursFreeList": hours_free,
        "efficiencyList": efficiency,
        "productiveList": productive,
        "distractionCountList": daily_counts_dict,
        "inefficiencyList": inefficiency,
        "flow": flow,
        "startDate": start_date,
        "endDate": end_date,
    }

    pretty_json = json.dumps(return_object, indent=4)
    print(pretty_json)
    return {"status": 200, "data": return_object}


if __name__ == "__main__":
    app.run(debug=True, port=3002)
