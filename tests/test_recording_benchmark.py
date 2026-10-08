"""Small controllerless timing-harness check; no performance threshold claim."""
from pathlib import Path
from types import SimpleNamespace
from PIL import Image


def test_incident_benchmark_measures_receipt_and_actual_source_span(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'tools'))
    import benchmark_buffered_recording as benchmark
    source=tmp_path/'software-pixels.png';Image.new('RGB',(20,20)).save(source)
    args=SimpleNamespace(output=tmp_path/'report.json',native_camera=False,source=source,
        samples=6,hz=30,visual_hz=5,rolling_seconds=1.,incident_every=2)
    result=benchmark.run_case(args,'controlled-fixture',benchmark.CaptureEvidence,benchmark.DurableRows)
    assert result['completion_receipt']=='verified' and result['failure'] is None
    assert result['source_observations']==6 and result['controller_commands']==0
    assert result['independently_qualified_findings']==0
    assert result['acquisition_span_seconds']>0 and result['acquisition_rate_hz']>0
    assert result['peak_sampled_snapshot_bytes']>0
    assert result['retained_arrival_rate_including_incidents']>0
    assert result['approximate_positive_queue_growth_frames_per_second']>=0
    assert result['pipeline']['incidents']['requests']==3
