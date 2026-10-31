"""Actual desktop/mobile browser and HTTP adapter, synthetic shared sources only."""
from dataclasses import replace
import threading
import time
import socket
import pytest
pw=pytest.importorskip('playwright.sync_api',reason='independent browser CI installs Playwright')
from tests.test_mobile_console import fixture
from ui.dashboard import start_dashboard
from stimulus.bus import Observation


@pytest.mark.parametrize('viewport',[{'width':1440,'height':1000},{'width':390,'height':844}])
def test_browser_hold_release_touch_focus_disconnect_emergency_and_monitoring(viewport):
    try:
        probe=socket.socket();probe.close()
    except PermissionError:pytest.skip('session denies loopback sockets')
    s=fixture();s.now[0]=time.monotonic()
    # Replace fixture's earlier sequence with an explicitly new generation.
    stop=threading.Event();sequence=[2]
    def feed():
        while not stop.wait(.04):
            s.now[0]=time.monotonic();sequence[0]+=1
            s.bus.publish_frame('elegoo-v4',s.producer,replace(s.frame,id='native-fixture:'+str(sequence[0]),
                sequence=sequence[0],received_at=s.now[0],stream_generation='browser-fixture'))
            owner=s.bus.observation_owners['elegoo-pose']
            s.bus.publish_observation('elegoo-pose',owner,Observation('elegoo-pose',sequence[0],s.now[0],
                {'pan_degrees':90},{'synthetic':True},'browser-pose'))
    worker=threading.Thread(target=feed);worker.start()
    server=start_dashboard(None,'m'*40,mobile=s.c,drive_token='d'*40,port=0)
    try:
        with pw.sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page(viewport=viewport,has_touch=viewport['width']<500)
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.address[1]}/mobile')
            page.locator('#mc-monitor').fill('m'*40);page.locator('#mc-drive').fill('d'*40)
            page.locator('#mc-connect button').first.click()
            page.wait_for_function("!document.querySelector('#mc-acquire').disabled")
            assert page.locator('#mc-monitor').input_value()==''
            page.locator('#mc-acquire').click();page.wait_for_function("!document.querySelector('#mc-stop').disabled")
            before=s.base.pulse.call_count
            page.locator('h1').click();page.keyboard.down('w')
            page.wait_for_timeout(350);page.keyboard.up('w');page.wait_for_timeout(200)
            assert s.base.pulse.call_count>before
            calls=s.base.pulse.call_count;page.wait_for_timeout(200);assert s.base.pulse.call_count==calls
            button=page.get_by_role('button',name='Forward left',exact=True)
            button.scroll_into_view_if_needed();button.hover();page.mouse.down();page.wait_for_timeout(350);page.mouse.up()
            assert s.base.pulse.call_count>calls
            page.evaluate("window.dispatchEvent(new Event('blur'))")
            page.wait_for_function("document.querySelector('#mc-release').disabled")
            page.locator('#mc-acquire').click();page.wait_for_function("!document.querySelector('#mc-release').disabled")
            page.locator('#mc-emergency').click()
            page.wait_for_timeout(200);assert s.e._safety_stopped
            page.locator('#mc-disconnect').click();assert s.c.lease is None
            page.screenshot(path=f'mobile-{viewport["width"]}.png',full_page=True)
            assert not errors
            browser.close()
    finally:
        stop.set();worker.join(2);server.close()
