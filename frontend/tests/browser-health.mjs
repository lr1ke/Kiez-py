import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
try {
  const page=await browser.newPage({viewport:{width:390,height:844}});
  const errors=[];
  page.on('pageerror', error=>errors.push(error.message));
  page.on('console', message=>{if(message.type()==='error' && /hydrat|match|uncaught/i.test(message.text()))errors.push(message.text());});
  await page.route('**/tile.openstreetmap.org/**',r=>r.abort());
  for(const path of ['/','/kiez/graefekiez','/kiez/reuterkiez/archive']) {
    await page.goto(`http://localhost:3001${path}`,{waitUntil:'networkidle'});
    if(path==='/kiez/graefekiez') {
      await page.getByRole('button',{name:/Leave a note/}).click();
      await page.keyboard.press('Escape');
    }
  }
  console.log(JSON.stringify(errors,null,2));
  assert.equal(errors.length,0,'Browser runtime/hydration errors');
  console.log('Browser runtime and hydration checks passed.');
}finally{await browser.close();}
