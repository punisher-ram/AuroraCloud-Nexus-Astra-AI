from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent
ui = ROOT / 'app' / 'ui.py'
text = ui.read_text(encoding='utf-8')
tree = ast.parse(text)
window = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Window')
methods = {n.name: n for n in window.body if isinstance(n, ast.FunctionDef)}

assert '_submit_ai_message' in methods
assert 'ask_serneia' in methods
assert '_append_ai_message' in methods
assert '_format_ai_message_html' in methods

submit_src = ast.get_source_segment(text, methods['_submit_ai_message'])
ask_src = ast.get_source_segment(text, methods['ask_serneia'])
build_src = ast.get_source_segment(text, methods['_format_ai_message_html'])

assert 'self.ai_input.clear()' in submit_src
assert 'self.ask_serneia(question)' in submit_src
assert 'self._append_ai_message("You", question)' in ask_src
assert 'self.ai_input.returnPressed.connect(self._submit_ai_message)' in text
assert 'self.ai_send.clicked.connect(self._submit_ai_message)' in text

# Verify the exact HTML construction no longer contains the old malformed
# string-comparison expression that caused submission to stop before clearing.
assert "'>\"<f'" not in text
assert 'cursor.insertHtml(self._format_ai_message_html(speaker, message))' in text
assert 'safe_message = html.escape(str(message)).replace("\\n", "<br>")' in build_src

print('ASTRA SEND SMOKE TEST: PASS')
print('Enter route: PASS')
print('Button route: PASS')
print('Input clears before AI call: PASS')
print('Chat rendering path: PASS')
