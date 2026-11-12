import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('stock_audit',Path(__file__).parents[1]/'tools/audit_elegoo_stock.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

def test_comparison_uses_exact_app_offset_and_detects_changed_byte():
    image=b'public image fixture';backup=bytes(audit.APP_OFFSET)+image+b'untouched partition'
    assert audit.compare_image(backup,image)['exact_bytes_equal']
    assert not audit.compare_image(backup,image[:-1]+b'!')['exact_bytes_equal']
    assert not audit.compare_image(bytes(audit.APP_OFFSET-1)+image+b'!',image)['exact_bytes_equal']

@pytest.mark.parametrize('backup,image',[(b'',b''),(b'too short',b'image'),(b'',bytes(audit.APP_SLOT+1))],ids=['empty','truncated','oversize'])
def test_short_or_oversize_inputs_are_rejected(backup,image):
    with pytest.raises(ValueError):audit.compare_image(backup,image)
