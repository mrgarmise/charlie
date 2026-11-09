"""Test-only ephemeral certificate trust is confined to this loopback browser fixture."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('browser_handoff',root/'verify_ticket.py')
handoff=importlib.util.module_from_spec(spec);spec.loader.exec_module(handoff)

def test_browser_download_handoff_and_explicit_pinned_peer_confirmation(simulated_device,peer_modules,tmp_path):
    sync_api=pytest.importorskip('playwright.sync_api')
    TLSProtocol,SecretStore=peer_modules
    state,directory,identity,server=simulated_device
    with sync_api.sync_playwright() as playwright:
        browser=playwright.chromium.launch()
        # Ephemeral localhost fixture only; production instructs verified CA/pin enrollment.
        context=browser.new_context(ignore_https_errors=True,accept_downloads=True)
        page=context.new_page();page.goto(f'https://127.0.0.1:{server.server_port}/setup')
        page.fill('#token',identity['token']);page.fill('#ssid','fixture-network');page.fill('#password','fixture-'+str(server.server_port))
        page.click('button');page.locator('#ticket').wait_for(state='visible')
        assert not state['committed']
        assert page.input_value('#token')=='' and page.input_value('#password')==''
        with page.expect_download() as download:
            page.click('#ticket')
        path=tmp_path/'ticket.json';download.value.save_as(path)
        ticket=handoff.parse_ticket(path.read_text(),state['device_id'])
        assert 'token' not in ticket and 'password' not in ticket
        endpoint=SimpleNamespace(address='127.0.0.1',port=server.server_port,source_ip='127.0.0.1')
        class Discovery:
            def candidates(self,*args):return [endpoint]
        result=handoff.verify(ticket,TLSProtocol(SecretStore(directory)),Discovery())
        assert result['verified'] and state['committed']
        context.close();browser.close()
