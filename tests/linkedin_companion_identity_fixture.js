// Synthetic local backend identity for worker tests. No real keys or requests.
const {webcrypto,createHmac}=require('crypto');
module.exports=function identityFixture(chrome){
  const origin='http://127.0.0.1:5000',key='12'.repeat(32);
  const state={trusted:{[origin]:key},key,origin,failWrite:false,proofs:[],access:[]};
  chrome.storage.local={get:async()=>({cvstudioLinkedinTrustedAppsV1:structuredClone(state.trusted)}),
    set:async data=>{if(state.failWrite)throw Error('Synthetic trust failure');if(state.beforeWrite)await state.beforeWrite();state.trusted=structuredClone(data.cvstudioLinkedinTrustedAppsV1)},
    setAccessLevel:async value=>state.access.push(value)};
  const execute=chrome.scripting.executeScript;
  chrome.scripting.executeScript=async args=>{
    if(args.func?.name!=='companionProof')return execute(args);
    const probe=await execute({target:args.target,func:()=>true});
    const current=await chrome.tabs.get(args.target.tabId),actual=new URL(current.url).origin;
    const [nonce,pair]=args.args;state.proofs.push({nonce,pair,actual});
    if(state.beforeProof)await state.beforeProof();
    const proof=createHmac('sha256',Buffer.from(state.key,'hex')).update('CVStudio companion v1|'+actual+'|'+nonce).digest('hex');
    return probe.map(item=>({...item,result:item.result && !state.unavailable ? {
      proof:state.proof??proof,...(pair?{key:state.key}:{})}:null}));
  };
  return {state,crypto:webcrypto,TextEncoder};
};
