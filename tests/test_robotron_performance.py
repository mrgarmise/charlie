import json
from experiments.ppal.evaluate_robotron_shadow import evaluate
from experiments.ppal.performance_ledger import append_record

def sh(now,pred, objects=()):
    return {"prediction":{"player_now":now,"player_predicted":pred,
      "targets":list(objects),"threats":[]},"differs":False}

def test_prediction_beats_stationary_baseline():
    r={"steps":[
      {"tick":0,"shadow":sh([0,0],[2,0])},
      {"tick":1,"shadow":sh([2,0],[4,0])},
    ]}
    e=evaluate(r)
    assert e["player"]["n"]==1
    assert e["player"]["prediction_median"]==0
    assert e["player"]["baseline_median"]==2
    assert e["player"]["wins"]==1

def test_nonadjacent_not_scored():
    r={"steps":[{"tick":0,"shadow":sh([0,0],[2,0])},
                {"tick":2,"shadow":sh([2,0],[4,0])}]}
    assert evaluate(r)["all"]["n"]==0

def test_ledger_appends_score(tmp_path):
    report=tmp_path/"run"/"report.json"; report.parent.mkdir()
    report.write_text(json.dumps({"result":"TIME LIMIT","seconds":20.0,"ticks":104}))
    ledger=tmp_path/"performance.jsonl"
    append_record(ledger,report,600,note="first real 20-second game")
    row=json.loads(ledger.read_text().strip())
    assert row["score"]==600
    assert row["objective"]=="maximize_score"
