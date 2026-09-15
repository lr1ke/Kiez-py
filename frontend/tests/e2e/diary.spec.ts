import { test,expect } from '@playwright/test';
// Avoid requesting OSM tiles from an automated browser; polygons and previews still exercise Leaflet.
test.beforeEach(async({page})=>{await page.route('**/tile.openstreetmap.org/**',route=>route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')}));});
test('map discovery, archive and missing Google errors remain usable',async({page})=>{
 await page.goto('/');await expect(page.getByRole('heading',{name:'Every place has a story.'})).toBeVisible();
 await expect(page.locator('.leaflet-container')).toBeVisible();await page.screenshot({path:'test-results/home-desktop.png',fullPage:true});
 await page.getByRole('button',{name:/Reuterkiez/}).click();await expect(page.locator('.map-preview h3')).toHaveText('Reuterkiez');
 await page.getByRole('link',{name:'Read notes',exact:true}).click();await expect(page.getByRole('heading',{name:'Reuterkiez.'})).toBeVisible();
 await page.getByRole('link',{name:'Open the archive'}).click();await page.locator('.archive-list > a').first().click();await expect(page.locator('.chronicle-prose')).not.toBeEmpty();
 await page.getByRole('button',{name:'Listen',exact:true}).click();await expect(page.locator('.listen-block [role=alert]')).toContainText('not connected');
});
test('location-gated publication keeps both entries, retries are idempotent, removal is protected',async({page,context})=>{
 await context.grantPermissions(['geolocation']);await context.setGeolocation({latitude:52.4917,longitude:13.415,accuracy:10});
 await page.goto('/kiez/graefekiez');await page.getByRole('button',{name:/Leave a note/}).click();await expect(page.getByRole('button',{name:'Publish my moment'})).toBeDisabled();await page.getByRole('button',{name:'Check location'}).click();await expect(page.getByText('You’re writing in')).toBeVisible();await page.getByLabel('Your nickname').fill('Test visitor');await page.getByLabel('Your moment',{exact:true}).fill('A bicycle bell and a quiet afternoon.');await page.getByLabel('Source language',{exact:true}).selectOption('en');await page.getByRole('button',{name:'Publish my moment'}).click();await expect(page.locator('.entry-text')).toHaveText('A bicycle bell and a quiet afternoon.');
 const result=await page.evaluate(async()=>{const location=await (await fetch('/api/location',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({latitude:52.4917,longitude:13.415,accuracy:10})})).json();const payload={nickname:'Test visitor',body:'Second moment, same place.',language:'en',inputMode:'text',locationToken:location.token,idempotencyKey:crypto.randomUUID()};const post=()=>fetch('/api/contributions',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json());return [await post(),await post()];});expect(result[0].id).toBe(result[1].id);
 await page.reload();await expect(page.locator('.entry-text')).toHaveText('Second moment, same place.');
 const response=await page.request.post('/api/admin/remove',{data:{id:result[0].id}});expect(response.status()).toBe(401);
});
test('mobile pages fit without horizontal overflow and composer is keyboard accessible',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:'test-results/home-mobile.png',fullPage:true});
 await page.goto('/kiez/graefekiez');await page.getByRole('button',{name:/Leave a note/}).click();await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('Berlin only search, aliases and location rejection', async ({page}) => {
  await page.goto('/');
  await expect(page.locator('.neighborhood-row')).toHaveCount(4);
  await expect(page.locator('body')).not.toContainText('Hamburg');
  await page.getByRole('textbox', {name:'Search neighborhoods'}).fill('Kreuzberg');
  await expect(page.locator('.neighborhood-row')).toHaveCount(2);
  await page.getByRole('textbox', {name:'Search neighborhoods'}).fill('Hamburg');
  await expect(page.locator('.neighborhood-row')).toHaveCount(0);
  await expect(page.getByText('No Kiez found.', {exact:false})).toBeVisible();
  const response = await page.request.post('/api/location', {data:{latitude:53.54057,longitude:9.99437,accuracy:10}});
  expect(response.status()).toBe(422);
  await page.goto('/kiez/hafencity');
  await expect(page.getByRole('heading')).toContainText('in the notes.');
});

test('failed publication keeps the draft and a recheck can publish it', async ({page,context}) => {
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({latitude:52.4917,longitude:13.415,accuracy:10});
  await page.goto('/kiez/graefekiez');
  await page.getByRole('button',{name:/Leave a note/}).click();
  await page.getByRole('button',{name:'Check location'}).click();
  await page.getByLabel('Your nickname').fill('Retry visitor');
  await page.getByLabel('Your moment',{exact:true}).fill('My draft survives an interruption.');
  await page.route('**/api/contributions', route => route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({error:'Please check your location again before publishing. Your draft is safe.'})}));
  await page.getByRole('button',{name:'Publish my moment'}).click();
  await expect(page.getByRole('alert')).toContainText('draft is safe');
  await expect(page.getByLabel('Your moment',{exact:true})).toHaveValue('My draft survives an interruption.');
  await page.unroute('**/api/contributions');
  await page.getByRole('button',{name:'Recheck'}).click();
  await page.getByRole('button',{name:'Publish my moment'}).click();
  await expect(page.locator('.entry-text')).toHaveText('My draft survives an interruption.');
});

test('publishes to the physically resolved Kiez and preserves keyboard draft', async ({page,context}) => {
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({latitude:52.4878,longitude:13.4325,accuracy:10});
  await page.goto('/kiez/graefekiez');
  await page.getByRole('button',{name:/Leave a note/}).click();
  await page.getByLabel('Your moment',{exact:true}).fill('A moment for Reuterkiez.');
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:/Leave a note/}).click();
  await expect(page.getByLabel('Your moment',{exact:true})).toHaveValue('A moment for Reuterkiez.');
  await page.getByRole('button',{name:'Check location'}).click();
  await expect(page.getByText('Your location is in a different Kiez.',{exact:false})).toBeVisible();
  await page.getByLabel('Your nickname').fill('Across the canal');
  await page.getByRole('button',{name:'Publish my moment'}).click();
  await expect(page).toHaveURL(/\/kiez\/reuterkiez$/);
  await expect(page.locator('.entry-text')).toHaveText('A moment for Reuterkiez.');
});

test('queued Arabic translation and cancellation retain the existing controls', async ({page}) => {
  await page.route('**/api/translate', r=>r.fulfill({status:202,contentType:'application/json',body:JSON.stringify({jobId:'browser-test-job',status:'pending'})}));
  await page.route('**/api/jobs/browser-test-job', r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:'browser-test-job',status:'completed',result:{text:'مرحبا من الحي',language:'ar',translated:true}})}));
  await page.goto('/kiez/schillerkiez');
  await page.getByRole('combobox',{name:'Listening language'}).selectOption('ar');
  await page.getByRole('button',{name:'Translate',exact:true}).click();
  await expect(page.locator('.translation p')).toHaveText('مرحبا من الحي');
  await expect(page.locator('.translation p')).toHaveAttribute('dir','rtl');
  let cancelled=false;
  await page.route('**/api/speech', r=>r.fulfill({status:202,contentType:'application/json',body:JSON.stringify({jobId:'cancel-test-job',status:'pending'})}));
  await page.route('**/api/jobs/cancel-test-job', r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:'cancel-test-job',status:'pending'})}));
  await page.route('**/api/jobs/cancel-test-job/cancel', r=>{cancelled=true;return r.fulfill({status:200,contentType:'application/json',body:'{"ok":true}'});});
  await page.getByRole('button',{name:'Listen',exact:true}).click();
  await page.getByRole('button',{name:'Cancel',exact:true}).click();
  await expect.poll(()=>cancelled).toBe(true);
  await expect(page.getByRole('button',{name:'Listen',exact:true})).toBeVisible();
});

test('voice recording produces an editable transcript before any publication', async ({page,context}) => {
  await context.grantPermissions(['microphone','geolocation']);
  await context.setGeolocation({latitude:52.4917,longitude:13.415,accuracy:10});
  await page.route('**/api/capabilities', r=>r.fulfill({status:200,contentType:'application/json',body:'{"available":true,"languages":["en","de","tr","ar","es"]}'}));
  await page.route('**/api/transcribe', r=>r.fulfill({status:202,contentType:'application/json',body:'{"jobId":"transcript-test","status":"pending"}'}));
  await page.route('**/api/jobs/transcript-test', r=>r.fulfill({status:200,contentType:'application/json',body:'{"status":"completed","result":{"text":"Ein ruhiger Tag.","language":"de"}}'}));
  let published=false;
  page.on('request', request=>{if(request.url().endsWith('/api/contributions'))published=true;});
  await page.goto('/kiez/graefekiez');
  await page.getByRole('button',{name:/Leave a note/}).click();
  await page.getByRole('button',{name:'Speak your moment'}).click();
  await page.getByRole('button',{name:/Stop recording/}).click();
  await expect(page.getByLabel('Your moment',{exact:true})).toHaveValue('Ein ruhiger Tag.');
  await expect(page.getByText('Read and edit your transcript before publishing.',{exact:false})).toBeVisible();
  expect(published).toBe(false);
  await page.getByLabel('Your moment',{exact:true}).fill('Ein ruhiger Tag am Kanal.');
  await page.keyboard.press('Escape');
});
