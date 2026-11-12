// DOM lifecycle regression tests; no browser dependencies or external services.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const html=fs.readFileSync('templates/index.html','utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1].split('\ndraw();')[0];
function fixture(reduced=false){
  const pending=[],events=[];
  class Element{
    constructor(tag='div'){this.tagName=tag;this.children=[];this.dataset={};this.style={};this.attributes={};this._text='';this.value='';this.checked=false;this.parent=null;this.title=''}
    set textContent(text){this._text=text;this.children=[]}
    get textContent(){return this._text}
    append(child){child.parent=this;this.children.push(child)}
    prepend(child){child.parent=this;this.children.unshift(child)}
    replaceChildren(){this.children=[];this._text=''}
    setAttribute(k,v){this.attributes[k]=v}
    focus(options){this.focusOptions=options}
    insertAdjacentHTML(_,text){const svg=new Element('svg');this.children.unshift(svg);svg.parent=this}
    set innerHTML(text){this.children=[];this.insertAdjacentHTML('afterbegin',text)}
    querySelectorAll(selector){return this.children.filter(c=>c.tagName===selector)}
    querySelector(selector){return this.children.find(c=>selector==='svg'?c.tagName==='svg':c.className===selector.slice(1))||null}
    remove(){events.push(this.className==='moving-piece'?'remove-ghost':'remove-node');if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this);this.parent=null}
    getBoundingClientRect(){return {left:10,top:20,width:50,height:this.height||50}}
    animate(){let finish;const finished=new Promise(resolve=>finish=resolve);pending.push(finish);return {finished}}
  }
  const elements=new Map(),document={addEventListener:()=>{},body:new Element('body'),createElement:tag=>new Element(tag),getElementById:id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)}};
  const context=vm.createContext({document,localStorage:{getItem:()=>null},matchMedia:()=>({matches:reduced}),AbortController,console});
  vm.runInContext(fs.readFileSync('static/review.js','utf8'),context);
  vm.runInContext(script,context);
  const run=code=>vm.runInContext(code,context);
  run('draw()');
  return {elements,document,pending,events,run};
}

test('selection, moves and flips preserve all squares and untouched pieces',()=>{
 const f=fixture(),board=f.elements.get('board'),squares=[...board.children];
 const rook=f.run("squares.get('a8').querySelector('svg')");
 f.run("selected='e2';draw();selected='';draw();flipped=true;draw()");
 assert.deepEqual(board.children,squares);
 assert.equal(f.run("squares.get('a8').querySelector('svg')"),rook);
 assert.equal(f.run("squares.get('a8').style.order"),63);
 f.run("fen='rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1';draw()");
 assert.deepEqual(board.children,squares);
 assert.equal(f.run("squares.get('a8').querySelector('svg')"),rook);
 assert.equal(f.run("squares.get('e2').querySelector('svg')"),null);
 assert.ok(f.run("squares.get('e4').querySelector('svg')"));
});

test('animation commits the destination before removing its overlay',async()=>{
 const f=fixture();f.events.length=0;
 // Inject only a host test callback, outside any browser context.
 const callback=()=>{f.events.push('commit');assert.equal(f.document.body.children.length,1);f.run("fen='rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1';draw()")};
 const animate=f.run('animateMove');
 const result=animate(f.run('START'),'e2e4',callback);
 assert.equal(f.document.body.children.length,1);
 assert.equal(f.run("squares.get('e2').querySelector('svg').style.visibility"),'hidden');
 f.pending.forEach(finish=>finish());await result;
 assert.ok(f.events.indexOf('commit')<f.events.indexOf('remove-ghost'));
 assert.equal(f.document.body.children.length,0);
 assert.equal(f.run("squares.get('e2').querySelector('svg')"),null);
 assert.notEqual(f.run("squares.get('e4').querySelector('svg').style.visibility"),'hidden');
});

test('castling moves both pieces and reduced motion commits without overlays',async()=>{
 const f=fixture();f.run("fen='r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1';draw()");
 let commits=0;const result=f.run('animateMove')(f.run('fen'),'e1g1',()=>commits++);
 assert.equal(f.document.body.children.length,2);f.pending.forEach(finish=>finish());await result;
 assert.equal(commits,1);assert.equal(f.document.body.children.length,0);
 const r=fixture(true);await r.run('animateMove')(r.run('START'),'e2e4',()=>commits++);
 assert.equal(commits,2);assert.equal(r.pending.length,0);
});

test('waiting for analysis preserves the explanation and its height',()=>{
 const f=fixture(),results=f.run("$('results')");results.textContent='Existing explanation';results.height=900;
 f.run('invalidate()');
 assert.equal(results.textContent,'Existing explanation');assert.equal(results.style.minHeight,'900px');
 assert.equal(results.dataset.stale,'true');assert.ok(f.elements.get('analysis-progress').textContent);
});


test('pointer focus prevents automatic scrolling without removing keyboard access',()=>{
 const f=fixture(),square=f.run("squares.get('e2')");let prevented=false;
 square.onmousedown({button:0,preventDefault(){prevented=true}});
 assert.equal(prevented,true);assert.equal(square.focusOptions.preventScroll,true);
 assert.equal(square.onkeydown,undefined);
 let secondaryPrevented=false;square.onmousedown({button:2,preventDefault(){secondaryPrevented=true}});
 assert.equal(secondaryPrevented,false);
});

test('turn changes keep the perspective message short and on a single line',()=>{
 const f=fixture();assert.equal(f.elements.get('perspective').textContent,'나는 백 · 내 차례예요.');
 f.run("fen='rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1';draw()");
 assert.equal(f.elements.get('perspective').textContent,'나는 백 · 상대 차례예요.');
});


test('cached game navigation and side changes make zero API calls',async()=>{
 const f=fixture();
 f.run(`
  globalThis.networkCalls=0;api=async()=>{networkCalls++;throw Error('Unexpected network request')};
  renderGameReview=()=>{};
  showAnalysis=()=>{$('results').dataset.stale='false'};
  const start={fen:START,legal:['e2e4'],status:'백 차례'};
  const end={fen:'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1',legal:[],status:'흑 차례'};
  const cached={white:{...start,my_turn:true,lines:[{move:'e2e4'}]},black:{...start,my_turn:false,lines:[{move:'e2e4'}]}};
  loadedGame={total:1,positions:[start,end],moves:[{fen:START,move:'e2e4',san:'e4'}],reviews:[{analysis:cached,number:1,color:'white',san:'e4',grade:'무난한 수',loss_cp:0,explanation:'test',best_san:'e4'}],finalAnalysis:{white:{...end,lines:[]},black:{...end,lines:[]}}};
  navigateGame(0);navigateGame(1);navigateGame(0);
 `);
 await f.run("chooseSide('black')");
 assert.equal(f.run('networkCalls'),0);
 assert.equal(f.run('pgnCursor'),0);
 assert.match(f.elements.get('analysis-progress').textContent,/새 엔진 분석 없음/);
});
