# CAL-1 interruption recovery — first checkpoint

Recovered the accessible unpublished workspace at `/workspace/scratch/0fac1d113cf9/charlie`. Remote independently verified at `f5bc3955bfacddca3445eb218fbff2d51de0caba`. No implementation reconstruction was necessary. Original tracked patch, source snapshot and prior JUnit logs were preserved before testing.

Fresh independent host validation: **222 focused tests passed in 38.77 seconds**, including actual Pi entry point, transport, Pico command handler/state machine with simulated camera/PWM, withheld GP10, supported retreat, camera correction and deployment rollback. Compilation and whitespace validation passed. Hashes, environment and exact results are in `validation-cal1-brain.json`. Prior JUnit reports are historical evidence, not this session's test result.

This checkpoint preserves the interrupted integrated implementation. No Pi, Pico, firmware, physical movement or gameplay was accessed. Software acceptance review continues after publication; the deployment helper is not yet the final approved package. Native Pi/MicroPython and physical powered-start/envelope qualification remain open.
