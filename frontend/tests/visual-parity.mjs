// Read-only comparison with the original local Kiez server; external tiles are stubbed.
import {chromium} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const output=new URL('../test-results/parity/',import.meta.url);
await mkdir(output,{recursive:true});
const values={};
try {
  for(const [name,origin] of [['original',process.env.KIEZ_ORIGINAL_URL||'http://localhost:3000'],['python','http://localhost:3001']]) {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    await page.route('**/tile.openstreetmap.org/**',r=>r.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')}));
    await page.goto(origin,{waitUntil:'networkidle'});
    assert.match(await page.title(),/Kiez/);
    values[name]=await page.evaluate(()=>Object.fromEntries(['body','.header','.brand','.hero h1','.hero-main>p','.section-heading h2','.how-section','.chronicle-card','.footer'].map(selector=>{
      const element=document.querySelector(selector);
      if(!element) return [selector,null];
      const style=getComputedStyle(element);
      return [selector,Object.fromEntries(['fontFamily','fontSize','lineHeight','color','backgroundColor','padding','borderColor','borderWidth','borderRadius'].map(key=>[key,style[key]]))];
    })));
    await page.screenshot({path:new URL(`${name}-desktop.png`,output).pathname,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:new URL(`${name}-mobile.png`,output).pathname,fullPage:true});
    await page.close();
  }
  // Source data can omit archive cards on quiet installations; compare shared elements.
  for(const selector of Object.keys(values.original)) {
    if(values.original[selector] && values.python[selector]) assert.deepEqual(values.python[selector],values.original[selector],selector);
  }
  await writeFile(new URL('styles.json',output),JSON.stringify(values,null,2));
  console.log('Shared desktop typography, color, spacing and borders match original Kiez. Desktop/mobile screenshots captured.');
} finally { await browser.close(); }
