# Hailo-8L preparation and Charlie perception contract

Target is **Raspberry Pi AI HAT+ 13 TOPS / Hailo-8L**. It is not Hailo-8 (26 TOPS)
or Hailo-10. Hailo's official Model Zoo lists YOLOv8n at 640×640 for Hailo-8L;
its repository directs Hailo-8/8L users to **Model Zoo v2.x with Dataflow Compiler
v3.x**. Current Model Zoo master targets different hardware. This supplies a
credible architecture path, not evidence this custom checkpoint compiles.

Primary references:
- https://github.com/hailo-ai/hailo_model_zoo
- https://github.com/hailo-ai/hailo_model_zoo/blob/v2.x/docs/HAILO8L_object_detection.rst
- https://github.com/hailo-ai/hailo_model_zoo/tree/v2.x/training/yolov8
- https://docs.ultralytics.com/modes/export/

## Export actually implemented

YOLOv8n convolution/C2f/SPPF backbone and three-scale detection head, pinned
Ultralytics 8.3.203. Input defaults to 640; engineering fixtures use 64 and are
**not** a deployable Robotron calibration set. FP32 ONNX, opset 11, batch one,
fixed square RGB NCHW input, exported Detect head with dynamic shapes disabled.
No NMS is embedded. The export is checked with ONNX checker and, when installed,
ONNX Runtime/Torch numerical comparison on a fixed zero input. This checks export
consistency, not actual-image precision, quantization or compiler support.

Preprocessing: aspect-preserving centered letterbox with pad 114, RGB channel
order, float32 `/255`, NCHW. Raw output is `[1,4+C,N]`, decoded center-x/y/width/
height plus per-class probabilities; apply confidence 0.25, class-aware NMS IoU
0.7, then remove padding/divide scale to source coordinates. Runtime head/export
node names and Hailo postprocessing may differ; do not assume a stock COCO
80-class configuration matches this custom C-class model.

Deployment bundle includes `best.pt`, `best.onnx`, `model.json`, `deployment.json`
and `hailo-calibration/*.png`. Calibration samples are at most 128 **training**
pixels, in source RGB dimensions; they are not claimed representative or sufficient.
Use authentic diverse training-only observations and independently validate the
compiler calibration preprocessing/normalization. Never calibrate on held-out
validation/test images. Tiny synthetic bundles are only structural fixtures.

## Separate compiler host procedure (not executed here)

1. Obtain Hailo's supported Dataflow Compiler 3.x environment for the chosen
   Model Zoo v2.x release on its supported host OS. Record exact Zoo, DFC, SDK,
   HailoRT/driver/firmware versions. Mint may need a supported container/VM; do not
   assume native compiler support. The Lab only detects executables and never
   installs a compiler or runs compilation implicitly.
2. Inspect `hailomz compile --help` and the **v2.x** YOLOv8 custom-retraining guide.
   Select YOLOv8n configuration, target `hailo8l`, custom checkpoint/classes and
   actual training calibration directory. Typical command template, contingent
   on your installed v2.x CLI and verified graph/config:

   ```bash
   hailomz compile yolov8n --ckpt best.onnx --hw-arch hailo8l \
     --calib-path /absolute/authentic-training-calibration --classes YOUR_CLASS_COUNT
   ```

3. Validate parse start/end nodes against the actual ONNX graph. The DFL/decoded
   output may need to be cut back to the six box/class convolution endpoints
   before Hailo's supported YOLO postprocessing. Adapt the network YAML/model
   script/NMS class count and input shape; test operators, sigmoid/softmax/DFL,
   layout, resize and normalization. Do not interpret ONNX checker success as
   parser/operator compatibility.
4. Evaluate FP32→quantized predictions on independent evaluation observations
   under a frozen comparison protocol. Check small sprites, dark scenes,
   confidence calibration, missed humans/player and class confusion; retain
   parser/compiler/quantization logs, calibration manifest and HEF hash.
5. Only with separate deployment approval, install the matching Pi HailoRT/driver
   stack and measure camera-independent recorded-frame inference on the actual
   Hailo-8L. Report latency, throughput, temperature, memory and detection quality.
   Validate decoding and coordinate maps against FP32. A HEF for another Hailo
   architecture does not satisfy this requirement. No HEF or hardware performance
   claim is made by this feature.

## Stable hardware-independent interface

`CandidateDetector(lab, model_id).observe(PIL_image, source_frame_id=..., timestamp=...)`
returns schema `charlie-perception-candidate-v1`: objects with `class_name`,
`x/y/w/h` in source pixels, confidence, uncertainty, origin and model ID; plus
frame timestamp/identifier, model ID/version, processing latency, dataset and
checkpoint provenance, authenticity category, qualification, observation-only
status and `physical_authorization: false`. Caller supplies the original frame
identity/timestamp; file mtime must not be relabeled as exposure time.

`CandidateDetector.detect(frame)` implements the existing Charlie detector
protocol (`experiments.ppal.eyes.detectors.Detection`). Its
`observation_only=True` makes existing `VisionPipeline` return **no WorldState**.
That compatibility bridge maps player/human/threat for legacy diagnostics; the
rich `observe` packet preserves actual classes/confidence/uncertainty. Generic
`detect` uses caller-unspecified frame metadata and should not be used for
provenance-sensitive measurements. No tracker, SELF verification, gameplay state,
PPAL actions, controller or authorization pathway is connected. Future Hailo
backends must implement the same packet without turning detection into agency
or action authority.
