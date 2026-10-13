from experiments.ppal.marathon_robotron import established_gameplay

def test_gameplay_requires_real_action():
    assert established_gameplay({"armed":True,"acquisition":"causal",
        "steps":[{"tick":1,"action":{"move":"STAY","fire":"NONE"}}]})

def test_loss_or_failed_start_is_not_gameplay():
    assert not established_gameplay({"armed":True,"acquisition":None,"steps":[]})
    assert not established_gameplay({"armed":True,"acquisition":"x",
                                      "steps":[{"status":"player_lost"}]})
