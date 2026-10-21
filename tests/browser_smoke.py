"""Run against a local server; uses only a synthetic, non-private candidate."""
import os
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p, tempfile.TemporaryDirectory() as folder:
    resume=Path(folder)/'example-resume.txt'
    resume.write_text('SUMMARY:\nExperienced automation engineer.\nPROFESSIONAL EXPERIENCE:\nJan 2020 - Present\nDeveloped Python automation frameworks using Pytest for clinical trials.\nAutomated browser UI tests using Cucumber BDD scenarios.\nWorked on API testing using Postman for the platform.\nImplemented CI/CD pipelines for test suites.\nTECHNICAL SKILLS:\nAWS, Jira, Agile, TestComplete.')
    custom=Path(folder)/'custom-jd.txt'
    custom.write_text('Must Have Skills:\nUse Python and SQL to build automated test solutions.\nGood to Have:\nAWS experience is preferred for cloud test environments.')
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000')
    expect(page.locator('#jd-summary')).to_contain_text('13 mandatory')
    page.set_input_files('#resume-file',str(resume))
    expect(page.locator('#analyze-button')).to_be_enabled()
    page.click('#analyze-button')
    expect(page.locator('#report-panel')).to_be_visible()
    page.locator('.evidence-row summary').first.click()
    assert page.locator('.evidence-row').first.get_attribute('open') is not None
    for kind in ('html','pdf'):
        with page.expect_download() as download: page.click('#export-'+kind)
        assert download.value.suggested_filename.endswith('.'+kind)
    page.select_option('#status-filter','Missing')
    assert all('Missing' in s for s in page.locator('.status-badge').all_text_contents())
    page.click('#custom-toggle')
    page.set_input_files('#jd-file',str(custom))
    expect(page.locator('#requirements-view')).to_be_visible()
    expect(page.locator('.requirement-card')).to_have_count(3)
    page.click('#approve-jd')
    expect(page.locator('#analyze-button')).to_be_enabled()
    page.click('#analyze-button')
    expect(page.locator('#report-panel')).to_be_visible()
    pending=[]
    page.route('**/api/analyze',lambda route:pending.append(route))
    with page.expect_request('**/api/analyze'): page.click('#analyze-button')
    expect(page.locator('#analyze-button')).to_contain_text('Processing')
    page.click('#default-toggle')
    assert pending
    pending[0].continue_()
    expect(page.locator('#notice')).to_contain_text('changed while screening')
    expect(page.locator('#report-panel')).to_be_hidden()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
    assert not errors, errors
    browser.close()
    print('Browser checks passed: default/custom JD, review, upload, screening, evidence, filters, HTML/PDF downloads, mobile layout; no page errors.')
