import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { spawnSync } from 'child_process'
import { createRequire } from 'module'
import { load } from 'cheerio'

const require = createRequire(import.meta.url)
const mammoth = require('mammoth')

const TESSERACT = process.env.TESSERACT_PATH || 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
const PROJECT_TESSDATA = join(process.cwd(), 'server', 'tessdata')
const PDFTOPPM_CANDIDATES = [process.env.PDFTOPPM_PATH, 'pdftoppm'].filter(Boolean)
const PDFTOPPM = PDFTOPPM_CANDIDATES.find(x => x === 'pdftoppm' || existsSync(x)) || 'pdftoppm'
const clean = value => String(value || '').replace(/\s+/g, ' ').trim()
const cleanOcrText = value => clean(value).replace(/([\u3400-\u9fff])\s+(?=[\u3400-\u9fff])/g, '$1')
export function extractionQuality(blocks=[]){const scores=blocks.map(x=>Number(x.character_confidence)).filter(Number.isFinite);if(!scores.length)return{status:'not_measured',average_character_confidence:null,low_confidence_block_ratio:null,requires_human_confirmation:false};const average=scores.reduce((a,b)=>a+b,0)/scores.length,low=scores.filter(x=>x<.55).length/scores.length;return{status:average<.65||low>.35?'low':'acceptable',average_character_confidence:Math.round(average*1000)/1000,low_confidence_block_ratio:Math.round(low*1000)/1000,requires_human_confirmation:average<.65||low>.35}}

export function orderedPageBlocks(items, page, viewportWidth) {
  const blocks = items.filter(x => clean(x.str)).map((item, i) => ({ block_id:`PDF_P${page}_B${i+1}`,page,text:clean(item.str),x:Number(item.transform?.[4]||0),y:Number(item.transform?.[5]||0),width:Number(item.width||0),height:Number(item.height||0),extraction_method:'pdf_text_layer',character_confidence:1 }))
  const middle=viewportWidth/2,left=blocks.filter(x=>x.x<middle),right=blocks.filter(x=>x.x>=middle)
  // Right-aligned dates and metrics can look like a second column. When main
  // content spans the page midpoint, keep row order instead of column order.
  const hasSpanningMainContent = left.some(block => block.x + block.width >= middle - 10)
  const columns=left.length>=3&&right.length>=3&&!hasSpanningMainContent?[left,right]:[blocks]
  return columns.flatMap(column=>column.sort((a,b)=>Math.abs(a.y-b.y)>4?b.y-a.y:a.x-b.x))
}

export function removeRepeatedPageArtifacts(blocks, pageCount) {
  if (pageCount < 2) return blocks
  const occurrences = new Map()
  for (const block of blocks) {
    const edge = block.y >= 0 && (block.y < 55 || block.y > 730)
    if (!edge || block.text.length > 120) continue
    if (!occurrences.has(block.text)) occurrences.set(block.text, new Set())
    occurrences.get(block.text).add(block.page)
  }
  const repeated = new Set([...occurrences].filter(([, pages]) => pages.size >= Math.min(2, pageCount)).map(([text]) => text))
  return blocks.filter(block => !repeated.has(block.text))
}

export async function extractPdfLayout(path) {
  const pdfjs=await import('pdfjs-dist/legacy/build/pdf.mjs'),data=new Uint8Array(readFileSync(path))
  const document=await pdfjs.getDocument({data,useWorkerFetch:false,isEvalSupported:false}).promise,blocks=[]
  for(let pageNumber=1;pageNumber<=document.numPages;pageNumber++){const page=await document.getPage(pageNumber),viewport=page.getViewport({scale:1}),content=await page.getTextContent();blocks.push(...orderedPageBlocks(content.items,pageNumber,viewport.width))}
  const cleaned=removeRepeatedPageArtifacts(blocks,document.numPages);return {blocks:cleaned,page_count:document.numPages,extraction_method:'pdf_text_layer',ocr_status:'not_required',ocr_languages:[],quality:extractionQuality(cleaned)}
}

function tesseractArgs(args){return existsSync(PROJECT_TESSDATA)?['--tessdata-dir',PROJECT_TESSDATA,...args]:args}
function availableLanguages(){if(!existsSync(TESSERACT))return[];const result=spawnSync(TESSERACT,tesseractArgs(['--list-langs']),{encoding:'utf8'});return String(result.stdout||'').split(/\r?\n/).map(x=>x.trim()).filter(x=>/^[a-z_]+$/i.test(x)&&x!=='List')}
function parseTsv(tsv,page){const grouped=new Map();for(const line of String(tsv||'').split(/\r?\n/).slice(1)){const cols=line.split('\t');if(cols.length<12)continue;const text=clean(cols.slice(11).join('\t')),confidence=Number(cols[10]);if(!text||confidence<0)continue;const key=`${cols[2]}:${cols[3]}:${cols[4]}`;if(!grouped.has(key))grouped.set(key,{words:[],confidence:[],x:Number(cols[6]),y:Number(cols[7]),width:0,height:Number(cols[9])});const row=grouped.get(key);row.words.push(text);row.confidence.push(confidence);row.width=Math.max(row.width,Number(cols[6])+Number(cols[8])-row.x)}return[...grouped.values()].map((row,i)=>({block_id:`OCR_P${page}_B${i+1}`,page,text:cleanOcrText(row.words.join(' ')),x:row.x,y:row.y,width:row.width,height:row.height,extraction_method:'tesseract_ocr',character_confidence:Math.round(row.confidence.reduce((a,b)=>a+b,0)/row.confidence.length)/100}))}

export function extractPdfOcr(path,preferredLanguage='chi_sim+eng'){
  const languages=availableLanguages();if(!existsSync(TESSERACT))return{blocks:[],extraction_method:'ocr_unavailable',ocr_status:'tool_missing',ocr_languages:languages,fallback_reason:'tesseract_not_installed'}
  const required=preferredLanguage.split('+'),missing=required.filter(x=>!languages.includes(x));if(preferredLanguage.includes('chi_sim')&&missing.includes('chi_sim'))return{blocks:[],extraction_method:'ocr_unavailable',ocr_status:'language_missing',ocr_languages:languages,fallback_reason:'missing_chinese_ocr_language'}
  const language=required.filter(x=>languages.includes(x)).join('+')||'eng',dir=mkdtempSync(join(tmpdir(),'talentgraph-ocr-'))
  try{const prefix=join(dir,'page'),command=PDFTOPPM.toLowerCase().endsWith('.cmd')?'cmd.exe':PDFTOPPM,args=PDFTOPPM.toLowerCase().endsWith('.cmd')?['/d','/s','/c',`"${PDFTOPPM}" -png -r 200 "${path}" "${prefix}"`]:['-png','-r','200',path,prefix],render=spawnSync(command,args,{encoding:'utf8'});if(render.status!==0)return{blocks:[],extraction_method:'ocr_unavailable',ocr_status:'render_failed',ocr_languages:languages,fallback_reason:clean(render.stderr)||'pdftoppm_failed'};const images=readdirSync(dir).filter(x=>x.endsWith('.png')).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})),blocks=[];let ocrError='';images.forEach((image,index)=>{const result=spawnSync(TESSERACT,tesseractArgs([join(dir,image),'stdout','-l',language,'--psm','6','-c','tessedit_create_tsv=1']),{encoding:'utf8',maxBuffer:20*1024*1024});if(result.status===0)blocks.push(...parseTsv(result.stdout,index+1));else ocrError=clean(result.stderr)});const quality=extractionQuality(blocks);return{blocks,page_count:images.length,extraction_method:'tesseract_ocr',ocr_status:blocks.length?(quality.requires_human_confirmation?'low_confidence':'completed'):'empty',ocr_languages:[language],quality,...(blocks.length?{}:{fallback_reason:ocrError||'ocr_returned_no_text'})}}finally{rmSync(dir,{recursive:true,force:true})}
}
export async function extractPdf(path,preferredLanguage='chi_sim+eng'){const native=await extractPdfLayout(path);if(native.blocks.reduce((n,x)=>n+x.text.length,0)>=30)return native;return extractPdfOcr(path,preferredLanguage)}

export function parseDocxHtml(html) {
  const $ = load(html), blocks = []
  $('h1,h2,h3,h4,h5,h6,p,li,td,th').each((index, element) => {
    if ($(element).parents('p,li,td,th').length) return
    const text = clean($(element).text())
    if (!text) return
    const tag = element.tagName.toLowerCase()
    blocks.push({ block_id:`DOCX_B${blocks.length+1}`,page:1,text,extraction_method:'docx_semantic',document_role:tag.startsWith('h')?'heading':tag==='li'?'list_item':['td','th'].includes(tag)?'table_cell':'paragraph',heading_level:tag.startsWith('h')?Number(tag.slice(1)):null })
  })
  return blocks
}

export async function extractDocx(path) {
  const result = await mammoth.convertToHtml({ path }, { styleMap:["p[style-name='Title'] => h1:fresh","p[style-name='Heading 1'] => h1:fresh","p[style-name='Heading 2'] => h2:fresh","p[style-name='Heading 3'] => h3:fresh"] })
  const blocks = parseDocxHtml(result.value)
  return { blocks, page_count:1, extraction_method:'docx_semantic', ocr_status:'not_required', ocr_languages:[], warnings:(result.messages||[]).map(x=>x.message) }
}
