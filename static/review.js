// A single imported game, with all completed reviews persisted locally in IndexedDB.
let loadedGame=null,pgnCursor=0,pgnBranch=false,reviewRunning=false,reviewToken=0,reviewController=null;
let savedGameAvailable=false,saveQueue=Promise.resolve(),shownSnapshot=null,shownSide=null;
const SAMPLE_PGN='[Event "짧은 복기 예제"]\n[White "나"]\n[Black "상대"]\n[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1';
function gameMessage(text,error=false){$('game-message').textContent=text;$('game-message').className=error?'error':'muted save-note'}
function storageTask(mode,fn){return new Promise((resolve,reject)=>{
 if(!window.indexedDB){reject(Error('이 브라우저에서는 저장을 사용할 수 없어요.'));return}
 const request=indexedDB.open('friendly-chess-coach-reviews',1);
 request.onupgradeneeded=()=>{request.result.createObjectStore('games')};
 request.onerror=()=>reject(request.error);
 request.onsuccess=()=>{const db=request.result;let tx;try{tx=db.transaction('games',mode);const result=fn(tx.objectStore('games'));let value;result.onsuccess=()=>{value=result.result};tx.oncomplete=()=>{db.close();resolve(value)};tx.onerror=()=>{db.close();reject(tx.error)};tx.onabort=()=>{db.close();reject(tx.error||Error('저장이 중단됐어요.'))}}catch(e){db.close();reject(e)}};
})}
function saveGame(game){
 const copy=JSON.parse(JSON.stringify(game));
 saveQueue=saveQueue.catch(()=>{}).then(()=>storageTask('readwrite',store=>store.put(copy,'latest'))).then(()=>{
  savedGameAvailable=true;$('restore-review').hidden=false;
  if(loadedGame===game)gameMessage('이 브라우저에 저장했어요. 다음에 열어도 완료된 리뷰부터 바로 볼 수 있어요.');
 }).catch(()=>{if(loadedGame===game)gameMessage('브라우저 저장이 막혀 현재 탭에만 보관 중이에요. 탭을 닫으면 사라질 수 있어요.',true)});
 return saveQueue;
}
function stopGameReview(){reviewToken++;reviewController?.abort();reviewController=null;reviewRunning=false;renderGameReview()}
function detachGame(){stopGameReview();loadedGame=null;pgnCursor=0;pgnBranch=false;$('game-nav').hidden=true;$('review-panel').hidden=true;updateGameControls()}
function updateGameControls(){
 if(!document.getElementById('game-nav'))return;
 $('workspace').dataset.mode=loadedGame?'review':'setup';
 $('workspace').dataset.branch=String(!!(loadedGame&&pgnBranch));
 $('branch-tools').hidden=!(loadedGame&&pgnBranch);
 $('branch-return').disabled=busy;
 $('branch-best').disabled=busy||analyzing||!best;
 $('branch-analyze').disabled=busy||analyzing;
 $('branch-status').textContent=loadedGame&&pgnBranch?`다른 수 탐색 중 · 원래 기보 ${pgnCursor}반수 장면에서 시작했어요.`:'';
 $('new-game-review').disabled=busy;
 $('import-pgn').disabled=busy;$('analyze').textContent=loadedGame?'이 장면 자세히 재분석':'✨ 다음 수 알려주세요';
 if(!loadedGame)return;
 for(const id of ['game-start','game-prev'])$(id).disabled=busy||pgnCursor<=0;
 for(const id of ['game-next','game-end'])$(id).disabled=busy||pgnCursor>=loadedGame.total;
 $('game-cursor').disabled=busy;
 if(!pgnBranch){$('undo').disabled=busy||pgnCursor===0;$('redo').disabled=busy||pgnCursor===loadedGame.total}
}
function drawGameNavigation(){
 if(!loadedGame)return;
 $('game-nav').hidden=false;$('game-cursor').max=loadedGame.total;$('game-cursor').value=pgnCursor;$('game-seek').disabled=true;$('seek-preview').textContent='바로 위치를 고른 뒤 ‘선택 위치로 이동’을 눌러 확정하세요.';
 $('game-position').textContent=`${pgnCursor} / ${loadedGame.total} 반수${pgnBranch?' · 변형 탐색 중 (위 버튼으로 원래 기보에 돌아갈 수 있어요)':''}`;
}
function showGameCache(){
 if(!loadedGame||pgnBranch)return false;
 const row=loadedGame.reviews?.[pgnCursor];
 const snapshot=pgnCursor===loadedGame.total?loadedGame.finalAnalysis:row?.analysis;
 const view=loadedGame.details?.[pgnCursor]?.[player]||snapshot?.[player];
 if(!view)return false;
 if(shownSnapshot===view&&shownSide===player&&$('results').dataset.stale==='false')return true;
 shownSnapshot=view;shownSide=player;
 best='';analyzing=false;showAnalysis(view);
 if(row){const card=node('article',undefined,'card');card.append(node('span',row.grade,'badge'));
  card.append(node('h3',`실제로 둔 수: ${row.number}${row.color==='white'?'.':'...'} ${row.san} (${row.color==='white'?'백':'흑'})`));
  card.append(node('p',row.explanation));card.append(node('p',`대안: ${row.best_san} · 추정 평가 손실 ${row.loss_cp>=9000?'메이트 수순 차이':(row.loss_cp/100).toFixed(2)+'폰'}`,'muted'));
  card.append(node('small','이 수를 두기 전의 판이에요. 다음 ▶를 누르면 실제 수를 둔 뒤로 이동해요. 수순 목록에서 다른 장면도 바로 살펴볼 수 있어요.'));
  $('results').prepend(card);
 }
 best=view.lines?.[0]?.move||'';
 $('best').textContent=view.my_turn?'추천 수 두기':'상대 예상 수 두기';
 progress('저장된 리뷰를 바로 보여드려요 · 새 엔진 분석 없음');controls();return true;
}
function saveDetailedGameAnalysis(result){
 if(!loadedGame||pgnBranch||result.fen!==fen)return;
 loadedGame.details??={};loadedGame.details[pgnCursor]??={};loadedGame.details[pgnCursor][player]=result;
 saveGame(loadedGame);
}
function navigateGame(index){
 if(!loadedGame||busy)return;
 index=Math.max(0,Math.min(loadedGame.total,index));invalidate('저장된 기보로 이동했어요.');
 pgnCursor=index;pgnBranch=false;
 history=loadedGame.moves.slice(0,index).map(x=>({fen:x.fen,move:x.move,san:x.san}));future=[];
 selected='';lastMove=index?loadedGame.moves[index-1].move:'';
 applyState(loadedGame.positions[index]);
 if(!showGameCache()){
  $('results').replaceChildren();$('results').dataset.stale='false';
  $('results').append(node('p','아직 이 장면의 분석 결과가 없어요. 전체 리뷰가 진행되면 여기에 바로 표시할게요.'));
  progress('미분석 장면 · 아래 전체 리뷰를 시작하거나 이어서 진행해 주세요.');
 }
 renderGameReview();
}
function renderGameReview(){
 if(!loadedGame)return;
 const game=loadedGame,rows=game.reviews||[],mine=rows.filter(r=>r.color===player);
 $('review-panel').hidden=false;
 $('review-players').textContent=`${game.headers.White||'백'} vs ${game.headers.Black||'흑'} · 기보 결과 ${game.headers.Result||'*'}`;
 $('review-progress').max=game.total;$('review-progress').value=rows.length;
 $('review-status').textContent=`${rows.length} / ${game.total} 반수 분석 완료${reviewRunning?' · 작전 회의 중…':rows.length===game.total?' · 전체 리뷰 완료!':' · 중지 상태 (완료된 부분은 바로 볼 수 있어요)'}`;
 $('review-start').disabled=reviewRunning||rows.length===game.total;
 $('review-start').textContent=rows.length?'리뷰 이어서':'전체 리뷰 시작';$('review-stop').disabled=!reviewRunning;
 const root=$('review-summary');root.replaceChildren();
 root.append(node('h3',`${player==='white'?'백':'흑'}으로 본 ${rows.length===game.total?'게임 요약':'중간 요약'}`));
 if(game.opening)root.append(node('p',`확인된 오프닝: ${game.opening.name} (${game.opening.eco}) · ${game.opening.ply}반수째 마지막 확인`));
 if(!mine.length){root.append(node('p','내 수의 분석 결과를 기다리고 있어요.'))}
 else{
  const errors=mine.filter(r=>r.severity>=2),small=mine.filter(r=>r.severity===1),good=mine.filter(r=>r.severity===0);
  root.append(node('p',`검토한 내 수 ${mine.length}개 · 무난/첫 후보 ${good.length} · 아쉬운 수 ${small.length} · 실수/큰 실수 ${errors.length}`));
  const strong=mine.filter(r=>r.grade==='엔진 첫 후보'||r.grade==='체크메이트!').slice(0,2);
  if(strong.length)root.append(node('p','잘 챙긴 장면: '+strong.map(r=>`${r.number}${r.color==='white'?'.':'...'} ${r.san}`).join(', ')+' — 엔진 첫 후보와 같거나 체크메이트를 완성했어요.'));
  const capture=errors.filter(r=>r.best_capture).length,checks=errors.filter(r=>r.best_check).length,exposed=errors.filter(r=>r.exposed.length).length;
  if(capture)root.append(node('p',`연습할 것: 실수로 분류된 ${capture}장면에서 잡기 후보가 더 좋았어요. 수를 두기 전 양쪽의 잡을 수 있는 기물부터 확인해 봐요.`));
  if(checks)root.append(node('p',`체크 후보를 다시 볼 장면이 ${checks}개 있어요. 체크 → 잡기 → 위협 순으로 후보를 찾아봐요.`));
  if(exposed)root.append(node('p',`실수 뒤 공격받고 지켜지지 않은 기물이 있는 장면이 ${exposed}개예요. 실제로 잡히는지는 대안 수순에서 확인해요.`));
  if(!errors.length)root.append(node('p','검토한 내 수에서는 1폰 이상 손실로 추정되는 장면이 없었어요. 짧은 탐색이라 놓친 전술이 있을 수 있으니 궁금한 장면은 자세히 분석해 봐요.'));
  const turning=[...mine].filter(r=>r.severity>0).sort((a,b)=>b.loss_cp-a.loss_cp).slice(0,3);
  for(const row of turning){const button=node('button',`${row.number}${row.color==='white'?'.':'...'} ${row.san} · ${row.grade} → ${row.best_san} 살펴보기`,'control');button.onclick=()=>navigateGame(row.ply-1);root.append(button)}
 }
 const list=$('review-moves'),listScroll=list.scrollTop;list.replaceChildren();
 for(let i=0;i<game.moves.length;i++){
  const move=game.moves[i],review=rows[i],button=node('button',`${move.number}${move.color==='white'?'.':'...'} ${move.san}${review?' · '+review.grade:''}`,'control');
  button.dataset.severity=review?.severity??'';
  if(!pgnBranch&&pgnCursor===i)button.setAttribute('aria-current','step');
  button.title='이 수를 두기 전 장면 보기';button.onclick=()=>navigateGame(i);list.append(button);
 }
 list.scrollTop=listScroll;drawGameNavigation();updateGameControls();
}
async function startGameReview(){
 if(!loadedGame||reviewRunning)return;
 const game=loadedGame,token=++reviewToken;reviewRunning=true;renderGameReview();
 try{
  while(game.reviews.length<game.total){
   reviewController=new AbortController();
   const batch=await api('review',{pgn:game.pgn,start:game.reviews.length},reviewController.signal);
   if(token!==reviewToken||loadedGame!==game)return;
   if(batch.game_id!==game.id||batch.next!==game.reviews.length+batch.rows.length||!batch.rows.length)throw Error('기보와 리뷰 결과가 맞지 않아요.');
   game.reviews.push(...batch.rows);if(batch.final_analysis)game.finalAnalysis=batch.final_analysis;
   renderGameReview();if(!pgnBranch)showGameCache();await saveGame(game);
  }
 }catch(e){if(e.name!=='AbortError'&&token===reviewToken)gameMessage('리뷰가 잠깐 멈췄어요. 완료된 부분부터 이어갈 수 있어요. '+e.message,true)}
 finally{if(token===reviewToken){reviewRunning=false;reviewController=null;renderGameReview()}}
}
async function importGame(){
 if(busy)return;busy=true;controls();gameMessage('PGN을 읽고 기물들의 이동 기록을 정리하고 있어요…');
 try{
  const game=await api('pgn',{pgn:$('pgn').value});stopGameReview();
  loadedGame={...game,schema:1,reviews:[],finalAnalysis:null,details:{}};pgnCursor=0;pgnBranch=false;
  $('pgn-import').open=false;busy=false;navigateGame(0);await saveGame(loadedGame);startGameReview();
 }catch(e){gameMessage(e.message,true)}finally{busy=false;controls()}
}
async function restoreGame(){
 if(busy)return;
 try{const game=await storageTask('readonly',store=>store.get('latest'));if(!game?.positions?.length||!Array.isArray(game.reviews))throw Error('저장된 게임을 찾지 못했어요.');
  stopGameReview();loadedGame=game;pgnBranch=false;$('pgn').value=game.pgn;$('pgn-import').open=false;navigateGame(0);
  gameMessage(`저장된 게임을 열었어요. ${game.reviews.length} / ${game.total}반수 리뷰가 준비돼 있어요.`);
 }catch(e){gameMessage(e.message,true)}
}
async function newGameReview(){
 if(busy)return;detachGame();invalidate();busy=true;controls();
 try{const state=await api('position',{fen:START});history=[];future=[];selected='';lastMove='';applyState(state);$('results').replaceChildren();progress('새 PGN을 불러오거나 FEN·직접 두기로 분석을 시작해 주세요.');$('pgn').value='';$('pgn-file').value='';$('pgn-import').open=true;gameMessage('새 게임을 가져와 주세요. 이전 리뷰는 새 게임을 불러오기 전까지 저장돼 있어요.');$('pgn').focus({preventScroll:true})}
 catch(e){gameMessage(e.message,true)}finally{busy=false;controls()}
}
document.addEventListener('DOMContentLoaded',()=>{
 $('new-game-review').onclick=newGameReview;
 $('import-pgn').onclick=importGame;$('review-start').onclick=startGameReview;$('review-stop').onclick=stopGameReview;
 $('game-start').onclick=()=>navigateGame(0);$('game-prev').onclick=()=>navigateGame(pgnCursor-1);
 $('game-next').onclick=()=>navigateGame(pgnCursor+1);$('game-end').onclick=()=>navigateGame(loadedGame?.total||0);
 $('game-cursor').oninput=()=>{$('seek-preview').textContent=`${$('game-cursor').value} / ${loadedGame?.total||0} 반수 선택 · 이동 버튼을 눌러 확정하세요.`;$('game-seek').disabled=busy||!loadedGame};
 $('game-seek').onclick=()=>navigateGame(+$('game-cursor').value);
 $('branch-return').onclick=()=>navigateGame(pgnCursor);
 $('branch-best').onclick=()=>{if(best)play(best)};
 $('branch-analyze').onclick=()=>analyze(true);
 $('sample-pgn').onclick=()=>{$('pgn').value=SAMPLE_PGN};$('restore-review').onclick=restoreGame;
 $('pgn-file').onchange=async()=>{const file=$('pgn-file').files[0];if(!file)return;if(file.size>150000){gameMessage('150KB 이하의 PGN 파일을 선택해 주세요.',true);return}$('pgn').value=await file.text();gameMessage('파일을 읽었어요. 불러오기 버튼을 눌러 주세요.')};
 storageTask('readonly',store=>store.get('latest')).then(game=>{if(game?.id){savedGameAvailable=true;$('restore-review').hidden=false;gameMessage('이 브라우저에 저장된 게임·리뷰가 있어요. 바로 다시 열 수 있어요.')}}).catch(()=>{});
});
