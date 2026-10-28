"""Opt-in actual Chromium desktop/mobile-emulation acceptance, synthetic only."""
import os
from pathlib import Path
import pytest
from test_human_questions_http import server, TOKEN
from test_human_interaction import fixture_record, ask
from memory.evidence import EvidenceJournal
from memory.human_interaction import HumanInteractionGateway
from memory.learning_projects import LearningExecutive

pytestmark=pytest.mark.skipif(os.environ.get('CHARLIE_BROWSER_TESTS')!='1', reason='requires installed Chromium; run dedicated browser CI')


@pytest.mark.parametrize('viewport',[dict(width=1280,height=900),dict(width=390,height=844)])
def test_real_browser_delayed_answer(server,viewport,tmp_path):
    from playwright.sync_api import sync_playwright
    port,path,pet_id=server
    # Delayed evidence from a second requester uses the same generic renderer.
    j=EvidenceJournal(path);g=HumanInteractionGateway(j)
    robotron_id=ask(LearningExecutive(j,None),g,fixture_record(j,'robotron'))['question_id'];j.close()
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        context=browser.new_context(viewport=viewport,http_credentials=dict(username='operator',password=TOKEN))
        page=context.new_page();page.goto(f'http://127.0.0.1:{port}/')
        assert page.get_by_role('heading',name="Charlie's questions").is_visible()
        assert page.locator('body').evaluate('(e)=>e.scrollWidth<=window.innerWidth')
        cards=page.locator('article')
        assert cards.count()==2
        for index,value in [(0,'unreadable or ambiguous result'),(1,'cat')]:
            card=cards.nth(index)
            card.locator('select').select_option(value)
            card.locator('textarea').fill('Synthetic browser review; fallible observation')
            card.get_by_role('button').click()
            page.wait_for_load_state()
        page.reload()
        assert page.locator('form').count()==0
        out=Path(os.environ.get('CHARLIE_BROWSER_ARTIFACTS',str(tmp_path)))
        out.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(out/f'questions-{viewport["width"]}.png'),full_page=True)
        context.close();browser.close()
    j=EvidenceJournal(path);g=HumanInteractionGateway(j)
    assert g.questions()[pet_id]['status']=='answered'
    assert g.questions()[robotron_id]['status']=='answered'
    assert len(g.results('pet_observe'))==len(g.results('robotron'))==1
    j.close()
