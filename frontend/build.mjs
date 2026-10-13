import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
const cwd=dirname(fileURLToPath(import.meta.url));
await build({entryPoints:[resolve(cwd,'src/main.tsx')],outfile:resolve(cwd,'../dist/skiper-ui.js'),bundle:true,minify:true,format:'iife',target:['es2022'],jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'},legalComments:'linked',metafile:true});
console.log('Built travel tile reveal and Skiper17/47 UI.');
