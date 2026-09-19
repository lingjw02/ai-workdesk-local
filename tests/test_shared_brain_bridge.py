"""Exercise bridge chat methods without constructing the production Engine/database."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from brain_context import build_chat_messages

class SharedBrainBridgeTests(unittest.TestCase):
    def test_main_brain_uses_same_history_and_global_memory(self):
        tree=ast.parse(Path('bridge.py').read_text(encoding='utf-8-sig'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='WorkDeskBridge')
        methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('handle_request','_chat_model_reply')]
        module=ast.Module(body=methods,type_ignores=[])
        store=SimpleNamespace(load_conversation=Mock(return_value={'messages':[{'role':'user','text':'My favorite tea is jasmine.'}]}))
        scope={'store':store,'build_chat_messages':build_chat_messages,'RouteRequest':lambda **kw:kw}
        exec(compile(module,'bridge.py','exec'),scope)
        bridge=SimpleNamespace()
        memory=SimpleNamespace(read=Mock(return_value=([{'type':'preference','content':'Use English'}],None)))
        router=SimpleNamespace(route=Mock(return_value='main-brain-route'),call=Mock(return_value=SimpleNamespace(ok=True,text='Jasmine tea.')))
        bridge.engine=SimpleNamespace(memory=memory,model_router=router)
        bridge._is_simple_chat=lambda text:True
        bridge._chat_model_reply=lambda text,conversation_id=None:scope['_chat_model_reply'](bridge,text,conversation_id)
        result=scope['handle_request'](bridge,'What tea do I like?',conversation_id='shared-conversation')
        self.assertEqual(result['reply'],'Jasmine tea.')
        store.load_conversation.assert_called_once_with('shared-conversation')
        memory.read.assert_called_once_with('MB','GLOBAL','global')
        messages=router.call.call_args.args[1]
        self.assertIn('Emilia',messages[0]['content'])
        self.assertIn('Use English',messages[1]['content'])
        self.assertEqual(messages[-2]['content'],'My favorite tea is jasmine.')
        self.assertEqual(messages[-1]['content'],'What tea do I like?')

if __name__=='__main__': unittest.main()
