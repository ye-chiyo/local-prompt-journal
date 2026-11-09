'use strict';
const $=selector=>document.querySelector('.usage-dashboard '+selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const number=value=>Math.round(value).toLocaleString('zh-CN');
const compact=value=>value>=1e9?(value/1e9).toFixed(2)+' B':value>=1e6?(value/1e6).toFixed(2)+' M':value>=1e3?(value/1e3).toFixed(1)+' K':String(value);
const colors=['#2d5a49','#8a9b70','#bf8a60','#547991','#76688c'];
const tooltip=$('#chart-tooltip');
let tooltipAnchor=null,data=null,sequence=0,controller=null,days=90,selectedProject=new URLSearchParams(location.search).get('project')||'';
let ringModels=[],currentTotal=0;
function positionTooltip(anchor,event){
 const rect=anchor.getBoundingClientRect();
 const width=tooltip.offsetWidth,height=tooltip.offsetHeight;
 const pointer=event&&event.type.startsWith('pointer');
 const anchorX=pointer?event.clientX:rect.left+rect.width/2;
 const anchorY=pointer?event.clientY:rect.top;
 const left=Math.max(10,Math.min(window.innerWidth-width-10,anchorX-width/2));
 const above=anchorY-height-16;
 const top=Math.max(10,Math.min(window.innerHeight-height-10,above>=10?above:anchorY+24));
 tooltip.style.left=left+'px';tooltip.style.top=top+'px';
}
function showTooltip(anchor,title,total,rows,event){
 if(tooltipAnchor&&tooltipAnchor!==anchor)tooltipAnchor.removeAttribute('aria-describedby');
 tooltipAnchor=anchor;
 tooltip.innerHTML='<strong>'+esc(title)+'</strong><div class="tooltip-total">'+(total===null?'token 未取得':number(total)+' token')+'</div>'+rows.map(([label,value])=>'<div class="tooltip-row"><span>'+esc(label)+'</span><b>'+esc(value)+'</b></div>').join('');
 anchor.setAttribute('aria-describedby','chart-tooltip');
 positionTooltip(anchor,event);
 tooltip.classList.add('visible');
}
function hideTooltip(){
 tooltip.classList.remove('visible');
 if(tooltipAnchor)tooltipAnchor.removeAttribute('aria-describedby');
 tooltipAnchor=null;
}
function bindTooltip(anchor,show,hide=()=>{}){
 anchor.addEventListener('pointerenter',event=>show(event));
 anchor.addEventListener('pointermove',event=>{if(tooltipAnchor===anchor)positionTooltip(anchor,event)});
 anchor.addEventListener('focus',event=>show(event));
 anchor.addEventListener('click',event=>show(event));
 anchor.addEventListener('pointerleave',()=>{if(document.activeElement!==anchor){hideTooltip();hide()}});
 anchor.addEventListener('blur',()=>{hideTooltip();hide()});
}

function point(radius,angle){return [120+radius*Math.sin(angle),120-radius*Math.cos(angle)]}
function segmentPath(start,end){
 const a=point(96,start),b=point(96,end),c=point(69,end),d=point(69,start),large=end-start>Math.PI?1:0;
 return 'M '+a.join(' ')+' A 96 96 0 '+large+' 1 '+b.join(' ')+' L '+c.join(' ')+' A 69 69 0 '+large+' 0 '+d.join(' ')+' Z';
}
function renderHeatmap(){
 const daily=data.daily,metric=$('#metric').value;
 const start=new Date(daily[0].date+'T00:00:00Z'),leading=(start.getUTCDay()+6)%7,columns=Math.ceil((leading+daily.length)/7);
 const max=Math.max(...daily.map(day=>day[metric==='rounds'?'rounds':'total']),1);
 $('.heatmap').style.setProperty('--columns',columns);
 const months=new Map();let markup='';
 for(let position=0;position<columns*7;position++){
  const index=position-leading;
  if(index<0||index>=daily.length){markup+='<span class="heat-placeholder" aria-hidden="true"></span>';continue}
  const day=daily[index],month=Number(day.date.slice(5,7));
  if(!months.has(month))months.set(month,Math.floor(position/7)+1);
  const amount=day[metric==='rounds'?'rounds':'total'],level=amount===0?0:Math.max(1,Math.ceil(amount/max*4));
  const label=day.date+'：'+number(day.total)+' token，'+number(day.rounds)+' 回合';
  markup+='<button class="heat-cell" data-level="'+level+'" data-index="'+index+'" aria-label="'+esc(label)+'"></button>';
 }
 $('#trend').innerHTML=markup;
 $('#months').innerHTML=Array.from(months,([month,column])=>'<span style="grid-column:'+column+'">'+month+'月</span>').join('');
 $('#heat-legend').innerHTML='<span>少</span>'+[0,1,2,3,4].map(level=>'<i class="legend-cell" data-level="'+level+'" title="'+(level===0?'0':number(max*(level-1)/4)+'—'+number(max*level/4))+' '+(metric==='rounds'?'回合':'token')+'"></i>').join('')+'<span>多</span>';
 $('#trend').querySelectorAll('button').forEach(cell=>{
  const day=daily[Number(cell.dataset.index)];
  bindTooltip(cell,event=>showTooltip(cell,day.date,day.total===0&&day.missingTokens?null:day.total,[['输入',day.total===0&&day.missingTokens?'未取得':number(day.input)],['输出',day.total===0&&day.missingTokens?'未取得':number(day.output)],['完成回合',number(day.rounds)],...(day.missingTokens?[['token 未取得的回合',number(day.missingTokens)]]:[])],event));
 });
}
function resetModel(){
 $('#ring').classList.remove('has-active');
 document.querySelectorAll('.usage-dashboard [data-model]').forEach(item=>item.classList.remove('is-active'));
 $('#ring-total').textContent=compact(currentTotal);$('#ring-label').textContent='总 token';
}
function activateModel(index){
 $('#ring').classList.add('has-active');
 document.querySelectorAll('.usage-dashboard [data-model]').forEach(item=>item.classList.toggle('is-active',Number(item.dataset.model)===index));
 $('#ring-total').textContent=compact(ringModels[index].total);$('#ring-label').textContent=ringModels[index].name;
}
function renderModels(){
 currentTotal=data.summary.total;
 ringModels=data.models.filter(model=>model.total>0);
 if(ringModels.length>5){
  const rest=ringModels.slice(4),other={name:'其他模型',total:0,input:0,output:0};
  for(const model of rest)for(const key of ['total','input','output'])other[key]+=model[key];
  ringModels=[...ringModels.slice(0,4),other];
 }
 $('#model-empty').hidden=ringModels.length>0;$('.ring-area').hidden=ringModels.length===0;
 let angle=0;
 $('#ring-chart').innerHTML=ringModels.map((model,index)=>{
  const share=model.total/currentTotal,start=angle,end=angle+share*Math.PI*2,mid=(start+end)/2;angle=end;
  const path=segmentPath(start,end-.00001),label=model.name+'：'+number(model.total)+' token';
  return '<g class="ring-sector" data-model="'+index+'" tabindex="0" role="button" aria-label="'+esc(label)+'"><path d="'+path+'" fill="transparent"></path><path class="ring-segment" d="'+path+'" fill="'+colors[index]+'" style="--dx:'+(Math.sin(mid)*5)+'px;--dy:'+(-Math.cos(mid)*5)+'px"></path></g>';
 }).join('');
 const percent=amount=>currentTotal?(amount/currentTotal*100).toFixed(1)+'%':'—';
 $('#legend').innerHTML=ringModels.map((model,index)=>'<li><button class="model-choice" data-model="'+index+'"><span class="model-line"><span class="swatch" style="background:'+colors[index]+'"></span><span class="model-name">'+esc(model.name)+'</span><b>'+percent(model.total)+'</b></span><small>'+compact(model.total)+' token</small></button></li>').join('');
 $('#models').innerHTML=data.models.map(model=>'<tr><td>'+esc(model.name)+'</td><td>'+number(model.total)+'</td><td>'+percent(model.total)+'</td></tr>').join('')||'<tr><td colspan="3">暂无模型用量</td></tr>';
 document.querySelectorAll('.usage-dashboard [data-model]').forEach(item=>{
  const index=Number(item.dataset.model),model=ringModels[index];
  const show=event=>{activateModel(index);showTooltip(item,model.name,model.total,[['输入',number(model.input)],['输出',number(model.output)],['占比',percent(model.total)]],event)};
  bindTooltip(item,show,resetModel);
  item.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();show(event)}});
 });
 resetModel();
}
function render(){
 hideTooltip();
 const s=data.summary;
 const unavailable=s.total===0&&(s.missingTokens||['waiting','empty','error'].includes(data.status.state));
 for(const [key,value] of Object.entries({rounds:number(s.rounds),tokens:unavailable?'未取得':compact(s.total),input:unavailable?'—':compact(s.input),output:unavailable?'—':compact(s.output),cached:unavailable?'—':compact(s.cached),active:s.active+' 天'}))$('#'+key).textContent=value;
 renderHeatmap();renderModels();
 const max=Math.max(...data.hours.map(hour=>hour.rounds),1);
 $('#hours').innerHTML=data.hours.map((hour,index)=>'<button class="bar '+(hour.rounds>=max*.65?'peak':'')+'" data-hour="'+index+'" style="height:'+Math.max(3,hour.rounds/max*100)+'%" aria-label="'+index+' 点：'+number(hour.rounds)+' 回合，'+number(hour.total)+' token"></button>').join('');
 $('#hours').querySelectorAll('button').forEach(bar=>{
  const index=Number(bar.dataset.hour),hour=data.hours[index];
  bindTooltip(bar,event=>showTooltip(bar,index+':00—'+(index+1)+':00',hour.total,[['完成回合',number(hour.rounds)]],event));
 });
 $('#projects').innerHTML=data.projects.map(project=>'<tr><td><a href="/usage?project='+encodeURIComponent(project.id)+'" title="'+esc(project.label)+'">'+esc(project.label.replace(/\\/g,'/').split('/').filter(Boolean).pop()||project.label)+'</a></td><td>'+number(project.rounds)+'</td><td>'+number(project.total)+'</td></tr>').join('')||'<tr><td colspan="3">暂无项目用量</td></tr>';
 const state=data.status,notices=[];
 if(state.state==='waiting')notices.push('等待统计来源连接');
 if(state.state==='empty')notices.push('暂无可读取的统计记录');
 if(state.state==='updating')notices.push('正在更新统计');
 if(['error','partial','paused'].includes(state.state))notices.push(state.error||'部分统计暂不可用');
 if(state.lastCheckedAt)notices.push('更新于 '+new Date(state.lastCheckedAt*1000).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}));
 if(state.lastCheckedAt&&Date.now()/1000-state.lastCheckedAt>60)notices.push('统计更新已暂停');
 if(s.running)notices.push(number(s.running)+' 回合进行中');
 if(s.interrupted+s.failed)notices.push(number(s.interrupted+s.failed)+' 回合中断或失败');
 if(s.missingTokens||data.gaps)notices.push('部分 token 未取得');
 if(state.unmatchedFiles)notices.push(number(state.unmatchedFiles)+' 个来源文件未能归属');
 if(!s.rounds&&!s.total&&state.state==='ready')notices.push('所选范围暂无统计记录');
 $('#usage-state').textContent=notices.join(' · ');
 $('#usage-state').classList.toggle('problem',['error','partial','paused'].includes(state.state));
}
async function load(){
 const request=++sequence;
 if(controller)controller.abort();
 controller=new AbortController();
 document.querySelector('.usage-dashboard').setAttribute('aria-busy','true');
 const params=new URLSearchParams({days:String(days),kind:$('#source').value});
 if(selectedProject)params.set('project',selectedProject);
 try{
  const response=await fetch('/api/usage?'+params,{signal:controller.signal,cache:'no-store'});
  if(!response.ok)throw Error();
  const next=await response.json();
  if(request!==sequence)return;
  data=next;
  const signature=JSON.stringify(data.projectChoices);
  if($('#project').dataset.signature!==signature){
   $('#project').innerHTML='<option value="">全部项目</option>'+data.projectChoices.map(project=>'<option value="'+esc(project.id)+'">'+esc(project.label)+'</option>').join('');
   $('#project').dataset.signature=signature;
  }
  $('#project').value=selectedProject;
  if(selectedProject&&!data.projectChoices.some(project=>project.id===selectedProject)){
   const option=new Option('所选项目',selectedProject,true,true);$('#project').add(option);
  }
  $('#usage-retry').hidden=true;render();
 }catch(error){
  if(error.name==='AbortError'||request!==sequence)return;
  $('#usage-state').textContent='用量读取失败，请重试。'+(data?' 已保留上次数据。':'');
  $('#usage-state').classList.add('problem');$('#usage-retry').hidden=false;
 }finally{if(request===sequence)document.querySelector('.usage-dashboard').setAttribute('aria-busy','false')}
}
document.querySelectorAll('.usage-dashboard [data-days]').forEach(button=>button.addEventListener('click',()=>{
 days=Number(button.dataset.days);
 document.querySelectorAll('.usage-dashboard [data-days]').forEach(other=>other.setAttribute('aria-pressed',String(other===button)));
 load();
}));
$('#project').addEventListener('change',()=>{
 selectedProject=$('#project').value;
 const url=new URL(location.href);
 if(selectedProject)url.searchParams.set('project',selectedProject);else url.searchParams.delete('project');
 history.replaceState(null,'',url);load();
});
$('#source').addEventListener('change',load);
$('#metric').addEventListener('change',()=>{if(data){hideTooltip();renderHeatmap()}});
$('#usage-retry').addEventListener('click',load);
document.addEventListener('keydown',event=>{if(event.key==='Escape'){hideTooltip();resetModel()}});
window.addEventListener('scroll',()=>{hideTooltip();resetModel()},{passive:true});
window.addEventListener('resize',()=>{hideTooltip();resetModel()});
setInterval(()=>{if(!document.hidden&&!tooltipAnchor)load()},10000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});
load();
