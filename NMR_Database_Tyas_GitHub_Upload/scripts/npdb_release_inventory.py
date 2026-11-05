"""Source-derived declaration inventory. Never equates source coverage to E2E PASS."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

CONTROLS={'button','link_button','download_button','file_uploader','form_submit_button','text_input','text_area',
          'selectbox','multiselect','radio','checkbox','number_input','slider','date_input','form','dialog',
          'expander','dataframe','data_editor','plotly_chart','image','tabs','page_link'}


def inventory(path,revision):
    source=Path(path).read_text();tree=ast.parse(source);rows=[];edges=[];stack=[];conditions=[]
    def add(kind,node,control,contract='',target=''):
        key=f'{kind}:{node.lineno}:{control}'
        rows.append(dict(id=hashlib.sha256(key.encode()).hexdigest()[:16],kind=kind,page=stack[-1] if stack else 'module',
            control=control,line=node.lineno,input_contract=contract,destination_or_side_effect=target or 'UNRESOLVED_RUNTIME',
            state_transition='UNRESOLVED_RUNTIME',role='; '.join(conditions) or 'UNRESOLVED_RUNTIME',
            expected_data='REQUIRES_JOURNEY_BINDING',error_empty_loading_state='REQUIRES_EXECUTION',
            test_id='journey_'+hashlib.sha256(key.encode()).hexdigest()[:16],result='UNTESTED',evidence_sha=revision))
    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self,node):
            add('function',node,node.name,ast.unparse(node.args));stack.append(node.name)
            self.generic_visit(node);stack.pop()
        visit_AsyncFunctionDef=visit_FunctionDef
        def visit_If(self,node):
            conditions.append(ast.unparse(node.test));self.visit(node.test)
            for x in node.body:self.visit(x)
            conditions.pop();conditions.append('NOT ('+ast.unparse(node.test)+')')
            for x in node.orelse:self.visit(x)
            conditions.pop()
        def visit_Call(self,node):
            func=ast.unparse(node.func)
            if isinstance(node.func,ast.Attribute) and node.func.attr in CONTROLS:
                label=ast.unparse(node.args[0]) if node.args else next((ast.unparse(k.value) for k in node.keywords if k.arg in ('label','title')),'DYNAMIC')
                add('control',node,func+': '+label,ast.unparse(node),next((ast.unparse(k.value) for k in node.keywords if k.arg in ('on_click','on_change')),''))
            if stack:
                edges.append(dict(source=stack[-1],target=func,line=node.lineno,result='UNTESTED'))
            self.generic_visit(node)
    Visitor().visit(tree)
    constants={}
    for n in tree.body:
        if isinstance(n,ast.Assign):
            for name in n.targets:
                if isinstance(name,ast.Name) and name.id in ('NAV_OPTIONS','COMPOUND_PAGE_OPTIONS','SIDEBAR_NAV_GROUPS','LEGACY_NAV_MAP','LEGACY_COMPOUND_PAGE_MAP'):
                    try:constants[name.id]=ast.literal_eval(n.value)
                    except (ValueError,TypeError):constants[name.id]={'expression':ast.unparse(n.value),'result':'UNTESTED'}
    relationships=[dict(child_table=m.group(1),parent_table=m.group(2),raw=m.group(0)) for m in
        re.finditer(r'FOREIGN KEY\s*\(([^)]+)\)\s*REFERENCES\s+(\w+)\s*\([^)]+\)',source,re.I)]
    return dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),evidence_sha=revision,
        coverage='ALL_AST_FUNCTION_AND_CONTROL_DECLARATIONS_NOT_ALL_RUNTIME_INSTANCES',
        completeness='RUNTIME_DYNAMIC_LABELS_LINKS_AND_ROLE_INSTANCES_UNVERIFIED',rows=rows,call_edges=edges,
        navigation_constants=constants,foreign_key_declarations=relationships)


if __name__=='__main__':
    result=inventory(sys.argv[1],sys.argv[3] if len(sys.argv)>3 else 'WORKTREE')
    Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(function_declarations=sum(r['kind']=='function' for r in result['rows']),
                         control_declarations=sum(r['kind']=='control' for r in result['rows']),
                         all_runtime_journeys='UNTESTED',source_sha256=result['source_sha256'])))
