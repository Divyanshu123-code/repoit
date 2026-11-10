"""Tree-sitter based parser for Python source repositories (P1-04).

Extracts symbols (modules, classes, methods, functions), docstrings,
imports, line ranges, and parameters safely without executing any code.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

import tree_sitter_python
from tree_sitter import Language, Node, Parser, Point

from app.parsing.models import (
    ImportItem,
    ImportStatement,
    ParsedModule,
    Symbol,
    SymbolType,
)

# Initialize Python Tree-sitter Language and Parser singleton
PY_LANGUAGE = Language(tree_sitter_python.language())


def _clean_docstring(raw: str) -> str:
    """Clean enclosing quotes and whitespace from docstring literals."""
    text = raw.strip()
    for quote in ('"""', "'''", '"', "'"):
        if text.startswith(quote) and text.endswith(quote) and len(text) >= len(quote) * 2:
            text = text[len(quote) : -len(quote)]
            break
    return text.strip()


def _get_docstring_from_body(body_node: Node | None, code_bytes: bytes) -> str | None:
    """Extract docstring if the first statement in a body/block is a string literal."""
    if body_node is None:
        return None

    # For module body, body_node is root_node; for class/func, body_node is block
    for child in body_node.children:
        if child.type == "comment":
            continue
        if child.type == "expression_statement":
            first_expr = child.children[0] if child.children else None
            if first_expr is not None and first_expr.type == "string":
                raw_str = code_bytes[first_expr.start_byte : first_expr.end_byte].decode(
                    errors="replace"
                )
                return _clean_docstring(raw_str)
        # Any other statement encountered first means there is no docstring
        break
    return None


def _extract_parameter_name(param_node: Node, code_bytes: bytes) -> str:
    """Extract the variable name of a parameter from its AST node."""
    if param_node.type == "identifier":
        return code_bytes[param_node.start_byte : param_node.end_byte].decode(errors="replace")

    if param_node.type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
        for sub in param_node.children:
            if sub.type in ("identifier", "list_splat", "dictionary_splat"):
                return _extract_parameter_name(sub, code_bytes)

    if param_node.type == "list_splat":
        for sub in param_node.children:
            if sub.type == "identifier":
                return f"*{code_bytes[sub.start_byte : sub.end_byte].decode(errors='replace')}"

    if param_node.type == "dictionary_splat":
        for sub in param_node.children:
            if sub.type == "identifier":
                return f"**{code_bytes[sub.start_byte : sub.end_byte].decode(errors='replace')}"

    # Fallback to node text stripped of whitespace
    return code_bytes[param_node.start_byte : param_node.end_byte].decode(errors="replace").strip()


def _extract_parameters(params_node: Node | None, code_bytes: bytes) -> list[str]:
    """Extract parameter names from a function's parameters node."""
    if params_node is None:
        return []

    params: list[str] = []
    for child in params_node.children:
        if child.type in ("(", ")", ","):
            continue
        param_name = _extract_parameter_name(child, code_bytes)
        if param_name and param_name not in ("/", "*"):
            params.append(param_name)
    return params


def _extract_bases(superclasses_node: Node | None, code_bytes: bytes) -> list[str]:
    """Extract base class names from class inheritance argument_list."""
    if superclasses_node is None:
        return []

    bases: list[str] = []
    for child in superclasses_node.children:
        if child.type in ("(", ")", ","):
            continue
        base_name = code_bytes[child.start_byte : child.end_byte].decode(errors="replace").strip()
        if base_name:
            bases.append(base_name)
    return bases


class TreeSitterPythonParser:
    """Parser wrapping tree-sitter for Python AST extraction."""

    def __init__(self) -> None:
        self.parser = Parser(PY_LANGUAGE)

    def parse_source(self, code: str | bytes, file_path: Path | str = "module.py") -> ParsedModule:
        """Parse Python source code and extract symbols, imports, and metadata."""
        code_bytes = code.encode("utf-8") if isinstance(code, str) else code
        path = Path(file_path)

        tree = self.parser.parse(code_bytes)
        root = tree.root_node

        total_lines = len(code_bytes.splitlines()) if code_bytes else 0
        sha256_hash = hashlib.sha256(code_bytes).hexdigest()
        module_docstring = _get_docstring_from_body(root, code_bytes)
        has_syntax_errors = root.has_error

        symbols: list[Symbol] = []
        imports: list[ImportStatement] = []

        self._walk_node(root, code_bytes, symbols, imports, parent_symbol=None)

        return ParsedModule(
            file_path=path,
            symbols=symbols,
            imports=imports,
            total_lines=total_lines,
            docstring=module_docstring,
            has_syntax_errors=has_syntax_errors,
            source_sha256=sha256_hash,
        )

    def parse_file(self, file_path: Path) -> ParsedModule:
        """Read and parse a file from filesystem."""
        content = file_path.read_bytes()
        return self.parse_source(content, file_path=file_path)

    def _walk_node(
        self,
        node: Node,
        code_bytes: bytes,
        symbols: list[Symbol],
        imports: list[ImportStatement],
        parent_symbol: str | None = None,
        parent_type: str | None = None,
    ) -> None:
        """Traverse AST nodes recursively to collect symbols and imports."""
        for child in node.children:
            if child.type == "import_statement":
                stmt = self._parse_import_statement(child, code_bytes)
                if stmt:
                    imports.extend(stmt)
            elif child.type == "import_from_statement":
                stmt_from = self._parse_import_from_statement(child, code_bytes)
                if stmt_from:
                    imports.append(stmt_from)
            elif child.type == "class_definition":
                self._parse_class_definition(
                    child,
                    code_bytes,
                    symbols,
                    imports,
                    parent_symbol,
                    parent_type,
                    decorators=[],
                )
            elif child.type == "function_definition":
                self._parse_function_definition(
                    child,
                    code_bytes,
                    symbols,
                    imports,
                    parent_symbol,
                    parent_type,
                    decorators=[],
                )
            elif child.type == "decorated_definition":
                self._parse_decorated_definition(
                    child, code_bytes, symbols, imports, parent_symbol, parent_type
                )
            else:
                # Recurse into nested blocks/structures
                if child.children:
                    self._walk_node(
                        child,
                        code_bytes,
                        symbols,
                        imports,
                        parent_symbol=parent_symbol,
                        parent_type=parent_type,
                    )

    def _parse_decorated_definition(
        self,
        node: Node,
        code_bytes: bytes,
        symbols: list[Symbol],
        imports: list[ImportStatement],
        parent_symbol: str | None,
        parent_type: str | None,
    ) -> None:
        """Handle definitions decorated with one or more decorators."""
        decorators: list[str] = []
        inner_def: Node | None = None

        for child in node.children:
            if child.type == "decorator":
                dec_text = (
                    code_bytes[child.start_byte : child.end_byte].decode(errors="replace").strip()
                )
                decorators.append(dec_text)
            elif child.type in ("class_definition", "function_definition"):
                inner_def = child

        if inner_def is None:
            return

        # Start line is the start of the entire decorated definition (first decorator)
        start_point = node.start_point

        if inner_def.type == "class_definition":
            self._parse_class_definition(
                inner_def,
                code_bytes,
                symbols,
                imports,
                parent_symbol,
                parent_type,
                decorators=decorators,
                override_start_point=start_point,
            )
        elif inner_def.type == "function_definition":
            self._parse_function_definition(
                inner_def,
                code_bytes,
                symbols,
                imports,
                parent_symbol,
                parent_type,
                decorators=decorators,
                override_start_point=start_point,
            )

    def _parse_class_definition(
        self,
        node: Node,
        code_bytes: bytes,
        symbols: list[Symbol],
        imports: list[ImportStatement],
        parent_symbol: str | None,
        parent_type: str | None,
        decorators: list[str],
        override_start_point: Point | None = None,
    ) -> None:
        """Parse class definition, its base classes, docstring, and member methods."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        class_name = code_bytes[name_node.start_byte : name_node.end_byte].decode(errors="replace")
        full_name = f"{parent_symbol}.{class_name}" if parent_symbol else class_name

        superclasses_node = node.child_by_field_name("superclasses")
        bases = _extract_bases(superclasses_node, code_bytes)

        body_node = node.child_by_field_name("body")
        docstring = _get_docstring_from_body(body_node, code_bytes)

        start: Point = (
            override_start_point if override_start_point is not None else node.start_point
        )
        end = node.end_point

        # Line numbers: 1-indexed; Column numbers: 0-indexed
        symbol = Symbol(
            name=class_name,
            full_name=full_name,
            symbol_type=SymbolType.CLASS,
            start_line=start.row + 1,
            end_line=end.row + 1,
            start_col=start.column,
            end_col=end.column,
            docstring=docstring,
            parent_symbol=parent_symbol,
            decorators=decorators,
            bases=bases,
        )
        symbols.append(symbol)

        # Parse body members (methods, nested classes)
        if body_node is not None:
            self._walk_node(
                body_node,
                code_bytes,
                symbols,
                imports,
                parent_symbol=full_name,
                parent_type="class",
            )

    def _parse_function_definition(
        self,
        node: Node,
        code_bytes: bytes,
        symbols: list[Symbol],
        imports: list[ImportStatement],
        parent_symbol: str | None,
        parent_type: str | None,
        decorators: list[str],
        override_start_point: Point | None = None,
    ) -> None:
        """Parse standalone functions or class methods."""
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return

        func_name = code_bytes[name_node.start_byte : name_node.end_byte].decode(errors="replace")
        full_name = f"{parent_symbol}.{func_name}" if parent_symbol else func_name

        params_node = node.child_by_field_name("parameters")
        parameters = _extract_parameters(params_node, code_bytes)

        body_node = node.child_by_field_name("body")
        docstring = _get_docstring_from_body(body_node, code_bytes)

        # Check async
        is_async = any(c.type == "async" for c in node.children)

        # Functions directly inside a class body are methods; otherwise they are functions
        symbol_type = SymbolType.METHOD if parent_type == "class" else SymbolType.FUNCTION

        start: Point = (
            override_start_point if override_start_point is not None else node.start_point
        )
        end = node.end_point

        symbol = Symbol(
            name=func_name,
            full_name=full_name,
            symbol_type=symbol_type,
            start_line=start.row + 1,
            end_line=end.row + 1,
            start_col=start.column,
            end_col=end.column,
            docstring=docstring,
            parameters=parameters,
            parent_symbol=parent_symbol,
            decorators=decorators,
            is_async=is_async,
        )
        symbols.append(symbol)

        # Recurse into body to collect nested functions or closures
        if body_node is not None:
            self._walk_node(
                body_node,
                code_bytes,
                symbols,
                imports,
                parent_symbol=full_name,
                parent_type="function",
            )

    def _parse_import_statement(self, node: Node, code_bytes: bytes) -> Sequence[ImportStatement]:
        """Parse plain import statements: import foo, bar as b."""
        raw_statement = code_bytes[node.start_byte : node.end_byte].decode(errors="replace").strip()
        start_line = node.start_point.row + 1
        end_line = node.end_point.row + 1

        statements: list[ImportStatement] = []

        for child in node.children:
            if child.type == "dotted_name":
                mod_name = code_bytes[child.start_byte : child.end_byte].decode(errors="replace")
                statements.append(
                    ImportStatement(
                        module=mod_name,
                        items=[],
                        alias=None,
                        is_from_import=False,
                        start_line=start_line,
                        end_line=end_line,
                        raw_statement=raw_statement,
                    )
                )
            elif child.type == "aliased_import":
                mod_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if mod_node is not None and alias_node is not None:
                    mod_name = code_bytes[mod_node.start_byte : mod_node.end_byte].decode(
                        errors="replace"
                    )
                    alias_name = code_bytes[alias_node.start_byte : alias_node.end_byte].decode(
                        errors="replace"
                    )
                    statements.append(
                        ImportStatement(
                            module=mod_name,
                            items=[],
                            alias=alias_name,
                            is_from_import=False,
                            start_line=start_line,
                            end_line=end_line,
                            raw_statement=raw_statement,
                        )
                    )
        return statements

    def _parse_import_from_statement(self, node: Node, code_bytes: bytes) -> ImportStatement | None:
        """Parse from-import statements: from foo.bar import a, b as c, *."""
        raw_statement = code_bytes[node.start_byte : node.end_byte].decode(errors="replace").strip()
        start_line = node.start_point.row + 1
        end_line = node.end_point.row + 1

        module_name = ""
        items: list[ImportItem] = []
        is_import_section = False

        for child in node.children:
            if child.type == "import":
                is_import_section = True
                continue

            if not is_import_section:
                if child.type in ("dotted_name", "relative_import"):
                    module_name = code_bytes[child.start_byte : child.end_byte].decode(
                        errors="replace"
                    )
            else:
                if child.type == "dotted_name":
                    item_name = code_bytes[child.start_byte : child.end_byte].decode(
                        errors="replace"
                    )
                    items.append(ImportItem(name=item_name))
                elif child.type == "aliased_import":
                    item_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")
                    if item_node is not None and alias_node is not None:
                        item_name = code_bytes[item_node.start_byte : item_node.end_byte].decode(
                            errors="replace"
                        )
                        alias_name = code_bytes[alias_node.start_byte : alias_node.end_byte].decode(
                            errors="replace"
                        )
                        items.append(ImportItem(name=item_name, alias=alias_name))
                elif child.type == "wildcard_import":
                    items.append(ImportItem(name="*"))

        return ImportStatement(
            module=module_name,
            items=items,
            alias=None,
            is_from_import=True,
            start_line=start_line,
            end_line=end_line,
            raw_statement=raw_statement,
        )


# Global default instance
_default_parser: TreeSitterPythonParser | None = None


def get_python_parser() -> TreeSitterPythonParser:
    """Return default singleton parser instance."""
    global _default_parser
    if _default_parser is None:
        _default_parser = TreeSitterPythonParser()
    return _default_parser


def parse_python_source(code: str | bytes, file_path: Path | str = "module.py") -> ParsedModule:
    """Convenience function to parse Python code."""
    return get_python_parser().parse_source(code, file_path=file_path)


def parse_python_file(file_path: Path) -> ParsedModule:
    """Convenience function to parse a Python file from disk."""
    return get_python_parser().parse_file(file_path)
