"""Static collection oracle for this pinned source; never imports upstream code."""

import ast


def expected_cases(source):
    tree = ast.parse(source)
    token_dict, fixture = None, None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "check_tokens":
                token_dict = node.value
        if isinstance(node, ast.FunctionDef) and node.name == "input_expected":
            fixture = node
    if not isinstance(token_dict, ast.Dict) or fixture is None:
        raise ValueError("pinned fixture structure missing")
    # Only dictionary KEYS are literal-evaluated, never constructor-containing values.
    keys = [ast.literal_eval(key) for key in token_dict.keys]
    if len(keys) != 18 or not all(isinstance(key, str) for key in keys):
        raise ValueError("pinned token cases changed")
    decorator = fixture.decorator_list[0]
    if ast.unparse(decorator) != "pytest.fixture(params=sorted(check_tokens))":
        raise ValueError("pinned parametrized fixture changed")
    cases = []
    definitions = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        definitions.append(node.name)
        if node.name == "test_tokenize":
            if [arg.arg for arg in node.args.args] != ["input", "expected"]:
                raise ValueError("pinned fixture consumers changed")
            values = sorted(keys)
        elif node.decorator_list:
            if len(node.decorator_list) != 1:
                raise ValueError("unhandled test decorators")
            call = node.decorator_list[0]
            if (
                not isinstance(call, ast.Call)
                or ast.unparse(call.func) != "pytest.mark.parametrize"
            ):
                raise ValueError("unhandled test decorator")
            if len(call.args) != 2 or call.keywords or ast.literal_eval(call.args[0]) != "line":
                raise ValueError("unhandled parametrization")
            values = ast.literal_eval(call.args[1])
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError("nonliteral parameter IDs")
        else:
            cases.append(node.name)
            continue
        cases.extend(f"{node.name}[{value}]" for value in values)
    if len(definitions) != 34 or len(cases) != 54 or len(set(cases)) != 54:
        raise ValueError("pinned collection structure changed")
    return cases
