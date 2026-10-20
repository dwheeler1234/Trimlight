/* Build a standalone preview with simulated state, not connected to Home Assistant. */
const fs = require("node:fs");
const path = require("node:path");
const test = fs.readFileSync(path.join(__dirname, "test_pattern_card.cjs"), "utf8");
const cssHtml = test.match(/await page\.setContent\(`([\s\S]*?)`\);/)[1];
const setup = test.match(/await page\.evaluate\(\(\) => \{([\s\S]*?)\n    \}\);/)[1];
const card = fs.readFileSync(path.join(__dirname, "../www/trimlight-pattern-card.js"), "utf8");
const output = process.argv[2] || path.join(__dirname, "../work/trimlight-pattern-preview.html");
const controls = `<style>body{max-width:390px;margin:auto}nav{display:flex;justify-content:center;gap:12px;margin:0 0 12px}nav button{padding:8px 12px;border-radius:8px;border:1px solid var(--divider-color);background:var(--secondary-background-color);color:var(--primary-text-color);cursor:pointer}.demo-note{font:13px Arial,sans-serif;text-align:center;color:var(--secondary-text-color)}</style><p class="demo-note">Interactive preview · simulated lights only</p><nav><button id="dark">Dark theme</button><button id="light">Light theme</button></nav>`;
const themes = `document.querySelector('#light').onclick=()=>{for(const [key,value] of Object.entries({'primary-color':'#3768b7','primary-background-color':'#eef0f5','secondary-background-color':'#f4f6fa','card-background-color':'#ffffff','primary-text-color':'#1b2433','secondary-text-color':'#546174','divider-color':'#d5dbe4'}))document.documentElement.style.setProperty('--'+key,value)};document.querySelector('#dark').onclick=()=>document.documentElement.removeAttribute('style');`;
fs.mkdirSync(path.dirname(output), {recursive:true});
fs.writeFileSync(output, `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trimlight pattern editor preview</title>${controls}${cssHtml}<script>${card}</script><script>${setup}\n${themes}</script></html>`);
console.log(output);
