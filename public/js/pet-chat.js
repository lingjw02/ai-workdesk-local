/* Emilia is an interface to the existing Main Brain conversation API. */
(() => {
  const $=id=>document.getElementById(id);
  let conversationId=null,loading=false,sending=false,openToken=0,previousPage='dashboard';
  function line(role,text){const item=document.createElement('div');item.className='pet-chat-line '+(role==='user'?'user':'assistant');const label=document.createElement('strong');label.textContent=role==='user'?'You':'Emilia';const body=document.createElement('p');body.textContent=text;item.append(label,body);$('petChatLog').append(item);$('petChatLog').scrollTop=$('petChatLog').scrollHeight;}
  async function open(){
    if(!$('petChatDialog').open)$('petChatDialog').showModal();
    if(sending)return;
    $('petChatInput').focus();loading=true;conversationId=null;const token=++openToken;
    $('petChatStatus').textContent='Opening your Main Brain conversation…';
    try{
      let remembered;try{remembered=localStorage.getItem('emilia.sharedConversation');}catch{}
      let id=Chat.getConversationId()||remembered;
      let conv=id?await Api.getConversation(id):null;
      if(!conv?.id){conv=await Api.createConversation();id=conv.id;}
      if(token!==openToken)return;
      conversationId=id;try{localStorage.setItem('emilia.sharedConversation',id);}catch{}
      $('petChatLog').replaceChildren();for(const m of conv.messages||[])line(m.role,m.text||'');
      $('petChatThread').textContent=conv.title||'New conversation';
      $('petChatStatus').textContent='Shared conversation and memory with Main Brain.';
      if(!(conv.messages||[]).length)line('assistant','I’m here. What’s on your mind?');
    }catch(e){$('petChatStatus').textContent='Unable to open chat: '+e.message;}
    finally{if(token===openToken)loading=false;}
  }
  async function send(event){
    event.preventDefault();const text=$('petChatInput').value.trim();if(!text||loading||sending||!conversationId)return;
    if(Api.chatPending){$('petChatStatus').textContent='Main Brain is already replying. Please wait.';return;}
    sending=true;$('petChatSend').disabled=true;$('petChatInput').disabled=true;$('petChatStatus').textContent='Emilia is thinking…';const id=conversationId;
    try{
      const result=await Api.sendChat({conversationId:id,text,chatMode:'chat',mode:'instant'});
      $('petChatInput').value='';line('user',text);line('assistant',result.reply||'No response was returned.');
      $('petChatStatus').textContent=result.taskResult?.status==='CLARIFICATION_REQUIRED'?'Main Brain needs clarification. You can reply here or open the full conversation.':'Saved to your shared conversation.';
      if(!Chat.getConversationId()||Chat.getConversationId()===id)await Chat.load(id);
      await App.refreshSidebar();
    }catch(e){$('petChatStatus').textContent='Message could not be sent: '+e.message;}
    finally{sending=false;$('petChatSend').disabled=false;$('petChatInput').disabled=false;if($('petChatDialog').open)$('petChatInput').focus();}
  }
  function init(){
    const header=document.querySelector('.companion-heading');
    const actions=document.createElement('div');actions.className='pet-actions';
    const talk=document.createElement('button');talk.id='petTalk';talk.textContent='Chat with Emilia';talk.onclick=open;
    const close=document.createElement('button');close.id='petRoomClose';close.textContent='Close room';close.setAttribute('aria-label','Close companion room and return to previous page');close.onclick=()=>App.showView(document.getElementById('view-'+previousPage)?previousPage:'dashboard');
    actions.append(talk,$('petVisibility'),close);header.append(actions);
    const menuTalk=document.createElement('button');menuTalk.id='petMenuTalk';menuTalk.textContent='Chat with Emilia';menuTalk.onclick=()=>{$('petMenu').hidden=true;open();};$('petMenu').prepend(menuTalk);
    const dialog=document.createElement('dialog');dialog.id='petChatDialog';dialog.className='pet-chat-dialog';dialog.dataset.private='true';dialog.setAttribute('aria-labelledby','petChatTitle');
    dialog.innerHTML='<header class="pet-chat-head"><div><h2 id="petChatTitle">Emilia</h2><span>Main Brain · same mind, same memory</span></div><button id="petChatClose" aria-label="Close Emilia chat">×</button></header><div class="pet-chat-thread"><span id="petChatThread"></span><button id="petChatFull">Open full conversation ↗</button></div><div id="petChatLog" class="pet-chat-log" role="log" aria-label="Conversation with Emilia"></div><p id="petChatStatus" role="status"></p><form id="petChatForm"><label class="sr-only" for="petChatInput">Message Emilia</label><textarea id="petChatInput" rows="3" placeholder="Talk to Emilia…" maxlength="16000"></textarea><div class="pet-chat-send"><small>Uses Main Brain’s configured model. Screen awareness stays local.</small><button id="petChatSend" type="submit">Send</button></div></form>';
    document.body.append(dialog);$('petChatClose').onclick=()=>dialog.close();$('petChatFull').onclick=()=>{if(conversationId){dialog.close();App.openChat(conversationId);}};
    $('petChatForm').onsubmit=send;$('petChatInput').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('petChatForm').requestSubmit();}};
    dialog.addEventListener('close',()=>{if(loading){openToken++;loading=false;}});
    let lastPage=document.querySelector('.view.active')?.id.replace('view-','')||'dashboard';
    document.addEventListener('studio:view',e=>{if(e.detail==='companion'&&lastPage!=='companion')previousPage=lastPage;lastPage=e.detail;});
  }
  document.addEventListener('DOMContentLoaded',init);
})();
